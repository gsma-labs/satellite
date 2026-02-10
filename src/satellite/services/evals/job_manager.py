import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from inspect_ai.log import EvalLog, list_eval_logs, read_eval_log

from satellite import PACKAGE_ROOT
from satellite.services.config import EvalSettings, ModelConfig

JobStatus = Literal["running", "success", "error", "cancelled"]

DEFAULT_JOBS_DIR = PACKAGE_ROOT / "jobs"
CANCELLED_MARKER = "cancelled"

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


def _aggregate_progress(
    model_dirs: Iterable[Path],
) -> tuple[JobStatus, int, int, int, int]:
    """Return (status, completed_evals, total_evals, completed_samples, total_samples).

    Completed evals are those with log.results (success, error, cancelled).
    For completed evals: samples come from log.results.completed_samples / total_samples.
    For running evals: total comes from log.eval.dataset.samples, completed stays 0.
    """
    statuses: list[JobStatus] = []
    completed_evals = 0
    total_evals = 0
    completed_samples = 0
    total_samples = 0

    for model_dir in model_dirs:
        for log_ref in list_eval_logs(str(model_dir)):
            log = read_eval_log(log_ref, header_only=True)
            statuses.append(_map_log_status(log))
            total_evals += 1

            if log.results:
                completed_evals += 1
                completed_samples += log.results.completed_samples
                total_samples += log.results.total_samples
                continue

            # Running eval — total from dataset metadata, 0 completed
            if log.eval and log.eval.dataset and log.eval.dataset.samples:
                total_samples += log.eval.dataset.samples

    status = min(statuses, key=STATUS_PRIORITY.get, default="running")
    return status, completed_evals, total_evals, completed_samples, total_samples


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
    completed_evals: int = 0
    total_evals: int = 0
    completed_samples: int = 0
    total_samples: int = 0


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
        """Create a single job for all models and write a manifest file."""
        job_id = self.next_job_id()
        job_dir = self.jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        evals = {m.model: benchmarks for m in models}
        total_evals = len(models) * len(benchmarks)

        manifest = {"evals": evals, "total_evals": total_evals}
        (job_dir / "job-manifest.json").write_text(json.dumps(manifest, indent=2))

        return Job(
            id=job_id,
            evals=evals,
            settings=settings,
            total_evals=total_evals,
        )

    def job_dirs(self) -> Iterator[Path]:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        for path in self.jobs_dir.iterdir():
            if path.is_dir() and path.name.startswith("job_"):
                yield path

    def load_job(self, job_dir: Path) -> Job | None:
        """Load a job from the filesystem using manifest or eval-set fallback."""
        evals, total_evals = self._load_evals_from_manifest(job_dir)

        # Fallback for legacy jobs without manifest
        if not evals:
            evals, total_evals = self._load_evals_from_eval_sets(job_dir)

        if not evals:
            return None

        if self._has_cancelled_marker(job_dir):
            return Job(
                id=job_dir.name,
                evals=evals,
                created_at=self._job_created_at(job_dir),
                status="cancelled",
                total_evals=total_evals,
            )

        model_dirs = self._discover_model_dirs(job_dir)
        if not model_dirs:
            # No eval logs yet — job is still initializing
            return Job(
                id=job_dir.name,
                evals=evals,
                created_at=self._job_created_at(job_dir),
                status="running",
                total_evals=total_evals,
            )

        status, completed_evals, _, completed_samples, total_samples = (
            _aggregate_progress(model_dirs)
        )

        return Job(
            id=job_dir.name,
            evals=evals,
            created_at=self._job_created_at(job_dir),
            status=status,
            completed_evals=completed_evals,
            total_evals=total_evals,
            completed_samples=completed_samples,
            total_samples=total_samples,
        )

    def _load_evals_from_manifest(
        self, job_dir: Path
    ) -> tuple[dict[str, list[str]], int]:
        """Load evals from job-manifest.json if it exists."""
        manifest_path = job_dir / "job-manifest.json"
        if not manifest_path.exists():
            return {}, 0
        data = json.loads(manifest_path.read_text())
        return data.get("evals", {}), data.get("total_evals", 0)

    def _load_evals_from_eval_sets(
        self, job_dir: Path
    ) -> tuple[dict[str, list[str]], int]:
        """Fallback: scan eval-set.json files for legacy jobs without manifest."""
        evals: dict[str, list[str]] = {}
        for eval_file in job_dir.glob("**/eval-set.json"):
            parsed = _parse_eval_set(eval_file)
            if parsed is None:
                continue
            model, benchmarks = parsed
            evals[model] = benchmarks
        total_evals = sum(len(b) for b in evals.values())
        return evals, total_evals

    def _discover_model_dirs(self, job_dir: Path) -> list[Path]:
        """Find all model subdirectories that contain eval logs."""
        model_dirs = []
        for subdir in job_dir.iterdir():
            if not subdir.is_dir():
                continue
            if list(list_eval_logs(str(subdir))):
                model_dirs.append(subdir)
        return model_dirs

    def _has_cancelled_marker(self, job_dir: Path) -> bool:
        """Check whether a cancelled marker file exists for this job."""
        return (job_dir / CANCELLED_MARKER).exists()

    def _job_created_at(self, job_dir: Path) -> datetime:
        """Determine job creation time from manifest or eval-set files."""
        manifest_path = job_dir / "job-manifest.json"
        if manifest_path.exists():
            return datetime.fromtimestamp(manifest_path.stat().st_mtime)
        eval_files = list(job_dir.glob("**/eval-set.json"))
        if not eval_files:
            return datetime.now()
        return min(datetime.fromtimestamp(f.stat().st_mtime) for f in eval_files)

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
