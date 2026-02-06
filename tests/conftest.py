"""Shared test fixtures for satetoad tests."""

import os
import resource
import signal
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from satetoad.services.config import ModelConfig
from satetoad.services.evals import JobManager


@pytest.fixture
def mock_popen() -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Mock subprocess.Popen for app view process tests.

    Yields:
        Tuple of (Popen mock, process instance mock)
    """
    with patch("satetoad.app.subprocess.Popen") as popen_mock:
        process = MagicMock()
        process.poll.return_value = None  # Process running by default
        popen_mock.return_value = process
        yield popen_mock, process


@pytest.fixture
def mock_job_manager() -> MagicMock:
    """Mock JobManager with empty state for isolated testing."""
    manager = MagicMock(spec=JobManager)
    manager.list_jobs.return_value = []
    manager.get_job.return_value = None
    return manager


@pytest.fixture
def sample_model_config() -> list[ModelConfig]:
    """Single model configuration for testing."""
    return [ModelConfig(provider="openai", api_key="sk-test", model="gpt-4o")]


# ============================================================================
# Fixtures for Zombie Process Detection
# ============================================================================


@pytest.fixture
def signal_handler_capture() -> Generator[dict[int, Any], None, None]:
    """Capture and restore signal handlers for testing.

    Useful for testing signal handler registration.
    """
    original_handlers = {
        signal.SIGTERM: signal.getsignal(signal.SIGTERM),
        signal.SIGINT: signal.getsignal(signal.SIGINT),
    }
    yield original_handlers

    for sig, handler in original_handlers.items():
        signal.signal(sig, handler)


@pytest.fixture
def mock_job_manager_for_zombie() -> MagicMock:
    """Mock JobManager that returns a valid jobs_dir."""
    manager = MagicMock()
    manager.jobs_dir = Path("/tmp/fake_logs")
    manager.list_jobs.return_value = []
    return manager


@pytest.fixture
def child_process_counter() -> Generator[Callable[[], int], None, None]:
    """Fixture to count child processes before/after test.

    Yields a callable that returns current child process count.
    """
    try:
        import psutil

        def count() -> int:
            return len(psutil.Process().children(recursive=True))

        yield count
    except ImportError:
        yield lambda: -1


# ============================================================================
# Fixtures for File Descriptor Leak Tests
# ============================================================================


@pytest.fixture
def fd_counter() -> Generator[tuple[Callable[[], int], Callable[[], int]], None, None]:
    """Fixture that provides FD counting functions.

    Yields:
        Tuple of (count_open_fds, get_fd_limit) callables.
        count_open_fds() returns current open FD count.
        get_fd_limit() returns the soft FD limit.
    """
    def count_open_fds() -> int:
        """Count currently open file descriptors."""
        count = 0
        # Only check up to soft limit (reasonable upper bound)
        soft_limit = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
        # Cap at 1024 for performance in tests
        check_limit = min(soft_limit, 1024)
        for fd in range(check_limit):
            try:
                os.fstat(fd)
                count += 1
            except OSError:
                pass
        return count

    def get_fd_limit() -> int:
        """Get the soft FD limit."""
        return resource.getrlimit(resource.RLIMIT_NOFILE)[0]

    yield count_open_fds, get_fd_limit


@pytest.fixture
def temp_jobs_structure(tmp_path: Path) -> Path:
    """Create a temporary jobs directory with many eval-set.json files.

    Simulates a realistic scenario with 50+ log files that would
    trigger FD accumulation when resources aren't properly closed.

    Returns:
        Path to the jobs directory.
    """
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()

    # Create 10 jobs with 5 log files each = 50 files
    for job_num in range(1, 11):
        job_dir = jobs_dir / f"job_{job_num}" / "openai" / "gpt-4o"
        job_dir.mkdir(parents=True)

        # Create eval-set.json
        eval_set = job_dir / "eval-set.json"
        eval_set.write_text('{"tasks": [{"name": "teleqna", "model": "openai/gpt-4o"}]}')

        # Create log files (timestamp format with T)
        for i in range(5):
            log_file = job_dir / f"2024-01-01T00-00-0{i}Z_teleqna_abc{i}.json"
            log_file.write_text("{}")

    # Create counter file
    (jobs_dir / "counter.txt").write_text("11")

    return jobs_dir
