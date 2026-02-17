import json
import logging
import time
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse

from inspect_ai.log import (
    EvalLog,
    list_eval_logs,
    read_eval_log,
    read_eval_log_sample_summaries,
)

from satellite import PACKAGE_ROOT
from satellite.services.config import EvalSettings, ModelConfig
from satellite.services.evals.registry import BENCHMARKS_BY_ID

_log = logging.getLogger(__name__)

JobStatus = Literal["running", "success", "error", "cancelled"]

DEFAULT_JOBS_DIR = PACKAGE_ROOT / "jobs"
CANCELLED_MARKER = "cancelled"
SATELLITE_PROGRESS_FILE = ".satellite-progress.json"

STATUS_PRIORITY: dict[JobStatus, int] = {
    "running": 0,
    "error": 1,
    "cancelled": 2,
    "success": 3,
}

RECOVERABLE_LOG_READ_ERRORS = (ValueError, OSError, RuntimeError)


def _map_log_status(log: EvalLog) -> JobStatus:
    """Map an EvalLog status to a JobStatus, treating 'started' as 'running'."""
    if log.status == "started":
        return "running"
    return log.status


def _planned_units(log: EvalLog) -> int:
    """Best-effort planned work units for this eval (samples * epochs).

    Prefer results.total_samples (completed runs), then dataset.sample_ids (reflects
    limit/sample_id selection), then dataset.samples as a fallback.
    """
    if log.results and log.results.total_samples:
        return log.results.total_samples
    if log.eval and log.eval.dataset:
        # Inspect writes the planned sample_ids list for the run. This is a more
        # accurate denominator than dataset.samples when limit/sample_id is used.
        sample_ids = getattr(log.eval.dataset, "sample_ids", None)
        epochs = getattr(getattr(log.eval, "config", None), "epochs", None)
        e = epochs if isinstance(epochs, int) and epochs > 0 else 1
        if isinstance(sample_ids, list) and sample_ids:
            return len(sample_ids) * e
        if log.eval.dataset.samples:
            return log.eval.dataset.samples * e
    return 0


def _load_satellite_progress(model_dir: Path) -> dict[str, dict]:
    """Load per-eval progress written by Inspect hooks (best-effort)."""
    path = model_dir / SATELLITE_PROGRESS_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    evals = data.get("evals")
    return evals if isinstance(evals, dict) else {}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _estimate_job_total_units(
    evals: dict[str, list[str]], settings: EvalSettings
) -> int:
    """Estimate total planned work units for a job from its manifest and settings."""
    total = 0
    limit = settings.limit
    epochs = settings.epochs if settings.epochs > 0 else 1

    for _, benchmarks in evals.items():
        for benchmark_id in benchmarks:
            cfg = BENCHMARKS_BY_ID.get(benchmark_id)
            if cfg is None:
                continue
            n = cfg.total_samples
            if limit is not None and limit > 0:
                n = min(n, limit)
            total += n * epochs
    return total


def _count_completed_samples(log_ref: object) -> int:
    """Count completed samples for a log.

    Uses Inspect's sample summaries, which are small and safe to read frequently.
    Retries briefly to avoid partial-write windows while Inspect is appending.
    """
    for attempt in range(2):
        try:
            summaries = read_eval_log_sample_summaries(log_ref)
            return sum(1 for s in summaries if getattr(s, "completed", False))
        except ValueError:
            if attempt == 0:
                time.sleep(0.05)
                continue
            return 0
        except (OSError, RuntimeError):
            return 0
    return 0


def _log_ref_dir(log_ref: object) -> Path | None:
    """Best-effort directory of a log reference returned by inspect_ai.log.list_eval_logs."""
    name = getattr(log_ref, "name", None)
    if not isinstance(name, str) or not name:
        return None

    # Inspect typically returns file:// URIs for file-based logs.
    parsed = urlparse(name)
    if parsed.scheme == "file":
        # parsed.path is URL-encoded; decode it to a real filesystem path.
        return Path(unquote(parsed.path)).parent

    # Fallback: treat name as a local path.
    try:
        return Path(name).expanduser().resolve().parent
    except (OSError, RuntimeError, ValueError):
        return None


def _aggregate_progress(
    model_dirs: Iterable[Path],
) -> tuple[JobStatus, int, int, float, int, int]:
    """Return (status, completed_evals, total_evals, eval_progress, completed_samples, total_samples).

    eval_progress is expressed in "eval units": each eval contributes a fraction in
    [0, 1] based on completed_samples / planned_samples. Summed across evals, it is
    directly comparable to total_evals (e.g. 2.4/5).
    """
    statuses: list[JobStatus] = []
    completed_evals = 0
    total_evals = 0
    eval_progress = 0.0
    completed_samples = 0
    total_samples = 0
    progress_cache: dict[Path, dict[str, dict]] = {}

    for model_dir in model_dirs:
        for log_ref in list_eval_logs(str(model_dir)):
            # Logs can live in nested subdirectories (e.g. model names with "/").
            # The per-sample hook writes `.satellite-progress.json` into the same
            # directory as the log files, so load it from the log's parent dir.
            log_dir = _log_ref_dir(log_ref) or model_dir
            satellite_progress = progress_cache.get(log_dir)
            if satellite_progress is None:
                satellite_progress = _load_satellite_progress(log_dir)
                progress_cache[log_dir] = satellite_progress

            log = _read_eval_log_header_safe(log_ref)
            if log is None:
                continue
            statuses.append(_map_log_status(log))
            total_evals += 1
            planned = _planned_units(log)

            eval_id = getattr(getattr(log, "eval", None), "eval_id", None)
            progress_entry = (
                satellite_progress.get(eval_id)
                if eval_id and satellite_progress
                else None
            )

            # Terminal evals contribute a full eval unit (the job will be marked as
            # stopped and shown as a full red bar anyway).
            if log.status != "started":
                completed_evals += 1
                eval_progress += 1.0
                if log.results:
                    completed_samples += log.results.completed_samples
                    total_samples += log.results.total_samples
                else:
                    # Cancelled runs may lack results; still surface best-effort counts.
                    done = 0
                    if isinstance(progress_entry, dict):
                        done = _safe_int(progress_entry.get("completed_units"), 0)
                        sidecar_planned = _safe_int(
                            progress_entry.get("planned_units"), 0
                        )
                        if sidecar_planned > 0:
                            planned = sidecar_planned
                    if done == 0:
                        done = _count_completed_samples(log_ref)
                    completed_samples += done
                    total_samples += planned or done
                continue

            # Running eval — compute progress from sample summaries.
            if isinstance(progress_entry, dict):
                done = _safe_int(progress_entry.get("completed_units"), 0)
                sidecar_planned = _safe_int(progress_entry.get("planned_units"), 0)
                if sidecar_planned > 0:
                    planned = sidecar_planned
            else:
                done = _count_completed_samples(log_ref)
            completed_samples += done
            total_samples += planned
            if planned > 0:
                eval_progress += min(done / planned, 1.0)

    status = min(statuses, key=STATUS_PRIORITY.get, default="running")
    return (
        status,
        completed_evals,
        total_evals,
        round(eval_progress, 6),
        completed_samples,
        total_samples,
    )


@dataclass(frozen=True)
class JobDetails:
    """Aggregated metadata for a job across all eval logs."""

    status: JobStatus
    total_samples: int
    total_tokens: int
    duration_seconds: float | None


def _parse_eval_set(eval_set_file: Path) -> tuple[str, list[str]] | None:
    """Parse eval-set.json and return (model, benchmarks) or None."""
    try:
        data = json.loads(eval_set_file.read_text())
    except (json.JSONDecodeError, ValueError) as exc:
        _log.warning("Skipping malformed eval-set %s: %s", eval_set_file, exc)
        return None
    tasks = data.get("tasks", [])
    if not tasks:
        return None
    return (tasks[0]["model"], [t["name"].rsplit("/", 1)[-1] for t in tasks])


def read_status(model_dir: Path) -> JobStatus:
    """Read status from inspect_ai log files."""
    logs = list(list_eval_logs(str(model_dir)))
    if not logs:
        return "error"

    statuses = [
        _map_log_status(log)
        for p in logs
        if (log := _read_eval_log_header_safe(p)) is not None
    ]
    if not statuses:
        return "running"
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


def _read_eval_log_header_safe(log_path: object) -> EvalLog | None:
    """Read an eval log header, skipping empty/incomplete logs during active writes."""
    if getattr(log_path, "size", None) == 0:
        return None

    try:
        return read_eval_log(log_path, header_only=True)
    except RECOVERABLE_LOG_READ_ERRORS as exc:
        _log.debug("Skipping unreadable eval log %s: %s", log_path, exc)
        return None


def _load_job_sample_counts(job_dir: str) -> dict[str, dict[str, int]]:
    """Return {model: {benchmark: sample_count}}."""
    counts: dict[str, dict[str, int]] = {}
    for log_path in list_eval_logs(job_dir, recursive=True):
        log = _read_eval_log_header_safe(log_path)
        if log is None:
            continue
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
        log = _read_eval_log_header_safe(log_path)
        if log is None:
            continue
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
        log = _read_eval_log_header_safe(log_path)
        if log is None:
            continue
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
    # Fractional progress expressed in eval units: 0..total_evals
    eval_progress: float = 0.0
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

        manifest = {
            "evals": evals,
            "total_evals": total_evals,
            "settings": asdict(settings),
        }
        (job_dir / "job-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

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
        evals, total_evals, settings = self._load_from_manifest(job_dir)

        # Fallback for legacy jobs without manifest
        if not evals:
            evals, total_evals = self._load_evals_from_eval_sets(job_dir)
            settings = EvalSettings()

        if not evals:
            return None

        planned_total_units = _estimate_job_total_units(evals, settings)

        if self._has_cancelled_marker(job_dir):
            return Job(
                id=job_dir.name,
                evals=evals,
                created_at=self._job_created_at(job_dir),
                status="cancelled",
                total_evals=total_evals,
                settings=settings,
                total_samples=planned_total_units,
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
                settings=settings,
                total_samples=planned_total_units,
            )

        # Best-effort inference for legacy jobs that don't include settings in the manifest.
        if planned_total_units == 0:
            inferred_limit: int | None = None
            inferred_epochs: int | None = None
            for model_dir in model_dirs:
                for log_ref in list_eval_logs(str(model_dir)):
                    log = _read_eval_log_header_safe(log_ref)
                    if log is None:
                        continue
                    cfg = getattr(getattr(log, "eval", None), "config", None)
                    if cfg is None:
                        continue
                    if inferred_limit is None:
                        inferred_limit = getattr(cfg, "limit", None)
                    if inferred_epochs is None:
                        inferred_epochs = getattr(cfg, "epochs", None)
                if inferred_limit is not None and inferred_epochs is not None:
                    break

            settings = EvalSettings(
                limit=inferred_limit if inferred_limit is not None else settings.limit,
                epochs=inferred_epochs
                if inferred_epochs is not None
                else settings.epochs,
                max_connections=settings.max_connections,
                token_limit=settings.token_limit,
                message_limit=settings.message_limit,
            )
            planned_total_units = _estimate_job_total_units(evals, settings)

        (
            status,
            completed_evals,
            found_evals,
            eval_progress,
            completed_samples,
            observed_total_samples,
        ) = _aggregate_progress(model_dirs)

        # If the manifest indicates more evals than we've observed in logs, we can't
        # conclude the job is complete even if all observed logs are "success".
        if found_evals < total_evals and status == "success":
            status = "running"

        return Job(
            id=job_dir.name,
            evals=evals,
            created_at=self._job_created_at(job_dir),
            status=status,
            settings=settings,
            completed_evals=completed_evals,
            total_evals=total_evals,
            eval_progress=min(eval_progress, float(total_evals)),
            completed_samples=completed_samples,
            total_samples=planned_total_units or observed_total_samples,
        )

    def _load_from_manifest(
        self, job_dir: Path
    ) -> tuple[dict[str, list[str]], int, EvalSettings]:
        """Load evals from job-manifest.json if it exists."""
        manifest_path = job_dir / "job-manifest.json"
        if not manifest_path.exists():
            return {}, 0, EvalSettings()
        try:
            data = json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, ValueError) as exc:
            _log.warning("Skipping malformed manifest %s: %s", manifest_path, exc)
            return {}, 0, EvalSettings()

        defaults = EvalSettings()
        raw_settings = (
            data.get("settings", {}) if isinstance(data.get("settings"), dict) else {}
        )
        settings = EvalSettings(
            limit=raw_settings.get("limit"),
            epochs=raw_settings.get("epochs", defaults.epochs),
            max_connections=raw_settings.get(
                "max_connections", defaults.max_connections
            ),
            token_limit=raw_settings.get("token_limit"),
            message_limit=raw_settings.get("message_limit"),
        )

        return data.get("evals", {}), data.get("total_evals", 0), settings

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
