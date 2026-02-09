"""Checklist item widget with animated status indicator."""

from textual.app import ComposeResult
from textual.containers import HorizontalGroup
from textual.reactive import var
from textual.widgets import Label, Static


class ChecklistItem(HorizontalGroup):
    """Checklist item with status indicator.

    States:
        pending: ○ (empty circle)
        in_progress: ◐ (half circle)
        completed: ● (filled circle)
        error: ✕ (cross)

    Usage:
        yield ChecklistItem("Checking model connectivity...", id="check-1")

        # Change state:
        self.query_one("#check-1", ChecklistItem).status = "in_progress"
    """

    DEFAULT_CSS = """
    ChecklistItem {
        height: 1;
        padding: 0 1;

        #status { width: 2; }
        #label { width: 1fr; }

        &.-in_progress #status { color: $warning; }
        &.-completed #status { color: $success; }
        &.-error #status { color: $error; }
    }
    """

    SYMBOLS = {
        "pending": "○",
        "in_progress": "◐",
        "completed": "●",
        "error": "✕",
    }

    status: var[str] = var("pending")

    def __init__(self, label: str, id: str | None = None) -> None:
        super().__init__(id=id)
        self._label = label

    def compose(self) -> ComposeResult:
        yield Static("○", id="status")
        yield Label(self._label, id="label")

    def watch_status(self, status: str) -> None:
        self.query_one("#status", Static).update(self.SYMBOLS.get(status, "○"))
        for state in ("in_progress", "completed", "error"):
            self.set_class(status == state, f"-{state}")
