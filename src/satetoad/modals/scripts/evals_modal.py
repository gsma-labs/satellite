"""EvalsModal - Modal for selecting evaluation actions.

Displays two options:
- Run evaluations: Opens the benchmark selection modal
- View progress: Opens the job list modal
"""

from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, HorizontalGroup
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Label

from satetoad.widgets.badge_label import BadgeLabel


class EvalsOptionItem(HorizontalGroup):
    """Single option row in the evals modal.

    Layout:
    +----------------------------------------+
    | ► Run evaluations                      |
    +----------------------------------------+
    """

    DEFAULT_CSS = """
    EvalsOptionItem {
        width: 1fr;
        height: auto;
        min-height: 2;
        padding: 0 2;

        &:hover {
            background: #44475A;
        }

        &.-highlight {
            background: #44475A;
        }

        #cursor {
            width: 2;
            color: #BD93F9;
        }

        #name {
            width: 1fr;
            text-style: bold;
            color: #F8F8F2;
        }

        #description {
            color: #faf9f5 60%;
        }
    }
    """

    class Selected(Message):
        """Posted when this option is selected."""

        def __init__(self, option_id: str) -> None:
            super().__init__()
            self.option_id = option_id

    def __init__(
        self,
        name: str,
        description: str,
        option_id: str,
        show_badge: bool = False,
        badge_count: int = 0,
    ) -> None:
        """Initialize the option item.

        Args:
            name: Display name
            description: Description text
            option_id: Identifier for this option
            show_badge: Whether to show a badge
            badge_count: Initial badge count
        """
        super().__init__()
        self._name = name
        self._description = description
        self._option_id = option_id
        self._show_badge = show_badge
        self._badge_count = badge_count
        self.can_focus = True

    @property
    def option_id(self) -> str:
        """Return the option identifier."""
        return self._option_id

    def compose(self) -> ComposeResult:
        """Compose the option item layout."""
        yield Static("►", id="cursor")
        with Vertical():
            with HorizontalGroup():
                yield Label(self._name, id="name")
                if self._show_badge:
                    yield BadgeLabel(count=self._badge_count, id="badge")
            yield Static(self._description, id="description")

    def get_badge(self) -> BadgeLabel | None:
        """Get the badge widget if it exists."""
        try:
            return self.query_one("#badge", BadgeLabel)
        except Exception:
            return None

    def set_badge_count(self, count: int) -> None:
        """Update the badge count."""
        badge = self.get_badge()
        if badge:
            badge.count = count

    def on_click(self) -> None:
        """Handle click - select this option."""
        self.post_message(self.Selected(self._option_id))

    def on_key(self, event: events.Key) -> None:
        """Handle key press - Enter selects."""
        if event.key in ("enter", "space"):
            event.stop()
            self.post_message(self.Selected(self._option_id))


class EvalsModal(ModalScreen[str | None]):
    """Modal for selecting evaluation actions.

    Returns the selected option ID, or None if cancelled.

    Layout:
    ╭─────────────────────────────────────╮
    │              Evals                  │
    ├─────────────────────────────────────┤
    │  ► Run evaluations                  │
    │    Select and run benchmarks        │
    │                                     │
    │    View progress              [1]   │
    │    Monitor running jobs             │
    │                                     │
    │              [Cancel]               │
    ╰─────────────────────────────────────╯
    """

    CSS_PATH = "../styles/modal_base.tcss"

    DEFAULT_CSS = """
    EvalsModal {
        align: center middle;
        background: black 50%;
    }

    EvalsModal #container {
        min-width: 45;
        max-width: 55;
    }

    EvalsModal #options-list {
        height: auto;
        padding: 1 0;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("tab", "app.focus_next", "Focus Next", show=False),
        Binding("shift+tab", "app.focus_previous", "Focus Previous", show=False),
    ]

    highlighted: reactive[int] = reactive(0)

    def __init__(self, pending_jobs: int = 0) -> None:
        """Initialize the modal.

        Args:
            pending_jobs: Number of pending/running jobs for badge
        """
        super().__init__()
        self._pending_jobs = pending_jobs

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="container"):
            yield Static("Evals", classes="modal-title")

            with Vertical(id="options-list"):
                yield EvalsOptionItem(
                    name="Run evaluations",
                    description="Select and run benchmarks",
                    option_id="run-evals",
                    show_badge=False,
                )
                yield EvalsOptionItem(
                    name="View progress",
                    description="Monitor running jobs",
                    option_id="view-progress",
                    show_badge=True,
                    badge_count=self._pending_jobs,
                )

            with HorizontalGroup(id="buttons"):
                yield Button("Cancel", id="cancel-btn", variant="default")

    def on_mount(self) -> None:
        """Focus first option."""
        self._update_highlight()

    def _update_highlight(self) -> None:
        """Update the highlight on options."""
        items = list(self.query(EvalsOptionItem))
        for i, item in enumerate(items):
            if i == self.highlighted:
                item.add_class("-highlight")
                item.query_one("#cursor").update("►")
            else:
                item.remove_class("-highlight")
                item.query_one("#cursor").update(" ")

    def watch_highlighted(self, value: int) -> None:
        """React to highlight changes."""
        self._update_highlight()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss(None)

    def on_evals_option_item_selected(self, event: EvalsOptionItem.Selected) -> None:
        """Handle option selection."""
        event.stop()
        self.dismiss(event.option_id)

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard navigation."""
        if event.key in ("down", "j"):
            self.highlighted = min(self.highlighted + 1, 1)
            event.stop()
        elif event.key in ("up", "k"):
            self.highlighted = max(self.highlighted - 1, 0)
            event.stop()
        elif event.key in ("enter", "space"):
            options = ["run-evals", "view-progress"]
            self.dismiss(options[self.highlighted])
            event.stop()

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)
