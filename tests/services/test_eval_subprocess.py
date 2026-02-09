"""Tests for eval subprocess isolation.

These tests verify that eval_set() is called via subprocess to avoid
FD pollution from Textual's async runtime.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from satetoad.services.config import EvalSettings
from satetoad.services.evals.runner import EvalResult, EvalRunner


def _make_mock_popen(returncode: int = 0, stderr: str = "") -> MagicMock:
    """Create a mock Popen that returns the given returncode and stderr."""
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", stderr)
    mock_process.returncode = returncode
    mock_process.pid = 12345
    mock_process.poll.return_value = None
    return mock_process


class TestRunEvalSetSubprocess:
    """Tests for _run_eval_set subprocess isolation."""

    def test_calls_subprocess_with_correct_command(self, tmp_path: Path) -> None:
        """Subprocess called with uv run python -m satetoad.services.evals.worker."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        runner = EvalRunner(tmp_path)

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _make_mock_popen()

            runner._run_eval_set("job_1", ["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            cmd = call_args[0][0]

            assert cmd == ["uv", "run", "python", "-m", "satetoad.services.evals.worker"]

    def test_passes_config_via_stdin(self, tmp_path: Path) -> None:
        """Config JSON passed via stdin with model, benchmarks, log_dir, and settings."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        runner = EvalRunner(tmp_path)

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_process = _make_mock_popen()
            mock_popen.return_value = mock_process
            settings = EvalSettings(limit=5, epochs=2)

            runner._run_eval_set("job_1", ["teleqna", "telemath"], "openai/gpt-4", log_dir, settings)

            call_kwargs = mock_process.communicate.call_args[1]
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
        runner = EvalRunner(tmp_path)

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _make_mock_popen(returncode=0)

            result = runner._run_eval_set("job_1", ["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            assert result == EvalResult(success=True)

    def test_returns_cancelled_on_returncode_2(self, tmp_path: Path) -> None:
        """Returns EvalResult with cancelled=True on returncode 2."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        runner = EvalRunner(tmp_path)

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _make_mock_popen(returncode=2, stderr="Cancelled")

            result = runner._run_eval_set("job_1", ["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            assert result.success is False
            assert result.cancelled is True

    def test_returns_error_on_nonzero_returncode(self, tmp_path: Path) -> None:
        """Returns EvalResult with error message on failure."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        runner = EvalRunner(tmp_path)

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _make_mock_popen(returncode=1, stderr="API error: invalid key")

            result = runner._run_eval_set("job_1", ["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            assert result.success is False
            assert result.cancelled is False
            assert "API error: invalid key" in result.error

    def test_uses_pipe_for_stdin_stdout_stderr(self, tmp_path: Path) -> None:
        """Subprocess is called with PIPE for stdin, stdout, stderr and text=True."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        runner = EvalRunner(tmp_path)

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _make_mock_popen()

            runner._run_eval_set("job_1", ["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs["text"] is True

    def test_starts_subprocess_in_new_session(self, tmp_path: Path) -> None:
        """Subprocess runs in its own session for process-group cancellation."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        runner = EvalRunner(tmp_path)

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_popen.return_value = _make_mock_popen()

            runner._run_eval_set("job_1", ["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs["start_new_session"] is True

    def test_default_settings_have_no_limit(self) -> None:
        """EvalSettings() defaults to limit=None (run all samples)."""
        settings = EvalSettings()
        assert settings.limit is None

    def test_omits_limit_when_none(self, tmp_path: Path) -> None:
        """Config JSON omits limit key when settings.limit is None."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        runner = EvalRunner(tmp_path)

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_process = _make_mock_popen()
            mock_popen.return_value = mock_process

            runner._run_eval_set("job_1", ["teleqna"], "openai/gpt-4", log_dir, EvalSettings())

            call_kwargs = mock_process.communicate.call_args[1]
            config = json.loads(call_kwargs["input"])

            assert "limit" not in config
            assert config["epochs"] == 1
            assert config["max_connections"] == 10

    def test_includes_limit_zero_in_config(self, tmp_path: Path) -> None:
        """Config JSON includes limit=0 when settings.limit is 0 (not silently dropped)."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        runner = EvalRunner(tmp_path)

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_process = _make_mock_popen()
            mock_popen.return_value = mock_process

            runner._run_eval_set("job_1", ["teleqna"], "openai/gpt-4", log_dir, EvalSettings(limit=0))

            call_kwargs = mock_process.communicate.call_args[1]
            config = json.loads(call_kwargs["input"])

            assert config["limit"] == 0

    def test_propagates_subprocess_exception(self, tmp_path: Path) -> None:
        """FileNotFoundError propagates when subprocess binary not found (fail fast)."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        runner = EvalRunner(tmp_path)

        with patch("satetoad.services.evals.runner.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = FileNotFoundError("uv not found")

            with pytest.raises(FileNotFoundError, match="uv not found"):
                runner._run_eval_set("job_1", ["teleqna"], "openai/gpt-4", log_dir, EvalSettings())
