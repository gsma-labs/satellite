"""EnvVarsModal - Modal for managing environment variables.

Provides full CRUD for .env file variables:
- View all configured env vars (masked values)
- Add new variables
- Edit existing variables (click to populate form)
- Delete variables

Press "c" from main screen to open.
"""

import re
from typing import TYPE_CHECKING, ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, HorizontalGroup, VerticalGroup, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from satetoad.widgets.env_var_item import EnvVarItem

if TYPE_CHECKING:
    from satetoad.services.config import EnvConfigManager


class EnvVarsModal(ModalScreen[bool]):
    """Modal for managing environment variables.

    Returns True if any changes were made, False otherwise.

    Keyboard Navigation:
    - Tab/Shift+Tab: Navigate between fields
    - Enter: Add/Update variable
    - Escape: Close modal
    """

    CSS_PATH = "../styles/env_vars_modal.tcss"

    DEFAULT_CSS = """
    EnvVarsModal {
        align: center middle;
        background: black 50%;
    }
    """

    AUTO_FOCUS = "#var-name-input"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close", "Close", show=False),
        Binding("tab", "app.focus_next", "Focus Next", show=False),
        Binding("shift+tab", "app.focus_previous", "Focus Previous", show=False),
    ]

    def __init__(self, env_manager: "EnvConfigManager") -> None:
        """Initialize the modal.

        Args:
            env_manager: EnvConfigManager instance for .env operations
        """
        super().__init__()
        self._env_manager = env_manager
        self._editing_var: str | None = None  # Track which var is being edited
        self._changes_made = False

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with VerticalGroup(id="container"):
            yield Static("Environment Variables", classes="modal-title")

            # List of configured variables
            with VerticalScroll(id="vars-list"):
                env_vars = self._env_manager.get_all_vars()
                if not env_vars:
                    yield Static("No variables configured", classes="empty-message")
                else:
                    for name, value in sorted(env_vars.items()):
                        yield EnvVarItem(name, value)

            # Add/Edit form
            yield Static("Add Variable", id="form-title", classes="section-title")

            with Horizontal(classes="form-row"):
                yield Label("Name:", classes="form-label")
                yield Input(
                    placeholder="VARIABLE_NAME",
                    id="var-name-input",
                )

            with Horizontal(classes="form-row"):
                yield Label("Value:", classes="form-label")
                yield Input(
                    placeholder="value",
                    password=True,
                    id="var-value-input",
                )

            # Buttons
            with HorizontalGroup(id="buttons"):
                yield Button("Close", id="close-btn")
                yield Button("Add", id="add-btn")

    def _refresh_list(self) -> None:
        """Refresh the variables list from .env."""
        vars_list = self.query_one("#vars-list", VerticalScroll)

        # Remove all children
        for child in list(vars_list.children):
            child.remove()

        # Re-populate
        env_vars = self._env_manager.get_all_vars()
        if not env_vars:
            vars_list.mount(Static("No variables configured", classes="empty-message"))
        else:
            for name, value in sorted(env_vars.items()):
                vars_list.mount(EnvVarItem(name, value))

    def _clear_form(self) -> None:
        """Clear the form inputs and reset to add mode."""
        self.query_one("#var-name-input", Input).value = ""
        self.query_one("#var-value-input", Input).value = ""
        self.query_one("#form-title", Static).update("Add Variable")
        self.query_one("#add-btn", Button).label = "Add"
        self.query_one("#var-name-input", Input).disabled = False
        self._editing_var = None

    def _validate_var_name(self, name: str) -> bool:
        """Validate environment variable name.

        Args:
            name: Variable name to validate

        Returns:
            True if valid, False otherwise
        """
        if not name:
            self.notify("Variable name is required", severity="error")
            return False

        # Must start with letter or underscore, contain only alphanumeric and underscore
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            self.notify(
                "Invalid name: must start with letter/underscore, contain only letters/numbers/underscores",
                severity="error",
            )
            return False

        return True

    def _add_or_update_var(self) -> None:
        """Add a new variable or update existing one."""
        name_input = self.query_one("#var-name-input", Input)
        value_input = self.query_one("#var-value-input", Input)

        name = name_input.value.strip().upper()  # Env vars are conventionally uppercase
        value = value_input.value

        if not self._validate_var_name(name):
            name_input.focus()
            return

        if not value:
            self.notify("Variable value is required", severity="error")
            value_input.focus()
            return

        # Set the variable (silent replacement if exists)
        self._env_manager.set_var(name, value)
        self._changes_made = True

        if self._editing_var:
            self.notify(f"Updated {name}", severity="information")
        else:
            self.notify(f"Added {name}", severity="information")

        self._clear_form()
        self._refresh_list()
        name_input.focus()

    @on(Button.Pressed, "#add-btn")
    def on_add_pressed(self, event: Button.Pressed) -> None:
        """Handle Add/Update button press."""
        event.stop()
        self._add_or_update_var()

    @on(Button.Pressed, "#close-btn")
    def on_close_pressed(self, event: Button.Pressed) -> None:
        """Handle Close button press."""
        event.stop()
        self.dismiss(self._changes_made)

    def action_close(self) -> None:
        """Close the modal (Escape key)."""
        self.dismiss(self._changes_made)

    @on(EnvVarItem.DeleteRequested)
    def on_delete_requested(self, event: EnvVarItem.DeleteRequested) -> None:
        """Handle delete request from an item."""
        event.stop()
        if self._env_manager.delete_var(event.var_name):
            self._changes_made = True
            self.notify(f"Deleted {event.var_name}", severity="information")
            self._refresh_list()

            # If we were editing this var, clear the form
            if self._editing_var == event.var_name:
                self._clear_form()

    @on(EnvVarItem.EditRequested)
    def on_edit_requested(self, event: EnvVarItem.EditRequested) -> None:
        """Handle edit request - populate form with existing values."""
        event.stop()
        self._editing_var = event.var_name

        name_input = self.query_one("#var-name-input", Input)
        value_input = self.query_one("#var-value-input", Input)

        name_input.value = event.var_name
        name_input.disabled = True  # Can't change name while editing
        value_input.value = event.var_value
        value_input.focus()

        self.query_one("#form-title", Static).update(f"Edit: {event.var_name}")
        self.query_one("#add-btn", Button).label = "Update"

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input fields."""
        event.stop()
        if event.input.id == "var-name-input":
            # Move to value input
            self.query_one("#var-value-input", Input).focus()
        elif event.input.id == "var-value-input":
            # Submit the form
            self._add_or_update_var()
