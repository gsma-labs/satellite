"""TabbedEvalsModal - Unified tabbed modal for evaluation workflows.

Combines Run Evals and View Progress into a single tabbed interface.
Selecting a job from View Progress opens a JobDetailModal overlay.

Supports multi-model evaluation:
- Displays all configured models in the Run Evals tab
- Creates one Job per model when running
"""

from typing import ClassVar

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalGroup, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Button, Input, Label, Static

from satetoad.modals.scripts.job_detail_modal import JobDetailModal
from satetoad.modals.scripts.job_list_modal import JobListItem
from satetoad.services.config import EvalSettings, EvalSettingsManager, ModelConfig
from satetoad.services.evals import BENCHMARKS_BY_ID, Job, JobManager
from satetoad.widgets.dropdown_button import DropdownButton
from satetoad.widgets.eval_list import EvalList, EvalListItem
from satetoad.widgets.tab_header import TabHeader


class RunEvalsContent(Vertical):
    """Content widget for the Run Evals tab."""

    class RunRequested(Message):
        """Posted when user wants to run selected benchmarks."""

        def __init__(self, selected_benchmarks: list[str]) -> None:
            super().__init__()
            self.selected_benchmarks = selected_benchmarks

    def __init__(
        self, model_configs: list[ModelConfig] | None = None, **kwargs
    ) -> None:
        """Initialize the content.

        Args:
            model_configs: List of configured models
        """
        super().__init__(**kwargs)
        self._model_configs = model_configs or []

    def compose(self) -> ComposeResult:
        """Compose the run evals content."""
        # Model info moved to footer - just show the benchmarks
        yield Label("Select benchmarks to run:", classes="section-label")

        with VerticalScroll(id="eval-list-container"):
            benchmark_list = [
                {"id": b.id, "name": b.name, "description": b.description}
                for b in BENCHMARKS_BY_ID.values()
            ]
            yield EvalList(
                benchmark_list,
                selected=set(BENCHMARKS_BY_ID.keys()),
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
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Compose the job list content."""
        self._jobs = self._job_manager.list_jobs(limit=20)

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
        """Start polling and update highlight on mount."""
        self._refresh_timer = self.set_interval(2.0, self._poll_refresh)
        if self._jobs:
            self._update_highlight()

    def on_unmount(self) -> None:
        """Stop polling when unmounted."""
        if self._refresh_timer is not None:
            self._refresh_timer.stop()

    def _poll_refresh(self) -> None:
        """Called by timer - refresh only if this tab is visible."""
        if not self.has_class("-active"):
            return
        self.refresh_jobs()

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
                self.mount(
                    Static(
                        "No jobs yet. Run evaluations to create jobs.",
                        id="empty-message",
                    )
                )
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


class SettingsContent(Vertical):
    """Content widget for the Settings tab."""

    class SettingsChanged(Message):
        """Posted when settings are modified."""

        def __init__(self, settings: EvalSettings) -> None:
            super().__init__()
            self.settings = settings

    def __init__(self, settings: EvalSettings, **kwargs) -> None:
        """Initialize with current settings."""
        super().__init__(**kwargs)
        self._settings = settings

    def compose(self) -> ComposeResult:
        """Compose the settings form."""
        yield Label("Evaluation Settings:", classes="section-label")

        with VerticalScroll(id="settings-scroll"):
            with HorizontalGroup(classes="settings-row"):
                yield Label("Limit:", classes="settings-label")
                yield Input(
                    "",
                    id="limit-input",
                    classes="settings-input",
                    type="integer",
                    placeholder=str(EvalSettings.DEFAULT_LIMIT),
                )
                yield Label("Samples per task", classes="settings-hint")

            with HorizontalGroup(classes="settings-row"):
                yield Label("Epochs:", classes="settings-label")
                yield Input(
                    "",
                    id="epochs-input",
                    classes="settings-input",
                    type="integer",
                    placeholder=str(EvalSettings.DEFAULT_EPOCHS),
                )
                yield Label("Repeat each sample", classes="settings-hint")

            with HorizontalGroup(classes="settings-row"):
                yield Label("Max Connections:", classes="settings-label")
                yield Input(
                    "",
                    id="max-connections-input",
                    classes="settings-input",
                    type="integer",
                    placeholder=str(EvalSettings.DEFAULT_MAX_CONNECTIONS),
                )
                yield Label("Concurrent API calls", classes="settings-hint")

            with HorizontalGroup(classes="settings-row"):
                yield Label("Token Limit:", classes="settings-label")
                yield Input(
                    "",
                    id="token-limit-input",
                    classes="settings-input",
                    placeholder="None",
                )
                yield Label("Per sample (optional)", classes="settings-hint")

            with HorizontalGroup(classes="settings-row"):
                yield Label("Message Limit:", classes="settings-label")
                yield Input(
                    "",
                    id="message-limit-input",
                    classes="settings-input",
                    placeholder="None",
                )
                yield Label("Per sample (optional)", classes="settings-hint")

    def get_settings(self) -> EvalSettings:
        """Get current settings from form inputs."""

        def parse_int(input_id: str, default: int) -> int:
            value = self.query_one(f"#{input_id}", Input).value.strip()
            if not value:
                return default
            try:
                return int(value)
            except ValueError:
                return default

        def parse_optional_int(input_id: str) -> int | None:
            value = self.query_one(f"#{input_id}", Input).value.strip()
            if not value:
                return None
            try:
                return int(value)
            except ValueError:
                return None

        return EvalSettings(
            limit=parse_int("limit-input", EvalSettings.DEFAULT_LIMIT),
            epochs=parse_int("epochs-input", EvalSettings.DEFAULT_EPOCHS),
            max_connections=parse_int("max-connections-input", EvalSettings.DEFAULT_MAX_CONNECTIONS),
            token_limit=parse_optional_int("token-limit-input"),
            message_limit=parse_optional_int("message-limit-input"),
        )

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes - post settings changed message."""
        event.stop()
        self.post_message(self.SettingsChanged(self.get_settings()))


class TabbedEvalsModal(ModalScreen[Job | None]):
    """Unified tabbed modal for evaluation workflows.

    Combines Run Evals and View Progress tabs. Selecting a job from
    View Progress opens a JobDetailModal overlay.

    Supports multi-model evaluation: creates one Job tracking all models.
    """

    CSS_PATH = "../styles/modal_base.tcss"

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
        job_manager: JobManager,
        settings_manager: EvalSettingsManager,
        model_configs: list[ModelConfig] | None = None,
    ) -> None:
        """Initialize the modal.

        Args:
            job_manager: JobManager instance (required)
            settings_manager: EvalSettingsManager for persisting settings
            model_configs: List of configured models
        """
        super().__init__()
        self._job_manager = job_manager
        self._settings_manager = settings_manager
        self._model_configs = model_configs or []
        self._run_evals_selected: set[str] | None = None
        self._settings = settings_manager.load()

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="container"):
            yield TabHeader(id="tab-header")

            with Vertical(id="tab-content"):
                yield RunEvalsContent(
                    model_configs=self._model_configs,
                    id="run-evals-pane",
                    classes="tab-pane -active",
                )
                yield JobListContent(
                    job_manager=self._job_manager,
                    id="view-progress-pane",
                    classes="tab-pane",
                )
                yield SettingsContent(
                    settings=self._settings,
                    id="settings-pane",
                    classes="tab-pane",
                )

            # Run Evals footer: models dropdown (left) + buttons (right)
            with HorizontalGroup(id="run-evals-footer"):
                yield DropdownButton(
                    label=self._get_models_label(),
                    items=self._get_model_items(),
                    id="models-dropdown",
                )
                with HorizontalGroup(id="run-evals-buttons", classes="button-row"):
                    yield Button("Cancel", id="cancel-btn", variant="default")
                    yield Button("Run", id="run-btn", variant="primary")

            # View Progress footer: just buttons
            with HorizontalGroup(id="view-progress-buttons", classes="button-row"):
                yield Button("Close", id="close-btn", variant="default")

            # Settings footer: just close button
            with HorizontalGroup(id="settings-buttons", classes="button-row"):
                yield Button("Close", id="settings-close-btn", variant="default")

    def _get_models_label(self) -> str:
        """Get the label for the models dropdown button."""
        count = len(self._model_configs)
        if count == 0:
            return "Models"
        return f"Models ({count})"

    def _get_model_items(self) -> list[str]:
        """Get the list of model items for the dropdown."""
        if not self._model_configs:
            return ["No models configured"]
        return [f"[{c.provider}] {c.model}" for c in self._model_configs]

    def on_mount(self) -> None:
        """Set up the tabs on mount."""
        header = self.query_one("#tab-header", TabHeader)
        header.add_tab("run-evals", "Evals", closable=False, activate=True)
        header.add_tab("view-progress", "Progress", closable=False, activate=False)
        header.add_tab("settings", "Settings", closable=False, activate=False)
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
            return

        if tab_id == "settings":
            self._restore_settings_state()

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

    def _restore_settings_state(self) -> None:
        """Restore settings tab state."""
        content = self.query_one("#settings-pane", SettingsContent)
        content.focus()

    def on_settings_content_settings_changed(
        self, event: SettingsContent.SettingsChanged
    ) -> None:
        """Handle settings changes - save to disk."""
        event.stop()
        self._settings = event.settings
        self._settings_manager.save(self._settings)

    def on_job_list_content_job_selected(
        self, event: JobListContent.JobSelected
    ) -> None:
        """Handle job selection - open job detail modal."""
        event.stop()
        job = self._job_manager.get_job(event.job_id)
        if job is None:
            self.notify(f"Job {event.job_id} not found", severity="error")
            return
        results = self._job_manager.get_job_results(event.job_id)
        self.app.push_screen(JobDetailModal(job=job, results=results))

    def on_run_evals_content_run_requested(
        self, event: RunEvalsContent.RunRequested
    ) -> None:
        """Handle run request from RunEvalsContent."""
        event.stop()
        self._run_selected(event.selected_benchmarks)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id in ("cancel-btn", "close-btn", "settings-close-btn"):
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
        """Validate and create a job for all configured models."""
        if not selected_benchmarks:
            self.notify("Please select at least one benchmark", severity="warning")
            return

        if not self._model_configs:
            self.notify("Please configure a model first", severity="error")
            return

        job = self._job_manager.create_job(
            benchmarks=selected_benchmarks,
            models=self._model_configs,
            settings=self._settings,
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
