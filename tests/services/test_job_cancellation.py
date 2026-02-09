"""Tests for job cancellation via EvalRunner.

Verifies that cancel_job() signals the active subprocess's process group
and escalates through SIGINT → SIGTERM → SIGKILL.
"""

import signal
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from satetoad.services.config import EvalSettings
from satetoad.services.evals.job_manager import Job, JobManager
from satetoad.services.evals.runner import CANCELLED_MARKER, EvalResult, EvalRunner


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
        """cancel_job() marks the job as cancelled in memory and on disk."""
        runner = EvalRunner(tmp_path)

        runner.cancel_job("job_1")

        assert runner._is_cancelled("job_1")
        assert (tmp_path / "job_1" / CANCELLED_MARKER).exists()

    def test_cancel_sends_sigint_to_process_group(self, tmp_path: Path) -> None:
        """cancel_job() sends SIGINT to the subprocess's process group."""
        runner = EvalRunner(tmp_path)
        mock_process = MagicMock()
        mock_process.pid = 99
        mock_process.poll.return_value = None  # Still running

        runner._active_processes["job_1"] = mock_process

        with (
            patch("satetoad.services.evals.runner.os.getpgid", return_value=99) as mock_getpgid,
            patch("satetoad.services.evals.runner.os.killpg") as mock_killpg,
        ):
            runner.cancel_job("job_1")

            mock_getpgid.assert_called_once_with(99)
            mock_killpg.assert_called_once_with(99, signal.SIGINT)

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

        with patch("satetoad.services.evals.runner.os.killpg") as mock_killpg:
            runner.cancel_job("job_1")

            mock_killpg.assert_not_called()

    def test_escalates_to_sigterm_then_sigkill(self, tmp_path: Path) -> None:
        """Escalation thread sends SIGTERM after 5s, SIGKILL after 3s more."""
        runner = EvalRunner(tmp_path)
        mock_process = MagicMock()
        mock_process.pid = 99
        # process.wait() always times out so escalation proceeds fully
        mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)

        with (
            patch("satetoad.services.evals.runner.os.getpgid", return_value=99),
            patch("satetoad.services.evals.runner.os.killpg") as mock_killpg,
            patch("satetoad.services.evals.runner.threading.Thread") as mock_thread,
        ):
            runner._terminate_process_tree(mock_process)

            # SIGINT sent immediately (not via thread)
            mock_killpg.assert_called_once_with(99, signal.SIGINT)

            # Grab the escalation function and run it synchronously
            escalate_fn = mock_thread.call_args[1]["target"]
            mock_killpg.reset_mock()

            escalate_fn()

            assert mock_killpg.call_args_list == [
                call(99, signal.SIGTERM),
                call(99, signal.SIGKILL),
            ]

    def test_escalation_stops_when_process_exits(self, tmp_path: Path) -> None:
        """Escalation thread stops if process exits after SIGINT."""
        runner = EvalRunner(tmp_path)
        mock_process = MagicMock()
        mock_process.pid = 99
        mock_process.wait.return_value = 0  # Exits immediately

        with (
            patch("satetoad.services.evals.runner.os.getpgid", return_value=99),
            patch("satetoad.services.evals.runner.os.killpg") as mock_killpg,
            patch("satetoad.services.evals.runner.threading.Thread") as mock_thread,
        ):
            runner._terminate_process_tree(mock_process)

            escalate_fn = mock_thread.call_args[1]["target"]
            mock_killpg.reset_mock()

            escalate_fn()

            # No further signals — process exited after SIGINT
            mock_killpg.assert_not_called()

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


def _write_manifest(job_dir: Path, evals: dict[str, list[str]]) -> None:
    """Write a job-manifest.json for testing."""
    import json

    job_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"evals": evals, "total_evals": sum(len(b) for b in evals.values())}
    (job_dir / "job-manifest.json").write_text(json.dumps(manifest))


class TestCancelledMarker:
    """Tests for the on-disk cancelled marker flow."""

    def test_cancel_writes_marker_file(self, tmp_path: Path) -> None:
        """cancel_job() creates a 'cancelled' marker file in the job directory."""
        runner = EvalRunner(tmp_path)

        runner.cancel_job("job_1")

        marker = tmp_path / "job_1" / CANCELLED_MARKER
        assert marker.exists()
        assert marker.stat().st_size == 0

    def test_load_job_returns_cancelled_when_marker_and_no_logs(
        self, tmp_path: Path
    ) -> None:
        """load_job() returns status='cancelled' when marker exists but no eval logs."""
        evals = {"openai/gpt-4": ["teleqna", "teletables"]}
        job_dir = tmp_path / "job_1"
        _write_manifest(job_dir, evals)
        (job_dir / CANCELLED_MARKER).touch()

        manager = JobManager(tmp_path)
        job = manager.load_job(job_dir)

        assert job is not None
        assert job.status == "cancelled"
        assert job.evals == evals
        assert job.total_evals == 2

    def test_load_job_returns_cancelled_when_marker_and_partial_logs(
        self, tmp_path: Path
    ) -> None:
        """load_job() returns status='cancelled' even if some eval logs exist."""
        evals = {"openai/gpt-4": ["teleqna"]}
        job_dir = tmp_path / "job_1"
        _write_manifest(job_dir, evals)
        (job_dir / CANCELLED_MARKER).touch()

        # Create a model dir with a dummy file (not a real eval log, but
        # the marker check should short-circuit before scanning logs)
        model_dir = job_dir / "openai/gpt-4"
        model_dir.mkdir(parents=True)

        manager = JobManager(tmp_path)
        job = manager.load_job(job_dir)

        assert job is not None
        assert job.status == "cancelled"

    def test_load_job_returns_running_without_marker(self, tmp_path: Path) -> None:
        """load_job() returns status='running' when no marker and no logs."""
        evals = {"openai/gpt-4": ["teleqna"]}
        job_dir = tmp_path / "job_1"
        _write_manifest(job_dir, evals)

        manager = JobManager(tmp_path)
        job = manager.load_job(job_dir)

        assert job is not None
        assert job.status == "running"
