"""TabItem - Single tab in a tab header.

Follows the EvalsOptionItem pattern with click handling and messages.
"""

from textual import events
from textual.app import ComposeResult
from textual.containers import HorizontalGroup
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, Static


class TabItem(HorizontalGroup):
    """Single clickable tab in the header row.

    Layout:
    +---------------------------+
    | [label]        [x]        |
    +---------------------------+

    The close button only appears when closable=True.
    """

    DEFAULT_CSS = """
    TabItem {
        width: 1fr;
        height: auto;
        padding: 0 2;
        margin: 0;
        background: transparent;
        color: #faf9f5 60%;
        border: tall black 20%;
        content-align: center middle;
        transition: border 250ms in_out_cubic, color 250ms in_out_cubic;

        &:hover {
            background: #BD93F9 10%;
            color: #F8F8F2;
            border: tall #BD93F9;
        }

        &.-active {
            background: #BD93F9 30%;
            color: #F8F8F2;
            border: tall #BD93F9;
        }

        #label {
            text-style: bold;
            text-align: center;
            width: 100%;
        }

        #close-btn {
            width: 3;
            color: #faf9f5 60%;
            display: none;
        }

        &.-closable #close-btn {
            display: block;
        }

        &.-closable #close-btn:hover {
            color: #FF5555;
        }
    }
    """

    class Activated(Message):
        """Posted when this tab is clicked/activated."""

        def __init__(self, tab_id: str) -> None:
            super().__init__()
            self.tab_id = tab_id

    class CloseRequested(Message):
        """Posted when close button is clicked on a closable tab."""

        def __init__(self, tab_id: str) -> None:
            super().__init__()
            self.tab_id = tab_id

    active: reactive[bool] = reactive(False)

    def __init__(
        self,
        label: str,
        tab_id: str,
        closable: bool = False,
        **kwargs,
    ) -> None:
        """Initialize the tab item.

        Args:
            label: Display text for the tab
            tab_id: Unique identifier for this tab
            closable: Whether to show close button
        """
        super().__init__(**kwargs)
        self._label = label
        self._tab_id = tab_id
        self._closable = closable
        self.can_focus = True

        if closable:
            self.add_class("-closable")

    @property
    def tab_id(self) -> str:
        """Return the tab identifier."""
        return self._tab_id

    @property
    def label(self) -> str:
        """Return the tab label."""
        return self._label

    def compose(self) -> ComposeResult:
        """Compose the tab item layout."""
        yield Label(self._label, id="label")
        yield Static(" x", id="close-btn")

    def watch_active(self, value: bool) -> None:
        """React to active state changes."""
        self.set_class(value, "-active")

    def on_key(self, event: events.Key) -> None:
        """Handle key press - Enter activates, Delete/Backspace closes."""
        if event.key in ("enter", "space"):
            event.stop()
            self.post_message(self.Activated(self._tab_id))
            return
        if event.key in ("delete", "backspace") and self._closable:
            event.stop()
            self.post_message(self.CloseRequested(self._tab_id))
