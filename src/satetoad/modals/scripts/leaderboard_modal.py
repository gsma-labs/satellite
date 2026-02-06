"""LeaderboardModal - Modal for viewing evaluation results from HuggingFace.

This modal fetches and displays the GSMA/leaderboard dataset from HuggingFace,
showing model rankings with TCI and individual benchmark scores.
"""

from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, Center
from textual.screen import ModalScreen
from textual.widgets import Button, Static, DataTable, LoadingIndicator

from satetoad.services.evals import BENCHMARKS_BY_ID
from satetoad.services.leaderboard import (
    LeaderboardEntry,
    fetch_leaderboard,
)


class LeaderboardModal(ModalScreen[None]):
    """Modal for viewing evaluation results and leaderboard from HuggingFace.

    Returns None on close (view-only modal).

    Layout:
    +------------------------------------------------------------------+
    |                      Preview Leaderboard                          |
    +------------------------------------------------------------------+
    | #  | Model              | Provider | TCI  | QnA | Logs | Math |..|
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

    def __init__(self) -> None:
        """Initialize the modal."""
        super().__init__()
        self._entries: list[LeaderboardEntry] = []
        self._error: str | None = None

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="container"):
            yield Static("Preview Leaderboard", classes="modal-title")

            # Loading state
            with Center(id="loading-container"):
                yield LoadingIndicator(id="loading")
                yield Static("Loading leaderboard...", id="loading-text")

            # Error state (hidden by default)
            yield Static("", id="error-text", classes="error-text")

            # Results table (hidden during loading)
            table = DataTable(id="results-table", classes="results-table")
            yield table

            # Close button
            with Horizontal(id="buttons"):
                yield Button("Close", id="close-btn", variant="primary")

    def on_mount(self) -> None:
        """Load leaderboard data when modal is mounted."""
        self._load_leaderboard()

    @work(exclusive=True, thread=True)
    def _load_leaderboard(self) -> None:
        """Fetch leaderboard data from HuggingFace in background thread."""
        try:
            entries = fetch_leaderboard()
            self.app.call_from_thread(self._show_leaderboard, entries)
        except Exception as e:
            self.app.call_from_thread(self._show_error, str(e))

    def _show_leaderboard(self, entries: list[LeaderboardEntry]) -> None:
        """Display the leaderboard data in the table."""
        self._entries = entries
        self._error = None

        # Hide loading, show table
        self.query_one("#loading-container").display = False
        self.query_one("#error-text").display = False
        table = self.query_one("#results-table", DataTable)
        table.display = True

        # Set up fixed columns
        table.clear(columns=True)
        table.add_column("#", key="rank", width=4)
        table.add_column("Model", key="model", width=22)
        table.add_column("Provider", key="provider", width=12)
        table.add_column("TCI", key="tci", width=7)

        # Add dynamic eval columns from registry
        for benchmark in BENCHMARKS_BY_ID.values():
            table.add_column(benchmark.short_name, key=benchmark.id, width=7)

        # Add rows with dynamic scores
        for rank, entry in enumerate(entries, start=1):
            row_data = [
                str(rank),
                entry.model,
                entry.provider,
                self._format_score(entry.tci),
            ]
            for benchmark in BENCHMARKS_BY_ID.values():
                row_data.append(self._format_score(entry.scores.get(benchmark.id)))
            table.add_row(*row_data)

        # Enable cursor navigation
        table.cursor_type = "row"
        table.zebra_stripes = True

    def _format_score(self, score: float | None) -> str:
        """Format a score for display."""
        if score is None:
            return "--"
        return f"{score:.1f}"

    def _show_error(self, message: str) -> None:
        """Display an error message."""
        self._error = message

        # Hide loading, show error
        self.query_one("#loading-container").display = False
        self.query_one("#results-table").display = False

        error_widget = self.query_one("#error-text", Static)
        error_widget.update(f"{message}\n\nPress 'r' to retry.")
        error_widget.display = True

    def action_retry(self) -> None:
        """Retry loading the leaderboard."""
        if self._error:
            # Show loading again
            self.query_one("#loading-container").display = True
            self.query_one("#error-text").display = False
            self._load_leaderboard()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "close-btn":
            self.dismiss(None)

    def action_close(self) -> None:
        """Close the modal (triggered by Escape key)."""
        self.dismiss(None)
