import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from inspect_ai.log import EvalLog, list_eval_logs, read_eval_log

from satetoad import PACKAGE_ROOT
from satetoad.services.config import EvalSettings, ModelConfig

JobStatus = Literal["running", "success", "error", "cancelled"]

DEFAULT_JOBS_DIR = PACKAGE_ROOT / "jobs"

STATUS_PRIORITY: dict[JobStatus, int] = {
    "running": 0,
    "error": 1,
    "cancelled": 2,
    "success": 3,
}


def _map_log_status(log: EvalLog) -> JobStatus:
    """Map an EvalLog status to a JobStatus, treating 'started' as 'running'."""
    if log.status == "started":
        return "running"
    return log.status


@dataclass(frozen=True)
class JobDetails:
    """Aggregated metadata for a job across all eval logs."""

    status: JobStatus
    total_samples: int
    total_tokens: int
    duration_seconds: float | None


def _parse_eval_set(eval_set_file: Path) -> tuple[str, list[str]] | None:
    """Parse eval-set.json and return (model, benchmarks) or None."""
    data = json.loads(eval_set_file.read_text())
    tasks = data.get("tasks", [])
    if not tasks:
        return None
    return (tasks[0]["model"], [t["name"].rsplit("/", 1)[-1] for t in tasks])


def read_status(model_dir: Path) -> JobStatus:
    """Read status from inspect_ai log files."""
    logs = list(list_eval_logs(str(model_dir)))
    if not logs:
        return "error"

    statuses = [_map_log_status(read_eval_log(p, header_only=True)) for p in logs]
    return min(statuses, key=STATUS_PRIORITY.get)


def aggregate_status(model_dirs: Iterable[Path]) -> JobStatus:
    """Aggregate status across all model directories."""
    statuses = [read_status(d) for d in model_dirs]
    return min(statuses, key=STATUS_PRIORITY.get, default="running")


def extract_accuracy(log: EvalLog) -> tuple[str, str, float] | None:
    """Extract (model, task_name, accuracy) from an eval log."""
    if not log.eval or not log.eval.task or not log.eval.model:
        return None
    if not log.results or not log.results.scores:
        return None

    accuracy = log.results.scores[0].metrics.get("accuracy")
    if not accuracy:
        return None

    task_short_name = log.eval.task.rsplit("/", 1)[-1]
    return (log.eval.model, task_short_name, accuracy.value)


def extract_sample_count(log: EvalLog) -> tuple[str, str, int] | None:
    """Extract (model, task_name, sample_count) from an eval log."""
    if not log.eval or not log.eval.task or not log.eval.model:
        return None
    if not log.results:
        return None

    task_short_name = log.eval.task.rsplit("/", 1)[-1]
    return (log.eval.model, task_short_name, log.results.total_samples)


def _load_job_sample_counts(job_dir: str) -> dict[str, dict[str, int]]:
    """Return {model: {benchmark: sample_count}}."""
    counts: dict[str, dict[str, int]] = {}
    for log_path in list_eval_logs(job_dir, recursive=True):
        log = read_eval_log(log_path, header_only=True)
        triple = extract_sample_count(log)
        if triple is None:
            continue

        model, task, sample_count = triple
        counts.setdefault(model, {})[task] = sample_count
    return counts


def _load_job_results(job_dir: str) -> dict[str, dict[str, float]]:
    """Return {model: {benchmark: score}}."""
    results: dict[str, dict[str, float]] = {}
    for log_path in list_eval_logs(job_dir, recursive=True):
        log = read_eval_log(log_path, header_only=True)
        triple = extract_accuracy(log)
        if triple is None:
            continue

        model, task, accuracy = triple
        results.setdefault(model, {})[task] = accuracy
    return results


def _load_job_details(job_dir: str) -> JobDetails | None:
    """Aggregate metadata across all eval logs in a job."""
    logs = list(list_eval_logs(job_dir, recursive=True))
    if not logs:
        return None

    total_samples = 0
    total_tokens = 0
    started_times: list[datetime] = []
    completed_times: list[datetime] = []
    statuses: list[JobStatus] = []

    for log_path in logs:
        log = read_eval_log(log_path, header_only=True)
        statuses.append(_map_log_status(log))

        if log.status == "started":
            continue

        if log.results:
            total_samples += log.results.total_samples

        if log.stats:
            for usage in log.stats.model_usage.values():
                total_tokens += usage.total_tokens

            if log.stats.started_at:
                started_times.append(datetime.fromisoformat(log.stats.started_at))
            if log.stats.completed_at:
                completed_times.append(datetime.fromisoformat(log.stats.completed_at))

    status = min(statuses, key=STATUS_PRIORITY.get, default="running")

    duration_seconds = None
    if started_times and completed_times:
        duration_seconds = (max(completed_times) - min(started_times)).total_seconds()

    return JobDetails(
        status=status,
        total_samples=total_samples,
        total_tokens=total_tokens,
        duration_seconds=duration_seconds,
    )


@dataclass(frozen=True)
class Job:
    """An evaluation job tracking multiple models and their benchmarks."""

    id: str
    evals: dict[str, list[str]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    status: JobStatus = "running"
    settings: EvalSettings = field(default_factory=EvalSettings)


class JobManager:
    """Creates and discovers evaluation jobs by scanning folders."""

    def __init__(self, jobs_dir: Path = DEFAULT_JOBS_DIR) -> None:
        self.jobs_dir = jobs_dir
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def next_job_id(self) -> str:
        return f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def create_job(
        self, benchmarks: list[str], models: list[ModelConfig], settings: EvalSettings
    ) -> Job:
        """Create a single job for all models."""
        job_id = self.next_job_id()
        (self.jobs_dir / job_id).mkdir(parents=True, exist_ok=True)
        evals = {m.model: benchmarks for m in models}
        return Job(id=job_id, evals=evals, settings=settings)

    def job_dirs(self) -> Iterator[Path]:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        for path in self.jobs_dir.iterdir():
            if path.is_dir() and path.name.startswith("job_"):
                yield path

    def load_job(self, job_dir: Path) -> Job | None:
        """Load a job from the filesystem."""
        eval_files = list(job_dir.glob("**/eval-set.json"))
        if not eval_files:
            return None

        evals: dict[str, list[str]] = {}
        model_dirs: list[Path] = []

        for eval_file in eval_files:
            parsed = _parse_eval_set(eval_file)
            if parsed is None:
                continue

            model, benchmarks = parsed
            evals[model] = benchmarks
            model_dirs.append(eval_file.parent)

        if not evals:
            return None

        return Job(
            id=job_dir.name,
            evals=evals,
            created_at=min(
                (datetime.fromtimestamp(f.stat().st_mtime) for f in eval_files),
                default=datetime.now(),
            ),
            status=aggregate_status(model_dirs),
        )

    def list_jobs(self, limit: int | None = None) -> list[Job]:
        """List jobs, running first, then by recency."""
        jobs = [job for d in self.job_dirs() if (job := self.load_job(d))]
        jobs.sort(key=lambda j: (j.status != "running", -j.created_at.timestamp()))

        if limit is None:
            return jobs
        return jobs[:limit]

    def get_job(self, job_id: str) -> Job | None:
        job_dir = self.jobs_dir / job_id
        if not job_dir.exists():
            return None
        return self.load_job(job_dir)

    def get_job_results(self, job_id: str) -> dict[str, dict[str, float]]:
        """Get accuracy scores: {model: {benchmark: score}}."""
        job_dir = self.jobs_dir / job_id
        if not job_dir.exists():
            return {}
        return _load_job_results(str(job_dir))

    def get_job_sample_counts(self, job_id: str) -> dict[str, dict[str, int]]:
        """Get sample counts: {model: {benchmark: count}}."""
        job_dir = self.jobs_dir / job_id
        if not job_dir.exists():
            return {}
        return _load_job_sample_counts(str(job_dir))

    def get_job_details(self, job_id: str) -> JobDetails | None:
        """Get aggregated metadata (status, samples, tokens, duration) for a job."""
        job_dir = self.jobs_dir / job_id
        if not job_dir.exists():
            return None
        return _load_job_details(str(job_dir))
