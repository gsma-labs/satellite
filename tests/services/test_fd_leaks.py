"""Tests for file descriptor leaks in satetoad services.

These tests use INVERTED ASSERTIONS: they assert operations DON'T leak FDs,
but when bugs exist (unclosed pipes, rglob accumulation, read_eval_log leaks),
the tests FAIL.

Run with: uv run pytest tests/services/test_fd_leaks.py -v
Expected: Tests FAIL, demonstrating the leaks exist.

Bug context:
- Error: "Dataset loading failed (file descriptor limit)" for teletables/three_gpp
- App view process creates pipes (stdout=PIPE, stderr=PIPE) but never consumes them
- JobManager calls read_eval_log() in loops without explicit cleanup
- Combined FD pressure triggers HuggingFace fork failure on Python 3.14+
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Test Class 1: App View Process Pipe FD Leaks
# ============================================================================


class TestAppViewProcessPipeFdLeak:
    """Tests for subprocess pipe file descriptor leaks in app view process.

    When Popen is created with stdout=PIPE and stderr=PIPE,
    the pipes must be consumed (read) and closed. Otherwise,
    the FDs remain open indefinitely.

    Tests are designed to FAIL when pipes are not properly handled.
    """

    def test_stop_view_closes_pipes(
        self,
        mock_popen: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """_stop_view_process() should close pipe file descriptors.

        BUG: terminate() called but pipes may remain open.

        FAILS when: Pipes not explicitly closed on stop.
        """
        popen_mock, process = mock_popen

        # Set up pipe mocks
        process.stdout = MagicMock()
        process.stderr = MagicMock()
        process.stdout.close = MagicMock()
        process.stderr.close = MagicMock()
        process.communicate = MagicMock(return_value=(b"", b""))

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app._launch_view(tmp_path)
            app._stop_view_process()

        # Pipes should be closed via communicate() or explicit close()
        # communicate() implicitly closes pipes after reading
        pipes_properly_handled = (
            process.communicate.called
            or (process.stdout.close.called and process.stderr.close.called)
        )

        assert pipes_properly_handled, (
            "_stop_view_process() terminates process but doesn't close pipes. "
            "Fix: Add process.communicate() or explicit pipe.close() calls "
            "in _stop_view_process() after terminate()."
        )

    def test_repeated_launches_accumulate_real_pipe_fds(
        self,
        tmp_path: Path,
        fd_counter: tuple[Callable[[], int], Callable[[], int]],
    ) -> None:
        """Repeated _launch_view() calls accumulate REAL pipe FDs.

        This test creates actual pipe file descriptors to prove
        that app leaks FDs when _stop_view_process() doesn't close pipes.

        FAILS when: Real FDs accumulate because pipes aren't closed.
        """
        count_fds, _ = fd_counter
        baseline_fds = count_fds()

        # Create real pipes that simulate what Popen does
        # Each launch should create 2 pipes (stdout, stderr) = 4 FDs
        # If _stop_view_process() doesn't close them, they accumulate
        leaked_pipes: list[tuple[int, int]] = []

        with patch("satetoad.app.subprocess.Popen") as popen_mock, \
             patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()

            for i in range(10):
                # Create REAL pipe FDs to simulate subprocess.PIPE behavior
                stdout_read, stdout_write = os.pipe()
                stderr_read, stderr_write = os.pipe()
                leaked_pipes.append((stdout_read, stderr_read))

                # Mock process that holds real pipe FDs
                process = MagicMock()
                process.poll.return_value = None
                process.terminate = MagicMock()
                process.wait = MagicMock()
                process.kill = MagicMock()
                # These are real file objects wrapping our pipes
                process.stdout = os.fdopen(stdout_read, "rb")
                process.stderr = os.fdopen(stderr_read, "rb")
                # Close write ends (subprocess would use these)
                os.close(stdout_write)
                os.close(stderr_write)

                popen_mock.return_value = process

                log_dir = tmp_path / f"logs_{i}"
                log_dir.mkdir(exist_ok=True)
                app._launch_view(log_dir)

        # After all launches, check if FDs leaked
        final_fds = count_fds()
        fd_increase = final_fds - baseline_fds

        # Clean up any remaining open pipes for test hygiene
        for pipe_pair in leaked_pipes:
            for fd in pipe_pair:
                try:
                    os.close(fd)
                except OSError:
                    pass  # Already closed (good!) or invalid

        # 10 launches * 2 pipes = 20 potential leaked FDs
        # If _stop_view_process() properly closes pipes, increase should be ~0
        # If it doesn't, we'll see significant increase
        assert fd_increase <= 2, (
            f"Repeated launches leaked {fd_increase} real FDs after 10 launches. "
            f"Baseline: {baseline_fds}, Final: {final_fds}. "
            f"Fix: _stop_view_process() must call communicate() or close pipes explicitly."
        )


# ============================================================================
# Test Class 2: JobManager FD Accumulation
# ============================================================================


class TestJobManagerFdAccumulation:
    """Tests for file descriptor accumulation in JobManager.

    JobManager uses rglob() and read_eval_log() which can accumulate
    open file handles if not properly managed.

    Tests are designed to FAIL when FDs leak.
    """

    def test_list_jobs_with_real_read_eval_log_leaks_fds(
        self,
        tmp_path: Path,
        fd_counter: tuple[Callable[[], int], Callable[[], int]],
    ) -> None:
        """list_jobs() with real read_eval_log() should not leak FDs.

        BUG: read_eval_log() from inspect_ai may hold file handles open.

        FAILS when: FD count increases after repeated list_jobs() calls
        that trigger read_eval_log().
        """
        from satetoad.services.evals import JobManager

        count_fds, _ = fd_counter

        # Create jobs directory with valid log files
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

        # Call list_jobs() many times - this triggers _extract_results_from_logs
        # which calls read_eval_log() for each log file
        for _ in range(30):
            _ = manager.list_jobs()

        final_fds = count_fds()
        fd_increase = final_fds - baseline_fds

        # 5 jobs * 3 logs * 30 iterations = 450 read_eval_log() calls
        # If FDs leak, we'll see significant growth
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
        """rglob() iterators leak FDs if not fully consumed.

        BUG: If code breaks out of rglob() loop early, directory
        handles may remain open.

        FAILS when: Partial rglob iteration leaks FDs.
        """
        count_fds, _ = fd_counter

        # Create deep directory structure
        base_dir = tmp_path / "deep"
        for i in range(10):
            for j in range(10):
                d = base_dir / f"level1_{i}" / f"level2_{j}"
                d.mkdir(parents=True)
                (d / "file.txt").write_text("test")

        baseline_fds = count_fds()

        # Simulate partial iteration (what happens if code breaks early)
        for _ in range(20):
            iterator = base_dir.rglob("*.txt")
            # Only consume first 5 items, don't exhaust iterator
            for idx, _ in enumerate(iterator):
                if idx >= 5:
                    break
            # Iterator not fully consumed - does it leak?

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
        """FD usage should be O(1), not O(n) with number of jobs.

        BUG: Without proper cleanup, FD usage grows with job count.

        FAILS when: FD increase scales with number of jobs.
        """
        from satetoad.services.evals import JobManager

        count_fds, _ = fd_counter

        # Create jobs directory with variable number of jobs
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()

        for job_num in range(1, num_jobs + 1):
            job_dir = jobs_dir / f"job_{job_num}" / "openai" / "gpt-4o"
            job_dir.mkdir(parents=True)
            (job_dir / "eval-set.json").write_text(
                '{"tasks": [{"name": "teleqna", "model": "openai/gpt-4o"}]}'
            )
            # Add log files to trigger read_eval_log
            for i in range(2):
                (job_dir / f"2024-01-01T00-00-0{i}Z_teleqna_x{i}.json").write_text("{}")

        (jobs_dir / "counter.txt").write_text(str(num_jobs + 1))

        manager = JobManager()
        manager._jobs_dir = jobs_dir

        baseline_fds = count_fds()

        # Single list_jobs() call processes all jobs
        _ = manager.list_jobs()

        final_fds = count_fds()
        fd_increase = final_fds - baseline_fds

        assert fd_increase <= expected_max_fd_increase, (
            f"FD usage scales with job count ({num_jobs} jobs -> {fd_increase} FDs). "
            f"Expected max {expected_max_fd_increase}. "
            f"Fix: Use context managers or explicit iterator cleanup "
            f"so FD usage is constant regardless of job count."
        )


# ============================================================================
# Test Class 3: Combined FD Stress Scenarios
# ============================================================================


class TestFdStressScenarios:
    """Stress tests that combine multiple FD leak scenarios.

    These tests simulate realistic usage patterns that can
    trigger FD exhaustion when multiple leaks combine.
    """

    def test_combined_operations_with_real_fds(
        self,
        tmp_path: Path,
        fd_counter: tuple[Callable[[], int], Callable[[], int]],
    ) -> None:
        """Combined JobManager and app view process usage with real FDs.

        Creates real pipe FDs to simulate actual subprocess behavior.

        FAILS when: Combined usage causes excessive FD growth.
        """
        from satetoad.services.evals import JobManager

        count_fds, get_limit = fd_counter

        # Set up jobs
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

        baseline_fds = count_fds()
        fd_limit = get_limit()
        leaked_fds: list[int] = []

        with patch("satetoad.app.subprocess.Popen") as popen_mock, \
             patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()

            for i in range(15):
                # Create real pipe FDs
                stdout_r, stdout_w = os.pipe()
                stderr_r, stderr_w = os.pipe()
                leaked_fds.extend([stdout_r, stderr_r])
                os.close(stdout_w)
                os.close(stderr_w)

                process = MagicMock()
                process.poll.return_value = None
                process.terminate = MagicMock()
                process.wait = MagicMock()
                process.stdout = os.fdopen(stdout_r, "rb")
                process.stderr = os.fdopen(stderr_r, "rb")
                popen_mock.return_value = process

                _ = manager.list_jobs()
                app._launch_view(jobs_dir / f"job_{(i % 5) + 1}")

            app._stop_view_process()

        final_fds = count_fds()

        # Cleanup leaked FDs
        for fd in leaked_fds:
            try:
                os.close(fd)
            except OSError:
                pass

        fd_percentage = (final_fds / fd_limit) * 100

        # Should stay well under 10% of limit
        assert fd_percentage < 10, (
            f"Combined usage reached {fd_percentage:.1f}% of FD limit "
            f"({final_fds}/{fd_limit}). "
            f"Multiple leak sources compounding. "
            f"Fix: Address both JobManager and app view process FD leaks."
        )

    def test_heavy_load_with_real_file_operations(
        self,
        tmp_path: Path,
        fd_counter: tuple[Callable[[], int], Callable[[], int]],
    ) -> None:
        """Heavy load with real file operations should not approach FD limit.

        FAILS when: FD usage exceeds 30% of soft limit.
        """
        from satetoad.services.evals import JobManager

        count_fds, get_limit = fd_counter

        # Create extensive job structure with real files
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
        baseline_fds = count_fds()

        # Heavy load simulation
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
        """Stress test should not trigger EMFILE (too many open files).

        FAILS when: OSError with EMFILE is raised.
        """
        from satetoad.services.evals import JobManager

        # Create moderate job structure
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

        # Should not raise OSError(24, 'Too many open files')
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
