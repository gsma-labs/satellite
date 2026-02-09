"""Tests for file descriptor leaks in satetoad services.

Verifies that subprocess DEVNULL usage, JobManager rglob, and
read_eval_log calls do not accumulate leaked file descriptors.

Run with: uv run pytest tests/services/test_fd_leaks.py -v
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestAppViewProcessPipeFdLeak:
    """Tests verifying subprocess uses DEVNULL instead of PIPE."""

    def test_launch_view_uses_devnull(
        self,
        mock_popen: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """_launch_view() uses DEVNULL for stdin/stdout/stderr."""
        popen_mock, process = mock_popen

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app.set_timer = MagicMock()
            app._launch_view(tmp_path)

        call_kwargs = popen_mock.call_args[1]
        assert call_kwargs["stdout"] == subprocess.DEVNULL
        assert call_kwargs["stderr"] == subprocess.DEVNULL
        assert call_kwargs["stdin"] == subprocess.DEVNULL

    def test_launch_view_uses_start_new_session(
        self,
        mock_popen: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """_launch_view() should isolate subprocess from Textual's terminal."""
        popen_mock, process = mock_popen

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app.set_timer = MagicMock()
            app._launch_view(tmp_path)

        call_kwargs = popen_mock.call_args[1]
        assert call_kwargs["start_new_session"] is True

    def test_repeated_launches_no_fd_leak(
        self,
        tmp_path: Path,
        fd_counter: tuple[Callable[[], int], Callable[[], int]],
    ) -> None:
        """Repeated _launch_view() calls do not accumulate FDs."""
        count_fds, _ = fd_counter
        baseline_fds = count_fds()

        with patch("satetoad.app.subprocess.Popen") as popen_mock, \
             patch("satetoad.app.MainScreen"), \
             patch("satetoad.app.os.killpg"), \
             patch("satetoad.app.os.getpgid", return_value=99999):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app.set_timer = MagicMock()

            for i in range(10):
                process = MagicMock()
                process.poll.return_value = None
                process.stdout = None  # DEVNULL produces no pipe
                process.stderr = None
                popen_mock.return_value = process

                log_dir = tmp_path / f"logs_{i}"
                log_dir.mkdir(exist_ok=True)
                app._launch_view(log_dir)

        final_fds = count_fds()
        fd_increase = final_fds - baseline_fds

        assert fd_increase <= 2, (
            f"Repeated launches leaked {fd_increase} FDs after 10 launches. "
            f"With DEVNULL, no pipe FDs should be created."
        )


class TestJobManagerFdAccumulation:
    """Tests for file descriptor accumulation in JobManager."""

    def test_list_jobs_with_real_read_eval_log_leaks_fds(
        self,
        tmp_path: Path,
        fd_counter: tuple[Callable[[], int], Callable[[], int]],
    ) -> None:
        """Repeated list_jobs() calls do not leak FDs via read_eval_log()."""
        from satetoad.services.evals import JobManager

        count_fds, _ = fd_counter

        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        for job_num in range(1, 6):
            job_dir = jobs_dir / f"job_{job_num}" / "openai" / "gpt-4o"
            job_dir.mkdir(parents=True)
            (job_dir / "eval-set.json").write_text(
                '{"tasks": [{"name": "teleqna", "model": "openai/gpt-4o"}]}'
            )
            # Create log files that will trigger read_eval_log
            for i in range(3):
                (job_dir / f"2024-01-01T00-00-0{i}Z_teleqna_abc{i}.json").write_text(
                    "{}"
                )

        (jobs_dir / "counter.txt").write_text("6")

        manager = JobManager()
        manager._jobs_dir = jobs_dir

        baseline_fds = count_fds()

        for _ in range(30):
            _ = manager.list_jobs()

        final_fds = count_fds()
        fd_increase = final_fds - baseline_fds

        assert fd_increase <= 5, (
            f"list_jobs() leaked {fd_increase} FDs after 30 calls. "
            f"Baseline: {baseline_fds}, Final: {final_fds}. "
            f"Fix: Ensure read_eval_log() file handles are properly closed."
        )

    def test_rglob_iterator_leaks_fds_when_not_exhausted(
        self,
        tmp_path: Path,
        fd_counter: tuple[Callable[[], int], Callable[[], int]],
    ) -> None:
        """Partial rglob() iteration does not leak directory handles."""
        count_fds, _ = fd_counter

        base_dir = tmp_path / "deep"
        for i in range(10):
            for j in range(10):
                d = base_dir / f"level1_{i}" / f"level2_{j}"
                d.mkdir(parents=True)
                (d / "file.txt").write_text("test")

        baseline_fds = count_fds()

        # Break early to leave iterator unconsumed
        for _ in range(20):
            iterator = base_dir.rglob("*.txt")
            for idx, _ in enumerate(iterator):
                if idx >= 5:
                    break

        final_fds = count_fds()
        fd_increase = final_fds - baseline_fds

        assert fd_increase <= 3, (
            f"Partial rglob() iteration leaked {fd_increase} FDs. "
            f"Baseline: {baseline_fds}, Final: {final_fds}. "
            f"Fix: Always wrap rglob() in list() or use context manager pattern."
        )

    @pytest.mark.parametrize(
        ("num_jobs", "expected_max_fd_increase"),
        [
            pytest.param(10, 5, id="10_jobs_max_5_fds"),
            pytest.param(30, 5, id="30_jobs_same_limit"),
            pytest.param(50, 5, id="50_jobs_same_limit"),
        ],
    )
    def test_fd_usage_scales_constant_not_linear(
        self,
        tmp_path: Path,
        fd_counter: tuple[Callable[[], int], Callable[[], int]],
        num_jobs: int,
        expected_max_fd_increase: int,
    ) -> None:
        """FD usage is O(1), not O(n) with number of jobs."""
        from satetoad.services.evals import JobManager

        count_fds, _ = fd_counter

        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        for job_num in range(1, num_jobs + 1):
            job_dir = jobs_dir / f"job_{job_num}" / "openai" / "gpt-4o"
            job_dir.mkdir(parents=True)
            (job_dir / "eval-set.json").write_text(
                '{"tasks": [{"name": "teleqna", "model": "openai/gpt-4o"}]}'
            )
            for i in range(2):
                (job_dir / f"2024-01-01T00-00-0{i}Z_teleqna_x{i}.json").write_text("{}")

        (jobs_dir / "counter.txt").write_text(str(num_jobs + 1))

        manager = JobManager()
        manager._jobs_dir = jobs_dir

        baseline_fds = count_fds()

        _ = manager.list_jobs()

        final_fds = count_fds()
        fd_increase = final_fds - baseline_fds

        assert fd_increase <= expected_max_fd_increase, (
            f"FD usage scales with job count ({num_jobs} jobs -> {fd_increase} FDs). "
            f"Expected max {expected_max_fd_increase}. "
            f"Fix: Use context managers or explicit iterator cleanup "
            f"so FD usage is constant regardless of job count."
        )


class TestFdStressScenarios:
    """Stress tests combining multiple FD-consuming operations."""

    def test_combined_operations_with_devnull(
        self,
        tmp_path: Path,
        fd_counter: tuple[Callable[[], int], Callable[[], int]],
    ) -> None:
        """Combined JobManager and view process usage stays under 10% of FD limit."""
        from satetoad.services.evals import JobManager

        count_fds, get_limit = fd_counter

        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        for job_num in range(1, 6):
            job_dir = jobs_dir / f"job_{job_num}" / "openai" / "gpt-4o"
            job_dir.mkdir(parents=True)
            (job_dir / "eval-set.json").write_text(
                '{"tasks": [{"name": "teleqna", "model": "openai/gpt-4o"}]}'
            )
        (jobs_dir / "counter.txt").write_text("6")

        manager = JobManager()
        manager._jobs_dir = jobs_dir

        fd_limit = get_limit()

        with patch("satetoad.app.subprocess.Popen") as popen_mock, \
             patch("satetoad.app.MainScreen"), \
             patch("satetoad.app.os.killpg"), \
             patch("satetoad.app.os.getpgid", return_value=99999):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app.set_timer = MagicMock()

            for i in range(15):
                process = MagicMock()
                process.poll.return_value = None
                process.stdout = None  # DEVNULL produces no pipe
                process.stderr = None
                popen_mock.return_value = process

                _ = manager.list_jobs()
                app._launch_view(jobs_dir / f"job_{(i % 5) + 1}")

            app._stop_view_process()

        final_fds = count_fds()
        fd_percentage = (final_fds / fd_limit) * 100

        assert fd_percentage < 10, (
            f"Combined usage reached {fd_percentage:.1f}% of FD limit "
            f"({final_fds}/{fd_limit}). "
            f"Fix: Address JobManager FD leaks."
        )

    def test_heavy_load_with_real_file_operations(
        self,
        tmp_path: Path,
        fd_counter: tuple[Callable[[], int], Callable[[], int]],
    ) -> None:
        """Heavy load with real file operations stays under 30% of FD limit."""
        from satetoad.services.evals import JobManager

        count_fds, get_limit = fd_counter

        jobs_dir = tmp_path / "jobs"

        for job_num in range(1, 21):
            for provider in ["openai", "anthropic", "google"]:
                job_dir = jobs_dir / f"job_{job_num}" / provider / "model"
                job_dir.mkdir(parents=True)
                (job_dir / "eval-set.json").write_text(
                    '{"tasks": [{"name": "test", "model": "test"}]}'
                )
                for i in range(5):
                    (job_dir / f"2024-01-01T00-00-0{i}Z_test_abc{i}.json").write_text(
                        "{}"
                    )

        (jobs_dir / "counter.txt").write_text("21")

        manager = JobManager()
        manager._jobs_dir = jobs_dir

        fd_limit = get_limit()

        for _ in range(30):
            _ = manager.list_jobs()

        final_fds = count_fds()
        fd_percentage = (final_fds / fd_limit) * 100

        assert fd_percentage < 30, (
            f"FD usage reached {fd_percentage:.1f}% of limit ({final_fds}/{fd_limit}). "
            f"Risk of 'too many open files' error under heavier load. "
            f"Fix: Implement explicit FD cleanup after processing."
        )

    def test_no_emfile_error_under_stress(
        self,
        tmp_path: Path,
        fd_counter: tuple[Callable[[], int], Callable[[], int]],
    ) -> None:
        """Stress test does not trigger EMFILE (too many open files)."""
        from satetoad.services.evals import JobManager

        jobs_dir = tmp_path / "jobs"

        for job_num in range(1, 16):
            job_dir = jobs_dir / f"job_{job_num}" / "openai" / "gpt-4o"
            job_dir.mkdir(parents=True)
            (job_dir / "eval-set.json").write_text(
                '{"tasks": [{"name": "teleqna", "model": "openai/gpt-4o"}]}'
            )
            for i in range(5):
                (job_dir / f"2024-01-01T00-00-0{i}Z_teleqna_x{i}.json").write_text("{}")

        (jobs_dir / "counter.txt").write_text("16")

        manager = JobManager()
        manager._jobs_dir = jobs_dir

        try:
            for _ in range(100):
                _ = manager.list_jobs()
        except OSError as e:
            if e.errno == 24:  # EMFILE - too many open files
                pytest.fail(
                    "Hit 'too many open files' error (EMFILE) under stress. "
                    "FD leaks causing exhaustion. Fix all FD leak sources."
                )
            raise
