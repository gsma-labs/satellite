"""RunEvalsModal - Modal for selecting and running evaluations.

This modal follows Toad's ModalScreen pattern:
- Inherits from ModalScreen[T] for typed return values
- Uses push_screen() to show with backdrop overlay
- Dismisses with dismiss(value) to return data to caller

Now integrates with JobManager to create persistent jobs.
"""

from typing import ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, HorizontalGroup
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from satetoad.examples.eval_data import get_benchmarks
from satetoad.models.job import Job
from satetoad.services.job_manager import JobManager
from satetoad.widgets.eval_list import EvalList
from satetoad.modals.set_model_modal import ModelConfig


class RunEvalsModal(ModalScreen[Job | None]):
    """Modal for selecting and running evaluation benchmarks.

    Returns a Job on run (created via JobManager), None on cancel.

    Layout:
    ╭─────────────────────────────────────╮
    │        Run Evaluations              │
    ├─────────────────────────────────────┤
    │  Model: openai/gpt-4o               │
    │                                     │
    │  Select benchmarks to run:          │
    │  ┌─────────────────────────────┐    │
    │  │ ► ● TeleQnA                 │    │
    │  │   ○ TeleTables              │    │
    │  │   ● TeleLogs                │    │
    │  └─────────────────────────────┘    │
    │                                     │
    │  [Select All] [Clear All]           │
    │                                     │
    │         [Cancel]  [Run Selected]    │
    ╰─────────────────────────────────────╯
    """

    CSS_PATH = "modal_base.tcss"

    # Fallback CSS for backdrop - ensures overlay effect
    DEFAULT_CSS = """
    RunEvalsModal {
        align: center middle;
        background: black 50%;
    }
    """

    # Ordered list of focusable widgets for keyboard navigation
    _FOCUSABLE_IDS: ClassVar[list[str]] = [
        "#eval-list",
        "#select-all-btn",
        "#clear-all-btn",
        "#cancel-btn",
        "#run-btn",
    ]

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("tab", "app.focus_next", "Focus Next", show=False),
        Binding("shift+tab", "app.focus_previous", "Focus Previous", show=False),
    ]

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        job_manager: JobManager | None = None,
    ) -> None:
        """Initialize the modal with optional model configuration.

        Args:
            model_config: Current model configuration for display
            job_manager: JobManager for creating jobs (creates new if not provided)
        """
        super().__init__()
        self._model_config = model_config
        self._job_manager = job_manager or JobManager()

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="container"):
            yield Static("Run Evaluations", classes="modal-title")

            # Show current model or warning
            if self._model_config:
                yield Static(
                    f"Model: [bold]{self._model_config.model}[/]",
                    classes="model-info",
                )
            else:
                yield Static(
                    "[warning]⚠ No model configured - set model first[/]",
                    classes="model-info",
                )

            yield Label("Select benchmarks to run:", classes="section-label")

            # Benchmark list with arrow key navigation
            benchmarks = get_benchmarks()
            yield EvalList(
                benchmarks,
                selected={b["id"] for b in benchmarks},  # All selected by default
                id="eval-list",
            )

            # Select/Clear all buttons
            with Horizontal(classes="action-row"):
                yield Button("Select All", id="select-all-btn", variant="default")
                yield Button("Clear All", id="clear-all-btn", variant="default")

            # Action buttons
            with HorizontalGroup(id="buttons"):
                yield Button("Cancel", id="cancel-btn", variant="default")
                yield Button("Run", id="run-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        if event.button.id == "select-all-btn":
            self.query_one("#eval-list", EvalList).select_all()
            return
        if event.button.id == "clear-all-btn":
            self.query_one("#eval-list", EvalList).clear_all()
            return
        if event.button.id == "run-btn":
            self._run_selected()

    @on(EvalList.RunRequested)
    def on_eval_list_run_requested(self, event: EvalList.RunRequested) -> None:
        """Handle run request from EvalList (triggered by 'r' key)."""
        event.stop()
        self._run_selected()

    def _run_selected(self) -> None:
        """Validate selection, create job, and dismiss with the Job."""
        eval_list = self.query_one("#eval-list", EvalList)
        selected = eval_list.get_selected()

        if not selected:
            self.notify(
                "Please select at least one benchmark",
                severity="warning",
            )
            return

        if not self._model_config:
            self.notify(
                "Please configure a model first",
                severity="error",
            )
            return

        # Create a new job via JobManager
        job = self._job_manager.create_job(
            benchmarks=selected,
            model_provider=self._model_config.provider,
            model_name=self._model_config.model,
        )

        # Return the created Job
        self.dismiss(job)

    def action_cancel(self) -> None:
        """Cancel and close the modal (triggered by Escape key)."""
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        """Intercept arrow keys to handle boundary navigation."""
        handler = {
            "down": self._handle_focus_next,
            "j": self._handle_focus_next,
            "up": self._handle_focus_previous,
            "k": self._handle_focus_previous,
        }.get(event.key)

        if handler is None:
            return

        if handler():
            event.stop()

    def _is_eval_list_focused(self) -> bool:
        """Check if EvalList or its descendant has focus."""
        focused = self.app.focused
        if focused is None:
            return False

        try:
            eval_list = self.query_one("#eval-list", EvalList)
        except Exception:
            return False

        if focused is eval_list:
            return True

        if not hasattr(focused, "ancestors_with_self"):
            return False

        return eval_list in focused.ancestors_with_self

    def _handle_focus_next(self) -> bool:
        """Handle down/j key. Returns True if we handled it."""
        if self._is_eval_list_focused():
            return self._handle_eval_list_next()

        return self._navigate_button(1)

    def _handle_eval_list_next(self) -> bool:
        """Handle navigation from eval list to buttons when at last item."""
        eval_list = self.query_one("#eval-list", EvalList)

        is_at_last_item = (
            eval_list.highlighted is not None
            and eval_list.highlighted >= len(eval_list._items) - 1
        )
        if not is_at_last_item:
            return False

        self.query_one("#select-all-btn").focus()
        return True

    def _find_focused_button_index(self) -> int | None:
        """Find the index of the currently focused button, or None if not on a button."""
        focused = self.app.focused
        button_ids = self._FOCUSABLE_IDS[1:]  # Skip eval-list

        for i, widget_id in enumerate(button_ids):
            try:
                if self.query_one(widget_id) is focused:
                    return i
            except Exception:
                continue
        return None

    def _navigate_button(self, direction: int) -> bool:
        """Navigate between buttons. direction: 1 for next, -1 for previous."""
        index = self._find_focused_button_index()
        if index is None:
            return False

        button_ids = self._FOCUSABLE_IDS[1:]  # Skip eval-list
        new_index = index + direction

        # Going back from first button returns to eval-list
        if new_index < 0:
            self.query_one("#eval-list").focus()
            return True

        # Move to next/previous button if within bounds
        if new_index < len(button_ids):
            self.query_one(button_ids[new_index]).focus()
        return True

    def _handle_focus_previous(self) -> bool:
        """Handle up/k key. Returns True if we handled it."""
        if self._is_eval_list_focused():
            return False
        return self._navigate_button(-1)
