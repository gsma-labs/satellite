"""Integration tests for eval_runner with real API calls.

These tests validate the full eval pipeline using OPENROUTER_API_KEY.
Run with: uv run pytest tests/integration/test_eval_runner.py -v
"""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

from satetoad.eval_runner import load_task
from satetoad.services.evals import EvalRunner
from satetoad.services.evals.job_manager import Job, JobManager

load_dotenv(Path(__file__).parent.parent.parent / ".env")


def has_openrouter_api_key() -> bool:
    """Check if OPENROUTER_API_KEY is available."""
    return bool(os.getenv("OPENROUTER_API_KEY"))


requires_api_key = pytest.mark.skipif(
    not has_openrouter_api_key(),
    reason="OPENROUTER_API_KEY not set in .env",
)


class TestTaskLoading:
    """Test that benchmark tasks load correctly."""

    @pytest.mark.parametrize(
        "benchmark_id",
        [
            pytest.param("teleqna", id="teleqna"),
            pytest.param("telelogs", id="telelogs"),
            pytest.param("telemath", id="telemath"),
            pytest.param("teletables", id="teletables"),
            pytest.param("three_gpp", id="three_gpp"),
        ],
    )
    def test_load_valid_benchmark(self, benchmark_id: str) -> None:
        """All declared benchmarks should load successfully."""
        task = load_task(benchmark_id)
        assert task is not None

    def test_load_invalid_benchmark_returns_none(self) -> None:
        """Invalid benchmark IDs should return None."""
        task = load_task("nonexistent_benchmark")
        assert task is None


class TestEvalSetParameters:
    """Verify eval_set is called with correct parameters."""

    def test_eval_set_called_with_correct_params(self, tmp_path: Path) -> None:
        """eval_set should receive limit=1, log_format=json, display=none."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        (jobs_dir / "counter.txt").write_text("0")

        manager = JobManager(jobs_dir)
        runner = EvalRunner()

        job = Job(
            id="test_params",
            model="openrouter/openai/gpt-4o-mini",
            benchmarks=["teleqna"],
            created_at=datetime.now(),
            status="running",
        )

        with patch("satetoad.services.evals.inspect_runner.eval_set") as mock_eval_set:
            mock_eval_set.return_value = (True, [])

            runner.run_job(job)

            mock_eval_set.assert_called_once()
            call_kwargs = mock_eval_set.call_args.kwargs

            assert call_kwargs["limit"] == 1
            assert call_kwargs["log_format"] == "json"
            assert call_kwargs["display"] == "none"
            assert call_kwargs["model"] == "openrouter/openai/gpt-4o-mini"


@requires_api_key
class TestRealEvalExecution:
    """Integration tests that run actual evaluations.

    These tests require OPENROUTER_API_KEY and make real API calls.
    They are slow and should be run separately from unit tests.
    """

    @pytest.mark.slow
    def test_run_teleqna_with_limit_one(self, tmp_path: Path) -> None:
        """Run teleqna benchmark with limit=1 using real API."""
        import json

        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        (jobs_dir / "counter.txt").write_text("0")

        manager = JobManager(jobs_dir)
        runner = EvalRunner()

        job = Job(
            id="integration_test",
            model="openrouter/openai/gpt-4o-mini",
            benchmarks=["teleqna"],
            created_at=datetime.now(),
            status="running",
        )

        result = runner.run_job(job)

        assert result.success, f"Eval failed: {result.error}"

        # Verify log directory was created
        log_dir = jobs_dir / "integration_test" / "openrouter" / "openai" / "gpt-4o-mini"
        assert log_dir.exists(), f"Log directory not created: {log_dir}"

        # Verify eval-set.json was created and contains valid data
        eval_set_file = log_dir / "eval-set.json"
        assert eval_set_file.exists(), "eval-set.json should be created"

        eval_set_data = json.loads(eval_set_file.read_text())
        assert "eval_set_id" in eval_set_data, "eval-set.json should have eval_set_id"
        assert "tasks" in eval_set_data, "eval-set.json should have tasks array"
        assert len(eval_set_data["tasks"]) >= 1, "eval-set.json should have at least 1 task"

        # Verify the task references the correct model
        task_data = eval_set_data["tasks"][0]
        assert "openrouter/openai/gpt-4o-mini" in task_data["model"]

        # Verify actual eval log file was created (.eval format)
        eval_logs = list(log_dir.glob("*.eval"))
        assert len(eval_logs) >= 1, f"No .eval log files found in {log_dir}"

        # Verify the eval log file is not empty and contains valid data
        eval_log_file = eval_logs[0]
        eval_log_size = eval_log_file.stat().st_size
        assert eval_log_size > 1000, f"Eval log file too small ({eval_log_size} bytes), likely empty or failed"

        # Verify log filename follows expected pattern: TIMESTAMP_TASKNAME_ID.eval
        log_name = eval_log_file.name
        assert "teleqna" in log_name.lower() or "evals" in log_name.lower(), (
            f"Log filename should contain task name: {log_name}"
        )
