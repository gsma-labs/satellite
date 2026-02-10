"""Tests for LeaderboardModal and multiprocessing/env guards.

Regression tests for the leaderboard crash: ``hf_hub_download`` uses
multiprocessing semaphores for file locking.  When the resource tracker
first initialises inside a Textual ``@work(thread=True)`` worker, its
``fork_exec`` fails with ``ValueError: bad value(s) in fds_to_keep``
because Textual's terminal driver has redirected file descriptors.

The fix pre-warms the resource tracker in ``main()`` via a throwaway
``multiprocessing.Semaphore`` before Textual takes the terminal.
"""

import multiprocessing
import os
from unittest.mock import MagicMock, patch

from textual import work
from textual.app import App
from textual.widgets import Static

from satellite.modals.scripts.leaderboard_modal import LeaderboardModal
from satellite.services.leaderboard import LeaderboardEntry


class LeaderboardModalTestApp(App):
    """Minimal app for testing LeaderboardModal in isolation."""
    def __init__(self, job_manager=None):
        super().__init__()
        self._job_manager = job_manager
    def on_mount(self):
        self.push_screen(LeaderboardModal(job_manager=self._job_manager))


class TestMultiprocessingGuards:
    def test_multiprocessing_spawn_method_set_by_main(self):
        """main() must call set_start_method('spawn')."""
        with (
            patch("multiprocessing.set_start_method") as set_method,
            patch("satellite.app.SatelliteApp") as app_cls,
        ):
            app_cls.return_value.run = MagicMock()
            from satellite.app import main
            main()
            set_method.assert_called_with("spawn", force=True)

    def test_multiprocessing_spawn_runtime_error_is_ignored(self):
        """main() gracefully handles RuntimeError from set_start_method."""
        with (
            patch("multiprocessing.set_start_method", side_effect=RuntimeError("already set")),
            patch("satellite.app.SatelliteApp") as app_cls,
        ):
            app_cls.return_value.run = MagicMock()
            from satellite.app import main
            main()  # should not raise

    def test_hf_env_vars_set_by_main(self):
        """main() must set HF env vars."""
        env_before = {
            k: os.environ.pop(k, None)
            for k in ("TOKENIZERS_PARALLELISM", "HF_DATASETS_DISABLE_PROGRESS_BARS", "HF_HUB_DISABLE_PROGRESS_BARS")
        }
        try:
            with (
                patch("multiprocessing.set_start_method"),
                patch("satellite.app.SatelliteApp") as app_cls,
            ):
                app_cls.return_value.run = MagicMock()
                from satellite.app import main
                main()
                assert os.environ.get("TOKENIZERS_PARALLELISM") == "false"
                assert os.environ.get("HF_DATASETS_DISABLE_PROGRESS_BARS") == "1"
                assert os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS") == "1"
        finally:
            for k, v in env_before.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class TestLeaderboardModalErrorHandling:
    async def test_leaderboard_modal_shows_error_on_network_failure(self):
        with patch(
            "satellite.modals.scripts.leaderboard_modal.fetch_leaderboard",
            side_effect=OSError("Network unreachable"),
        ):
            app = LeaderboardModalTestApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                modal = app.screen
                error_widget = modal.query_one("#error-text", Static)
                assert error_widget.display is True
                rendered = str(error_widget.render())
                assert "Network unreachable" in rendered

    async def test_leaderboard_retry_after_error(self):
        call_count = 0
        def mock_fetch():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("Network unreachable")
            return []
        with (
            patch("satellite.modals.scripts.leaderboard_modal.fetch_leaderboard", side_effect=mock_fetch),
            patch("satellite.modals.scripts.leaderboard_modal.collect_local_entries", return_value=[]),
        ):
            app = LeaderboardModalTestApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                modal = app.screen
                assert modal.query_one("#error-text").display is True
                await pilot.press("r")
                await pilot.pause()
                await pilot.pause()
                assert call_count == 2


class TestLeaderboardModalRendering:
    async def test_leaderboard_modal_renders_entries(self):
        entries = [
            LeaderboardEntry(model="gpt-4o", provider="OpenAI", scores={"teleqna": 82.5}, avg_score=82.5, is_local=False),
            LeaderboardEntry(model="claude-3", provider="Anthropic", scores={"teleqna": 80.0}, avg_score=80.0, is_local=True),
        ]
        with (
            patch("satellite.modals.scripts.leaderboard_modal.fetch_leaderboard", return_value=entries),
            patch("satellite.modals.scripts.leaderboard_modal.collect_local_entries", return_value=[]),
            patch("satellite.modals.scripts.leaderboard_modal.merge_leaderboard", return_value=entries),
        ):
            app = LeaderboardModalTestApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                modal = app.screen
                table = modal.query_one("#results-table")
                assert table.display is True
                assert table.row_count == 2


# ── Bug 1 (real crash): resource tracker in Textual worker ──────────

class SemaphoreWorkerApp(App):
    """App that creates a multiprocessing Semaphore inside a @work thread.

    This reproduces the exact crash path: hf_hub_download → file lock →
    multiprocessing.Semaphore → resource_tracker.fork_exec → ValueError.
    """

    def __init__(self) -> None:
        super().__init__()
        self.worker_error: str | None = None
        self.worker_done = False

    def on_mount(self) -> None:
        self._create_semaphore_in_worker()

    @work(exclusive=True, thread=True)
    def _create_semaphore_in_worker(self) -> None:
        try:
            sem = multiprocessing.Semaphore(1)
            del sem
        except ValueError as exc:
            self.worker_error = str(exc)
        self.worker_done = True
        self.app.call_from_thread(self.exit)


class TestResourceTrackerWarmup:
    """Verify the resource tracker is pre-warmed before Textual takes the
    terminal, preventing 'bad value(s) in fds_to_keep' in worker threads."""

    async def test_semaphore_in_textual_worker_does_not_crash(self) -> None:
        """Creating a multiprocessing.Semaphore inside a @work(thread=True)
        must not raise ValueError.  This is the exact code path triggered
        by hf_hub_download's file locking inside LeaderboardModal."""
        app = SemaphoreWorkerApp()

        async with app.run_test() as pilot:
            # Give the worker thread time to finish
            for _ in range(10):
                await pilot.pause()
                if app.worker_done:
                    break

        assert app.worker_error is None, (
            f"Semaphore creation in Textual worker crashed: {app.worker_error}"
        )
