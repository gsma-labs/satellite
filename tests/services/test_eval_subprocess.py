"""Tests for eval subprocess isolation.

These tests verify that eval_set() is called via subprocess to avoid
FD pollution from Textual's async runtime.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from satetoad.services.evals.eval_runner import EvalResult, run_eval_set


class TestRunEvalSetSubprocess:
    """Tests for run_eval_set subprocess isolation."""

    def test_calls_subprocess_with_correct_command(self, tmp_path: Path) -> None:
        """Subprocess called with uv run python -m satetoad.eval_runner."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.eval_runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            run_eval_set(["teleqna"], "openai/gpt-4", log_dir)

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            assert cmd[:4] == ["uv", "run", "python", "-m"]
            assert cmd[4] == "satetoad.eval_runner"
            # Config path is the 6th element
            assert cmd[5].endswith(".json")

    def test_writes_config_json_with_correct_structure(self, tmp_path: Path) -> None:
        """Config JSON contains model, benchmarks, and log_dir."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        captured_config_path = None

        def capture_config(cmd, **kwargs):
            nonlocal captured_config_path
            captured_config_path = cmd[5]
            # Read config before it gets deleted
            config_content = Path(captured_config_path).read_text()
            # Store for assertion
            capture_config.content = json.loads(config_content)
            return MagicMock(returncode=0, stderr="")

        with patch(
            "satetoad.services.evals.eval_runner.subprocess.run",
            side_effect=capture_config,
        ):
            run_eval_set(["teleqna", "telemath"], "openai/gpt-4", log_dir)

        assert capture_config.content == {
            "model": "openai/gpt-4",
            "benchmarks": ["teleqna", "telemath"],
            "log_dir": str(log_dir),
        }

    def test_returns_success_on_zero_returncode(self, tmp_path: Path) -> None:
        """Returns EvalResult(success=True) when subprocess succeeds."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.eval_runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            result = run_eval_set(["teleqna"], "openai/gpt-4", log_dir)

            assert result == EvalResult(success=True)

    def test_returns_cancelled_on_returncode_2(self, tmp_path: Path) -> None:
        """Returns EvalResult with cancelled=True on returncode 2."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.eval_runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=2, stderr="Cancelled")

            result = run_eval_set(["teleqna"], "openai/gpt-4", log_dir)

            assert result.success is False
            assert result.cancelled is True

    def test_returns_error_on_nonzero_returncode(self, tmp_path: Path) -> None:
        """Returns EvalResult with error message on failure."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.eval_runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stderr="API error: invalid key"
            )

            result = run_eval_set(["teleqna"], "openai/gpt-4", log_dir)

            assert result.success is False
            assert result.cancelled is False
            assert "API error: invalid key" in result.error

    def test_cleans_up_temp_file_on_success(self, tmp_path: Path) -> None:
        """Temp config file deleted after successful run."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        captured_path = None

        def capture_path(cmd, **kwargs):
            nonlocal captured_path
            captured_path = Path(cmd[5])
            return MagicMock(returncode=0, stderr="")

        with patch(
            "satetoad.services.evals.eval_runner.subprocess.run",
            side_effect=capture_path,
        ):
            run_eval_set(["teleqna"], "openai/gpt-4", log_dir)

        # File should be deleted
        assert not captured_path.exists()

    def test_cleans_up_temp_file_on_error(self, tmp_path: Path) -> None:
        """Temp config file deleted even on subprocess failure."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        captured_path = None

        def capture_path(cmd, **kwargs):
            nonlocal captured_path
            captured_path = Path(cmd[5])
            return MagicMock(returncode=1, stderr="Error")

        with patch(
            "satetoad.services.evals.eval_runner.subprocess.run",
            side_effect=capture_path,
        ):
            run_eval_set(["teleqna"], "openai/gpt-4", log_dir)

        # File should be deleted even on error
        assert not captured_path.exists()

    def test_handles_subprocess_exception(self, tmp_path: Path) -> None:
        """Returns error result when subprocess raises exception."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.eval_runner.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("uv not found")

            result = run_eval_set(["teleqna"], "openai/gpt-4", log_dir)

            assert result.success is False
            assert "uv not found" in result.error
