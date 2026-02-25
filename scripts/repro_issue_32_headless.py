#!/usr/bin/env python3
"""Headless reproducer for issue #32 false progress errors.

This script exercises `read_status()` using a deterministic sequential
multi-model timeline and 250ms-style polling. It reports transient
`error` states for models that have not started yet.
"""

from __future__ import annotations

import argparse
import tempfile
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

from satellite.services.evals import job_manager as jm


class _FakeLogRef:
    """Simple stand-in for inspect log references."""

    def __init__(self, token: str, root: Path, size: int = 1) -> None:
        self.token = token
        self.size = size
        self.name = (root / f"{token}.json").as_uri()

    def __repr__(self) -> str:
        return self.token


def _phase_for_tick(tick: int, total_ticks: int) -> int:
    """Split the timeline into 3 sequential execution phases."""
    if total_ticks <= 1:
        return 0
    first = max(1, total_ticks // 3)
    second = max(first + 1, (2 * total_ticks) // 3)
    if tick < first:
        return 0
    if tick < second:
        return 1
    return 2


def _format_statuses(statuses: dict[str, str]) -> str:
    return ", ".join(f"{model}={status}" for model, status in statuses.items())


def _build_phase_data(root: Path) -> list[tuple[dict[str, list[_FakeLogRef]], set[str]]]:
    """Return (logs_by_model, pending_models) for each simulated phase."""
    return [
        (
            {
                "model-a": [_FakeLogRef("a-started", root)],
                "model-b": [],
                "model-c": [],
            },
            {"model-b", "model-c"},
        ),
        (
            {
                "model-a": [_FakeLogRef("a-success", root)],
                "model-b": [_FakeLogRef("b-started", root)],
                "model-c": [],
            },
            {"model-c"},
        ),
        (
            {
                "model-a": [_FakeLogRef("a-success", root)],
                "model-b": [_FakeLogRef("b-success", root)],
                "model-c": [_FakeLogRef("c-started", root)],
            },
            set(),
        ),
    ]


def _build_header_lookup() -> dict[str, SimpleNamespace]:
    """Return fake eval logs consumed by `_map_log_status`."""
    return {
        "a-started": SimpleNamespace(status="started"),
        "b-started": SimpleNamespace(status="started"),
        "c-started": SimpleNamespace(status="started"),
        "a-success": SimpleNamespace(status="success"),
        "b-success": SimpleNamespace(status="success"),
    }


def _run_repro(poll_interval_ms: int, duration_s: float) -> bool:
    """Run deterministic polling simulation and return True if false-error observed."""
    total_ticks = max(1, int((duration_s * 1000) / poll_interval_ms))
    header_lookup = _build_header_lookup()

    with tempfile.TemporaryDirectory(prefix="issue32_headless_repro_") as tmp:
        root = Path(tmp)
        phase_data = _build_phase_data(root)
        model_dirs = {
            "model-a": root / "model-a",
            "model-b": root / "model-b",
            "model-c": root / "model-c",
        }
        for model_dir in model_dirs.values():
            model_dir.mkdir(parents=True, exist_ok=True)

        current_logs_by_model: dict[str, list[_FakeLogRef]] = {}

        def _list_eval_logs_stub(path: object, *_args: object, **_kwargs: object):
            model_name = Path(str(path)).name
            return list(current_logs_by_model.get(model_name, []))

        def _read_header_stub(log_ref: object) -> SimpleNamespace | None:
            token = getattr(log_ref, "token", None)
            if not isinstance(token, str):
                return None
            return header_lookup.get(token)

        original_list_eval_logs: Callable[..., object] = jm.list_eval_logs
        original_read_header = jm._read_eval_log_header_safe
        jm.list_eval_logs = _list_eval_logs_stub  # type: ignore[assignment]
        jm._read_eval_log_header_safe = _read_header_stub  # type: ignore[assignment]

        false_error_observed = False
        try:
            for tick in range(total_ticks):
                phase = _phase_for_tick(tick, total_ticks)
                current_logs_by_model, pending_models = phase_data[phase]

                statuses = {
                    model: jm.read_status(model_dir)
                    for model, model_dir in model_dirs.items()
                }
                false_errors = [
                    model
                    for model in sorted(pending_models)
                    if statuses.get(model) == "error"
                ]
                if false_errors:
                    false_error_observed = True

                print(
                    f"tick={tick:02d} phase={phase} "
                    f"statuses[{_format_statuses(statuses)}] "
                    f"false_error_models={false_errors}"
                )
        finally:
            jm.list_eval_logs = original_list_eval_logs  # type: ignore[assignment]
            jm._read_eval_log_header_safe = original_read_header

    return false_error_observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect",
        choices=["false-error", "no-false-error"],
        required=True,
        help="Expected outcome for this run.",
    )
    parser.add_argument(
        "--poll-interval-ms",
        type=int,
        default=250,
        help="Polling interval used by the simulation.",
    )
    parser.add_argument(
        "--duration-s",
        type=float,
        default=3.0,
        help="Total simulation duration in seconds.",
    )
    args = parser.parse_args()

    observed = _run_repro(args.poll_interval_ms, args.duration_s)
    expected = args.expect == "false-error"

    if observed == expected:
        print(
            f"PASS: expected={args.expect} observed_false_error={observed}",
        )
        return 0

    print(
        f"FAIL: expected={args.expect} observed_false_error={observed}",
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
