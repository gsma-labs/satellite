"""TabbedEvalsModal - Unified tabbed modal for evaluation workflows.

Combines Run Evals and View Progress into a single tabbed interface.
Selecting a job from View Progress opens a JobDetailModal overlay.
"""

from typing import ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalGroup, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from satetoad.examples.eval_data import get_benchmarks
from satetoad.models.job import Job
from satetoad.modals.job_detail_modal import JobDetailModal
from satetoad.modals.job_list_modal import JobListItem
from satetoad.modals.set_model_modal import ModelConfig
from satetoad.services.job_manager import JobManager
from satetoad.widgets.eval_list import EvalList, EvalListItem
from satetoad.widgets.tab_header import TabHeader


class RunEvalsContent(Vertical):
    """Content widget for the Run Evals tab."""

    class RunRequested(Message):
        """Posted when user wants to run selected benchmarks."""

        def __init__(self, selected_benchmarks: list[str]) -> None:
            super().__init__()
            self.selected_benchmarks = selected_benchmarks

    def __init__(self, model_config: ModelConfig | None = None, **kwargs) -> None:
        """Initialize the content.

        Args:
            model_config: Current model configuration
        """
        super().__init__(**kwargs)
        self._model_config = model_config

    def compose(self) -> ComposeResult:
        """Compose the run evals content."""
        if self._model_config:
            yield Static(
                f"Model: [bold]{self._model_config.model}[/]",
                classes="model-info",
            )
        if not self._model_config:
            yield Static(
                "[warning]No model configured - set model first[/]",
                classes="model-info",
            )

        yield Label("Select benchmarks to run:", classes="section-label")

        with VerticalScroll(id="eval-list-container"):
            benchmarks = get_benchmarks()
            yield EvalList(
                benchmarks,
                selected={b["id"] for b in benchmarks},
                id="eval-list",
            )

    def get_selected(self) -> list[str]:
        """Get list of selected benchmark IDs."""
        eval_list = self.query_one("#eval-list", EvalList)
        return eval_list.get_selected()

    def set_selected(self, benchmark_ids: set[str]) -> None:
        """Set selected benchmarks."""
        eval_list = self.query_one("#eval-list", EvalList)
        eval_list.clear_all()
        for item in eval_list.query(EvalListItem):
            if item.eval_id in benchmark_ids:
                item.selected = True
                eval_list._selected.add(item.eval_id)

    @on(EvalList.RunRequested)
    def on_eval_list_run_requested(self, event: EvalList.RunRequested) -> None:
        """Handle run request from EvalList (triggered by 'r' key)."""
        event.stop()
        selected = self.get_selected()
        if not selected:
            return
        self.post_message(self.RunRequested(selected))


class JobListContent(Vertical):
    """Content widget for the View Progress tab."""

    class JobSelected(Message):
        """Posted when a job is selected."""

        def __init__(self, job_id: str) -> None:
            super().__init__()
            self.job_id = job_id

    highlighted: reactive[int] = reactive(0)

    def __init__(self, job_manager: JobManager, **kwargs) -> None:
        """Initialize the content.

        Args:
            job_manager: JobManager for listing jobs
        """
        super().__init__(**kwargs)
        self._job_manager = job_manager
        self._jobs: list[Job] = []

    def compose(self) -> ComposeResult:
        """Compose the job list content."""
        self._jobs = self._job_manager.list_jobs(limit=20)

        # Header to match Evals tab structure
        yield Static("", classes="model-info")  # Spacer to align with Evals tab
        yield Label("Recent jobs:", classes="section-label")

        if not self._jobs:
            yield Static(
                "No jobs yet. Run evaluations to create jobs.",
                id="empty-message",
            )
            return

        with VerticalScroll(id="job-list"):
            for job in self._jobs:
                yield JobListItem(job)

    def on_mount(self) -> None:
        """Update highlight on mount."""
        if self._jobs:
            self._update_highlight()

    def refresh_jobs(self) -> None:
        """Refresh the job list from storage."""
        self._jobs = self._job_manager.list_jobs(limit=20)

        # Handle transition between empty and populated states
        job_list = self.query("#job-list")
        empty_msg = self.query("#empty-message")

        if not self._jobs:
            # No jobs - show empty message, hide job list
            if job_list:
                job_list.first().remove()
            if not empty_msg:
                self.mount(Static(
                    "No jobs yet. Run evaluations to create jobs.",
                    id="empty-message",
                ))
            return

        # Has jobs - show job list, hide empty message
        if empty_msg:
            empty_msg.first().remove()

        if not job_list:
            # Create job list if it doesn't exist
            scroll = VerticalScroll(id="job-list")
            self.mount(scroll)
            for job in self._jobs:
                scroll.mount(JobListItem(job))
        else:
            # Update existing job list
            existing_list = job_list.first()
            existing_list.remove_children()
            for job in self._jobs:
                existing_list.mount(JobListItem(job))

        self._update_highlight()

    def _update_highlight(self) -> None:
        """Update the highlight on job items."""
        items = list(self.query(JobListItem))
        for i, item in enumerate(items):
            if i == self.highlighted:
                item.add_class("-highlight")
            if i != self.highlighted:
                item.remove_class("-highlight")

    def watch_highlighted(self, value: int) -> None:
        """React to highlight changes."""
        self._update_highlight()

    def on_job_list_item_selected(self, event: JobListItem.Selected) -> None:
        """Handle job selection from item click."""
        event.stop()
        self.post_message(self.JobSelected(event.job_id))

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard navigation."""
        if not self._jobs:
            return

        if event.key in ("down", "j"):
            self.highlighted = min(self.highlighted + 1, len(self._jobs) - 1)
            event.stop()
            return

        if event.key in ("up", "k"):
            self.highlighted = max(self.highlighted - 1, 0)
            event.stop()
            return

        if event.key in ("enter", "space"):
            if 0 <= self.highlighted < len(self._jobs):
                self.post_message(self.JobSelected(self._jobs[self.highlighted].id))
                event.stop()


class TabbedEvalsModal(ModalScreen[Job | None]):
    """Unified tabbed modal for evaluation workflows.

    Combines Run Evals and View Progress tabs. Selecting a job from
    View Progress opens a JobDetailModal overlay.
    """

    CSS_PATH = "modal_base.tcss"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close_or_cancel", "Close", show=False),
        Binding("tab", "next_tab", "Next Tab", show=False),
        Binding("shift+tab", "prev_tab", "Previous Tab", show=False),
        Binding("up", "app.focus_previous", "Focus Previous", show=False),
        Binding("down", "app.focus_next", "Focus Next", show=False),
        Binding("left", "app.focus_previous", "Focus Previous", show=False),
        Binding("right", "app.focus_next", "Focus Next", show=False),
    ]

    active_tab: reactive[str] = reactive("run-evals")

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        job_manager: JobManager | None = None,
    ) -> None:
        """Initialize the modal.

        Args:
            model_config: Current model configuration
            job_manager: JobManager instance
        """
        super().__init__()
        self._model_config = model_config
        self._job_manager = job_manager or JobManager()
        self._run_evals_selected: set[str] | None = None

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="container"):
            yield TabHeader(id="tab-header")

            with Vertical(id="tab-content"):
                yield RunEvalsContent(
                    model_config=self._model_config,
                    id="run-evals-pane",
                    classes="tab-pane -active",
                )
                yield JobListContent(
                    job_manager=self._job_manager,
                    id="view-progress-pane",
                    classes="tab-pane",
                )

            with HorizontalGroup(id="run-evals-buttons", classes="button-row"):
                yield Button("Cancel", id="cancel-btn", variant="default")
                yield Button("Run", id="run-btn", variant="primary")

            with HorizontalGroup(id="view-progress-buttons", classes="button-row"):
                yield Button("Close", id="close-btn", variant="default")

    def on_mount(self) -> None:
        """Set up the tabs on mount."""
        header = self.query_one("#tab-header", TabHeader)
        header.add_tab("run-evals", "Evals", closable=False, activate=True)
        header.add_tab("view-progress", "Progress", closable=False, activate=False)
        self.add_class("-tab-run-evals")
        self.query_one("#eval-list", EvalList).focus()

    def watch_active_tab(self, old_value: str, new_value: str) -> None:
        """React to active tab changes."""
        self.remove_class(f"-tab-{old_value}")
        self.add_class(f"-tab-{new_value}")
        self._update_tab_panes(new_value)

    def _update_tab_panes(self, active_tab_id: str) -> None:
        """Show/hide tab panes based on active tab."""
        for pane in self.query(".tab-pane"):
            pane_id = pane.id or ""
            is_active = pane_id == f"{active_tab_id}-pane"
            if is_active:
                pane.add_class("-active")
            if not is_active:
                pane.remove_class("-active")

    def on_tab_header_tab_changed(self, event: TabHeader.TabChanged) -> None:
        """Handle tab switch."""
        event.stop()
        self._save_tab_state(event.old_tab_id)
        self.active_tab = event.new_tab_id
        self._restore_tab_state(event.new_tab_id)

    def _save_tab_state(self, tab_id: str | None) -> None:
        """Save state for a tab before switching away."""
        if tab_id != "run-evals":
            return
        content = self.query_one("#run-evals-pane", RunEvalsContent)
        self._run_evals_selected = set(content.get_selected())

    def _restore_tab_state(self, tab_id: str) -> None:
        """Restore state for a tab after switching to it."""
        if tab_id == "run-evals":
            self._restore_run_evals_state()
            return

        if tab_id == "view-progress":
            self._restore_view_progress_state()

    def _restore_run_evals_state(self) -> None:
        """Restore run evals tab state."""
        if self._run_evals_selected is not None:
            content = self.query_one("#run-evals-pane", RunEvalsContent)
            content.set_selected(self._run_evals_selected)
        self.query_one("#eval-list", EvalList).focus()

    def _restore_view_progress_state(self) -> None:
        """Restore view progress tab state."""
        content = self.query_one("#view-progress-pane", JobListContent)
        content.refresh_jobs()
        content.focus()

    def on_job_list_content_job_selected(
        self, event: JobListContent.JobSelected
    ) -> None:
        """Handle job selection - open job detail modal."""
        event.stop()
        job = self._job_manager.get_job(event.job_id)
        if job is None:
            self.notify(f"Job {event.job_id} not found", severity="error")
            return
        self.app.push_screen(JobDetailModal(job=job))

    def on_run_evals_content_run_requested(
        self, event: RunEvalsContent.RunRequested
    ) -> None:
        """Handle run request from RunEvalsContent."""
        event.stop()
        self._run_selected(event.selected_benchmarks)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id in ("cancel-btn", "close-btn"):
            self.dismiss(None)
            return

        if button_id == "run-btn":
            content = self.query_one("#run-evals-pane", RunEvalsContent)
            selected = content.get_selected()
            if not selected:
                self.notify("Please select at least one benchmark", severity="warning")
                return
            self._run_selected(selected)

    def _run_selected(self, selected_benchmarks: list[str]) -> None:
        """Validate and create a job."""
        if not selected_benchmarks:
            self.notify("Please select at least one benchmark", severity="warning")
            return

        if not self._model_config:
            self.notify("Please configure a model first", severity="error")
            return

        job = self._job_manager.create_job(
            benchmarks=selected_benchmarks,
            model_provider=self._model_config.provider,
            model_name=self._model_config.model,
        )
        self.dismiss(job)

    def action_close_or_cancel(self) -> None:
        """Handle Escape - dismiss modal."""
        self.dismiss(None)

    def action_prev_tab(self) -> None:
        """Switch to previous tab."""
        self.query_one("#tab-header", TabHeader).action_prev_tab()

    def action_next_tab(self) -> None:
        """Switch to next tab."""
        self.query_one("#tab-header", TabHeader).action_next_tab()
