"""Headless TUI tests for the eval running flow.

Tests the full flow from clicking Run button to job creation,
verifying subprocess isolation works correctly.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from textual.app import App
from textual.widgets import Button

from satetoad.modals import ModelConfig, TabbedEvalsModal
from satetoad.services.config import EvalSettingsManager
from satetoad.services.evals import BENCHMARKS_BY_ID, Job, JobManager
from satetoad.widgets.eval_list import EvalList


class RunEvalsTestApp(App):
    """Test app for Run Evals flow."""

    def __init__(
        self,
        model_configs: list[ModelConfig],
        job_manager: JobManager,
        settings_manager: EvalSettingsManager | None = None,
    ) -> None:
        super().__init__()
        self._model_configs = model_configs
        self._job_manager = job_manager
        self._settings_manager = settings_manager or EvalSettingsManager()
        self.returned_job: Job | None = None

    def on_mount(self) -> None:
        modal = TabbedEvalsModal(
            job_manager=self._job_manager,
            settings_manager=self._settings_manager,
            model_configs=self._model_configs,
        )
        self.push_screen(modal, callback=self._on_modal_dismiss)

    def _on_modal_dismiss(self, job: Job | None) -> None:
        self.returned_job = job


class TestRunEvalsFlow:
    """Tests for the complete Run Evals flow."""

    @pytest.fixture
    def job_manager(self, tmp_path: Path) -> JobManager:
        """Create a real JobManager with temp directory."""
        return JobManager(tmp_path / "jobs")

    @pytest.fixture
    def model_config(self) -> list[ModelConfig]:
        """Single model configuration for testing."""
        return [ModelConfig(provider="openai", api_key="sk-test", model="gpt-4o")]

    async def test_run_button_creates_job_with_selected_benchmarks(
        self,
        job_manager: JobManager,
        model_config: list[ModelConfig],
    ) -> None:
        """Clicking Run creates a Job with selected benchmark IDs."""
        app = RunEvalsTestApp(
            model_configs=model_config,
            job_manager=job_manager,
        )

        async with app.run_test() as pilot:
            modal = app.screen
            eval_list = modal.query_one("#eval-list", EvalList)

            # All benchmarks should be pre-selected
            assert set(eval_list.get_selected()) == set(BENCHMARKS_BY_ID.keys())

            # Click Run button
            run_btn = modal.query_one("#run-btn", Button)
            await pilot.click(run_btn)
            await pilot.pause()

        # Job should be returned with all benchmarks
        assert app.returned_job is not None
        # Job.evals maps model -> benchmarks
        assert "gpt-4o" in app.returned_job.evals
        assert set(app.returned_job.evals["gpt-4o"]) == set(BENCHMARKS_BY_ID.keys())

    async def test_run_button_with_partial_selection(
        self,
        job_manager: JobManager,
        model_config: list[ModelConfig],
    ) -> None:
        """Run button respects user's benchmark selection."""
        app = RunEvalsTestApp(
            model_configs=model_config,
            job_manager=job_manager,
        )

        async with app.run_test() as pilot:
            modal = app.screen
            eval_list = modal.query_one("#eval-list", EvalList)

            # Clear all, then select only teleqna
            eval_list.clear_all()
            eval_list._selected.add("teleqna")

            # Click Run button
            run_btn = modal.query_one("#run-btn", Button)
            await pilot.click(run_btn)
            await pilot.pause()

        # Job should only have teleqna
        assert app.returned_job is not None
        assert app.returned_job.evals["gpt-4o"] == ["teleqna"]

    async def test_run_without_model_shows_error(
        self,
        job_manager: JobManager,
    ) -> None:
        """Run button without configured model shows error notification."""
        app = RunEvalsTestApp(
            model_configs=[],  # No models configured
            job_manager=job_manager,
        )

        async with app.run_test() as pilot:
            modal = app.screen

            # Click Run button
            run_btn = modal.query_one("#run-btn", Button)
            await pilot.click(run_btn)
            await pilot.pause()

            # Modal should stay open (not dismissed)
            assert isinstance(app.screen, TabbedEvalsModal)

        # No job should be created
        assert app.returned_job is None


class TestMultiModelEvalFlow:
    """Tests for multi-model evaluation support."""

    @pytest.fixture
    def job_manager(self, tmp_path: Path) -> JobManager:
        """Create a real JobManager with temp directory."""
        return JobManager(tmp_path / "jobs")

    async def test_run_creates_job_with_multiple_models(
        self,
        job_manager: JobManager,
    ) -> None:
        """Run with multiple models creates job tracking all of them."""
        multi_model_config = [
            ModelConfig(provider="openai", api_key="sk-test1", model="gpt-4o"),
            ModelConfig(provider="anthropic", api_key="sk-test2", model="claude-3"),
        ]

        app = RunEvalsTestApp(
            model_configs=multi_model_config,
            job_manager=job_manager,
        )

        async with app.run_test() as pilot:
            modal = app.screen

            # Click Run button
            run_btn = modal.query_one("#run-btn", Button)
            await pilot.click(run_btn)
            await pilot.pause()

        # Job should have both models
        assert app.returned_job is not None
        assert len(app.returned_job.evals) == 2
        assert "gpt-4o" in app.returned_job.evals
        assert "claude-3" in app.returned_job.evals
