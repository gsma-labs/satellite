"""Headless TUI tests for the eval running flow.

Tests the full flow from clicking Run button to job creation,
verifying subprocess isolation works correctly.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.widgets import Button

from satetoad.modals.set_model_modal import ModelConfig
from satetoad.modals.tabbed_evals_modal import TabbedEvalsModal
from satetoad.services.config import EvalSettingsManager
from satetoad.services.evals import Job, JobManager
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
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        (jobs_dir / "counter.txt").write_text("0")
        return JobManager(jobs_dir)

    @pytest.fixture
    def model_config(self) -> list[ModelConfig]:
        """Single model configuration for testing."""
        return [ModelConfig(provider="openai", api_key="sk-test", model="gpt-4o")]

    @patch("satetoad.modals.tabbed_evals_modal.get_benchmarks")
    async def test_run_button_creates_job_with_selected_benchmarks(
        self,
        mock_get_benchmarks: MagicMock,
        job_manager: JobManager,
        model_config: list[ModelConfig],
    ) -> None:
        """Clicking Run creates a Job with selected benchmark IDs."""
        mock_get_benchmarks.return_value = [
            {"id": "teleqna", "name": "TeleQnA", "description": "QA benchmark"},
            {"id": "telemath", "name": "TeleMath", "description": "Math benchmark"},
        ]

        app = RunEvalsTestApp(
            model_configs=model_config,
            job_manager=job_manager,
        )

        async with app.run_test() as pilot:
            modal = app.screen
            eval_list = modal.query_one("#eval-list", EvalList)

            # Benchmarks should be pre-selected
            assert set(eval_list.get_selected()) == {"teleqna", "telemath"}

            # Click Run button
            run_btn = modal.query_one("#run-btn", Button)
            await pilot.click(run_btn)
            await pilot.pause()

        # Job should be returned with both benchmarks
        assert app.returned_job is not None
        assert app.returned_job.id == "job_1"
        # Job.evals maps model -> benchmarks
        assert "gpt-4o" in app.returned_job.evals
        assert set(app.returned_job.evals["gpt-4o"]) == {"teleqna", "telemath"}

    @patch("satetoad.modals.tabbed_evals_modal.get_benchmarks")
    async def test_run_button_with_partial_selection(
        self,
        mock_get_benchmarks: MagicMock,
        job_manager: JobManager,
        model_config: list[ModelConfig],
    ) -> None:
        """Run button respects user's benchmark selection."""
        mock_get_benchmarks.return_value = [
            {"id": "teleqna", "name": "TeleQnA", "description": "QA benchmark"},
            {"id": "telemath", "name": "TeleMath", "description": "Math benchmark"},
            {"id": "telelogs", "name": "TeleLogs", "description": "Logs benchmark"},
        ]

        app = RunEvalsTestApp(
            model_configs=model_config,
            job_manager=job_manager,
        )

        async with app.run_test() as pilot:
            modal = app.screen
            eval_list = modal.query_one("#eval-list", EvalList)

            # Clear all, then select only teleqna
            eval_list.clear_all()
            # Re-select just one
            eval_list._selected.add("teleqna")

            # Click Run button
            run_btn = modal.query_one("#run-btn", Button)
            await pilot.click(run_btn)
            await pilot.pause()

        # Job should only have teleqna
        assert app.returned_job is not None
        assert app.returned_job.evals["gpt-4o"] == ["teleqna"]

    @patch("satetoad.modals.tabbed_evals_modal.get_benchmarks")
    async def test_run_without_model_shows_error(
        self,
        mock_get_benchmarks: MagicMock,
        job_manager: JobManager,
    ) -> None:
        """Run button without configured model shows error notification."""
        mock_get_benchmarks.return_value = [
            {"id": "teleqna", "name": "TeleQnA", "description": "QA benchmark"},
        ]

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
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        (jobs_dir / "counter.txt").write_text("0")
        return JobManager(jobs_dir)

    @patch("satetoad.modals.tabbed_evals_modal.get_benchmarks")
    async def test_run_creates_job_with_multiple_models(
        self,
        mock_get_benchmarks: MagicMock,
        job_manager: JobManager,
    ) -> None:
        """Run with multiple models creates job tracking all of them."""
        mock_get_benchmarks.return_value = [
            {"id": "teleqna", "name": "TeleQnA", "description": "QA benchmark"},
        ]

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
