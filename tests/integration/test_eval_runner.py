"""Integration tests for eval_runner with real API calls.

These tests validate the full eval pipeline using OPENROUTER_API_KEY.
Run with: uv run pytest tests/integration/test_eval_runner.py -v
"""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv
from inspect_ai.log import list_eval_logs

from satetoad.services.config import EvalSettings
from satetoad.services.evals import EvalRunner
from satetoad.services.evals.job_manager import Job, JobManager
from satetoad.services.evals.worker import load_task

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
        """_run_eval_set passes correct config via subprocess stdin."""
        import json

        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        runner = EvalRunner(jobs_dir)

        job = Job(
            id="test_params",
            evals={"openrouter/openai/gpt-4o-mini": ["teleqna"]},
            status="running",
            settings=EvalSettings(limit=1),
        )

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.communicate.return_value = ("", "")
            mock_process.returncode = 0
            mock_process.pid = 12345
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            runner.run_job(job)

            mock_popen.assert_called_once()
            call_kwargs = mock_process.communicate.call_args[1]
            config = json.loads(call_kwargs["input"])

            assert config["limit"] == 1
            assert config["model"] == "openrouter/openai/gpt-4o-mini"
            assert config["benchmarks"] == ["teleqna"]


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

        runner = EvalRunner(jobs_dir)

        job = Job(
            id="integration_test",
            evals={"openrouter/openai/gpt-4o-mini": ["teleqna"]},
            status="running",
            settings=EvalSettings(limit=1),
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

        # Verify eval log files were created (inspect-ai writes JSON format)
        eval_logs = list(list_eval_logs(str(log_dir)))
        assert len(eval_logs) >= 1, f"No eval log files found in {log_dir}"
