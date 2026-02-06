"""ConfiguredModelsList widget for displaying and managing configured models.

Shows a scrollable list of configured models with delete buttons.
Used in the SetModelModal for multi-model configuration.
"""

from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Button, Label, Static

if TYPE_CHECKING:
    from satetoad.services.config import ModelConfig


class ConfiguredModelItem(Static):
    """A single model entry in the configured models list.

    Displays provider and model name with a delete button.
    """

    DEFAULT_CSS = """
    ConfiguredModelItem {
        layout: horizontal;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: $surface;
    }

    ConfiguredModelItem .model-info {
        width: 1fr;
    }

    ConfiguredModelItem .provider-badge {
        color: $text-muted;
        margin-right: 1;
    }

    ConfiguredModelItem .model-name {
        color: $text;
    }

    ConfiguredModelItem .delete-btn {
        min-width: 3;
        background: transparent;
        color: $error;
        border: none;
    }

    ConfiguredModelItem .delete-btn:hover {
        background: $error 20%;
    }
    """

    class DeleteRequested(Message):
        """Posted when user clicks delete on a model."""

        def __init__(self, normalized_path: str) -> None:
            self.normalized_path = normalized_path
            super().__init__()

    def __init__(
        self,
        model_config: "ModelConfig",
        normalized_path: str,
    ) -> None:
        """Initialize model item.

        Args:
            model_config: The model configuration to display
            normalized_path: Normalized path for identification
        """
        super().__init__()
        self._config = model_config
        self._normalized_path = normalized_path

    def compose(self) -> ComposeResult:
        """Compose the model item layout."""
        yield Label(f"[{self._config.provider}]", classes="provider-badge")
        yield Label(self._config.model, classes="model-name model-info")
        sanitized_id = self._normalized_path.replace("/", "-").replace(".", "-")
        yield Button("x", classes="delete-btn", id=f"delete-{sanitized_id}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle delete button click."""
        if event.button.has_class("delete-btn"):
            event.stop()
            self.post_message(self.DeleteRequested(self._normalized_path))


class ConfiguredModelsList(VerticalScroll):
    """Scrollable list of configured models with add/remove support.

    Posts ConfiguredModelItem.DeleteRequested when a model is deleted.
    """

    DEFAULT_CSS = """
    ConfiguredModelsList {
        height: auto;
        max-height: 10;
        border: solid $surface-lighten-2;
        padding: 1;
        margin-bottom: 1;
    }

    ConfiguredModelsList.empty {
        height: 3;
    }

    ConfiguredModelsList .empty-message {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(
        self, models: list[tuple["ModelConfig", str]] | None = None, **kwargs: Any
    ) -> None:
        """Initialize the models list.

        Args:
            models: List of (ModelConfig, normalized_path) tuples
            **kwargs: Additional arguments passed to VerticalScroll
        """
        super().__init__(**kwargs)
        self._models: list[tuple["ModelConfig", str]] = models or []

    def compose(self) -> ComposeResult:
        """Compose the list content."""
        if not self._models:
            yield Static("No models configured", classes="empty-message")
            return

        for config, normalized_path in self._models:
            yield ConfiguredModelItem(config, normalized_path)

    def on_mount(self) -> None:
        """Update empty class on mount."""
        self._update_empty_class()

    def _update_empty_class(self) -> None:
        """Add/remove empty class based on model count."""
        if self._models:
            self.remove_class("empty")
        else:
            self.add_class("empty")

    def add_model(self, config: "ModelConfig", normalized_path: str) -> None:
        """Add a model to the list.

        If a model with the same normalized_path exists, it's replaced.

        Args:
            config: Model configuration
            normalized_path: Normalized path for deduplication
        """
        # Remove existing with same normalized path (silent replacement)
        self._models = [(c, p) for c, p in self._models if p != normalized_path]
        self._models.append((config, normalized_path))
        self._refresh_list()

    def remove_model(self, normalized_path: str) -> bool:
        """Remove a model by normalized path.

        Args:
            normalized_path: Path of model to remove

        Returns:
            True if removed, False if not found
        """
        original_count = len(self._models)
        self._models = [(c, p) for c, p in self._models if p != normalized_path]

        if len(self._models) < original_count:
            self._refresh_list()
            return True
        return False

    def get_models(self) -> list["ModelConfig"]:
        """Get list of configured ModelConfig objects.

        Returns:
            List of ModelConfig instances
        """
        return [config for config, _ in self._models]

    def get_model_count(self) -> int:
        """Get number of configured models."""
        return len(self._models)

    def clear(self) -> None:
        """Remove all models."""
        self._models = []
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Refresh the list UI."""
        self._update_empty_class()

        # Remove all children
        for child in list(self.children):
            child.remove()

        # Re-compose
        if not self._models:
            self.mount(Static("No models configured", classes="empty-message"))
            return

        for config, normalized_path in self._models:
            self.mount(ConfiguredModelItem(config, normalized_path))

    def on_configured_model_item_delete_requested(
        self,
        event: ConfiguredModelItem.DeleteRequested,
    ) -> None:
        """Handle delete request from a model item."""
        self.remove_model(event.normalized_path)
