"""Tests for eval subprocess isolation.

These tests verify that eval_set() is called via subprocess to avoid
FD pollution from Textual's async runtime.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from satetoad.services.config import EvalSettings
from satetoad.services.evals.runner import EvalResult, run_eval_set


class TestRunEvalSetSubprocess:
    """Tests for run_eval_set subprocess isolation."""

    def test_calls_subprocess_with_correct_command(self, tmp_path: Path) -> None:
        """Subprocess called with uv run python -m satetoad.services.evals.worker."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            run_eval_set(["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            cmd = call_args[0][0]

            assert cmd == ["uv", "run", "python", "-m", "satetoad.services.evals.worker"]

    def test_passes_config_via_stdin(self, tmp_path: Path) -> None:
        """Config JSON passed via stdin with model, benchmarks, log_dir, and settings."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            settings = EvalSettings(limit=5, epochs=2)

            run_eval_set(["teleqna", "telemath"], "openai/gpt-4", log_dir, settings)

            call_kwargs = mock_run.call_args[1]
            config = json.loads(call_kwargs["input"])

            assert config["model"] == "openai/gpt-4"
            assert config["benchmarks"] == ["teleqna", "telemath"]
            assert config["log_dir"] == str(log_dir)
            assert config["limit"] == 5
            assert config["epochs"] == 2

    def test_returns_success_on_zero_returncode(self, tmp_path: Path) -> None:
        """Returns EvalResult(success=True) when subprocess succeeds."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            result = run_eval_set(["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            assert result == EvalResult(success=True)

    def test_returns_cancelled_on_returncode_2(self, tmp_path: Path) -> None:
        """Returns EvalResult with cancelled=True on returncode 2."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=2, stderr="Cancelled")

            result = run_eval_set(["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            assert result.success is False
            assert result.cancelled is True

    def test_returns_error_on_nonzero_returncode(self, tmp_path: Path) -> None:
        """Returns EvalResult with error message on failure."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stderr="API error: invalid key"
            )

            result = run_eval_set(["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            assert result.success is False
            assert result.cancelled is False
            assert "API error: invalid key" in result.error

    def test_captures_output(self, tmp_path: Path) -> None:
        """Subprocess is called with capture_output=True and text=True."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.runner.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            run_eval_set(["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["capture_output"] is True
            assert call_kwargs["text"] is True

    def test_propagates_subprocess_exception(self, tmp_path: Path) -> None:
        """FileNotFoundError propagates when subprocess binary not found (fail fast)."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with patch("satetoad.services.evals.runner.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("uv not found")

            with pytest.raises(FileNotFoundError, match="uv not found"):
                run_eval_set(["teleqna"], "openai/gpt-4", log_dir, EvalSettings())
