"""Inspect hooks for per-sample progress reporting.

Satellite runs Inspect in a headless subprocess. Inspect's JSON logs are rewritten
as the run progresses, which makes frequent progress polling expensive.

This hook writes a small sidecar JSON file in the eval_set log_dir that is updated
on every sample completion. Satellite can read this file to render smooth, per-sample
progress without parsing the full Inspect logs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anyio
from inspect_ai.hooks import (
    EvalSetStart,
    SampleEnd,
    TaskEnd,
    TaskStart,
    Hooks,
    hooks,
)

PROGRESS_FILE_NAME = ".satellite-progress.json"
PROGRESS_SCHEMA_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_short_name(task: str | None) -> str | None:
    if not task:
        return None
    return task.rsplit("/", 1)[-1]


def _planned_units_from_spec(spec: Any) -> int:
    """Compute planned work units for a task (samples * epochs)."""
    dataset = getattr(spec, "dataset", None)
    config = getattr(spec, "config", None)

    sample_ids = getattr(dataset, "sample_ids", None) if dataset is not None else None
    samples = getattr(dataset, "samples", None) if dataset is not None else None
    limit = getattr(config, "limit", None) if config is not None else None
    epochs = getattr(config, "epochs", None) if config is not None else None

    base = 0
    if isinstance(sample_ids, list) and sample_ids:
        base = len(sample_ids)
    elif isinstance(samples, int) and samples > 0:
        base = samples
        if isinstance(limit, int) and limit > 0:
            base = min(base, limit)

    e = epochs if isinstance(epochs, int) and epochs > 0 else 1
    return base * e


@dataclass
class _EvalProgress:
    task: str | None
    planned_units: int
    completed_units: int
    status: str
    updated_at: str | None = None
    last_sample_id: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "planned_units": self.planned_units,
            "completed_units": self.completed_units,
            "status": self.status,
            "updated_at": self.updated_at,
            "last_sample_id": self.last_sample_id,
        }


@hooks("satellite-progress", "Write per-sample progress for Satellite TUI.")
class SatelliteProgressHooks(Hooks):
    """Inspect hook subscriber that writes `.satellite-progress.json` to log_dir."""

    def __init__(self) -> None:
        self._lock: anyio.Lock | None = None
        self._progress_path: Path | None = None
        self._eval_set_id: str | None = None
        self._evals: dict[str, _EvalProgress] = {}

    def _ensure_lock(self) -> anyio.Lock:
        if self._lock is None:
            self._lock = anyio.Lock()
        return self._lock

    async def on_eval_set_start(self, data: EvalSetStart) -> None:
        async with self._ensure_lock():
            self._eval_set_id = data.eval_set_id
            self._progress_path = Path(data.log_dir) / PROGRESS_FILE_NAME
            self._evals = {}
        await self._write()

    async def on_task_start(self, data: TaskStart) -> None:
        planned = _planned_units_from_spec(data.spec)
        task = _task_short_name(getattr(data.spec, "task", None))

        async with self._ensure_lock():
            self._evals[data.eval_id] = _EvalProgress(
                task=task,
                planned_units=planned,
                completed_units=0,
                status="running",
                updated_at=_utc_now_iso(),
            )
        await self._write()

    async def on_sample_end(self, data: SampleEnd) -> None:
        async with self._ensure_lock():
            progress = self._evals.get(data.eval_id)
            if progress is None:
                progress = _EvalProgress(
                    task=None,
                    planned_units=0,
                    completed_units=0,
                    status="running",
                )
                self._evals[data.eval_id] = progress

            progress.completed_units += 1
            progress.updated_at = _utc_now_iso()
            progress.last_sample_id = data.sample_id

            if (
                progress.planned_units > 0
                and progress.completed_units > progress.planned_units
            ):
                progress.completed_units = progress.planned_units

        await self._write()

    async def on_task_end(self, data: TaskEnd) -> None:
        status = getattr(data.log, "status", None) or "unknown"
        results = getattr(data.log, "results", None)

        async with self._ensure_lock():
            progress = self._evals.get(data.eval_id)
            if progress is None:
                progress = _EvalProgress(
                    task=None,
                    planned_units=0,
                    completed_units=0,
                    status=str(status),
                )
                self._evals[data.eval_id] = progress

            progress.status = str(status)
            progress.updated_at = _utc_now_iso()
            if results is not None:
                # EvalResults.total_samples includes epochs.
                total_samples = getattr(results, "total_samples", None)
                completed_samples = getattr(results, "completed_samples", None)
                if isinstance(total_samples, int) and total_samples > 0:
                    progress.planned_units = total_samples
                if isinstance(completed_samples, int) and completed_samples >= 0:
                    progress.completed_units = max(
                        progress.completed_units, completed_samples
                    )

        await self._write()

    async def _write(self) -> None:
        """Write the progress file atomically."""
        async with self._ensure_lock():
            path = self._progress_path
            if path is None:
                return

            eval_set_id = self._eval_set_id
            evals = {k: v.to_json() for k, v in self._evals.items()}

            payload = {
                "version": PROGRESS_SCHEMA_VERSION,
                "eval_set_id": eval_set_id,
                "log_dir": str(path.parent),
                "updated_at": _utc_now_iso(),
                "evals": evals,
            }

            def _write_sync() -> None:
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix(path.suffix + ".tmp")
                    tmp.write_text(
                        json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
                        + "\n"
                    )
                    tmp.replace(path)
                except (OSError, ValueError):
                    pass  # Progress reporting is best-effort; don't crash the eval.

            await anyio.to_thread.run_sync(_write_sync)
