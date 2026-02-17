"""Tests for JobDetailModal results display.

Tests the bug fix where selecting a job from View Progress
now correctly fetches and displays results instead of "No results yet".
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from textual.app import App

from satellite.modals import (
    JobDetailModal,
    JobListItem,
    ModelConfig,
    TabbedEvalsModal,
)
from satellite.services.config import EvalSettingsManager
from satellite.services.evals import Job, JobDetails, JobManager
from satellite.widgets.tab_header import TabHeader
from satellite.widgets.tab_item import TabItem


def _make_mock_job_manager(
    job: Job,
    results: dict[str, dict[str, float]] | None = None,
    details: JobDetails | None = None,
) -> MagicMock:
    """Create a mock JobManager returning the given results/details."""
    manager = MagicMock(spec=JobManager)
    manager.list_jobs.return_value = [job]
    manager.get_job.return_value = job
    manager.get_job_results.return_value = results or {}
    manager.get_job_details.return_value = details
    return manager


# ============================================================================
# Test Apps for Headless Testing
# ============================================================================


class JobDetailModalTestApp(App):
    """Test app for JobDetailModal in isolation."""

    def __init__(
        self,
        job: Job,
        results: dict[str, dict[str, float]] | None = None,
        details: JobDetails | None = None,
        job_manager: MagicMock | None = None,
    ) -> None:
        super().__init__()
        self._job = job
        self._job_manager = job_manager or _make_mock_job_manager(
            job, results, details
        )

    def on_mount(self) -> None:
        self.push_screen(
            JobDetailModal(job=self._job, job_manager=self._job_manager)
        )


class TabbedEvalsJobSelectionTestApp(App):
    """Test app for testing job selection flow in TabbedEvalsModal."""

    def __init__(
        self,
        job_manager: JobManager,
        model_configs: list[ModelConfig] | None = None,
        settings_manager: EvalSettingsManager | None = None,
    ) -> None:
        super().__init__()
        self._job_manager = job_manager
        self._model_configs = model_configs or []
        self._settings_manager = settings_manager or EvalSettingsManager()
        self.pushed_detail_modal: JobDetailModal | None = None

    def on_mount(self) -> None:
        modal = TabbedEvalsModal(
            job_manager=self._job_manager,
            settings_manager=self._settings_manager,
            model_configs=self._model_configs,
        )
        self.push_screen(modal)

    def push_screen(self, screen, *args, **kwargs):
        """Track pushed JobDetailModal for assertions."""
        if isinstance(screen, JobDetailModal):
            self.pushed_detail_modal = screen
        return super().push_screen(screen, *args, **kwargs)


# ============================================================================
# Test Class 1: JobDetailModal Results Display
# ============================================================================


class TestJobDetailModalResultsDisplay:
    """Tests for JobDetailModal rendering results correctly."""

    @pytest.fixture
    def sample_job(self) -> Job:
        """Create a sample job for testing."""
        return Job(
            id="job_1",
            evals={"openai/gpt-4o": ["teleqna", "telemath"]},
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            status="success",
        )

    async def test_modal_shows_pending_scores_when_results_is_none(
        self, sample_job: Job
    ) -> None:
        """JobDetailModal shows '--' pending markers when results is None."""
        app = JobDetailModalTestApp(job=sample_job, results=None)

        async with app.run_test():
            modal = app.screen

            pending_cells = list(modal.query(".score-pending"))
            # 1 model x 2 benchmarks = 2 pending cells
            assert len(pending_cells) == 2

    async def test_modal_shows_pending_scores_when_results_is_empty(
        self, sample_job: Job
    ) -> None:
        """JobDetailModal shows '--' pending markers when results is empty dict."""
        app = JobDetailModalTestApp(job=sample_job, results={})

        async with app.run_test():
            modal = app.screen

            pending_cells = list(modal.query(".score-pending"))
            assert len(pending_cells) == 2

    async def test_modal_displays_results_when_provided(
        self, sample_job: Job
    ) -> None:
        """JobDetailModal displays actual scores when results provided."""
        results = {"openai/gpt-4o": {"teleqna": 0.85, "telemath": 0.72}}
        app = JobDetailModalTestApp(job=sample_job, results=results)

        async with app.run_test():
            modal = app.screen

            # No pending cells when all results are available
            pending_cells = list(modal.query(".score-pending"))
            assert len(pending_cells) == 0

            # Scores rendered as {score:.2f} in .scores-cell elements
            score_cells = list(modal.query(".scores-cell"))
            score_text = " ".join(str(cell.render()) for cell in score_cells)
            assert "0.85" in score_text
            assert "0.72" in score_text

    @pytest.mark.parametrize(
        ("score", "expected_text"),
        [
            pytest.param(0.95, "0.95", id="high_score"),
            pytest.param(0.50, "0.50", id="mid_score"),
            pytest.param(0.0, "0.00", id="zero_score"),
        ],
    )
    async def test_modal_formats_scores_as_decimal(
        self, sample_job: Job, score: float, expected_text: str
    ) -> None:
        """JobDetailModal formats scores as {score:.2f} decimal."""
        results = {"openai/gpt-4o": {"teleqna": score, "telemath": score}}
        app = JobDetailModalTestApp(job=sample_job, results=results)

        async with app.run_test():
            modal = app.screen

            score_cells = list(modal.query(".scores-cell"))
            all_text = " ".join(str(cell.render()) for cell in score_cells)
            assert expected_text in all_text

    async def test_poll_refresh_survives_job_manager_exception(
        self, sample_job: Job
    ) -> None:
        """Polling should not crash if JobManager throws during refresh."""
        manager = MagicMock(spec=JobManager)
        manager.get_job_results.side_effect = [
            {"openai/gpt-4o": {"teleqna": 0.85, "telemath": 0.72}},
            RuntimeError("read failure"),
        ]
        manager.get_job_details.return_value = JobDetails(
            status="success",
            total_samples=10,
            total_tokens=1000,
            duration_seconds=5.0,
        )

        app = JobDetailModalTestApp(job=sample_job, job_manager=manager)

        async with app.run_test():
            modal = app.screen

            score_cells = list(modal.query(".scores-cell"))
            score_text_before = " ".join(str(cell.render()) for cell in score_cells)
            assert "0.85" in score_text_before
            assert "0.72" in score_text_before

            modal._poll_refresh()

            score_cells = list(modal.query(".scores-cell"))
            score_text_after = " ".join(str(cell.render()) for cell in score_cells)
            assert "0.85" in score_text_after
            assert "0.72" in score_text_after
            assert manager.get_job_results.call_count == 2


# ============================================================================
# Test Class 2: Job Selection Fetches Results (Bug Fix Verification)
# ============================================================================


class TestJobSelectionFetchesResults:
    """Tests verifying that job selection correctly fetches results.

    This tests the bug fix where selecting a job from View Progress
    now calls get_job_results() before opening JobDetailModal.
    """

    @pytest.fixture
    def job_manager_with_results(self, tmp_path: Path) -> MagicMock:
        """Create a mock JobManager that returns results."""
        sample_job = Job(
            id="job_1",
            evals={"openai/gpt-4o": ["teleqna"]},
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            status="success",
        )

        return _make_mock_job_manager(
            job=sample_job,
            results={"openai/gpt-4o": {"teleqna": 0.85}},
            details=JobDetails(
                status="success",
                total_samples=10,
                total_tokens=5000,
                duration_seconds=45.0,
            ),
        )

    async def test_selecting_job_calls_get_job_results(
        self,
        job_manager_with_results: MagicMock,
    ) -> None:
        """Selecting a job from View Progress calls get_job_results()."""
        model_configs = [
            ModelConfig(provider="openai", api_key="sk-test", model="gpt-4o")
        ]
        app = TabbedEvalsJobSelectionTestApp(
            job_manager=job_manager_with_results,
            model_configs=model_configs,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Switch to Progress tab
            modal = app.screen
            tabs = list(modal.query_one("#tab-header", TabHeader).query(TabItem))
            await pilot.click(tabs[1])
            await pilot.pause()

            # Find and click the job item
            job_items = list(modal.query(JobListItem))
            assert len(job_items) == 1

            await pilot.click(job_items[0])
            await pilot.pause()

        # Verify get_job_results was called (once by on_mount of the detail modal)
        job_manager_with_results.get_job_results.assert_called_with("job_1")

    async def test_job_detail_modal_receives_job_manager(
        self,
        job_manager_with_results: MagicMock,
    ) -> None:
        """JobDetailModal receives job_manager when opened from job selection."""
        model_configs = [
            ModelConfig(provider="openai", api_key="sk-test", model="gpt-4o")
        ]
        app = TabbedEvalsJobSelectionTestApp(
            job_manager=job_manager_with_results,
            model_configs=model_configs,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Switch to Progress tab
            modal = app.screen
            tabs = list(modal.query_one("#tab-header", TabHeader).query(TabItem))
            await pilot.click(tabs[1])
            await pilot.pause()

            # Click the job item
            job_items = list(modal.query(JobListItem))
            await pilot.click(job_items[0])
            await pilot.pause()

        # Verify the pushed modal has a job_manager reference
        assert app.pushed_detail_modal is not None
        assert app.pushed_detail_modal._job_manager is job_manager_with_results


# ============================================================================
# Test Class 3: datetime.now Default Factory Fix
# ============================================================================


class TestJobDatetimeDefault:
    """Tests for Job dataclass datetime default factory fix."""

    def test_job_created_at_is_datetime_instance(self) -> None:
        """Job.created_at should be a datetime instance, not a function."""
        job = Job(id="test_job", evals={})

        # Before fix: created_at would be <function datetime.now>
        # After fix: created_at is an actual datetime
        assert isinstance(job.created_at, datetime)

    def test_job_created_at_is_current_time(self) -> None:
        """Job.created_at should be close to current time when created."""
        before = datetime.now()
        job = Job(id="test_job", evals={})
        after = datetime.now()

        # created_at should be between before and after
        assert before <= job.created_at <= after

    def test_multiple_jobs_have_different_timestamps(self) -> None:
        """Each Job should have its own timestamp, not share a reference."""
        import time

        job1 = Job(id="job_1", evals={})
        time.sleep(0.01)  # Small delay to ensure different timestamps
        job2 = Job(id="job_2", evals={})

        # Before fix: both would have the same callable reference
        # After fix: each has its own timestamp
        assert job1.created_at != job2.created_at


# ============================================================================
# Test Class 4: Dynamic Modal Width Based on Benchmark Count
# ============================================================================


class TestJobDetailModalDynamicWidth:
    """Tests for JobDetailModal dynamic width based on benchmark count."""

    @pytest.mark.parametrize(
        ("num_benchmarks", "expected_width"),
        [
            pytest.param(0, 60, id="no_benchmarks"),
            pytest.param(3, 62, id="three_benchmarks"),
            pytest.param(5, 86, id="five_benchmarks"),
            pytest.param(7, 110, id="seven_benchmarks"),
        ],
    )
    async def test_container_max_width_scales_with_benchmarks(
        self, num_benchmarks: int, expected_width: int
    ) -> None:
        """Container max_width is calculated from benchmark count."""
        benchmarks = [f"bench_{i}" for i in range(num_benchmarks)]
        job = Job(
            id="test_job",
            evals={"model/test": benchmarks} if benchmarks else {},
            created_at=datetime(2024, 1, 1),
            status="success",
        )
        app = JobDetailModalTestApp(job=job, results=None)

        async with app.run_test():
            container = app.screen.query_one("#container")
            assert container.styles.max_width.value == expected_width
