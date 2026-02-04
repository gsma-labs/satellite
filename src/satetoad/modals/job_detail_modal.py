"""JobDetailModal - Modal dialog displaying job details."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalGroup, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from satetoad.models.job import Job, JobStatus, STATUS_ICONS


class JobDetailModal(ModalScreen[None]):
    """Modal dialog displaying job details.

    Shows status, timestamps, model info, benchmarks, and results.
    Dismisses with Escape or Close button.
    """

    CSS_PATH = "job_detail_modal.tcss"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss", "Close", show=False),
    ]

    def __init__(self, job: Job) -> None:
        """Initialize the modal.

        Args:
            job: The job to display
        """
        super().__init__()
        self._job = job

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with VerticalGroup(id="container"):
            with Horizontal(id="header"):
                yield Static(self._job.display_name, classes="modal-title")
                yield Static("x", id="close-x")

            with VerticalScroll(id="detail-scroll"):
                yield from self._compose_status()
                yield from self._compose_timestamps()
                yield from self._compose_model_info()
                yield from self._compose_error()
                yield from self._compose_benchmarks()
                yield from self._compose_results()

    def _compose_status(self) -> ComposeResult:
        """Compose the status row."""
        icon = STATUS_ICONS.get(self._job.status, "○")
        status_class = f"status-{self._job.status.value}"
        yield Label("Status", classes="detail-label")
        yield Static(
            f"{icon} {self._job.status.value.capitalize()}",
            classes=f"detail-value {status_class}",
        )

    def _compose_timestamps(self) -> ComposeResult:
        """Compose timestamp rows."""
        yield Label("Created", classes="detail-label")
        yield Static(
            self._job.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            classes="detail-value",
        )

        if not self._job.completed_at:
            return

        yield Label("Completed", classes="detail-label")
        yield Static(
            self._job.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
            classes="detail-value",
        )

    def _compose_model_info(self) -> ComposeResult:
        """Compose model information row."""
        if not self._job.model_provider and not self._job.model_name:
            return

        yield Label("Model", classes="detail-label")
        provider = self._job.model_provider or "Unknown"
        model = self._job.model_name or "Unknown"
        yield Static(f"{provider}/{model}", classes="detail-value")

    def _compose_error(self) -> ComposeResult:
        """Compose error message row for failed jobs."""
        if self._job.status != JobStatus.FAILED or not self._job.error:
            return

        yield Label("Error", classes="detail-label")
        yield Static(self._job.error, classes="detail-value error-text")

    def _compose_benchmarks(self) -> ComposeResult:
        """Compose benchmarks list."""
        yield Label("Benchmarks", classes="detail-label")
        for benchmark in self._job.benchmarks:
            yield Static(f"  {benchmark}", classes="benchmark-item")

    def _compose_results(self) -> ComposeResult:
        """Compose results list for completed jobs."""
        if not self._job.results:
            return

        yield Label("Results", classes="detail-label")
        for benchmark_id, score in self._job.results.items():
            yield Static(
                f"  {benchmark_id}: [#50FA7B]{score:.2f}[/]",
                classes="result-item",
            )

    def on_click(self, event) -> None:
        """Handle click on close button."""
        for widget in event.widget.ancestors_with_self:
            if getattr(widget, "id", None) == "close-x":
                self.dismiss(None)
                return
