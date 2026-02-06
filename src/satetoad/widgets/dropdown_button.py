"""DropdownButton - A button that shows a dropdown list when clicked.

Reusable widget for displaying a list of items in a popup above the button.
The dropdown is read-only (no selection action) and closes on blur/ESC/X.

Pattern copied from Toad's ModeSwitcher/Select overlay behavior.
"""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static


class _DropdownList(Vertical, can_focus=True):
    """Focusable dropdown list that hides on blur via CSS."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close", "Close", show=False),
    ]

    DEFAULT_CSS = """
    _DropdownList {
        display: none;
        width: auto;
        height: auto;
        background: #1E1F29;
        border: solid #BD93F9 30%;
        padding: 0 1;
        overlay: screen;
        constrain: inside inflect;
    }

    _DropdownList:focus {
        display: block;
    }

    _DropdownList:blur {
        display: none;
    }

    _DropdownList .dropdown-header {
        width: 100%;
        height: auto;
        border-bottom: solid #BD93F9 30%;
        margin-bottom: 0;
    }

    _DropdownList .dropdown-title {
        width: 1fr;
        color: #F8F8F2;
        text-style: bold;
    }

    _DropdownList .dropdown-close {
        width: 3;
        text-align: center;
        color: #faf9f5 60%;
    }

    _DropdownList .dropdown-close:hover {
        color: #FF5555;
    }
    """

    def action_close(self) -> None:
        """Close the dropdown by removing focus."""
        self.blur()

    def on_click(self, event) -> None:
        """Handle click on close button."""
        for widget in event.widget.ancestors_with_self:
            if getattr(widget, "classes", None) and "dropdown-close" in widget.classes:
                self.blur()
                return


class DropdownButton(Vertical):
    """A button with a dropdown list that appears above it.

    The dropdown shows when the button is clicked and hides on blur.
    """

    DEFAULT_CSS = """
    DropdownButton {
        width: auto;
        height: auto;
        border: none;
    }

    DropdownButton:focus-within {
        border: none;
    }

    DropdownButton .dropdown-item {
        width: auto;
        height: auto;
        padding: 0 1;
        color: #F8F8F2;
    }

    DropdownButton .dropdown-trigger {
        width: auto;
        min-width: 16;
        background: #44475A 30%;
        border: tall #BD93F9 30%;
        color: #F8F8F2;
    }

    DropdownButton .dropdown-trigger:hover {
        background: #44475A 50%;
    }

    DropdownButton .dropdown-trigger:focus {
        border: tall #BD93F9;
    }
    """

    def __init__(
        self,
        label: str,
        items: list[str],
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the dropdown button.

        Args:
            label: The button label (shown with triangle indicator)
            items: List of strings to display in the dropdown
            name: Optional name for the widget
            id: Optional ID for the widget
            classes: Optional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._label = label
        self._items = items

    def compose(self) -> ComposeResult:
        """Compose the dropdown layout."""
        with _DropdownList(classes="dropdown-list"):
            with Horizontal(classes="dropdown-header"):
                yield Static(self._label, classes="dropdown-title")
                yield Static("x", classes="dropdown-close")
            for item in self._items:
                yield Static(item, classes="dropdown-item")
        yield Button(f"{self._label}  ▼", classes="dropdown-trigger")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Open dropdown on button press by focusing the list."""
        if event.button.has_class("dropdown-trigger"):
            event.stop()
            self.query_one(".dropdown-list").focus()

    def update_items(self, items: list[str]) -> None:
        """Update the dropdown items.

        Args:
            items: New list of strings to display
        """
        self._items = items
        dropdown_list = self.query_one(".dropdown-list", _DropdownList)
        dropdown_list.remove_children()
        for item in items:
            dropdown_list.mount(Static(item, classes="dropdown-item"))
