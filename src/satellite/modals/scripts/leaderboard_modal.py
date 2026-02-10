"""LeaderboardModal - Modal for viewing evaluation results from HuggingFace."""

from typing import ClassVar

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static, DataTable, LoadingIndicator

from satellite.services.evals import BENCHMARKS_BY_ID, JobManager
from satellite.services.leaderboard import (
    LeaderboardEntry,
    collect_local_entries,
    fetch_leaderboard,
    merge_leaderboard,
)

LOCAL_ROW_STYLE = "bold #F1FA8C"


class LeaderboardModal(ModalScreen[None]):
    """Modal for viewing evaluation results and leaderboard from HuggingFace.

    Returns None on close (view-only modal).

    Layout:
    +------------------------------------------------------------------+
    |                      Preview Leaderboard                          |
    +------------------------------------------------------------------+
    | #  | Model              | Provider | Avg  | QnA | Logs | Math |..|
    |----|--------------------+----------+------+-----+------+------|..|
    | 1  | gpt-4o             | OpenAI   | 78.5 | 82  | 75   | 80   |..|
    | 2  | claude-3-opus      | Anthropic| 76.2 | 80  | 74   | 78   |..|
    | ...                                                              |
    +------------------------------------------------------------------+
    |                                                        [Close]   |
    +------------------------------------------------------------------+
    """

    CSS_PATH = "../styles/modal_base.tcss"

    DEFAULT_CSS = """
    LeaderboardModal {
        align: center middle;
        background: black 50%;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close", "Close", show=False),
        Binding("r", "retry", "Retry", show=False),
    ]

    def __init__(self, job_manager: JobManager | None = None) -> None:
        super().__init__()
        self._job_manager = job_manager
        self._error: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="container"):
            yield Static("Preview Leaderboard", classes="modal-title")

            with Center(id="loading-container"):
                yield LoadingIndicator(id="loading")
                yield Static("Loading leaderboard...", id="loading-text")

            yield Static("", id="error-text", classes="error-text")
            yield DataTable(id="results-table", classes="results-table")

            with Horizontal(id="buttons"):
                yield Button("Close", id="close-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#container").styles.opacity = 1.0
        self._load_leaderboard()

    @work(exclusive=True, thread=True)
    def _load_leaderboard(self) -> None:
        try:
            remote = fetch_leaderboard()
            local = (
                collect_local_entries(self._job_manager) if self._job_manager else []
            )
            entries = merge_leaderboard(remote, local)
            self.app.call_from_thread(self._show_leaderboard, entries)
        except (ConnectionError, TimeoutError, OSError) as e:
            self.app.call_from_thread(self._show_error, str(e))

    def _show_leaderboard(self, entries: list[LeaderboardEntry]) -> None:
        if not self.is_mounted:
            return
        self._error = None

        self.query_one("#loading-container").display = False
        self.query_one("#error-text").display = False
        table = self.query_one("#results-table", DataTable)
        table.display = True

        table.clear(columns=True)
        table.add_column("#", key="rank", width=4)
        table.add_column("Model", key="model", width=22)
        table.add_column("Provider", key="provider", width=12)
        table.add_column("Avg", key="avg_score", width=7)

        for benchmark in BENCHMARKS_BY_ID.values():
            table.add_column(benchmark.short_name, key=benchmark.id, width=7)

        for rank, entry in enumerate(entries, start=1):
            cells = self._build_row_cells(rank, entry)
            if entry.is_local:
                cells = [Text(c, style=LOCAL_ROW_STYLE) for c in cells]
            table.add_row(*cells)

        table.cursor_type = "row"
        table.zebra_stripes = True

    def _build_row_cells(self, rank: int, entry: LeaderboardEntry) -> list[str]:
        cells = [
            str(rank),
            entry.model,
            entry.provider,
            self._format_score(entry.avg_score),
        ]
        for benchmark in BENCHMARKS_BY_ID.values():
            cells.append(self._format_score(entry.scores.get(benchmark.id)))
        return cells

    def _format_score(self, score: float | None) -> str:
        if score is None:
            return "--"
        return f"{score:.1f}"

    def _show_error(self, message: str) -> None:
        if not self.is_mounted:
            return
        self._error = message

        self.query_one("#loading-container").display = False
        self.query_one("#results-table").display = False

        error_widget = self.query_one("#error-text", Static)
        error_widget.update(f"{message}\n\nPress 'r' to retry.")
        error_widget.display = True

    def action_retry(self) -> None:
        if not self._error:
            return
        self.query_one("#loading-container").display = True
        self.query_one("#error-text").display = False
        self._load_leaderboard()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
