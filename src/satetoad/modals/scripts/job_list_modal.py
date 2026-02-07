"""JobListModal - Modal for viewing evaluation jobs.

Lists all jobs and allows navigation to individual job details.
"""

from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalGroup, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Button, ProgressBar, Static

from satetoad.services.evals import Job, JobManager, JobStatus

CANCEL_SYMBOL = "✕"

STATUS_SYMBOLS: dict[JobStatus, str] = {
    "running": "●",
    "success": "◉",
    "cancelled": "●",
    "error": "✕",
}


class JobListItem(HorizontalGroup):
    """Single job row in the job list.

    Layout:
    +----------------------------------------+
    | jobs_1     openai/gpt-4o  TeleQnA, ... |
    +----------------------------------------+
    """

    DEFAULT_CSS = """
    JobListItem {
        width: 1fr;
        height: auto;
        min-height: 1;
        padding: 0 1;

        &:hover {
            background: #44475A 50%;
        }

        &.-highlight {
            background: #44475A;
        }

        #job-info {
            width: auto;
            margin: 0 2 0 0;
            text-wrap: nowrap;
            text-overflow: ellipsis;
        }

        ProgressBar {
            width: 1fr;
            height: 1;
            padding: 0;
        }

        Bar {
            width: 1fr;
        }

        #cancel-btn {
            dock: right;
            width: 3;
            height: 1;
            color: #FF5555;

            &:hover {
                color: #FF5555;
                text-style: bold;
            }
        }
    }
    """

    class Selected(Message):
        """Posted when this job is selected."""

        def __init__(self, job_id: str) -> None:
            super().__init__()
            self.job_id = job_id

    class CancelRequested(Message):
        """Posted when the cancel button is clicked on a running job."""

        def __init__(self, job_id: str) -> None:
            super().__init__()
            self.job_id = job_id

    def __init__(self, job: Job) -> None:
        """Initialize the job list item.

        Args:
            job: The job to display
        """
        super().__init__()
        self._job = job
        self._last_bar_total = 0
        self._last_bar_progress = 0
        self.can_focus = True
        self.add_class(f"-{job.status}")

    @property
    def job_id(self) -> str:
        """Return the job ID."""
        return self._job.id

    def compose(self) -> ComposeResult:
        """Compose the job item layout: status icon + job id + progress bar + cancel."""
        yield Static(STATUS_SYMBOLS[self._job.status], id="status")
        yield Static(self._job.id, id="job-info")
        yield self._build_progress_bar()

        if self._job.status == "running":
            yield Static(CANCEL_SYMBOL, id="cancel-btn")

    def _build_progress_bar(self) -> ProgressBar:
        """Build a ProgressBar reflecting the current job state."""
        total, _ = self._desired_bar_values()
        return ProgressBar(total=total, show_percentage=False, show_eta=False)

    def _is_stopped(self) -> bool:
        """Check if the job is in a terminal non-success state."""
        return self._job.status in ("error", "cancelled")

    def on_mount(self) -> None:
        """Set the initial progress bar value after mount."""
        total, progress = self._desired_bar_values()
        self._last_bar_total = total
        self._last_bar_progress = progress
        bar = self.query_one(ProgressBar)
        bar.update(total=total, progress=progress)

    def update_job(self, job: Job) -> None:
        """Update this item with refreshed job data."""
        old_status = self._job.status
        self._job = job

        if old_status != job.status:
            self.remove_class(f"-{old_status}")
            self.add_class(f"-{job.status}")
            self.query_one("#status", Static).update(STATUS_SYMBOLS[job.status])

        self._sync_progress_bar()
        self._sync_cancel_button()

    def _sync_progress_bar(self) -> None:
        """Update the progress bar in-place, skipping no-op updates."""
        total, progress = self._desired_bar_values()
        if total == self._last_bar_total and progress == self._last_bar_progress:
            return

        self._last_bar_total = total
        self._last_bar_progress = progress

        bar = self.query_one(ProgressBar)
        bar.update(total=total, progress=progress)

    def _desired_bar_values(self) -> tuple[int, int]:
        """Return (total, progress) for the progress bar."""
        if self._job.status == "success":
            return (100, 100)
        if self._is_stopped():
            if self._job.completed_evals == 0:
                return (100, 100)
            return (max(self._job.total_evals, 1), self._job.completed_evals)
        if self._job.total_evals > 0:
            return (self._job.total_evals, self._job.completed_evals)
        return (100, 0)

    def _sync_cancel_button(self) -> None:
        """Show or hide the cancel button based on job status."""
        cancel_btns = self.query("#cancel-btn")
        if self._job.status == "running" and not cancel_btns:
            self.mount(Static(CANCEL_SYMBOL, id="cancel-btn"))
        if self._job.status != "running" and cancel_btns:
            cancel_btns.first().remove()

    def _is_cancel_click(self, event: events.Click) -> bool:
        """Check if the click target is the cancel button."""
        for widget in event.widget.ancestors_with_self:
            if getattr(widget, "id", None) == "cancel-btn":
                return True
        return False

    def on_click(self, event: events.Click) -> None:
        """Handle click - cancel button or select this job."""
        if self._is_cancel_click(event):
            event.stop()
            self.post_message(self.CancelRequested(self._job.id))
            return
        self.post_message(self.Selected(self._job.id))

    def on_key(self, event: events.Key) -> None:
        """Handle key press - Enter selects."""
        if event.key in ("enter", "space"):
            event.stop()
            self.post_message(self.Selected(self._job.id))


EMPTY_JOBS_MESSAGE = "No jobs yet. Run evaluations to create jobs."


class JobListModal(ModalScreen[str | None]):
    """Modal for viewing and selecting evaluation jobs.

    Returns the selected job ID, or None if cancelled.
    Polls every 2 seconds to update progress bars.
    """

    CSS_PATH = "../styles/modal_base.tcss"

    DEFAULT_CSS = """
    JobListModal {
        align: center middle;
        background: black 50%;
    }

    JobListModal #container {
        min-width: 50;
        max-width: 70;
    }

    JobListModal #job-list {
        height: auto;
        max-height: 15;
        border: solid #BD93F9 30%;
        background: #282A36;
        padding: 0;
    }

    JobListModal #empty-message {
        padding: 2;
        text-align: center;
        color: #faf9f5 60%;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close", "Close", show=False),
        Binding("tab", "app.focus_next", "Focus Next", show=False),
        Binding("shift+tab", "app.focus_previous", "Focus Previous", show=False),
    ]

    highlighted: reactive[int] = reactive(0)

    def __init__(self, job_manager: JobManager) -> None:
        """Initialize the modal.

        Args:
            job_manager: JobManager instance (required)
        """
        super().__init__()
        self._job_manager = job_manager
        self._jobs: list[Job] = []
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        self._jobs = self._job_manager.list_jobs(limit=20)

        with Vertical(id="container"):
            yield Static("View Progress", classes="modal-title")
            yield from self._compose_job_list()

            with HorizontalGroup(id="buttons"):
                yield Button("Close", id="close-btn", variant="default")

    def _compose_job_list(self) -> ComposeResult:
        """Compose either the job list or empty message."""
        if not self._jobs:
            yield Static(EMPTY_JOBS_MESSAGE, id="empty-message")
            return

        with VerticalScroll(id="job-list"):
            for job in self._jobs:
                yield JobListItem(job)

    def on_mount(self) -> None:
        """Focus first job item if available and start polling."""
        if self._jobs:
            self._update_highlight()
        self._refresh_timer = self.set_interval(2.0, self._refresh_jobs)

    def on_unmount(self) -> None:
        """Stop polling when unmounted."""
        if self._refresh_timer is not None:
            self._refresh_timer.stop()

    def _refresh_jobs(self) -> None:
        """Poll job manager and update items in-place."""
        fresh_jobs = self._job_manager.list_jobs(limit=20)

        if self._job_ids_changed(fresh_jobs):
            self._jobs = fresh_jobs
            self._rebuild_job_list()
            return

        self._jobs = fresh_jobs
        self._update_existing_items()

    def _job_ids_changed(self, fresh_jobs: list[Job]) -> bool:
        """Check if the job ID set has changed (new/removed jobs)."""
        old_ids = {j.id for j in self._jobs}
        new_ids = {j.id for j in fresh_jobs}
        return old_ids != new_ids

    def _rebuild_job_list(self) -> None:
        """Fully rebuild the job list (when jobs are added/removed)."""
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
        items = list(self.query(JobListItem))
        job_by_id = {j.id: j for j in self._jobs}
        for item in items:
            fresh = job_by_id.get(item.job_id)
            if fresh is None:
                continue
            item.update_job(fresh)

    def _update_highlight(self) -> None:
        """Update the highlight on job items."""
        for i, item in enumerate(self.query(JobListItem)):
            item.set_class(i == self.highlighted, "-highlight")

    def watch_highlighted(self, value: int) -> None:
        """React to highlight changes."""
        self._update_highlight()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "close-btn":
            self.dismiss(None)

    def on_job_list_item_cancel_requested(
        self, event: JobListItem.CancelRequested
    ) -> None:
        """Handle cancel request - forward to eval runner."""
        event.stop()
        if self.app._eval_runner is not None:
            self.app._eval_runner.cancel_job(event.job_id)

    def on_job_list_item_selected(self, event: JobListItem.Selected) -> None:
        """Handle job selection."""
        event.stop()
        self.dismiss(event.job_id)

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard navigation."""
        if not self._jobs:
            return

        if event.key in ("down", "j"):
            self.highlighted = min(self.highlighted + 1, len(self._jobs) - 1)
            event.stop()
            return

        if event.key in ("up", "k"):
            self.highlighted = max(self.highlighted - 1, 0)
            event.stop()
            return

        if event.key in ("enter", "space") and 0 <= self.highlighted < len(self._jobs):
            self.dismiss(self._jobs[self.highlighted].id)
            event.stop()

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(None)
