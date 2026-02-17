"""Tests for JobManager resilience when jobs folder is deleted at runtime."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from satellite.services.evals import JobManager
from satellite.services.evals.job_manager import (
    _aggregate_progress,
    _load_job_results,
)


class TestJobManagerFolderDeletion:
    """Tests that JobManager handles deleted jobs folder gracefully."""

    def test_job_dirs_recovers_when_folder_deleted(self, tmp_path: Path) -> None:
        """job_dirs() should not crash if jobs folder is deleted at runtime.

        FAILS when: FileNotFoundError raised on iterdir() of missing directory.
        """
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        manager = JobManager(jobs_dir=jobs_dir)

        # Verify it works initially
        assert list(manager.job_dirs()) == []

        # Delete the folder (simulating external deletion)
        jobs_dir.rmdir()

        # Should NOT raise FileNotFoundError
        result = list(manager.job_dirs())
        assert result == []

    def test_list_jobs_recovers_when_folder_deleted(self, tmp_path: Path) -> None:
        """list_jobs() should return empty list if folder deleted, not crash."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        manager = JobManager(jobs_dir=jobs_dir)
        assert manager.list_jobs() == []

        # Delete folder
        jobs_dir.rmdir()

        # Should return empty, not crash
        assert manager.list_jobs() == []

    def test_create_job_works_after_folder_deleted(
        self, tmp_path: Path, sample_model_config: list
    ) -> None:
        """create_job() should recreate folder if deleted."""
        from satellite.services.config import EvalSettings

        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        manager = JobManager(jobs_dir=jobs_dir)

        # Delete folder
        jobs_dir.rmdir()

        # Should work - recreate and create job
        job = manager.create_job(
            benchmarks=["teleqna"],
            models=sample_model_config,
            settings=EvalSettings(),
        )
        assert job.id.startswith("job_")
        assert jobs_dir.exists()


class TestJobManagerInProgressLogs:
    """Tests that in-progress/unreadable logs do not crash polling paths."""

    def test_load_job_results_skips_unreadable_log(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """_load_job_results() should skip unreadable logs instead of raising."""
        job_dir = tmp_path / "job_1"
        job_dir.mkdir()
        ref = SimpleNamespace(name=(job_dir / "teleqna.json").as_uri(), size=1)

        monkeypatch.setattr(
            "satellite.services.evals.job_manager.list_eval_logs",
            lambda *_args, **_kwargs: [ref],
        )
        monkeypatch.setattr(
            "satellite.services.evals.job_manager.read_eval_log",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("parse error: premature EOF")
            ),
        )

        assert _load_job_results(str(job_dir)) == {}

    def test_aggregate_progress_skips_unreadable_log(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """_aggregate_progress() should continue when a header read fails."""
        model_dir = tmp_path / "openai"
        model_dir.mkdir()
        ref = SimpleNamespace(name=(model_dir / "teleqna.json").as_uri(), size=1)

        monkeypatch.setattr(
            "satellite.services.evals.job_manager.list_eval_logs",
            lambda *_args, **_kwargs: [ref],
        )
        monkeypatch.setattr(
            "satellite.services.evals.job_manager.read_eval_log",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                ValueError("Unable to read log file")
            ),
        )

        assert _aggregate_progress([model_dir]) == ("running", 0, 0, 0.0, 0, 0)
