"""EvalsContainer widget - expandable container for Evals options.

Displays an EvalBox-style header that expands to show sub-options
like "Run evaluations" and "View progress" with badge support.

PATTERN: Inline collapsible expansion
"""

from textual.app import ComposeResult
from textual.containers import VerticalGroup
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Digits, Label, Static

from satetoad.widgets.badge_label import BadgeLabel
from satetoad.widgets.eval_sub_option import EvalSubOption


class EvalsContainer(VerticalGroup):
    """Expandable container for Evals sub-options.

    Collapsed:
    +-------------------------------+
    |  2  | Evals              [1]  |
    |     | Select and run evals    |
    +-------------------------------+

    Expanded:
    +-------------------------------+
    |  2  | Evals              [1]  |
    |     | Select and run evals    |
    |     ├─ Run evaluations        |
    |     └─ View progress    [1]   |
    +-------------------------------+
    """

    DEFAULT_CSS = """
    EvalsContainer {
        width: 1fr;
        height: auto;
        min-height: 3;
        border: tall #6272A4 30%;
        padding: 0 1;
        background: #282A36 90%;

        &:hover {
            background: #44475A;
        }

        &.-highlight {
            background: #44475A;
            border: tall #BD93F9;
        }

        &.-expanded {
            border: tall #BD93F9;
        }

        #header {
            width: 1fr;
            height: auto;
        }

        #header-row {
            width: 1fr;
            height: auto;
            layout: horizontal;
        }

        #header-content {
            width: 1fr;
        }

        #name {
            text-style: bold;
            color: #F8F8F2;
        }

        #description {
            color: #faf9f5 60%;
            text-wrap: nowrap;
            text-overflow: ellipsis;
        }

        Digits {
            width: 4;
            padding: 0 1 0 0;
            color: #50FA7B;
        }

        #sub-options {
            display: none;
            width: 1fr;
            height: auto;
            padding: 0 0 0 4;
        }

        &.-expanded #sub-options {
            display: block;
        }
    }
    """

    expanded: reactive[bool] = reactive(False)
    pending_jobs: reactive[int] = reactive(0)

    class SubOptionSelected(Message):
        """Posted when a sub-option is selected."""

        def __init__(self, option_id: str) -> None:
            super().__init__()
            self.option_id = option_id

    def __init__(
        self,
        digit: str = "2",
        name: str = "Evals",
        description: str = "Select and run evaluations",
        box_id: str = "evals",
        pending_jobs: int = 0,
    ) -> None:
        """Initialize the Evals container.

        Args:
            digit: Shortcut digit to display
            name: Container name
            description: Container description
            box_id: Container identifier
            pending_jobs: Initial pending job count
        """
        super().__init__()
        self._digit = digit
        self._name = name
        self._description = description
        self._box_id = box_id
        self._initial_pending = pending_jobs

    @property
    def box_id(self) -> str:
        """Return the container identifier."""
        return self._box_id

    def compose(self) -> ComposeResult:
        """Compose the container layout."""
        # Header section (like EvalBox)
        with VerticalGroup(id="header"):
            with Static(id="header-row"):
                yield Digits(self._digit)
                with VerticalGroup(id="header-content"):
                    yield Label(self._name, id="name")
                    yield Static(self._description, id="description")
                yield BadgeLabel(count=self._initial_pending, id="header-badge")

        # Sub-options section (hidden until expanded)
        with VerticalGroup(id="sub-options"):
            yield EvalSubOption(
                name="Run evaluations",
                option_id="run-evals",
                prefix="├─",
                show_badge=False,
                widget_id="opt-run-evals",
            )
            yield EvalSubOption(
                name="View progress",
                option_id="view-progress",
                prefix="└─",
                show_badge=True,
                badge_count=self._initial_pending,
                widget_id="opt-view-progress",
            )

    def on_mount(self) -> None:
        """Initialize after mounting."""
        self.pending_jobs = self._initial_pending

    def watch_expanded(self, expanded: bool) -> None:
        """React to expansion state changes."""
        if expanded:
            self.add_class("-expanded")
        else:
            self.remove_class("-expanded")

    def watch_pending_jobs(self, count: int) -> None:
        """React to pending job count changes."""
        # Update header badge
        try:
            header_badge = self.query_one("#header-badge", BadgeLabel)
            header_badge.count = count
        except Exception:
            pass

        # Update view progress badge
        try:
            view_progress = self.query_one("#opt-view-progress", EvalSubOption)
            view_progress.set_badge_count(count)
        except Exception:
            pass

    def toggle_expanded(self) -> None:
        """Toggle the expanded state."""
        self.expanded = not self.expanded

    def on_eval_sub_option_selected(self, event: EvalSubOption.Selected) -> None:
        """Handle sub-option selection - bubble up as our message."""
        event.stop()
        self.post_message(self.SubOptionSelected(event.option_id))

    def on_click(self) -> None:
        """Handle click - toggle expansion."""
        self.toggle_expanded()

    def increment_pending(self, amount: int = 1) -> None:
        """Increment the pending jobs count.

        Args:
            amount: Amount to add (default 1)
        """
        self.pending_jobs += amount

    def decrement_pending(self, amount: int = 1) -> None:
        """Decrement the pending jobs count.

        Args:
            amount: Amount to subtract (default 1)
        """
        self.pending_jobs = max(0, self.pending_jobs - amount)
