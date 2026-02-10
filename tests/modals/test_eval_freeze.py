"""Tests for eval screen freeze bug."""

import time
from unittest.mock import MagicMock

from textual.app import App

from satellite.modals import ModelConfig, TabbedEvalsModal
from satellite.modals.scripts.job_list_modal import JobListModal
from satellite.services.config import EvalSettingsManager
from satellite.services.evals import Job, JobManager


def _make_slow_job_manager(delay=0.5):
    manager = MagicMock(spec=JobManager)
    def slow_list_jobs(limit=None):
        time.sleep(delay)
        return []
    manager.list_jobs.side_effect = slow_list_jobs
    manager.get_job.return_value = None
    return manager


class TabbedEvalsTestApp(App):
    def __init__(self, job_manager):
        super().__init__()
        self._job_manager = job_manager
    def on_mount(self):
        modal = TabbedEvalsModal(
            job_manager=self._job_manager,
            settings_manager=EvalSettingsManager(),
            model_configs=[ModelConfig(provider="openai", api_key="sk-test", model="gpt-4o")],
        )
        self.push_screen(modal)


class JobListModalTestApp(App):
    def __init__(self, job_manager):
        super().__init__()
        self._job_manager = job_manager
    def on_mount(self):
        self.push_screen(JobListModal(job_manager=self._job_manager))


class TestJobListContentNonBlocking:
    async def test_poll_refresh_should_not_block_main_thread(self):
        slow_manager = _make_slow_job_manager(delay=0.5)
        app = TabbedEvalsTestApp(job_manager=slow_manager)
        async with app.run_test() as pilot:
            await pilot.pause()
            modal = app.screen
            content = modal.query_one("#view-progress-pane")
            content.add_class("-active")
            start = time.monotonic()
            content._poll_refresh()
            elapsed = time.monotonic() - start
            assert elapsed < 0.1, f"_poll_refresh blocked for {elapsed:.2f}s"

    async def test_refresh_jobs_uses_worker_thread(self):
        slow_manager = _make_slow_job_manager(delay=0.5)
        app = TabbedEvalsTestApp(job_manager=slow_manager)
        async with app.run_test() as pilot:
            await pilot.pause()
            modal = app.screen
            content = modal.query_one("#view-progress-pane")
            start = time.monotonic()
            content.refresh_jobs()
            elapsed = time.monotonic() - start
            assert elapsed < 0.1, f"refresh_jobs() blocked for {elapsed:.2f}s"


class TestJobListModalNonBlocking:
    async def test_job_list_modal_refresh_non_blocking(self):
        slow_manager = _make_slow_job_manager(delay=0.5)
        app = JobListModalTestApp(job_manager=slow_manager)
        async with app.run_test() as pilot:
            await pilot.pause()
            modal = app.screen
            start = time.monotonic()
            modal._refresh_jobs()
            elapsed = time.monotonic() - start
            assert elapsed < 0.1, f"_refresh_jobs blocked for {elapsed:.2f}s"

    async def test_refresh_eventually_updates_ui(self):
        fast_manager = MagicMock(spec=JobManager)
        fast_manager.list_jobs.return_value = []
        fast_manager.get_job.return_value = None
        app = JobListModalTestApp(job_manager=fast_manager)
        async with app.run_test() as pilot:
            await pilot.pause()
            modal = app.screen
            modal._refresh_jobs()
            await pilot.pause()
            await pilot.pause()
            assert fast_manager.list_jobs.call_count >= 2
