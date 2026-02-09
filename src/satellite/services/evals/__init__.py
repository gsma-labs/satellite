"""Evaluation services for running and tracking benchmarks."""

from satellite.services.evals.runner import EvalResult, EvalRunner
from satellite.services.evals.job_manager import Job, JobDetails, JobManager, JobStatus
from satellite.services.evals.registry import (
    BENCHMARKS,
    BENCHMARKS_BY_ID,
    BenchmarkConfig,
)

__all__ = [
    "BENCHMARKS",
    "BENCHMARKS_BY_ID",
    "BenchmarkConfig",
    "EvalResult",
    "EvalRunner",
    "Job",
    "JobDetails",
    "JobManager",
    "JobStatus",
]
