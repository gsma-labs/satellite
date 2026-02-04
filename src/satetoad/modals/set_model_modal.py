"""SetModelModal - Modal dialog for configuring model provider and API key.

This modal demonstrates the ModalScreen pattern in Textual:
- ModalScreen[T] provides typed return values via dismiss()
- The backdrop is automatically handled by Textual
- Escape key binding for quick dismissal
- Callback-based result handling in the parent screen
"""

import re
from dataclasses import dataclass
from typing import ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, HorizontalGroup, VerticalGroup
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from satetoad.examples.eval_data import MODEL_PROVIDERS, PROVIDERS_BY_CATEGORY


class EnterOnlySelect(Select):
    """Select widget that only opens dropdown on Enter key, not on arrow keys or space."""

    BINDINGS = [
        Binding("enter", "show_overlay", "Show menu", show=False),
    ]


@dataclass
class ModelConfig:
    """Configuration data returned from the SetModelModal.

    Attributes:
        provider: The selected provider ID (e.g., "anthropic", "openai")
        api_key: The API key entered by the user
        model: The full model name (e.g., "claude-3-5-sonnet")
    """

    provider: str
    api_key: str
    model: str


class SetModelModal(ModalScreen[ModelConfig | None]):
    """Modal dialog for configuring API key and model provider.

    Returns ModelConfig on save, None on cancel/escape.

    Keyboard Navigation:
    - Up/k: Move to previous field
    - Down/j: Move to next field
    - Tab/Shift+Tab: Standard focus navigation
    - Enter: Submit or move to next field
    - Escape: Cancel
    """

    CSS_PATH = "set_model_modal.tcss"

    # Fallback CSS for backdrop - ensures overlay effect even if TCSS fails to load
    DEFAULT_CSS = """
    SetModelModal {
        align: center middle;
        background: black 50%;
    }
    """

    # Auto-focus first field when modal opens
    AUTO_FOCUS = "#provider-select"

    # Ordered list of focusable form fields for keyboard navigation
    _FOCUSABLE_FIELDS: ClassVar[list[str]] = [
        "#provider-select",
        "#credential-input",
        "#model-input",
    ]

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel", show=False),
        # k/j only - up/down/enter handled in on_key for dropdown-aware behavior
        Binding("k", "focus_previous_field", "Previous field", show=False),
        Binding("j", "focus_next_field", "Next field", show=False),
        Binding("tab", "app.focus_next", "Focus Next", show=False),
        Binding("shift+tab", "app.focus_previous", "Focus Previous", show=False),
    ]

    def __init__(
        self,
        initial_provider: str | None = None,
        initial_api_key: str = "",
        initial_model: str = "",
        category: str | None = None,
        title: str = "Set Model Configuration",
    ) -> None:
        """Initialize the modal with optional pre-filled values.

        Args:
            initial_provider: Pre-selected provider ID
            initial_api_key: Pre-filled API key
            initial_model: Pre-filled model name
            category: Provider category to filter by (e.g., "lab-apis", "cloud-apis")
            title: Custom title for the modal
        """
        super().__init__()
        self._category = category
        self._title = title
        self._providers = self._get_providers_for_category()
        self._initial_provider = initial_provider or (self._providers[0]["id"] if self._providers else "")
        self._initial_api_key = initial_api_key
        self._initial_model = initial_model
        self._current_prefix = ""

    def _get_providers_for_category(self) -> list[dict]:
        """Get providers filtered by category if set."""
        if self._category:
            return PROVIDERS_BY_CATEGORY.get(self._category, [])
        return MODEL_PROVIDERS

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        # Use VerticalGroup with id="container" (Toad pattern for proper modal overlay)
        with VerticalGroup(id="container"):
            yield Static(self._title, classes="modal-title")

            # Provider selection row
            with Horizontal(classes="form-row"):
                yield Label("Provider:", classes="form-label")
                yield EnterOnlySelect(
                    [(p["name"], p["id"]) for p in self._providers],
                    id="provider-select",
                    value=self._initial_provider,
                )

            # Credential input row (dynamic based on provider)
            with Horizontal(classes="form-row", id="credential-row"):
                yield Label("API Key:", id="credential-label", classes="form-label")
                yield Input(
                    placeholder="Enter your API key",
                    password=True,
                    id="credential-input",
                    value=self._initial_api_key,
                )

            # Model input row
            with Horizontal(classes="form-row"):
                yield Label("Model:", classes="form-label")
                yield Input(
                    placeholder="Enter model name",
                    id="model-input",
                    value=self._initial_model,
                )

            # Hint showing model prefix
            yield Static("", id="prefix-hint", classes="model-hint")

            # Action buttons (HorizontalGroup with id="buttons" for Toad pattern)
            with HorizontalGroup(id="buttons"):
                yield Button("Cancel", id="cancel-btn")
                yield Button("Go", id="save-btn")

    def on_mount(self) -> None:
        """Initialize the model prefix hint and credential field when mounted."""
        self._update_prefix_hint()
        self._update_credential_field_for_current_provider()

    def _get_provider_data(self, provider_id: str) -> dict | None:
        """Get provider configuration by ID."""
        for provider in self._providers:
            if provider["id"] == provider_id:
                return provider
        return None

    def _update_prefix_hint(self) -> None:
        """Update the model prefix hint based on selected provider."""
        try:
            select = self.query_one("#provider-select", Select)
            provider_id = str(select.value) if select.value else ""
            provider = self._get_provider_data(provider_id)

            hint_widget = self.query_one("#prefix-hint", Static)

            if provider:
                prefix = provider.get("model_prefix", "")
                env_var = provider.get("env_var", "")
                self._current_prefix = prefix

                hints = []
                if prefix:
                    hints.append(f"Model prefix: {prefix}")
                if env_var:
                    hints.append(f"Env: {env_var}")

                if hints:
                    hint_widget.update(f"[dim]{' | '.join(hints)}[/]")
                else:
                    hint_widget.update("[dim]Enter full model name[/]")
        except Exception:
            pass

    def _update_credential_field_for_current_provider(self) -> None:
        """Update credential field based on currently selected provider."""
        try:
            select = self.query_one("#provider-select", Select)
            provider_id = str(select.value) if select.value else ""
            provider = self._get_provider_data(provider_id)
            if provider:
                self._update_credential_field(provider)
        except Exception:
            pass

    def _update_credential_field(self, provider: dict) -> None:
        """Update credential field based on provider configuration."""
        cred_row = self.query_one("#credential-row", Horizontal)
        cred_label = self.query_one("#credential-label", Label)
        cred_input = self.query_one("#credential-input", Input)

        # Default to api_key for backward compatibility (Lab APIs, etc.)
        cred_type = provider.get("credential_type", "api_key")

        if cred_type == "none":
            cred_row.add_class("hidden")
            return

        cred_row.remove_class("hidden")

        # Update label and placeholder
        label = provider.get("credential_label", "API Key:")
        cred_label.update(label)
        cred_input.placeholder = provider.get("credential_placeholder", "Enter value")

        # Password field only for API keys
        cred_input.password = (cred_type == "api_key")

        # Set default value for base_url types (if field is empty)
        default_val = provider.get("credential_default", "")
        if cred_type == "base_url" and not cred_input.value and default_val:
            cred_input.value = default_val

    @on(Select.Changed, "#provider-select")
    def on_provider_changed(self, event: Select.Changed) -> None:
        """Handle provider selection change - update prefix hint, credential field, and model input."""
        old_prefix = self._current_prefix
        self._update_prefix_hint()
        self._update_credential_field_for_current_provider()

        # Update model input with new prefix if it was using the old prefix
        try:
            model_input = self.query_one("#model-input", Input)
            current_value = model_input.value

            # If model input is empty or equals old prefix, set to new prefix
            if not current_value or current_value == old_prefix:
                model_input.value = self._current_prefix
                return

            # Replace old prefix with new prefix if value starts with it
            if old_prefix and current_value.startswith(old_prefix):
                model_input.value = self._current_prefix + current_value[len(old_prefix) :]
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        if event.button.id == "save-btn":
            self._save_config()

    def action_cancel(self) -> None:
        """Cancel and close the modal (triggered by Escape key)."""
        self.dismiss(None)

    def _save_config(self) -> None:
        """Validate inputs and save the configuration."""
        try:
            provider_id = str(self.query_one("#provider-select", Select).value)
            credential = self.query_one("#credential-input", Input).value.strip()
            model = self.query_one("#model-input", Input).value.strip()

            # Get provider configuration for credential type
            provider_data = self._get_provider_data(provider_id)
            cred_type = provider_data.get("credential_type", "api_key") if provider_data else "api_key"
            cred_required = provider_data.get("credential_required", True) if provider_data else True

            # Validate credential based on type
            if cred_type == "none":
                credential = ""
            elif cred_required and not credential:
                label = provider_data.get("credential_label", "Credential") if provider_data else "Credential"
                self.notify(f"{label.rstrip(':')} is required", severity="error")
                self.query_one("#credential-input", Input).focus()
                return
            elif cred_type == "api_key" and credential:
                if not self._validate_api_key(credential):
                    return
            elif cred_type == "base_url" and credential:
                if not self._validate_base_url(credential):
                    return

            # Validate model name
            if not model:
                self.notify("Model name is required", severity="error")
                self.query_one("#model-input", Input).focus()
                return

            if not self._validate_model_name(model):
                return

            # Create config and dismiss modal
            config = ModelConfig(
                provider=provider_id,
                api_key=credential,
                model=model,
            )
            self.dismiss(config)

        except (ValueError, TypeError) as e:
            self.notify(f"Configuration error: {e}", severity="error")

    def _validate_api_key(self, api_key: str) -> bool:
        """Validate API key format for security.

        Returns True if valid, False otherwise (with notification).
        """
        # Length check
        if len(api_key) < 10:
            self.notify("API key is too short", severity="error")
            self.query_one("#credential-input", Input).focus()
            return False

        if len(api_key) > 500:
            self.notify("API key is too long", severity="error")
            self.query_one("#credential-input", Input).focus()
            return False

        # Check for injection characters
        invalid_chars = ["\n", "\r", "\0", ";", "&", "|", "$", "`"]
        if any(c in api_key for c in invalid_chars):
            self.notify("API key contains invalid characters", severity="error")
            self.query_one("#credential-input", Input).focus()
            return False

        return True

    def _validate_base_url(self, url: str) -> bool:
        """Validate base URL format.

        Returns True if valid, False otherwise (with notification).
        """
        if not url:
            return True

        if not url.startswith(("http://", "https://")):
            self.notify("URL must start with http:// or https://", severity="error")
            self.query_one("#credential-input", Input).focus()
            return False

        if len(url) > 500:
            self.notify("URL is too long", severity="error")
            self.query_one("#credential-input", Input).focus()
            return False

        return True

    def _validate_model_name(self, model: str) -> bool:
        """Validate model name format for security.

        Returns True if valid, False otherwise (with notification).
        """
        # Length check
        if len(model) > 200:
            self.notify("Model name is too long", severity="error")
            self.query_one("#model-input", Input).focus()
            return False

        # Model names should be alphanumeric with limited special chars
        if not re.match(r"^[a-zA-Z0-9._:/-]+$", model):
            self.notify("Model name contains invalid characters", severity="error")
            self.query_one("#model-input", Input).focus()
            return False

        return True

    # --- Keyboard Navigation Methods ---

    def _get_current_field_index(self) -> int | None:
        """Get the index of the currently focused field."""
        focused = self.app.focused
        if focused is None:
            return None

        for index, field_id in enumerate(self._FOCUSABLE_FIELDS):
            try:
                field = self.query_one(field_id)
                # Check if focused widget is the field or a descendant of it
                if focused is field:
                    return index
                # For Select widget, check if focus is on internal component
                if hasattr(focused, "ancestors_with_self"):
                    if field in focused.ancestors_with_self:
                        return index
            except Exception:
                pass
        return None

    def action_focus_next_field(self) -> None:
        """Move focus to the next form field (Down/j key)."""
        current = self._get_current_field_index()
        if current is None:
            # Focus first field if nothing focused
            self.query_one(self._FOCUSABLE_FIELDS[0]).focus()
        elif current < len(self._FOCUSABLE_FIELDS) - 1:
            # Move to next field
            self.query_one(self._FOCUSABLE_FIELDS[current + 1]).focus()
        else:
            # At last field, focus Save button
            self.query_one("#save-btn").focus()

    def action_focus_previous_field(self) -> None:
        """Move focus to the previous form field (Up/k key)."""
        current = self._get_current_field_index()
        if current is None:
            # Focus last field if nothing focused
            self.query_one(self._FOCUSABLE_FIELDS[-1]).focus()
        elif current > 0:
            # Move to previous field
            self.query_one(self._FOCUSABLE_FIELDS[current - 1]).focus()

    def on_key(self, event: events.Key) -> None:
        """Handle key events - intercept up/down/enter when dropdown is closed."""
        # Check if provider dropdown is expanded
        try:
            provider_select = self.query_one("#provider-select", Select)
            dropdown_open = provider_select.expanded
        except Exception:
            dropdown_open = False

        # If dropdown is open, let SelectOverlay handle all keys
        if dropdown_open:
            return  # Don't stop event - let it propagate to SelectOverlay

        # Dropdown is closed - handle navigation keys
        if event.key in ("up", "k"):
            event.stop()
            self.action_focus_previous_field()
        elif event.key in ("down", "j"):
            event.stop()
            self.action_focus_next_field()
        elif event.key == "enter":
            event.stop()
            self.action_activate_field()

    def _is_widget_focused(self, widget_id: str) -> bool:
        """Check if a widget (or its child) has focus."""
        try:
            widget = self.query_one(widget_id)
            focused = self.app.focused
            if focused is widget:
                return True
            # Check if focused widget is a child of the target
            if hasattr(focused, "ancestors_with_self"):
                return widget in focused.ancestors_with_self
        except Exception:
            pass
        return False

    def action_activate_field(self) -> None:
        """Activate current field or submit if on button (Enter key)."""
        if self._is_widget_focused("#save-btn"):
            self._save_config()
            return

        if self._is_widget_focused("#cancel-btn"):
            self.dismiss(None)
            return

        if self._is_widget_focused("#provider-select"):
            select = self.query_one("#provider-select", Select)
            if hasattr(select, "action_show_overlay"):
                select.action_show_overlay()
            return

        # On Input fields, move to next field
        self.action_focus_next_field()
