"""Tests for job cancellation via EvalRunner.

Verifies that cancel_job() signals the active subprocess and skips
remaining models in the job.
"""

import signal
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from satetoad.services.config import EvalSettings
from satetoad.services.evals.job_manager import Job
from satetoad.services.evals.runner import EvalResult, EvalRunner


def _make_mock_popen(returncode: int = 0, stderr: str = "") -> MagicMock:
    """Create a mock Popen with given returncode and stderr."""
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", stderr)
    mock_process.returncode = returncode
    mock_process.pid = 42
    mock_process.poll.return_value = None
    return mock_process


class TestCancelJob:
    """Tests for EvalRunner.cancel_job()."""

    def test_cancel_sets_cancelled_flag(self, tmp_path: Path) -> None:
        """cancel_job() marks the job as cancelled."""
        runner = EvalRunner(tmp_path)

        runner.cancel_job("job_1")

        assert runner._is_cancelled("job_1")

    def test_cancel_sends_sigint_to_active_process(self, tmp_path: Path) -> None:
        """cancel_job() sends SIGINT to the stored subprocess."""
        runner = EvalRunner(tmp_path)
        mock_process = MagicMock()
        mock_process.pid = 99
        mock_process.poll.return_value = None  # Still running

        runner._active_processes["job_1"] = mock_process

        with patch("satetoad.services.evals.runner.os.kill") as mock_kill:
            runner.cancel_job("job_1")

            mock_kill.assert_called_once_with(99, signal.SIGINT)

    def test_cancel_noop_for_unknown_job(self, tmp_path: Path) -> None:
        """cancel_job() is a no-op for jobs that don't exist."""
        runner = EvalRunner(tmp_path)

        # Should not raise
        runner.cancel_job("nonexistent_job")

        assert runner._is_cancelled("nonexistent_job")

    def test_cancel_noop_for_finished_process(self, tmp_path: Path) -> None:
        """cancel_job() doesn't signal a process that already exited."""
        runner = EvalRunner(tmp_path)
        mock_process = MagicMock()
        mock_process.pid = 99
        mock_process.poll.return_value = 0  # Already finished

        runner._active_processes["job_1"] = mock_process

        with patch("satetoad.services.evals.runner.os.kill") as mock_kill:
            runner.cancel_job("job_1")

            mock_kill.assert_not_called()

    def test_run_job_skips_remaining_models_after_cancel(
        self, tmp_path: Path
    ) -> None:
        """After cancel, run_job() returns cancelled without running remaining models."""
        runner = EvalRunner(tmp_path)
        job = Job(
            id="job_1",
            evals={
                "openai/gpt-4": ["teleqna"],
                "anthropic/claude": ["teleqna"],
            },
        )

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            mock_proc = _make_mock_popen(returncode=0)
            call_count += 1
            # Cancel after first model starts
            runner.cancel_job("job_1")
            return mock_proc

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = side_effect

            result = runner.run_job(job)

            assert result.cancelled is True
            assert call_count == 1, "Should only run the first model before cancelling"
