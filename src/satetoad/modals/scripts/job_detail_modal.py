"""JobDetailModal - Modal dialog displaying job details."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, VerticalGroup
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from satetoad.services.evals import Job


class JobDetailModal(ModalScreen[None]):
    """Modal dialog displaying job details.

    Shows timestamps, model info, benchmarks, and results.
    Dismisses with Escape or Close button.
    """

    CSS_PATH = "../styles/job_detail_modal.tcss"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss", "Close", show=False),
    ]

    def __init__(
        self, job: Job, results: dict[str, dict[str, float]] | None = None
    ) -> None:
        """Initialize the modal.

        Args:
            job: The job to display
            results: Optional pre-fetched results {model: {benchmark: score}}
        """
        super().__init__()
        self._job = job
        self._results = results or {}

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with VerticalGroup(id="container"):
            with Horizontal(id="header"):
                yield Static(self._job.id, classes="modal-title")
                yield Static("x", id="close-x")

            yield from self._compose_timestamps()
            yield from self._compose_scores_table()

    def _compose_timestamps(self) -> ComposeResult:
        """Compose timestamp rows."""
        yield Label("Created", classes="detail-label")
        yield Static(
            self._job.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            classes="detail-value",
        )

    def _short_name(self, full_name: str) -> str:
        """Extract short name from full path (e.g., 'openrouter/openai/gpt-4' -> 'gpt-4')."""
        return full_name.rsplit("/", 1)[-1]

    def _calculate_container_width(self) -> int:
        """Calculate modal width based on number of benchmarks."""
        if not self._job.evals:
            return 60
        num_benchmarks = len(next(iter(self._job.evals.values())))
        return 20 + (num_benchmarks * 12) + 6  # model + benchmarks + padding/border

    def on_mount(self) -> None:
        """Set container width dynamically based on benchmark count."""
        self.query_one("#container").styles.max_width = self._calculate_container_width()

    def _compose_scores_table(self) -> ComposeResult:
        """Compose scores as a table: rows=models, columns=benchmarks."""
        if not self._job.evals:
            yield Label("Scores", classes="detail-label")
            yield Static("  No evaluations configured", classes="result-item dim")
            return

        models = list(self._job.evals.keys())
        benchmarks = list(self._job.evals.values())[0]

        yield Label("Scores", classes="detail-label")

        with ScrollableContainer(id="scores-table", can_focus=False):
            # Header row: empty cell + benchmark names
            with Horizontal(classes="scores-row scores-header"):
                yield Static("", classes="scores-model")
                for b in benchmarks:
                    yield Static(self._short_name(b), classes="scores-cell")

            # Data rows: model name + scores
            for model in models:
                model_scores = self._results.get(model, {})
                with Horizontal(classes="scores-row"):
                    yield Static(self._short_name(model), classes="scores-model")
                    for benchmark in benchmarks:
                        score = model_scores.get(benchmark)
                        if score is None:
                            yield Static("[#6272A4]--[/]", classes="scores-cell score-pending")
                            continue
                        yield Static(f"[#50FA7B]{score:.2f}[/]", classes="scores-cell")

    def on_click(self, event) -> None:
        """Handle click on close button."""
        for widget in event.widget.ancestors_with_self:
            if getattr(widget, "id", None) == "close-x":
                self.dismiss(None)
                return
