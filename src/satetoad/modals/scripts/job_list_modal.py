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
from textual.widgets import Button, Static

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
            width: 1fr;
            text-wrap: nowrap;
            text-overflow: ellipsis;
        }

        #cancel-btn {
            width: 3;
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
        self.can_focus = True
        self.add_class(f"-{job.status}")

    @property
    def job_id(self) -> str:
        """Return the job ID."""
        return self._job.id

    def compose(self) -> ComposeResult:
        """Compose the job item layout."""
        models = list(self._job.evals.keys())
        model_text = models[0] if len(models) == 1 else f"{len(models)} models"

        benchmarks = list(self._job.evals.values())[0] if self._job.evals else []
        benchmark_text = ", ".join(benchmarks[:3])
        if len(benchmarks) > 3:
            benchmark_text += f" +{len(benchmarks) - 3}"

        # Single inline with middle dot separators
        display = f"{self._job.id} · {model_text} · {benchmark_text}"

        yield Static(STATUS_SYMBOLS[self._job.status], id="status")
        yield Static(display, id="job-info")

        if self._job.status == "running":
            yield Static(CANCEL_SYMBOL, id="cancel-btn")

    def on_click(self, event: events.Click) -> None:
        """Handle click - cancel button or select this job."""
        cancel_btn = self.query("#cancel-btn")
        if cancel_btn and event.widget is cancel_btn.first():
            event.stop()
            self.post_message(self.CancelRequested(self._job.id))
            return
        self.post_message(self.Selected(self._job.id))

    def on_key(self, event: events.Key) -> None:
        """Handle key press - Enter selects."""
        if event.key in ("enter", "space"):
            event.stop()
            self.post_message(self.Selected(self._job.id))


class JobListModal(ModalScreen[str | None]):
    """Modal for viewing and selecting evaluation jobs.

    Returns the selected job ID, or None if cancelled.

    Layout:
    ╭─────────────────────────────────────╮
    │           View Progress             │
    ├─────────────────────────────────────┤
    │  jobs_1   openai/gpt-4o   TeleQnA   │
    │  jobs_2   anthropic/...   TeleMath  │
    │                                     │
    │              [Close]                │
    ╰─────────────────────────────────────╯
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
            yield Static(
                "No jobs yet.\nRun evaluations to create jobs.",
                id="empty-message",
            )
            return

        with VerticalScroll(id="job-list"):
            for job in self._jobs:
                yield JobListItem(job)

    def on_mount(self) -> None:
        """Focus first job item if available."""
        if self._jobs:
            self._update_highlight()

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
