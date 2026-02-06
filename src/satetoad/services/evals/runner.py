"""Runs inspect-ai evaluations via subprocess.

Textual's multiprocessing causes ValueError: bad value(s) in fds_to_keep.
The subprocess architecture provides isolation with a clean file descriptor table.
"""

import json
import subprocess
from pathlib import Path
from typing import NamedTuple

from satetoad.services.config import EvalSettings
from satetoad.services.evals.job_manager import Job

CANCELLED_EXIT_CODE = 2


class EvalResult(NamedTuple):
    """Result from running evaluations."""

    success: bool
    error: str | None = None
    cancelled: bool = False


class EvalRunner:
    """Runs inspect-ai evaluations via subprocess."""

    def __init__(self, jobs_dir: Path) -> None:
        """Initialize with jobs directory for log output."""
        self.jobs_dir = jobs_dir

    def run_job(self, job: Job) -> EvalResult:
        """Run benchmarks for all models in a job. Fails fast on first error."""
        if not job.evals:
            return EvalResult(False, "No models configured")

        for model, benchmarks in job.evals.items():
            if not benchmarks:
                continue

            # Model paths like "openai/gpt-4" create nested dirs (jobs/job_1/openai/gpt-4/)
            log_dir = self.jobs_dir / job.id / model
            log_dir.mkdir(parents=True, exist_ok=True)

            result = run_eval_set(benchmarks, model, log_dir, job.settings)
            if not result.success:
                return EvalResult(False, f"{model}: {result.error}", cancelled=result.cancelled)

        return EvalResult(True)


def run_eval_set(
    benchmark_ids: list[str], model: str, log_dir: Path, settings: EvalSettings
) -> EvalResult:
    """Execute eval_set via subprocess to avoid FD conflicts with Textual."""
    config = json.dumps({
        "model": model,
        "benchmarks": benchmark_ids,
        "log_dir": str(log_dir),
        "limit": settings.limit,
        "epochs": settings.epochs,
        "max_connections": settings.max_connections,
        "token_limit": settings.token_limit,
        "message_limit": settings.message_limit,
    })

    result = subprocess.run(
        ["uv", "run", "python", "-m", "satetoad.services.evals.worker"],
        input=config,
        capture_output=True,
        text=True,
    )

    if result.returncode == CANCELLED_EXIT_CODE:
        return EvalResult(False, "Cancelled", cancelled=True)

    if result.returncode != 0:
        return EvalResult(False, result.stderr.strip() or "Subprocess failed")

    return EvalResult(True)
