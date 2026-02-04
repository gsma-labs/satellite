"""Job manager service for evaluation job persistence.

Handles job creation, retrieval, and storage using XDG-compliant
directories via platformdirs.

Jobs are stored at:
- macOS: ~/Library/Application Support/satetoad/jobs/
- Linux: ~/.local/share/satetoad/jobs/
- Windows: C:/Users/<user>/AppData/Local/satetoad/jobs/
"""

import json
from pathlib import Path

from platformdirs import user_data_dir

from satetoad.models.job import Job, JobStatus


class JobManager:
    """Manages evaluation job persistence and retrieval.

    Jobs are stored as individual directories with metadata.json files.
    A counter.txt file tracks the next job number.

    Directory structure:
        jobs/
        ├── counter.txt     # Contains next job number
        ├── job_1/
        │   └── metadata.json
        ├── job_2/
        │   └── metadata.json
        └── ...
    """

    def __init__(self) -> None:
        """Initialize the job manager and ensure directories exist."""
        self._data_dir = Path(user_data_dir("satetoad", ensure_exists=True))
        self._jobs_dir = self._data_dir / "jobs"
        self._jobs_dir.mkdir(exist_ok=True)
        self._counter_file = self._jobs_dir / "counter.txt"

    @property
    def jobs_dir(self) -> Path:
        """Return the jobs directory path."""
        return self._jobs_dir

    def _get_next_job_number(self) -> int:
        """Get and increment the job counter."""
        if self._counter_file.exists():
            counter = int(self._counter_file.read_text().strip())
        else:
            counter = 1

        self._counter_file.write_text(str(counter + 1))
        return counter

    def create_job(
        self,
        benchmarks: list[str],
        model_provider: str | None = None,
        model_name: str | None = None,
    ) -> Job:
        """Create a new job and persist it to disk.

        Args:
            benchmarks: List of benchmark IDs to run
            model_provider: Model provider name
            model_name: Model name

        Returns:
            The newly created Job instance
        """
        job_number = self._get_next_job_number()
        job_id = f"job_{job_number}"

        job = Job(
            id=job_id,
            benchmarks=benchmarks,
            model_provider=model_provider,
            model_name=model_name,
            status=JobStatus.PENDING,
        )

        # Create job directory and save metadata
        job_dir = self._jobs_dir / job_id
        job_dir.mkdir(exist_ok=True)

        metadata_file = job_dir / "metadata.json"
        metadata_file.write_text(json.dumps(job.to_dict(), indent=2))

        return job

    def get_job(self, job_id: str) -> Job | None:
        """Retrieve a job by ID.

        Args:
            job_id: The job identifier (e.g., "job_1")

        Returns:
            The Job instance or None if not found
        """
        job_dir = self._jobs_dir / job_id
        metadata_file = job_dir / "metadata.json"

        if not metadata_file.exists():
            return None

        data = json.loads(metadata_file.read_text())
        return Job.from_dict(data)

    def list_jobs(self, limit: int | None = None) -> list[Job]:
        """List all jobs, most recent first.

        Args:
            limit: Maximum number of jobs to return (None for all)

        Returns:
            List of Job instances sorted by creation time (newest first)
        """
        jobs: list[Job] = []

        for job_dir in self._jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue

            metadata_file = job_dir / "metadata.json"
            if not metadata_file.exists():
                continue

            try:
                data = json.loads(metadata_file.read_text())
                jobs.append(Job.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                # Skip corrupted job files
                continue

        # Sort by creation time, newest first
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        if limit is not None:
            jobs = jobs[:limit]

        return jobs

    def update_job(self, job: Job) -> None:
        """Update a job's metadata on disk.

        Args:
            job: The Job instance to update
        """
        job_dir = self._jobs_dir / job.id
        if not job_dir.exists():
            job_dir.mkdir(exist_ok=True)

        metadata_file = job_dir / "metadata.json"
        metadata_file.write_text(json.dumps(job.to_dict(), indent=2))

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its directory.

        Args:
            job_id: The job identifier to delete

        Returns:
            True if deleted, False if not found
        """
        import shutil

        job_dir = self._jobs_dir / job_id
        if not job_dir.exists():
            return False

        shutil.rmtree(job_dir)
        return True

    def get_active_job_count(self) -> int:
        """Count jobs that are pending or running.

        Returns:
            Number of active jobs
        """
        return sum(1 for job in self.list_jobs() if job.is_active)

    def mark_job_running(self, job_id: str) -> Job | None:
        """Mark a job as running.

        Args:
            job_id: The job identifier

        Returns:
            Updated Job or None if not found
        """
        job = self.get_job(job_id)
        if job is None:
            return None

        job.status = JobStatus.RUNNING
        self.update_job(job)
        return job

    def mark_job_completed(
        self, job_id: str, results: dict[str, float]
    ) -> Job | None:
        """Mark a job as completed with results.

        Args:
            job_id: The job identifier
            results: Dictionary of benchmark_id -> score

        Returns:
            Updated Job or None if not found
        """
        from datetime import datetime

        job = self.get_job(job_id)
        if job is None:
            return None

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now()
        job.results = results
        self.update_job(job)
        return job

    def mark_job_failed(self, job_id: str, error: str) -> Job | None:
        """Mark a job as failed with an error message.

        Args:
            job_id: The job identifier
            error: Error message describing the failure

        Returns:
            Updated Job or None if not found
        """
        from datetime import datetime

        job = self.get_job(job_id)
        if job is None:
            return None

        job.status = JobStatus.FAILED
        job.completed_at = datetime.now()
        job.error = error
        self.update_job(job)
        return job
