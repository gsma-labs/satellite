"""JobListMixin - Shared job list management for JobListModal and JobListContent.

Extracts duplicated methods for job list polling, rebuild, and highlight
management. Both JobListModal and JobListContent (in TabbedEvalsModal)
share identical implementations of these 5 methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import VerticalScroll
from textual.widgets import Static

if TYPE_CHECKING:
    from satellite.services.evals import Job

EMPTY_JOBS_MESSAGE = "No jobs yet. Run evaluations to create jobs."


class JobListMixin:
    """Mixin providing shared job-list management methods.

    Expects consumers to provide:
    - self._jobs: list[Job]
    - self.highlighted: reactive[int]
    - Textual DOMNode methods (query, mount, etc.)
    """

    _jobs: list[Job]

    def _job_ids_changed(self, fresh_jobs: list[Job]) -> bool:
        """Check if the job ID set has changed (new/removed jobs)."""
        old_ids = {j.id for j in self._jobs}
        new_ids = {j.id for j in fresh_jobs}
        return old_ids != new_ids

    def _rebuild_job_list(self) -> None:
        """Fully rebuild the job list (when jobs are added/removed)."""
        from satellite.modals.scripts.job_list_modal import JobListItem

        job_list = self.query("#job-list")
        empty_msg = self.query("#empty-message")

        if not self._jobs:
            if job_list:
                job_list.first().remove()
            if not empty_msg:
                self.mount(Static(EMPTY_JOBS_MESSAGE, id="empty-message"))
            return

        if empty_msg:
            empty_msg.first().remove()

        if job_list:
            container = job_list.first()
            container.remove_children()
            for job in self._jobs:
                container.mount(JobListItem(job))
            return

        scroll = VerticalScroll(id="job-list")
        self.mount(scroll)
        for job in self._jobs:
            scroll.mount(JobListItem(job))

    def _update_existing_items(self) -> None:
        """Update existing job items in-place with fresh data."""
        from satellite.modals.scripts.job_list_modal import JobListItem

        items = list(self.query(JobListItem))
        job_by_id = {j.id: j for j in self._jobs}
        for item in items:
            fresh = job_by_id.get(item.job_id)
            if fresh is None:
                continue
            item.update_job(fresh)

    def _update_highlight(self) -> None:
        """Update the highlight on job items."""
        from satellite.modals.scripts.job_list_modal import JobListItem

        for i, item in enumerate(self.query(JobListItem)):
            item.set_class(i == self.highlighted, "-highlight")

    def watch_highlighted(self, value: int) -> None:
        """React to highlight changes."""
        self._update_highlight()
