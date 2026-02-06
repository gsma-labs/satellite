"""Tests for TabbedEvalsModal rendering and tab functionality."""

from unittest.mock import MagicMock, patch

from textual.app import App
from textual.widgets import Button

from satetoad.modals.set_model_modal import ModelConfig
from satetoad.modals.tabbed_evals_modal import TabbedEvalsModal
from satetoad.services.config import EvalSettingsManager
from satetoad.services.evals import JobManager
from satetoad.widgets.eval_list import EvalList
from satetoad.widgets.tab_header import TabHeader
from satetoad.widgets.tab_item import TabItem


class TabbedEvalsModalTestApp(App):
    """Minimal app for testing TabbedEvalsModal in isolation."""

    def __init__(
        self,
        model_configs: list[ModelConfig] | None = None,
        job_manager: JobManager | None = None,
        settings_manager: EvalSettingsManager | None = None,
    ) -> None:
        super().__init__()
        self._model_configs = model_configs
        self._job_manager = job_manager
        self._settings_manager = settings_manager or EvalSettingsManager()

    def on_mount(self) -> None:
        modal = TabbedEvalsModal(
            job_manager=self._job_manager,
            settings_manager=self._settings_manager,
            model_configs=self._model_configs,
        )
        self.push_screen(modal)


class TestTabbedEvalsModalRendering:
    """Tests for TabbedEvalsModal initial rendering."""

    @patch("satetoad.modals.tabbed_evals_modal.get_benchmarks")
    async def test_modal_renders_evals_and_progress_tabs(
        self,
        mock_get_benchmarks: MagicMock,
        mock_job_manager: MagicMock,
        sample_model_config: list[ModelConfig],
    ) -> None:
        """TabbedEvalsModal renders with correct tabs and default state."""
        mock_get_benchmarks.return_value = [
            {"id": "test-bench", "name": "Test Benchmark", "description": "Test"}
        ]

        app = TabbedEvalsModalTestApp(
            model_configs=sample_model_config,
            job_manager=mock_job_manager,
        )

        async with app.run_test():
            modal = app.screen
            tab_header = modal.query_one("#tab-header", TabHeader)
            tabs = list(tab_header.query(TabItem))

            assert tab_header.get_tab_ids() == ["run-evals", "view-progress"]
            assert [tab.label for tab in tabs] == ["Evals", "Progress"]
            assert tab_header.active_tab == "run-evals"
            assert tabs[0].has_class("-active")
            assert not tabs[1].has_class("-active")


class TestTabbedEvalsModalTabSwitching:
    """Tests for tab switching behavior."""

    @patch("satetoad.modals.tabbed_evals_modal.get_benchmarks")
    async def test_clicking_progress_tab_switches_active_tab(
        self,
        mock_get_benchmarks: MagicMock,
        mock_job_manager: MagicMock,
        sample_model_config: list[ModelConfig],
    ) -> None:
        """Clicking Progress tab switches active state."""
        mock_get_benchmarks.return_value = [
            {"id": "test-bench", "name": "Test Benchmark", "description": "Test"}
        ]

        app = TabbedEvalsModalTestApp(
            model_configs=sample_model_config,
            job_manager=mock_job_manager,
        )

        async with app.run_test() as pilot:
            # Wait for layout to complete before interacting with widgets
            await pilot.pause()

            modal = app.screen
            tab_header = modal.query_one("#tab-header", TabHeader)
            tabs = list(tab_header.query(TabItem))

            # Click the Progress tab
            await pilot.click(tabs[1])
            await pilot.pause()

            assert tab_header.active_tab == "view-progress"
            assert not tabs[0].has_class("-active")
            assert tabs[1].has_class("-active")


class TestTabbedEvalsModalButtons:
    """Tests for button interactions."""

    @patch("satetoad.modals.tabbed_evals_modal.get_benchmarks")
    async def test_cancel_button_dismisses_modal(
        self,
        mock_get_benchmarks: MagicMock,
        mock_job_manager: MagicMock,
        sample_model_config: list[ModelConfig],
    ) -> None:
        """Cancel button dismisses modal."""
        mock_get_benchmarks.return_value = [
            {"id": "test-bench", "name": "Test Benchmark", "description": "Test"}
        ]

        app = TabbedEvalsModalTestApp(
            model_configs=sample_model_config,
            job_manager=mock_job_manager,
        )

        async with app.run_test() as pilot:
            # Verify modal is active
            assert isinstance(app.screen, TabbedEvalsModal)

            cancel_btn = app.screen.query_one("#cancel-btn", Button)
            await pilot.click(cancel_btn)
            await pilot.pause()

            # Modal should be dismissed (no longer the active screen)
            assert not isinstance(app.screen, TabbedEvalsModal)

    @patch("satetoad.modals.tabbed_evals_modal.get_benchmarks")
    async def test_close_button_on_progress_tab_dismisses_modal(
        self,
        mock_get_benchmarks: MagicMock,
        mock_job_manager: MagicMock,
        sample_model_config: list[ModelConfig],
    ) -> None:
        """Close button on Progress tab dismisses modal."""
        mock_get_benchmarks.return_value = [
            {"id": "test-bench", "name": "Test Benchmark", "description": "Test"}
        ]

        app = TabbedEvalsModalTestApp(
            model_configs=sample_model_config,
            job_manager=mock_job_manager,
        )

        async with app.run_test() as pilot:
            # Wait for layout to complete before interacting with widgets
            await pilot.pause()

            modal = app.screen
            tabs = list(modal.query_one("#tab-header", TabHeader).query(TabItem))

            # Switch to Progress tab
            await pilot.click(tabs[1])
            await pilot.pause()

            close_btn = modal.query_one("#close-btn", Button)
            await pilot.click(close_btn)
            await pilot.pause()

            # Modal should be dismissed
            assert not isinstance(app.screen, TabbedEvalsModal)

    @patch("satetoad.modals.tabbed_evals_modal.get_benchmarks")
    async def test_run_button_without_selection_keeps_modal_open(
        self,
        mock_get_benchmarks: MagicMock,
        mock_job_manager: MagicMock,
        sample_model_config: list[ModelConfig],
    ) -> None:
        """Run button without selected benchmarks keeps modal open."""
        mock_get_benchmarks.return_value = [
            {"id": "test-bench", "name": "Test Benchmark", "description": "Test"}
        ]

        app = TabbedEvalsModalTestApp(
            model_configs=sample_model_config,
            job_manager=mock_job_manager,
        )

        async with app.run_test() as pilot:
            modal = app.screen
            eval_list = modal.query_one("#eval-list", EvalList)

            # Clear all selections
            eval_list.clear_all()
            assert eval_list.get_selected() == []

            # Click Run button
            run_btn = modal.query_one("#run-btn", Button)
            await pilot.click(run_btn)
            await pilot.pause()

            # Modal should stay open (not dismissed)
            assert isinstance(app.screen, TabbedEvalsModal)
