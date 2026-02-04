"""EvalSubOption widget - sub-option row inside EvalsContainer.

Displays a single option like "Run evaluations" or "View progress"
with optional badge support.

PATTERN: Simplified EvalBox without digit, with optional badge
"""

from textual.app import ComposeResult
from textual.containers import HorizontalGroup
from textual.message import Message
from textual.widgets import Label, Static

from satetoad.widgets.badge_label import BadgeLabel


class EvalSubOption(HorizontalGroup):
    """Sub-option row for the Evals container.

    Layout:
    +--------------------------------+
    | ├─ Run evaluations             |
    +--------------------------------+
    | └─ View progress         [3]   |
    +--------------------------------+

    Emits Selected message when clicked or Enter pressed.
    """

    DEFAULT_CSS = """
    EvalSubOption {
        width: 1fr;
        height: auto;
        padding: 0 1 0 3;
        margin: 0;

        &:hover {
            background: #44475A 50%;
        }

        &.-highlight {
            background: #44475A;
        }

        &:focus {
            background: #44475A;
        }

        #prefix {
            width: 3;
            color: #faf9f5 60%;
        }

        #name {
            width: 1fr;
            color: #F8F8F2;
        }
    }
    """

    class Selected(Message):
        """Posted when the sub-option is selected."""

        def __init__(self, option_id: str) -> None:
            super().__init__()
            self.option_id = option_id

    def __init__(
        self,
        name: str,
        option_id: str,
        prefix: str = "├─",
        show_badge: bool = False,
        badge_count: int = 0,
        widget_id: str | None = None,
    ) -> None:
        """Initialize the sub-option.

        Args:
            name: Display name (e.g., "Run evaluations")
            option_id: Identifier for this option
            prefix: Tree prefix character (├─ or └─)
            show_badge: Whether to show a badge
            badge_count: Initial badge count
            widget_id: Widget ID
        """
        super().__init__(id=widget_id)
        self._name = name
        self._option_id = option_id
        self._prefix = prefix
        self._show_badge = show_badge
        self._badge_count = badge_count
        self.can_focus = True

    @property
    def option_id(self) -> str:
        """Return the option identifier."""
        return self._option_id

    def compose(self) -> ComposeResult:
        """Compose the sub-option layout."""
        yield Static(self._prefix, id="prefix")
        yield Label(self._name, id="name")
        if self._show_badge:
            yield BadgeLabel(count=self._badge_count, id="badge")

    def get_badge(self) -> BadgeLabel | None:
        """Get the badge widget if it exists."""
        try:
            return self.query_one("#badge", BadgeLabel)
        except Exception:
            return None

    def set_badge_count(self, count: int) -> None:
        """Update the badge count.

        Args:
            count: New count to display
        """
        badge = self.get_badge()
        if badge:
            badge.count = count

    def increment_badge(self, amount: int = 1) -> None:
        """Increment the badge count.

        Args:
            amount: Amount to add (default 1)
        """
        badge = self.get_badge()
        if badge:
            badge.increment(amount)

    def on_click(self) -> None:
        """Handle click - post Selected message."""
        self.post_message(self.Selected(self._option_id))

    def on_key(self, event) -> None:
        """Handle key press - Enter/Space triggers selection."""
        if event.key in ("enter", "space"):
            event.stop()
            self.post_message(self.Selected(self._option_id))
