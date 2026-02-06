"""EnvVarItem widget for displaying environment variables.

Shows a single env var with name, masked value, and delete button.
Used in the EnvVarsModal for managing .env variables.
"""

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Button, Label, Static


def _mask_value(value: str, visible_chars: int = 4) -> str:
    """Mask a sensitive value, showing only the last few characters.

    Args:
        value: The value to mask
        visible_chars: Number of characters to show at the end

    Returns:
        Masked string like "***abc123"
    """
    if len(value) <= visible_chars:
        return "*" * len(value)
    return "***" + value[-visible_chars:]


class EnvVarItem(Static):
    """A single environment variable entry in the list.

    Displays variable name, masked value, and delete button.
    Posts EditRequested when clicked, DeleteRequested when delete pressed.
    """

    DEFAULT_CSS = """
    EnvVarItem {
        layout: horizontal;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: $surface;
    }

    EnvVarItem:hover {
        background: $surface-lighten-1;
    }

    EnvVarItem .var-name {
        width: 1fr;
        color: $text;
        text-style: bold;
    }

    EnvVarItem .var-value {
        width: 1fr;
        color: $text-muted;
    }

    EnvVarItem .delete-btn {
        min-width: 3;
        background: transparent;
        color: $error;
        border: none;
    }

    EnvVarItem .delete-btn:hover {
        background: $error 20%;
    }
    """

    class DeleteRequested(Message):
        """Posted when user clicks delete on a variable."""

        def __init__(self, var_name: str) -> None:
            self.var_name = var_name
            super().__init__()

    class EditRequested(Message):
        """Posted when user clicks on the item to edit."""

        def __init__(self, var_name: str, var_value: str) -> None:
            self.var_name = var_name
            self.var_value = var_value
            super().__init__()

    def __init__(self, var_name: str, var_value: str) -> None:
        """Initialize env var item.

        Args:
            var_name: Variable name (e.g., "OPENAI_API_KEY")
            var_value: Variable value (will be masked in display)
        """
        super().__init__()
        self._var_name = var_name
        self._var_value = var_value

    def compose(self) -> ComposeResult:
        """Compose the item layout."""
        yield Label(self._var_name, classes="var-name")
        yield Label(_mask_value(self._var_value), classes="var-value")
        # Sanitize ID: replace any non-alphanumeric chars with dash
        sanitized_id = "".join(
            c if c.isalnum() else "-" for c in self._var_name
        )
        yield Button("x", classes="delete-btn", id=f"delete-{sanitized_id}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle delete button click."""
        if event.button.has_class("delete-btn"):
            event.stop()
            self.post_message(self.DeleteRequested(self._var_name))

    def on_click(self) -> None:
        """Handle click on the item for editing."""
        self.post_message(self.EditRequested(self._var_name, self._var_value))
