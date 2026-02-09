"""Runs inspect-ai evaluations via subprocess.

Textual's multiprocessing causes ValueError: bad value(s) in fds_to_keep.
The subprocess architecture provides isolation with a clean file descriptor table.
"""

import json
import os
import signal
import subprocess
import threading
from pathlib import Path
from typing import NamedTuple

from satellite.services.config import EvalSettings
from satellite.services.evals.job_manager import Job
from satellite.services.evals.worker import mark_started_logs_cancelled

CANCELLED_EXIT_CODE = 2
CANCELLED_MARKER = "cancelled"
WORKER_CMD = ["uv", "run", "python", "-m", "satellite.services.evals.worker"]


class EvalResult(NamedTuple):
    """Result from running evaluations."""

    success: bool
    error: str | None = None
    cancelled: bool = False


class EvalRunner:
    """Runs inspect-ai evaluations via subprocess.

    Tracks active subprocesses per job so they can be cancelled individually.
    Thread-safe: run_job() executes in a background thread, cancel_job()
    is called from the main thread.
    """

    def __init__(self, jobs_dir: Path) -> None:
        """Initialize with jobs directory for log output."""
        self.jobs_dir = jobs_dir
        self._lock = threading.Lock()
        self._active_processes: dict[str, subprocess.Popen[str]] = {}
        self._cancelled_jobs: set[str] = set()

    def cancel_job(self, job_id: str) -> None:
        """Cancel a running job by signalling its entire process group.

        Sends SIGINT immediately, then escalates to SIGTERM/SIGKILL
        in a background thread. Safe to call for unknown or already-finished
        jobs (no-op).
        """
        with self._lock:
            self._cancelled_jobs.add(job_id)
            process = self._active_processes.get(job_id)

        self._write_cancelled_marker(job_id)

        if process is None:
            return
        if process.poll() is not None:
            return

        self._terminate_process_tree(process)

    def _terminate_process_tree(self, process: subprocess.Popen[str]) -> None:
        """Send SIGINT to process group, escalate to SIGTERM/SIGKILL."""
        try:
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGINT)
        except (ProcessLookupError, OSError):
            return

        def _escalate() -> None:
            try:
                process.wait(timeout=5)
                return
            except subprocess.TimeoutExpired:
                pass

            try:
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                return

            try:
                process.wait(timeout=3)
                return
            except subprocess.TimeoutExpired:
                pass

            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass

        threading.Thread(target=_escalate, daemon=True).start()

    def _is_cancelled(self, job_id: str) -> bool:
        """Check if a job has been marked for cancellation."""
        with self._lock:
            return job_id in self._cancelled_jobs

    def _write_cancelled_marker(self, job_id: str) -> None:
        """Write a marker file so load_job() knows this job was cancelled."""
        marker = self.jobs_dir / job_id / CANCELLED_MARKER
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()

    def run_job(self, job: Job) -> EvalResult:
        """Run benchmarks for all models in a job. Fails fast on first error."""
        if not job.evals:
            return EvalResult(False, "No models configured")

        try:
            return self._run_all_models(job)
        finally:
            with self._lock:
                self._cancelled_jobs.discard(job.id)

    def _run_all_models(self, job: Job) -> EvalResult:
        """Run each model's benchmarks sequentially. Fails fast on first error."""
        for model, benchmarks in job.evals.items():
            if self._is_cancelled(job.id):
                return EvalResult(False, "Cancelled", cancelled=True)

            if not benchmarks:
                continue

            log_dir = self.jobs_dir / job.id / model
            log_dir.mkdir(parents=True, exist_ok=True)

            result = self._run_eval_set(
                job.id, benchmarks, model, log_dir, job.settings
            )
            if not result.success:
                return EvalResult(
                    False, f"{model}: {result.error}", cancelled=result.cancelled
                )

        return EvalResult(True)

    def _run_eval_set(
        self,
        job_id: str,
        benchmark_ids: list[str],
        model: str,
        log_dir: Path,
        settings: EvalSettings,
    ) -> EvalResult:
        """Execute eval_set via subprocess to avoid FD conflicts with Textual."""
        config_dict: dict = {
            "model": model,
            "benchmarks": benchmark_ids,
            "log_dir": str(log_dir),
            "epochs": settings.epochs,
            "max_connections": settings.max_connections,
        }
        if settings.limit is not None:
            config_dict["limit"] = settings.limit
        if settings.token_limit is not None:
            config_dict["token_limit"] = settings.token_limit
        if settings.message_limit is not None:
            config_dict["message_limit"] = settings.message_limit
        config = json.dumps(config_dict)

        process = subprocess.Popen(
            WORKER_CMD,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )

        with self._lock:
            self._active_processes[job_id] = process

        try:
            _, stderr = process.communicate(input=config)
        finally:
            with self._lock:
                self._active_processes.pop(job_id, None)

        if self._is_cancelled(job_id) or process.returncode == CANCELLED_EXIT_CODE:
            mark_started_logs_cancelled(str(log_dir))
            return EvalResult(False, "Cancelled", cancelled=True)

        if process.returncode != 0:
            return EvalResult(False, (stderr or "").strip() or "Subprocess failed")

        return EvalResult(True)
