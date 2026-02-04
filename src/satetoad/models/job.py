"""Job model for evaluation runs.

A Job represents a single evaluation run with one or more benchmarks.
Jobs are persisted to disk and survive app restarts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobStatus(Enum):
    """Status of an evaluation job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


STATUS_ICONS: dict[JobStatus, str] = {
    JobStatus.PENDING: "○",
    JobStatus.RUNNING: "◐",
    JobStatus.COMPLETED: "●",
    JobStatus.FAILED: "✕",
}


@dataclass
class Job:
    """Represents an evaluation job.

    Attributes:
        id: Unique identifier (e.g., "job_1")
        benchmarks: List of benchmark IDs to run
        model_provider: Model provider name (e.g., "openai")
        model_name: Model name (e.g., "gpt-4o")
        status: Current job status
        created_at: When the job was created
        completed_at: When the job finished (if completed/failed)
        error: Error message if job failed
        results: Dictionary of benchmark_id -> score (if completed)
    """

    id: str
    benchmarks: list[str]
    model_provider: str | None = None
    model_name: str | None = None
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    error: str | None = None
    results: dict[str, float] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        """Human-friendly display name (e.g., 'job_1')."""
        return self.id

    @property
    def is_active(self) -> bool:
        """Check if job is still running or pending."""
        return self.status in (JobStatus.PENDING, JobStatus.RUNNING)

    def to_dict(self) -> dict[str, Any]:
        """Serialize job to dictionary for JSON storage."""
        return {
            "id": self.id,
            "benchmarks": self.benchmarks,
            "model_provider": self.model_provider,
            "model_name": self.model_name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "error": self.error,
            "results": self.results,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        """Deserialize job from dictionary."""
        return cls(
            id=data["id"],
            benchmarks=data["benchmarks"],
            model_provider=data.get("model_provider"),
            model_name=data.get("model_name"),
            status=JobStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            error=data.get("error"),
            results=data.get("results", {}),
        )
