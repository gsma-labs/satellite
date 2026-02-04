"""SubmitModal - Modal for submitting evaluation results.

This modal follows Toad's ModalScreen pattern:
- Inherits from ModalScreen[T] for typed return values
- Uses push_screen() to show with backdrop overlay
- Dismisses with dismiss(value) to return data to caller
"""

from dataclasses import dataclass
from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from satetoad.modals.set_model_modal import ModelConfig


@dataclass
class SubmitData:
    """Data returned from the SubmitModal on successful submission.

    Attributes:
        name: Submission name (e.g., model name)
        organization: Organization name
        notes: Optional additional notes
    """

    name: str
    organization: str
    notes: str


class SubmitModal(ModalScreen[SubmitData | None]):
    """Modal for submitting evaluation results to the leaderboard.

    Returns SubmitData on submit, None on cancel.

    Layout:
    ╭─────────────────────────────────────╮
    │         Submit Results              │
    ├─────────────────────────────────────┤
    │                                     │
    │  Submission Name: [______________]  │
    │                                     │
    │  Organization:    [______________]  │
    │                                     │
    │  Notes:           [______________]  │
    │                                     │
    │         [Cancel]  [Submit]          │
    ╰─────────────────────────────────────╯
    """

    CSS_PATH = "modal_base.tcss"

    # Fallback CSS for backdrop - ensures overlay effect
    DEFAULT_CSS = """
    SubmitModal {
        align: center middle;
        background: black 50%;
    }
    """

    _FOCUSABLE_FIELDS: ClassVar[list[str]] = [
        "#name-input",
        "#org-input",
        "#notes-input",
        "#cancel-btn",
        "#submit-btn",
    ]

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("k", "focus_previous_field", "Previous field", show=False),
        Binding("j", "focus_next_field", "Next field", show=False),
    ]

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        has_results: bool = False,
    ) -> None:
        """Initialize the modal.

        Args:
            model_config: Current model configuration for pre-filling
            has_results: Whether evaluation results exist to submit
        """
        super().__init__()
        self._model_config = model_config
        self._has_results = has_results

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="container"):
            yield Static("Submit Results", classes="modal-title")

            if not self._has_results:
                yield Static(
                    "[warning]⚠ Run evaluations first before submitting.[/]",
                    classes="placeholder-text",
                )

            # Submission name (pre-fill with model name if available)
            with Horizontal(classes="form-row"):
                yield Label("Submission Name:", classes="form-label")
                yield Input(
                    placeholder="e.g., GPT-4-Turbo",
                    id="name-input",
                    classes="form-input",
                    value=self._model_config.model if self._model_config else "",
                )

            # Organization
            with Horizontal(classes="form-row"):
                yield Label("Organization:", classes="form-label")
                yield Input(
                    placeholder="e.g., OpenAI",
                    id="org-input",
                    classes="form-input",
                )

            # Notes
            with Horizontal(classes="form-row"):
                yield Label("Notes (optional):", classes="form-label")
                yield Input(
                    placeholder="Any additional notes",
                    id="notes-input",
                    classes="form-input",
                )

            # Action buttons
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel-btn", variant="default")
                yield Button("Submit", id="submit-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        if event.button.id == "submit-btn":
            self._submit()

    def _submit(self) -> None:
        """Validate and submit the form."""
        name = self.query_one("#name-input", Input).value.strip()
        org = self.query_one("#org-input", Input).value.strip()
        notes = self.query_one("#notes-input", Input).value.strip()

        if not name:
            self.notify(
                "Please enter a submission name",
                severity="warning",
            )
            self.query_one("#name-input", Input).focus()
            return

        if not self._has_results:
            self.notify(
                "Run evaluations first before submitting",
                severity="error",
            )
            return

        # Return submission data
        self.dismiss(SubmitData(name=name, organization=org, notes=notes))

    def action_cancel(self) -> None:
        """Cancel and close the modal (triggered by Escape key)."""
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        """Handle key events for field navigation."""
        if event.key in ("up", "k"):
            event.stop()
            self.action_focus_previous_field()
        elif event.key in ("down", "j"):
            event.stop()
            self.action_focus_next_field()

    def action_focus_next_field(self) -> None:
        """Focus the next field in the form."""
        self._cycle_focus(1)

    def action_focus_previous_field(self) -> None:
        """Focus the previous field in the form."""
        self._cycle_focus(-1)

    def _cycle_focus(self, direction: int) -> None:
        """Cycle focus through fields."""
        focused = self.focused
        if focused is None:
            self.query_one(self._FOCUSABLE_FIELDS[0]).focus()
            return

        for i, selector in enumerate(self._FOCUSABLE_FIELDS):
            try:
                if focused is self.query_one(selector):
                    new_idx = (i + direction) % len(self._FOCUSABLE_FIELDS)
                    self.query_one(self._FOCUSABLE_FIELDS[new_idx]).focus()
                    return
            except Exception:
                continue
