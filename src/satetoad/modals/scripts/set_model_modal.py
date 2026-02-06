"""SetModelModal - Modal dialog for configuring model provider and API key.

This modal demonstrates the ModalScreen pattern in Textual:
- ModalScreen[T] provides typed return values via dismiss()
- The backdrop is automatically handled by Textual
- Escape key binding for quick dismissal
- Callback-based result handling in the parent screen

Supports multi-model configuration:
- Users can add multiple models before saving
- Silent replacement for duplicate normalized paths
- Returns list[ModelConfig] instead of single ModelConfig
"""

import re
from typing import ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, HorizontalGroup, VerticalGroup
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from satetoad.examples.eval_data import MODEL_PROVIDERS, PROVIDERS_BY_CATEGORY
from satetoad.services.config import EnvConfigManager, ModelConfig, normalize_model_path
from satetoad.widgets.configured_models_list import ConfiguredModelItem, ConfiguredModelsList

# Titles for category-filtered modals
CATEGORY_TITLES = {
    "lab-apis": "Lab APIs",
    "cloud-apis": "Cloud APIs",
    "open-hosted": "Open (Hosted)",
    "open-local": "Open (Local)",
}


class EnterOnlySelect(Select):
    """Select widget that only opens dropdown on Enter key, not on arrow keys or space."""

    BINDINGS = [
        Binding("enter", "show_overlay", "Show menu", show=False),
    ]


class SetModelModal(ModalScreen[list[ModelConfig] | None]):
    """Modal dialog for configuring API key and model provider.

    Supports multi-model configuration - users can add multiple models
    before saving. Returns list[ModelConfig] on save, None on cancel/escape.

    Keyboard Navigation:
    - Up/k: Move to previous field
    - Down/j: Move to next field
    - Tab/Shift+Tab: Standard focus navigation
    - Enter: Submit or move to next field
    - Escape: Cancel
    """

    CSS_PATH = "../styles/set_model_modal.tcss"

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
        category: str | None = None,
        initial_provider: str | None = None,
        initial_api_key: str = "",
        initial_model: str = "",
        title: str = "Model Configuration",
        initial_models: list[ModelConfig] | None = None,
        env_manager: EnvConfigManager | None = None,
    ) -> None:
        """Initialize the modal with optional pre-filled values.

        Args:
            category: Provider category to filter by (lab-apis, cloud-apis, etc.)
            initial_provider: Pre-selected provider ID
            initial_api_key: Pre-filled API key
            initial_model: Pre-filled model name
            title: Custom title for the modal (overridden if category is set)
            initial_models: Pre-configured models to show in the list
            env_manager: Environment config manager for API key detection
        """
        super().__init__()
        # Filter providers by category, fallback to all
        self._providers = PROVIDERS_BY_CATEGORY.get(category, MODEL_PROVIDERS) if category else MODEL_PROVIDERS
        # Title from category or explicit title
        self._title = CATEGORY_TITLES.get(category, title) if category else title
        self._initial_provider = initial_provider or (
            self._providers[0]["id"] if self._providers else ""
        )
        self._initial_api_key = initial_api_key
        self._initial_model = initial_model
        self._current_prefix = ""
        self._initial_models = initial_models or []
        self._env_manager = env_manager
        # Snapshot current .env state for rollback on cancel
        self._snapshot = env_manager.load_models() if env_manager else []

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        # Use VerticalGroup with id="container" (Toad pattern for proper modal overlay)
        with VerticalGroup(id="container"):
            yield Static(self._title, classes="modal-title")

            # Configured models list (shows added models)
            models_for_list = [
                (config, normalize_model_path(config.model))
                for config in self._initial_models
            ]
            yield ConfiguredModelsList(models_for_list, id="models-list")

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
                yield Button("Add", id="add-btn")
                yield Button("Save All", id="save-btn", variant="primary")

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
        select = self.query_one("#provider-select", Select)
        hint_widget = self.query_one("#prefix-hint", Static)

        if not select.value:
            hint_widget.update("[dim]Enter full model name[/]")
            return

        provider = self._get_provider_data(select.value)

        if not provider:
            hint_widget.update("[dim]Enter full model name[/]")
            return

        prefix = provider.get("model_prefix", "")
        self._current_prefix = prefix

        hints = []
        if prefix:
            hints.append(f"Prefix: {prefix}")

        # Show API key status for providers that need API keys
        env_var = provider.get("env_var", "")
        if provider.get("credential_type", "api_key") == "api_key" and env_var:
            key_exists = (
                env_var in self._env_manager.get_all_vars() if self._env_manager else False
            )
            if key_exists:
                hints.append(f"[green]✓ {env_var}[/green]")
            else:
                hints.append(f"[yellow]⚠ {env_var} not set (press 'c')[/yellow]")

        hint_text = " | ".join(hints) if hints else "Enter full model name"
        hint_widget.update(hint_text)

    def _update_credential_field_for_current_provider(self) -> None:
        """Update credential field based on currently selected provider."""
        select = self.query_one("#provider-select", Select)
        if not select.value:
            return
        provider = self._get_provider_data(select.value)
        if provider:
            self._update_credential_field(provider)

    def _update_credential_field(self, provider: dict) -> None:
        """Update credential field based on provider configuration.

        API keys are hidden - users manage them via Configuration (press 'c').
        Only base_url types show the credential field.
        """
        cred_row = self.query_one("#credential-row", Horizontal)
        cred_type = provider.get("credential_type", "api_key")

        # Hide for api_key and none types - API keys managed via Configuration (press 'c')
        if cred_type != "base_url":
            cred_row.add_class("hidden")
            return

        # Show for base_url type (local providers like Ollama, vLLM)
        cred_row.remove_class("hidden")

        cred_label = self.query_one("#credential-label", Label)
        cred_input = self.query_one("#credential-input", Input)

        cred_label.update(provider.get("credential_label", "Base URL:"))
        cred_input.placeholder = provider.get("credential_placeholder", "Enter URL")
        cred_input.password = False

        # Set default value if field is empty
        default_val = provider.get("credential_default", "")
        if not cred_input.value and default_val:
            cred_input.value = default_val

    @on(Select.Changed, "#provider-select")
    def on_provider_changed(self, event: Select.Changed) -> None:
        """Handle provider selection change - update prefix hint, credential field, and model input."""
        old_prefix = self._current_prefix
        self._update_prefix_hint()
        self._update_credential_field_for_current_provider()

        # Update model input with new prefix if it was using the old prefix
        model_input = self.query_one("#model-input", Input)
        current_value = model_input.value

        # If model input is empty or equals old prefix, set to new prefix
        if not current_value or current_value == old_prefix:
            model_input.value = self._current_prefix
            return

        # Replace old prefix with new prefix if value starts with it
        if old_prefix and current_value.startswith(old_prefix):
            model_input.value = self._current_prefix + current_value[len(old_prefix):]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self._restore_snapshot()
            self.dismiss(None)
            return
        if event.button.id == "add-btn":
            self._add_model_to_list()
            return
        if event.button.id == "save-btn":
            self._save_all_models()

    def action_cancel(self) -> None:
        """Cancel and close the modal (triggered by Escape key)."""
        self._restore_snapshot()
        self.dismiss(None)

    def _restore_snapshot(self) -> None:
        """Restore .env to state when modal opened (rollback)."""
        if self._env_manager is None:
            return
        self._env_manager.save_models(self._snapshot)

    def _validate_and_create_config(self) -> ModelConfig | None:
        """Validate inputs and create a ModelConfig.

        API keys are NOT collected here - they are managed via Configuration (press 'c').
        Only base URLs are collected for local providers.

        Returns the config if valid, None otherwise.
        """
        provider_id = self.query_one("#provider-select", Select).value
        credential = self.query_one("#credential-input", Input).value.strip()
        model = self.query_one("#model-input", Input).value.strip()

        if not provider_id:
            self.notify("Please select a provider", severity="error")
            self.query_one("#provider-select", Select).focus()
            return None

        provider_data = self._get_provider_data(provider_id)
        if not provider_data:
            self.notify("Invalid provider selected", severity="error")
            self.query_one("#provider-select", Select).focus()
            return None

        cred_type = provider_data.get("credential_type", "api_key")

        # Handle credential based on type
        if cred_type != "base_url":
            # API keys managed via Configuration (press 'c'), not here
            credential = ""
        elif not self._validate_base_url_credential(provider_data, credential):
            return None

        # Validate model name
        if not model:
            self.notify("Model name is required", severity="error")
            self.query_one("#model-input", Input).focus()
            return None

        if not self._validate_model_name(model):
            return None

        return ModelConfig(
            provider=provider_id,
            api_key=credential,  # Empty for api_key types, URL for base_url
            model=model,
        )

    def _add_model_to_list(self) -> None:
        """Validate current input and add to the models list."""
        config = self._validate_and_create_config()
        if config is None:
            return

        # Add to the list (silently replaces if same normalized path)
        models_list = self.query_one("#models-list", ConfiguredModelsList)
        normalized = normalize_model_path(config.model)
        models_list.add_model(config, normalized)

        # Persist immediately to .env
        self._persist_current_models()

        # Clear form for next entry
        self._clear_form()

        # Show confirmation
        self.notify(f"Added {config.model}", severity="information")

    def _persist_current_models(self) -> None:
        """Write current model list to .env immediately."""
        if self._env_manager is None:
            return
        models_list = self.query_one("#models-list", ConfiguredModelsList)
        models = models_list.get_models()
        self._env_manager.save_models(models)

    @on(ConfiguredModelItem.DeleteRequested)
    def on_model_delete_requested(
        self, event: ConfiguredModelItem.DeleteRequested
    ) -> None:
        """Handle model deletion - persist immediately after list removes it."""
        # List already removed the model, just persist the change
        self._persist_current_models()
        self.notify("Model removed", severity="information")

    def _save_all_models(self) -> None:
        """Save all configured models and dismiss the modal."""
        models_list = self.query_one("#models-list", ConfiguredModelsList)
        models = models_list.get_models()

        if not models:
            self.notify("Add at least one model before saving", severity="warning")
            return

        self.dismiss(models)

    def _clear_form(self) -> None:
        """Clear the form fields for the next model entry."""
        credential_input = self.query_one("#credential-input", Input)
        model_input = self.query_one("#model-input", Input)

        credential_input.value = ""
        model_input.value = self._current_prefix

        # Focus provider select for next entry
        self.query_one("#provider-select").focus()

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

    def _validate_base_url_credential(
        self, provider_data: dict | None, credential: str
    ) -> bool:
        """Validate base URL credential for local providers.

        Returns True if valid, False otherwise (with notification).
        """
        cred_required = (
            provider_data.get("credential_required", True) if provider_data else True
        )

        if cred_required and not credential:
            label = (
                provider_data.get("credential_label", "Base URL")
                if provider_data
                else "Base URL"
            )
            self.notify(f"{label.rstrip(':')} is required", severity="error")
            self.query_one("#credential-input", Input).focus()
            return False

        if credential and not self._validate_base_url(credential):
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
            # At last field, focus Add button
            self.query_one("#add-btn").focus()

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
            self._save_all_models()
            return

        if self._is_widget_focused("#add-btn"):
            self._add_model_to_list()
            return

        if self._is_widget_focused("#cancel-btn"):
            self._restore_snapshot()
            self.dismiss(None)
            return

        if self._is_widget_focused("#provider-select"):
            select = self.query_one("#provider-select", Select)
            if hasattr(select, "action_show_overlay"):
                select.action_show_overlay()
            return

        # On Input fields, move to next field
        self.action_focus_next_field()
