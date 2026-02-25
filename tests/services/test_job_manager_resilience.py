"""Tests for JobManager resilience when jobs folder is deleted at runtime."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from satellite.services.evals import JobManager
from satellite.services.evals.job_manager import (
    _aggregate_progress,
    _load_job_results,
    read_status,
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

    def test_read_status_returns_running_when_no_logs(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """No logs yet is a startup state and should not surface as error."""
        model_dir = tmp_path / "model-a"
        model_dir.mkdir()

        monkeypatch.setattr(
            "satellite.services.evals.job_manager.list_eval_logs",
            lambda *_args, **_kwargs: [],
        )

        assert read_status(model_dir) == "running"

    def test_issue_32_no_false_error_for_not_started_models(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Sequential multi-model polling should not show error for queued models."""
        model_dirs = {
            "model-a": tmp_path / "model-a",
            "model-b": tmp_path / "model-b",
            "model-c": tmp_path / "model-c",
        }
        for model_dir in model_dirs.values():
            model_dir.mkdir()

        logs_by_model: dict[str, list[SimpleNamespace]] = {
            "model-a": [],
            "model-b": [],
            "model-c": [],
        }

        monkeypatch.setattr(
            "satellite.services.evals.job_manager.list_eval_logs",
            lambda path, *_args, **_kwargs: list(logs_by_model[Path(str(path)).name]),
        )

        monkeypatch.setattr(
            "satellite.services.evals.job_manager._read_eval_log_header_safe",
            lambda log_ref: SimpleNamespace(status=log_ref.status),
        )

        phases = [
            (
                {
                    "model-a": [SimpleNamespace(status="started", size=1)],
                    "model-b": [],
                    "model-c": [],
                },
                {"model-b", "model-c"},
            ),
            (
                {
                    "model-a": [SimpleNamespace(status="success", size=1)],
                    "model-b": [SimpleNamespace(status="started", size=1)],
                    "model-c": [],
                },
                {"model-c"},
            ),
        ]

        for phase_logs, pending_models in phases:
            logs_by_model.update(phase_logs)
            statuses = {
                model: read_status(model_dir)
                for model, model_dir in model_dirs.items()
            }
            for model in pending_models:
                assert statuses[model] == "running"

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

        def raise_parse_runtime_error(*_args, **_kwargs):
            raise RuntimeError("parse error: premature EOF")

        monkeypatch.setattr(
            "satellite.services.evals.job_manager.read_eval_log",
            raise_parse_runtime_error,
        )

        assert _load_job_results(str(job_dir)) == {}

    def test_load_job_results_skips_zero_byte_log_without_read(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """_load_job_results() should not parse logs still at 0 bytes."""
        job_dir = tmp_path / "job_1"
        job_dir.mkdir()
        ref = SimpleNamespace(name=(job_dir / "teleqna.json").as_uri(), size=0)

        monkeypatch.setattr(
            "satellite.services.evals.job_manager.list_eval_logs",
            lambda *_args, **_kwargs: [ref],
        )

        def fail_if_read_attempted(*_args, **_kwargs):
            raise AssertionError("read_eval_log should not be called for size=0 logs")

        monkeypatch.setattr(
            "satellite.services.evals.job_manager.read_eval_log",
            fail_if_read_attempted,
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

        def raise_unreadable_log_error(*_args, **_kwargs):
            raise ValueError("Unable to read log file")

        monkeypatch.setattr(
            "satellite.services.evals.job_manager.read_eval_log",
            raise_unreadable_log_error,
        )

        assert _aggregate_progress([model_dir]) == ("running", 0, 0, 0.0, 0, 0)
