"""JobListModal - Modal for viewing evaluation jobs.

Lists all jobs with their status and allows navigation
to individual job details.
"""

from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, HorizontalGroup
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from satetoad.models.job import Job, STATUS_ICONS
from satetoad.services.job_manager import JobManager


class JobListItem(HorizontalGroup):
    """Single job row in the job list.

    Layout:
    +----------------------------------------+
    | ● job_1     TeleQnA, TeleLogs  Running |
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

        #status-icon {
            width: 2;
            color: #faf9f5 60%;
        }

        &.-pending #status-icon {
            color: #FFB86C;
        }

        &.-running #status-icon {
            color: #8BE9FD;
        }

        &.-completed #status-icon {
            color: #50FA7B;
        }

        &.-failed #status-icon {
            color: #FF5555;
        }

        #job-name {
            width: 10;
            text-style: bold;
            color: #F8F8F2;
        }

        #benchmarks {
            width: 1fr;
            color: #faf9f5 60%;
            text-wrap: nowrap;
            text-overflow: ellipsis;
        }

        #status-text {
            width: auto;
            padding: 0 0 0 1;
            color: #faf9f5 60%;
        }
    }
    """

    class Selected(Message):
        """Posted when this job is selected."""

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
        # Add status class for styling
        self.add_class(f"-{job.status.value}")

    @property
    def job_id(self) -> str:
        """Return the job ID."""
        return self._job.id

    def compose(self) -> ComposeResult:
        """Compose the job item layout."""
        icon = STATUS_ICONS.get(self._job.status, "○")
        yield Static(icon, id="status-icon")
        yield Label(self._job.display_name, id="job-name")

        benchmarks = ", ".join(self._job.benchmarks[:3])
        if len(self._job.benchmarks) > 3:
            benchmarks += f" +{len(self._job.benchmarks) - 3}"
        yield Static(benchmarks, id="benchmarks")
        yield Static(self._job.status.value.capitalize(), id="status-text")

    def on_click(self) -> None:
        """Handle click - select this job."""
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
    │  ● job_1   TeleQnA, TeleLogs Running│
    │  ○ job_2   TeleMath         Pending │
    │  ✕ job_3   3GPP             Failed  │
    │                                     │
    │              [Close]                │
    ╰─────────────────────────────────────╯
    """

    CSS_PATH = "modal_base.tcss"

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

    def __init__(self, job_manager: JobManager | None = None) -> None:
        """Initialize the modal.

        Args:
            job_manager: JobManager instance (creates new one if not provided)
        """
        super().__init__()
        self._job_manager = job_manager or JobManager()
        self._jobs: list[Job] = []

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="container"):
            yield Static("View Progress", classes="modal-title")

            # Load jobs
            self._jobs = self._job_manager.list_jobs(limit=20)

            if self._jobs:
                with VerticalScroll(id="job-list"):
                    for job in self._jobs:
                        yield JobListItem(job)
            else:
                yield Static(
                    "No jobs yet.\nRun evaluations to create jobs.",
                    id="empty-message",
                )

            # Close button
            with HorizontalGroup(id="buttons"):
                yield Button("Close", id="close-btn", variant="default")

    def on_mount(self) -> None:
        """Focus first job item if available."""
        if self._jobs:
            self._update_highlight()

    def _update_highlight(self) -> None:
        """Update the highlight on job items."""
        items = list(self.query(JobListItem))
        for i, item in enumerate(items):
            if i == self.highlighted:
                item.add_class("-highlight")
            else:
                item.remove_class("-highlight")

    def watch_highlighted(self, value: int) -> None:
        """React to highlight changes."""
        self._update_highlight()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "close-btn":
            self.dismiss(None)

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
        elif event.key in ("up", "k"):
            self.highlighted = max(self.highlighted - 1, 0)
            event.stop()
        elif event.key in ("enter", "space"):
            if 0 <= self.highlighted < len(self._jobs):
                self.dismiss(self._jobs[self.highlighted].id)
                event.stop()

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(None)
