"""Tests for progress bar update behavior in JobListItem.

Covers:
- _desired_bar_values() returns correct (total, progress) for each Job state
- _sync_progress_bar() skips no-op updates
- _job_ids_changed() uses set comparison (order-independent)
- on_mount syncs cached bar values to prevent first-poll re-animation
"""

from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.widgets import ProgressBar

from satellite.modals.scripts.job_list_modal import JobListItem, JobListModal
from satellite.modals.scripts.tabbed_evals_modal import JobListContent
from satellite.services.evals import Job


def _make_job(
    job_id: str = "job_1",
    status: str = "running",
    completed_evals: int = 0,
    total_evals: int = 5,
    eval_progress: float | None = None,
    completed_samples: int = 0,
    total_samples: int = 100,
) -> Job:
    """Create a Job with the given fields."""
    if eval_progress is None:
        # Default to whole-eval progress for tests that don't care about fractional progress.
        eval_progress = float(completed_evals)
    return Job(
        id=job_id,
        status=status,
        completed_evals=completed_evals,
        total_evals=total_evals,
        eval_progress=eval_progress,
        completed_samples=completed_samples,
        total_samples=total_samples,
    )


# ---------------------------------------------------------------------------
# _desired_bar_values() — pure logic tests (no mount needed)
# ---------------------------------------------------------------------------


class TestDesiredBarValues:
    """Test _desired_bar_values() returns correct (total, progress) for each state."""

    @pytest.mark.parametrize(
        ("status", "total_evals", "eval_progress", "expected"),
        [
            pytest.param("running", 5, 0.0, (5.0, 0.0), id="running_zero_progress"),
            pytest.param("running", 5, 2.0, (5.0, 2.0), id="running_whole_eval_progress"),
            pytest.param("running", 5, 2.4, (5.0, 2.4), id="running_fractional_progress"),
            pytest.param("running", 0, 0.0, (100.0, 0.0), id="running_no_evals_yet"),
            pytest.param("success", 5, 5.0, (100.0, 100.0), id="success"),
            pytest.param("error", 5, 3.0, (100.0, 100.0), id="error_with_progress"),
            pytest.param("error", 5, 0.0, (100.0, 100.0), id="error_no_progress"),
            pytest.param("cancelled", 5, 2.0, (100.0, 100.0), id="cancelled_with_progress"),
            pytest.param("cancelled", 5, 0.0, (100.0, 100.0), id="cancelled_no_progress"),
        ],
    )
    def test_desired_bar_values(
        self,
        status: str,
        total_evals: int,
        eval_progress: float,
        expected: tuple[float, float],
    ) -> None:
        """_desired_bar_values() uses fractional eval progress while running."""
        job = _make_job(
            status=status,
            total_evals=total_evals,
            eval_progress=eval_progress,
        )
        item = JobListItem(job)
        assert item._desired_bar_values() == expected


# ---------------------------------------------------------------------------
# _job_ids_changed() — set comparison (order-independent)
# ---------------------------------------------------------------------------


class TestJobIdsChanged:
    """Test that _job_ids_changed uses set comparison, not ordered list."""

    def test_same_ids_different_order_returns_false(
        self,
        mock_job_manager: MagicMock,
    ) -> None:
        """Same job IDs in different order should NOT trigger rebuild."""
        modal = JobListModal(mock_job_manager)
        modal._jobs = [_make_job("a"), _make_job("b"), _make_job("c")]

        reordered = [_make_job("c"), _make_job("a"), _make_job("b")]
        assert modal._job_ids_changed(reordered) is False

    def test_new_job_added_returns_true(
        self,
        mock_job_manager: MagicMock,
    ) -> None:
        """A genuinely new job ID should trigger rebuild."""
        modal = JobListModal(mock_job_manager)
        modal._jobs = [_make_job("a"), _make_job("b")]

        with_new = [_make_job("a"), _make_job("b"), _make_job("c")]
        assert modal._job_ids_changed(with_new) is True

    def test_job_removed_returns_true(
        self,
        mock_job_manager: MagicMock,
    ) -> None:
        """A removed job ID should trigger rebuild."""
        modal = JobListModal(mock_job_manager)
        modal._jobs = [_make_job("a"), _make_job("b"), _make_job("c")]

        without = [_make_job("a"), _make_job("b")]
        assert modal._job_ids_changed(without) is True

    def test_empty_to_empty_returns_false(
        self,
        mock_job_manager: MagicMock,
    ) -> None:
        """Empty→empty should not trigger rebuild."""
        modal = JobListModal(mock_job_manager)
        modal._jobs = []
        assert modal._job_ids_changed([]) is False

    def test_tabbed_same_ids_different_order_returns_false(
        self,
        mock_job_manager: MagicMock,
    ) -> None:
        """JobListContent also uses set comparison (order-independent)."""
        content = JobListContent(mock_job_manager)
        content._jobs = [_make_job("x"), _make_job("y")]

        reordered = [_make_job("y"), _make_job("x")]
        assert content._job_ids_changed(reordered) is False


# ---------------------------------------------------------------------------
# on_mount + _sync_progress_bar — headless Textual tests
# ---------------------------------------------------------------------------


class _ProgressBarTestApp(App):
    """Minimal app for mounting a JobListItem in isolation."""

    def __init__(self, job: Job) -> None:
        super().__init__()
        self._job = job

    def compose(self) -> ComposeResult:
        yield JobListItem(self._job)


class TestProgressBarCacheSync:
    """Test cache synchronization: on_mount sets cache, sync skips no-ops."""

    async def test_on_mount_sets_cached_values(self) -> None:
        """After mount, cached values match _desired_bar_values()."""
        job = _make_job(status="running", completed_evals=2, total_evals=5)
        app = _ProgressBarTestApp(job)

        async with app.run_test():
            item = app.query_one(JobListItem)
            assert item._last_bar_total == 5.0
            assert item._last_bar_progress == 2.0

    async def test_on_mount_success_job_cached_at_100(self) -> None:
        """Success job should cache (100, 100) after mount."""
        job = _make_job(status="success", completed_evals=5, total_evals=5)
        app = _ProgressBarTestApp(job)

        async with app.run_test():
            item = app.query_one(JobListItem)
            assert item._last_bar_total == 100.0
            assert item._last_bar_progress == 100.0

    async def test_noop_when_values_unchanged(self) -> None:
        """Calling _sync_progress_bar with same job data should not call bar.update."""
        job = _make_job(status="running", completed_evals=2, total_evals=5)
        app = _ProgressBarTestApp(job)

        async with app.run_test():
            item = app.query_one(JobListItem)
            bar = item.query_one(ProgressBar)

            # Record bar state after mount
            total_before = bar.total
            progress_before = bar.progress

            # Call sync again with same data — should be a no-op
            item._sync_progress_bar()

            assert bar.total == total_before
            assert bar.progress == progress_before

    async def test_updates_when_progress_advances(self) -> None:
        """_sync_progress_bar should update bar when job progress changes."""
        job = _make_job(status="running", completed_evals=1, total_evals=5)
        app = _ProgressBarTestApp(job)

        async with app.run_test():
            item = app.query_one(JobListItem)

            # Simulate progress advancing
            advanced_job = _make_job(
                status="running", completed_evals=3, total_evals=5
            )
            item.update_job(advanced_job)

            assert item._last_bar_total == 5.0
            assert item._last_bar_progress == 3.0
