"""Stress tests for interactive TUI flows.

Red-team tests that drive the actual Textual app headlessly to find
crashes, deadlocks, and race conditions under aggressive user input.

Covers:
1. Rapid leaderboard open/close (press "2" -> Escape x5)
2. Opening leaderboard while eval tab is polling
3. Rapid tab switching in TabbedEvalsModal
4. Dismissing modal during worker thread execution
5. Full SatelliteApp leaderboard open/close via key "2"
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.widgets import Static

from satellite.app import SatelliteApp
from satellite.modals import TabbedEvalsModal
from satellite.modals.scripts.leaderboard_modal import LeaderboardModal
from satellite.services.config import EvalSettingsManager, ModelConfig
from satellite.services.evals import JobManager
from satellite.services.leaderboard import LeaderboardEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_ENTRIES = [
    LeaderboardEntry(
        model="gpt-4o",
        provider="OpenAI",
        scores={"teleqna": 82.5},
        avg_score=82.5,
        is_local=False,
    ),
    LeaderboardEntry(
        model="claude-3",
        provider="Anthropic",
        scores={"teleqna": 80.0},
        avg_score=80.0,
        is_local=True,
    ),
]


def _make_mock_job_manager() -> MagicMock:
    """Create a mock JobManager with safe defaults."""
    manager = MagicMock(spec=JobManager)
    manager.list_jobs.return_value = []
    manager.get_job.return_value = None
    manager.jobs_dir = "/tmp/fake_jobs"
    return manager


def _make_slow_job_manager(delay: float = 1.0) -> MagicMock:
    """Create a mock JobManager whose list_jobs blocks for *delay* seconds."""
    manager = MagicMock(spec=JobManager)

    def slow_list_jobs(limit=None):
        time.sleep(delay)
        return []

    manager.list_jobs.side_effect = slow_list_jobs
    manager.get_job.return_value = None
    manager.jobs_dir = "/tmp/fake_jobs"
    return manager


# ---------------------------------------------------------------------------
# Lightweight test apps (no subprocess or filesystem side-effects)
# ---------------------------------------------------------------------------


class LeaderboardStressApp(App):
    """Minimal app that pushes a LeaderboardModal on mount."""

    def __init__(self, job_manager=None):
        super().__init__()
        self._job_manager = job_manager

    def on_mount(self):
        self.push_screen(
            LeaderboardModal(job_manager=self._job_manager)
        )


class TabbedEvalsStressApp(App):
    """Minimal app that pushes a TabbedEvalsModal on mount."""

    def __init__(self, job_manager=None):
        super().__init__()
        self._job_manager = job_manager or _make_mock_job_manager()

    def on_mount(self):
        self.push_screen(
            TabbedEvalsModal(
                job_manager=self._job_manager,
                settings_manager=EvalSettingsManager(),
                model_configs=[
                    ModelConfig(
                        provider="openai", api_key="sk-test", model="gpt-4o"
                    )
                ],
            )
        )


class MainScreenStressApp(App):
    """App that pushes MainScreen -- used for key-binding tests.

    Patches out everything that touches the filesystem or network.
    """

    def __init__(self):
        super().__init__()

    def on_mount(self):
        from satellite.screens.main import MainScreen

        self.push_screen(MainScreen())


# ---------------------------------------------------------------------------
# Test 1 – Rapid leaderboard open/close (LeaderboardModal x5)
# ---------------------------------------------------------------------------


class TestRapidLeaderboardOpenClose:
    """Rapidly open and close the leaderboard modal to check for crashes."""

    @patch(
        "satellite.modals.scripts.leaderboard_modal.fetch_leaderboard",
        return_value=SAMPLE_ENTRIES,
    )
    @patch(
        "satellite.modals.scripts.leaderboard_modal.collect_local_entries",
        return_value=[],
    )
    @patch(
        "satellite.modals.scripts.leaderboard_modal.merge_leaderboard",
        return_value=SAMPLE_ENTRIES,
    )
    async def test_rapid_open_close_with_data(self, _merge, _local, _fetch):
        """Open -> close leaderboard 5x with data — no crash."""
        mock_jm = _make_mock_job_manager()

        for cycle in range(5):
            app = LeaderboardStressApp(job_manager=mock_jm)
            async with app.run_test() as pilot:
                # Give the worker time to complete
                await pilot.pause()
                await pilot.pause()
                # Dismiss
                await pilot.press("escape")
                await pilot.pause()

    @patch(
        "satellite.modals.scripts.leaderboard_modal.fetch_leaderboard",
        side_effect=OSError("Network down"),
    )
    async def test_rapid_open_close_with_error(self, _fetch):
        """Open -> close leaderboard 5x when fetch raises — no crash."""
        mock_jm = _make_mock_job_manager()

        for cycle in range(5):
            app = LeaderboardStressApp(job_manager=mock_jm)
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()

    @patch(
        "satellite.modals.scripts.leaderboard_modal.fetch_leaderboard",
        return_value=SAMPLE_ENTRIES,
    )
    @patch(
        "satellite.modals.scripts.leaderboard_modal.collect_local_entries",
        return_value=[],
    )
    @patch(
        "satellite.modals.scripts.leaderboard_modal.merge_leaderboard",
        return_value=SAMPLE_ENTRIES,
    )
    async def test_immediate_escape_before_worker_completes(
        self, _merge, _local, _fetch
    ):
        """Press escape immediately — worker may still be running."""
        mock_jm = _make_mock_job_manager()
        app = LeaderboardStressApp(job_manager=mock_jm)
        async with app.run_test() as pilot:
            # Don't wait for the worker; dismiss immediately
            await pilot.press("escape")
            await pilot.pause()


# ---------------------------------------------------------------------------
# Test 2 – Open leaderboard while eval-tab is polling
# ---------------------------------------------------------------------------


class TestLeaderboardDuringEvalPolling:
    """Open leaderboard on top of TabbedEvalsModal while polling is active."""

    @patch(
        "satellite.modals.scripts.leaderboard_modal.fetch_leaderboard",
        return_value=SAMPLE_ENTRIES,
    )
    @patch(
        "satellite.modals.scripts.leaderboard_modal.collect_local_entries",
        return_value=[],
    )
    @patch(
        "satellite.modals.scripts.leaderboard_modal.merge_leaderboard",
        return_value=SAMPLE_ENTRIES,
    )
    async def test_leaderboard_over_polling_progress_tab(
        self, _merge, _local, _fetch
    ):
        """Push leaderboard modal while Progress tab timer is running."""
        mock_jm = _make_mock_job_manager()
        app = TabbedEvalsStressApp(job_manager=mock_jm)

        async with app.run_test() as pilot:
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, TabbedEvalsModal)

            # Switch to Progress tab (second tab)
            from satellite.widgets.tab_header import TabHeader
            from satellite.widgets.tab_item import TabItem

            tabs = list(
                modal.query_one("#tab-header", TabHeader).query(TabItem)
            )
            await pilot.click(tabs[1])
            await pilot.pause()

            # Progress tab is now active and its 2s timer is running.
            # Push a leaderboard modal on top.
            app.push_screen(LeaderboardModal(job_manager=mock_jm))
            await pilot.pause()
            await pilot.pause()

            # The top screen should be the leaderboard
            assert isinstance(app.screen, LeaderboardModal)

            # Close the leaderboard
            await pilot.press("escape")
            await pilot.pause()

            # We should be back on the TabbedEvalsModal
            assert isinstance(app.screen, TabbedEvalsModal)

            # Verify the progress tab is still the active tab
            assert modal.active_tab == "view-progress"


# ---------------------------------------------------------------------------
# Test 3 – Rapid tab switching in TabbedEvalsModal
# ---------------------------------------------------------------------------


class TestRapidTabSwitching:
    """Rapidly switch tabs in TabbedEvalsModal to stress reactive updates."""

    async def test_rapid_tab_cycling_10_times(self):
        """Press Tab 10 times rapidly — no crash or hang."""
        mock_jm = _make_mock_job_manager()
        app = TabbedEvalsStressApp(job_manager=mock_jm)

        async with app.run_test() as pilot:
            await pilot.pause()

            # The TabbedEvalsModal overrides tab to switch between
            # Evals / Progress / Settings tabs.
            for _ in range(10):
                await pilot.press("tab")
                # Small pause to let event loop tick
                await pilot.pause()

            # Modal should still be alive and responsive
            modal = app.screen
            assert isinstance(modal, TabbedEvalsModal)

            # Verify we can still dismiss
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, TabbedEvalsModal)

    async def test_rapid_tab_switching_interleaved_with_escape(self):
        """Tab-Tab-Escape pattern — ensure no stale state."""
        mock_jm = _make_mock_job_manager()
        app = TabbedEvalsStressApp(job_manager=mock_jm)

        async with app.run_test() as pilot:
            await pilot.pause()

            # Switch a couple of tabs, then dismiss
            await pilot.press("tab")
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, TabbedEvalsModal)

            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, TabbedEvalsModal)


# ---------------------------------------------------------------------------
# Test 4 – Dismiss modal during active worker thread
# ---------------------------------------------------------------------------


class TestDismissDuringWorker:
    """Dismiss TabbedEvalsModal while a background worker is still running."""

    async def test_escape_during_slow_refresh(self):
        """Dismiss modal while _refresh_jobs_in_thread is blocked on IO.

        This tests for NoActiveApp / widget-not-found errors that happen
        when call_from_thread returns to a widget that has been unmounted.
        """
        slow_jm = _make_slow_job_manager(delay=1.0)
        app = TabbedEvalsStressApp(job_manager=slow_jm)

        async with app.run_test() as pilot:
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, TabbedEvalsModal)

            # Switch to Progress tab to trigger the polling timer / worker
            from satellite.widgets.tab_header import TabHeader
            from satellite.widgets.tab_item import TabItem

            tabs = list(
                modal.query_one("#tab-header", TabHeader).query(TabItem)
            )
            await pilot.click(tabs[1])
            await pilot.pause()

            # The worker is now sleeping for 1s in list_jobs.
            # Dismiss immediately — the worker's call_from_thread callback
            # will fire after the modal is already gone.
            await pilot.press("escape")
            await pilot.pause()

            assert not isinstance(app.screen, TabbedEvalsModal)

            # Give the slow worker time to finish and attempt its callback
            # (this is where NoActiveApp would surface if unguarded).
            await asyncio.sleep(1.5)
            await pilot.pause()
            # If we reach here without exception, the app survived.

    async def test_multiple_dismiss_during_worker(self):
        """Rapid open -> escape cycles with slow job manager."""
        slow_jm = _make_slow_job_manager(delay=0.5)

        for _ in range(3):
            app = TabbedEvalsStressApp(job_manager=slow_jm)
            async with app.run_test() as pilot:
                await pilot.pause()

                # Switch to Progress tab
                from satellite.widgets.tab_header import TabHeader
                from satellite.widgets.tab_item import TabItem

                modal = app.screen
                tabs = list(
                    modal.query_one("#tab-header", TabHeader).query(TabItem)
                )
                await pilot.click(tabs[1])
                await pilot.pause()

                # Dismiss while worker may still be running
                await pilot.press("escape")
                await pilot.pause()

                # Brief sleep to let any orphaned callbacks fire
                await asyncio.sleep(0.7)
                await pilot.pause()


# ---------------------------------------------------------------------------
# Test 5 – Full SatelliteApp: key "2" opens LeaderboardModal
# ---------------------------------------------------------------------------


class TestSatelliteAppLeaderboardKey:
    """Drive the real SatelliteApp with mocked externals."""

    @patch("satellite.app.subprocess.Popen")
    @patch("satellite.app.JobManager")
    @patch(
        "satellite.modals.scripts.leaderboard_modal.fetch_leaderboard",
        return_value=SAMPLE_ENTRIES,
    )
    @patch(
        "satellite.modals.scripts.leaderboard_modal.collect_local_entries",
        return_value=[],
    )
    @patch(
        "satellite.modals.scripts.leaderboard_modal.merge_leaderboard",
        return_value=SAMPLE_ENTRIES,
    )
    async def test_press_2_opens_leaderboard(
        self, _merge, _local, _fetch, mock_jm_cls, mock_popen
    ):
        """Press '2' on MainScreen -> LeaderboardModal appears."""
        # Configure the mocked JobManager class
        mock_jm_instance = _make_mock_job_manager()
        mock_jm_cls.return_value = mock_jm_instance

        # Prevent subprocess launch
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        app = SatelliteApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()

            # MainScreen should be the current screen
            from satellite.screens.main import MainScreen

            assert isinstance(app.screen, MainScreen)

            # Press "2" to open leaderboard
            await pilot.press("2")
            await pilot.pause()
            await pilot.pause()

            assert isinstance(app.screen, LeaderboardModal)

            # Dismiss
            await pilot.press("escape")
            await pilot.pause()

            assert isinstance(app.screen, MainScreen)

    @patch("satellite.app.subprocess.Popen")
    @patch("satellite.app.JobManager")
    @patch(
        "satellite.modals.scripts.leaderboard_modal.fetch_leaderboard",
        side_effect=OSError("Network error"),
    )
    async def test_press_2_leaderboard_error_then_dismiss(
        self, _fetch, mock_jm_cls, mock_popen
    ):
        """Press '2' when fetch fails -> see error -> dismiss cleanly."""
        mock_jm_instance = _make_mock_job_manager()
        mock_jm_cls.return_value = mock_jm_instance

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        app = SatelliteApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()

            await pilot.press("2")
            await pilot.pause()
            await pilot.pause()

            modal = app.screen
            assert isinstance(modal, LeaderboardModal)

            # Error text should be visible
            error_widget = modal.query_one("#error-text", Static)
            assert error_widget.display is True
            rendered = str(error_widget.render())
            assert "Network error" in rendered

            await pilot.press("escape")
            await pilot.pause()

            from satellite.screens.main import MainScreen

            assert isinstance(app.screen, MainScreen)

    @patch("satellite.app.subprocess.Popen")
    @patch("satellite.app.JobManager")
    @patch(
        "satellite.modals.scripts.leaderboard_modal.fetch_leaderboard",
        return_value=SAMPLE_ENTRIES,
    )
    @patch(
        "satellite.modals.scripts.leaderboard_modal.collect_local_entries",
        return_value=[],
    )
    @patch(
        "satellite.modals.scripts.leaderboard_modal.merge_leaderboard",
        return_value=SAMPLE_ENTRIES,
    )
    async def test_rapid_2_escape_on_satellite_app(
        self, _merge, _local, _fetch, mock_jm_cls, mock_popen
    ):
        """Rapidly press 2 -> Escape 3 times on the real SatelliteApp."""
        mock_jm_instance = _make_mock_job_manager()
        mock_jm_cls.return_value = mock_jm_instance

        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        app = SatelliteApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()

            from satellite.screens.main import MainScreen

            for _ in range(3):
                assert isinstance(app.screen, MainScreen)
                await pilot.press("2")
                await pilot.pause()
                await pilot.pause()
                assert isinstance(app.screen, LeaderboardModal)
                await pilot.press("escape")
                await pilot.pause()
