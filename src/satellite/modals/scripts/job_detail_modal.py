"""JobDetailModal - Modal dialog displaying job details with live refresh."""

import webbrowser
from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, VerticalGroup
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Label, Static

from satellite.services.evals import Job, JobDetails, JobManager

INSPECT_TRACES_BASE_URL = "http://127.0.0.1:7575/#/logs"
POLL_INTERVAL_SECONDS = 2.0
TERMINAL_STATUSES = frozenset({"success", "error", "cancelled"})
PENDING_COLOR = "#6272A4"  # Dracula comment color for pending/loading states
PENDING_PLACEHOLDER = f"[{PENDING_COLOR}]--[/]"

STATUS_COLORS: dict[str, str] = {
    "success": "#50FA7B",
    "error": "#FF5555",
    "running": "#8BE9FD",
    "cancelled": "#FFB86C",
}


def _format_tokens(total: int) -> str:
    """Format token count with K/M suffix."""
    if total >= 1_000_000:
        return f"{total / 1_000_000:.1f}M"
    if total >= 1_000:
        return f"{total / 1_000:.1f}K"
    return str(total)


def _format_duration(seconds: float | None) -> str:
    """Format duration as 'Xm Ys' or '< 1s'."""
    if seconds is None:
        return "in progress"
    if seconds < 1:
        return "< 1s"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


class JobDetailModal(ModalScreen[None]):
    """Modal dialog displaying job details with live-updating scores.

    Polls the JobManager every 2 seconds while the job is running,
    updating metadata and scores in-place. Stops polling once the
    job reaches a terminal status (success, error, cancelled).
    """

    CSS_PATH = "../styles/job_detail_modal.tcss"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss", "Close", show=False),
    ]

    def __init__(self, job: Job, job_manager: JobManager) -> None:
        """Initialize the modal.

        Args:
            job: The job to display
            job_manager: Manager for fetching live results and details
        """
        super().__init__()
        self._job = job
        self._job_manager = job_manager
        self._results: dict[str, dict[str, float]] = {}
        self._details: JobDetails | None = None
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with VerticalGroup(id="container"):
            with Horizontal(id="header"):
                yield Static(self._job.id, classes="modal-title")
                yield Static("x", id="close-x")

            yield from self._compose_traces_link()
            yield from self._compose_timestamps()
            yield from self._compose_metadata()
            yield from self._compose_scores_table()

    def _compose_timestamps(self) -> ComposeResult:
        """Compose timestamp row."""
        with Horizontal(classes="metadata-row"):
            yield Static("Created ", classes="meta-label")
            yield Static(
                self._job.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                classes="meta-value",
            )

    def _compose_metadata(self) -> ComposeResult:
        """Compose aggregated metadata as a compact 2x2 grid with placeholder IDs."""
        with Horizontal(classes="metadata-row"):
            yield Static("Status ", classes="meta-label")
            yield Static(PENDING_PLACEHOLDER, id="val-status", classes="meta-value")
            yield Static("Duration ", classes="meta-label")
            yield Static(PENDING_PLACEHOLDER, id="val-duration", classes="meta-value")

        with Horizontal(classes="metadata-row"):
            yield Static("Samples ", classes="meta-label")
            yield Static(PENDING_PLACEHOLDER, id="val-samples", classes="meta-value")
            yield Static("Tokens ", classes="meta-label")
            yield Static(PENDING_PLACEHOLDER, id="val-tokens", classes="meta-value")

    def _compose_traces_link(self) -> ComposeResult:
        """Compose a clickable link to open the Inspect AI trace viewer."""
        yield Static(
            "[#BD93F9]\u2192 Check Traces[/]",
            classes="trace-link",
        )

    def _short_name(self, full_name: str) -> str:
        """Extract short name from full path (e.g., 'openrouter/openai/gpt-4' -> 'gpt-4')."""
        return full_name.rsplit("/", 1)[-1]

    def _calculate_container_width(self) -> int:
        """Calculate modal width based on number of benchmarks."""
        if not self._job.evals:
            return 60
        num_benchmarks = len(next(iter(self._job.evals.values())))
        return 20 + (num_benchmarks * 12) + 6

    def on_mount(self) -> None:
        """Fetch initial data and start polling if the job is still running."""
        self.query_one("#container").styles.opacity = 1.0
        self.query_one("#container").styles.max_width = self._calculate_container_width()

        self._fetch_and_update()

        if self._job.status not in TERMINAL_STATUSES:
            self._refresh_timer = self.set_interval(
                POLL_INTERVAL_SECONDS, self._poll_refresh
            )

    def on_unmount(self) -> None:
        """Stop the polling timer to prevent leaks."""
        if self._refresh_timer is None:
            return
        self._refresh_timer.stop()

    def _fetch_and_update(self) -> None:
        """Fetch latest results/details from JobManager and update the UI."""
        self._results = self._job_manager.get_job_results(self._job.id)
        self._details = self._job_manager.get_job_details(self._job.id)

        self._update_metadata()
        self._update_scores_table()

    def _poll_refresh(self) -> None:
        """Timer callback — re-fetch data and stop polling once terminal."""
        self._fetch_and_update()

        if self._details is None:
            return
        if self._details.status not in TERMINAL_STATUSES:
            return
        if self._refresh_timer is None:
            return

        self._refresh_timer.stop()
        self._refresh_timer = None

    def _update_metadata(self) -> None:
        """Update the four metadata value widgets in-place."""
        if self._details is None:
            return

        color = STATUS_COLORS.get(self._details.status, "#F8F8F2")
        self.query_one("#val-status", Static).update(
            f"[{color}]{self._details.status}[/]"
        )
        self.query_one("#val-duration", Static).update(
            _format_duration(self._details.duration_seconds)
        )
        self.query_one("#val-samples", Static).update(
            f"{self._details.total_samples} evaluated"
        )
        self.query_one("#val-tokens", Static).update(
            _format_tokens(self._details.total_tokens)
        )

    def _update_scores_table(self) -> None:
        """Rebuild the scores table rows with current results."""
        if not self._job.evals:
            return

        table = self.query_one("#scores-table", ScrollableContainer)
        table.remove_children()

        models = list(self._job.evals.keys())
        benchmarks = list(self._job.evals.values())[0]

        self._mount_header_row(table, benchmarks)
        self._mount_data_rows(table, models, benchmarks)

    def _mount_header_row(
        self, table: ScrollableContainer, benchmarks: list[str]
    ) -> None:
        """Mount the header row with benchmark names."""
        header = Horizontal(classes="scores-row scores-header")
        table.mount(header)
        header.mount(Static("", classes="scores-model"))
        for benchmark in benchmarks:
            header.mount(Static(self._short_name(benchmark), classes="scores-cell"))

    def _score_cell(self, score: float | None) -> Static:
        """Create a score cell widget for the scores table."""
        if score is None:
            return Static(PENDING_PLACEHOLDER, classes="scores-cell score-pending")
        return Static(f"[#50FA7B]{score:.2f}[/]", classes="scores-cell")

    def _mount_data_rows(
        self, table: ScrollableContainer, models: list[str], benchmarks: list[str]
    ) -> None:
        """Mount data rows with model scores."""
        for model in models:
            model_scores = self._results.get(model, {})
            row = Horizontal(classes="scores-row")
            table.mount(row)
            row.mount(Static(self._short_name(model), classes="scores-model"))

            for benchmark in benchmarks:
                row.mount(self._score_cell(model_scores.get(benchmark)))

    def _compose_scores_table(self) -> ComposeResult:
        """Compose the initial (empty) scores table container."""
        if not self._job.evals:
            yield Label("Scores", classes="detail-label")
            yield Static("  No evaluations configured", classes="result-item dim")
            return

        yield Label("Scores", classes="detail-label")
        yield ScrollableContainer(id="scores-table", can_focus=False)

    def on_click(self, event: events.Click) -> None:
        """Handle click on close button or trace link."""
        for widget in event.widget.ancestors_with_self:
            if self._is_close_button(widget):
                self.dismiss(None)
                return
            if self._is_trace_link(widget):
                self._open_trace_viewer()
                return

    def _is_close_button(self, widget) -> bool:
        """Check if widget is the close button."""
        return getattr(widget, "id", None) == "close-x"

    def _is_trace_link(self, widget) -> bool:
        """Check if widget is the trace link."""
        return "trace-link" in widget.classes

    def _open_trace_viewer(self) -> None:
        """Open the Inspect AI trace viewer for this job."""
        url = f"{INSPECT_TRACES_BASE_URL}/{self._job.id}/"
        webbrowser.open(url)
