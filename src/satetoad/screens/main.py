"""Main screen - Evaluation interface for Open Telco.

This is the landing page users see when launching satetoad.

Layout:
+---------------------------------------------+
|  [JuliaSet]    |  Satellite v0.1.0          |
+---------------------------------------------+
|  +----------+  +----------+  +----------+   |
|  | 1 Evals  |  | 2 Leader |  | 3 Submit |   |
+---------------------------------------------+
|  Models                                     |
|  ──────────                                 |
|  +----------+  +----------+                 |
|  | 4 Lab    |  | 5 Cloud  |                 |
|  |   APIs   |  |   APIs   |                 |
|  +----------+  +----------+                 |
|  +----------+  +----------+                 |
|  | 6 Open   |  | 7 Open   |                 |
|  | (Hosted) |  | (Local)  |                 |
|  +----------+  +----------+                 |
+---------------------------------------------+

All options open as modal overlays (Toad pattern) for a consistent UX.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer
from textual.binding import Binding
from textual.containers import VerticalGroup, Grid
from textual import on

from textual.widgets import Static
from satetoad.models.job import Job
from satetoad.services.job_manager import JobManager
from satetoad.widgets.julia_set import JuliaSet
from satetoad.widgets.grid_select import GridSelect
from satetoad.widgets.eval_box import EvalBox
from satetoad.modals import (
    ModelConfig,
    SetModelModal,
    LeaderboardModal,
    SubmitData,
    SubmitModal,
)
from satetoad.modals.tabbed_evals_modal import TabbedEvalsModal
from satetoad.examples.eval_data import EVAL_BOXES, MODEL_BOXES, APP_INFO


class MainScreen(Screen):
    """Evaluation interface screen - main dashboard.

    All options open as modal overlays (Toad pattern) for consistent UX.

    Top row: Action boxes (Evals, Leaderboard, Submit)
    Below: "Models" heading + 4 provider category boxes
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("tab", "app.focus_next", "switch tab"),
        Binding("shift+tab", "app.focus_previous", "Focus Previous", show=False),
        # Action boxes (1-3)
        Binding("1", "goto_evals", "Quick Launch", key_display="1-9 a-f", show=False),
        Binding("2", "goto_leaderboard", "Leaderboard", show=False),
        Binding("3", "goto_submit", "Submit", show=False),
        # Model category boxes (4-7)
        Binding("4", "goto_lab_apis", "Lab APIs", show=False),
        Binding("5", "goto_cloud_apis", "Cloud APIs", show=False),
        Binding("6", "goto_open_hosted", "Open Hosted", show=False),
        Binding("7", "goto_open_local", "Open Local", show=False),
        # Unused quick launch keys
        Binding("8", "quick_launch", "", show=False),
        Binding("9", "quick_launch", "", show=False),
        Binding("a", "quick_launch", "", show=False),
        Binding("b", "quick_launch", "", show=False),
        Binding("c", "quick_launch", "", show=False),
        Binding("d", "quick_launch", "", show=False),
        Binding("e", "quick_launch", "", show=False),
        Binding("f", "quick_launch", "", show=False),
        # Resume
        Binding("ctrl+r", "resume", "Resume", show=False),
        Binding("?", "help", "Help", show=False),
    ]

    # Store the current model configuration (set via modal)
    _current_config: ModelConfig | None = None

    # Store evaluation results (benchmark_id -> score)
    _eval_results: dict[str, float] | None = None

    # Job manager for persistent job storage
    _job_manager: JobManager | None = None

    def compose(self) -> ComposeResult:
        """Compose the evaluation interface layout.

        Layout:
        - Header with Julia set fractal + app info
        - Top row: Action boxes (Evals, Leaderboard, Submit)
        - "Models" heading with underline
        - Model category boxes (Lab APIs, Cloud APIs, Open Hosted, Open Local)
        """
        # Initialize job manager
        self._job_manager = JobManager()

        # Header with Julia set and app info side by side
        with VerticalGroup(id="header"):
            with Grid(id="title-grid"):
                yield JuliaSet()
                yield Static(self._get_info(), id="info")

        # Action boxes (Evals, Leaderboard, Submit)
        with GridSelect(id="action-boxes", min_column_width=24, max_column_width=45):
            for box in EVAL_BOXES:
                yield EvalBox(
                    digit=box["shortcut"],
                    name=box["name"],
                    description=box["description"],
                    box_id=box["id"],
                )

        # Models section heading (Toad pattern)
        yield Static("Models", classes="heading")

        # Model category boxes
        with GridSelect(id="model-boxes", min_column_width=24, max_column_width=45):
            for box in MODEL_BOXES:
                yield EvalBox(
                    digit=box["shortcut"],
                    name=box["name"],
                    description=box["description"],
                    box_id=box["id"],
                )

        yield Footer()

    def on_mount(self) -> None:
        """Focus the action boxes on screen mount."""
        self.query_one("#action-boxes", GridSelect).focus()

    def _get_info(self) -> str:
        """Generate app info text."""
        return f"""\
[bold]{APP_INFO['name']}[/] [dim]v{APP_INFO['version']}[/]
[#50FA7B]{APP_INFO['tagline']}[/]
[dim]{APP_INFO['subtitle']}[/]

[dim]Use arrow keys to navigate, Enter to select[/]
[dim]Press 1-3 for quick access[/]
"""

    @on(GridSelect.LeaveDown, "#action-boxes")
    def on_action_leave_down(self, event: GridSelect.LeaveDown) -> None:
        """Move focus from action-boxes to model-boxes when pressing down at bottom."""
        self.query_one("#model-boxes", GridSelect).focus()

    @on(GridSelect.LeaveUp, "#model-boxes")
    def on_model_leave_up(self, event: GridSelect.LeaveUp) -> None:
        """Move focus from model-boxes back to action-boxes when pressing up at top."""
        self.query_one("#action-boxes", GridSelect).focus()

    @on(GridSelect.Selected)
    def on_box_selected(self, event: GridSelect.Selected) -> None:
        """Handle box selection - open corresponding modal overlay."""
        widget = event.selected_widget
        if not hasattr(widget, "box_id"):
            return

        handlers = {
            # Action boxes
            "evals": self._show_evals_modal,
            "leaderboard": self._show_leaderboard_modal,
            "submit": self._show_submit_modal,
            # Model category boxes
            "lab-apis": lambda: self._show_model_modal("lab-apis", "Lab APIs"),
            "cloud-apis": lambda: self._show_model_modal("cloud-apis", "Cloud APIs"),
            "open-hosted": lambda: self._show_model_modal("open-hosted", "Open (Hosted)"),
            "open-local": lambda: self._show_model_modal("open-local", "Open (Local)"),
        }
        handler = handlers.get(widget.box_id)
        if handler:
            handler()

    def _show_model_modal(self, category: str, title: str) -> None:
        """Push the SetModelModal filtered to a specific provider category."""
        initial_provider = self._current_config.provider if self._current_config else None
        initial_api_key = self._current_config.api_key if self._current_config else ""
        initial_model = self._current_config.model if self._current_config else ""

        self.app.push_screen(
            SetModelModal(
                initial_provider=initial_provider,
                initial_api_key=initial_api_key,
                initial_model=initial_model,
                category=category,
                title=f"{title} - Model Configuration",
            ),
            callback=self._on_model_config_saved,
        )

    def _on_model_config_saved(self, config: ModelConfig | None) -> None:
        """Handle the result from SetModelModal."""
        if config is not None:
            self._current_config = config
            self.notify(
                f"Provider: {config.provider}\nModel: {config.model}",
                title="Configuration Saved",
            )

    def _show_evals_modal(self) -> None:
        """Push the TabbedEvalsModal for running evals and viewing progress."""
        self.app.push_screen(
            TabbedEvalsModal(
                model_config=self._current_config,
                job_manager=self._job_manager,
            ),
            callback=self._on_evals_completed,
        )

    def _on_evals_completed(self, job: Job | None) -> None:
        """Handle the result from TabbedEvalsModal."""
        if job is not None:
            # Notify user about the new job
            self.notify(
                f"Job {job.display_name} created with {len(job.benchmarks)} benchmark(s)",
                title="Evaluation Started",
            )

            # Mock running the job (in real app, this would run async)
            self._simulate_job_completion(job)

    def _simulate_job_completion(self, job: Job) -> None:
        """Simulate running a job and completing it with mock results.

        In a real application, this would be async and actually run
        the benchmarks against the model.
        """
        if self._job_manager is None:
            return

        # Mark as running
        self._job_manager.mark_job_running(job.id)

        # Generate mock results
        mock_results = {b: 0.75 + (hash(b) % 20) / 100 for b in job.benchmarks}

        # Mark as completed (with a slight delay for effect)
        def complete_job() -> None:
            if self._job_manager:
                self._job_manager.mark_job_completed(job.id, mock_results)
                self.notify(
                    f"Job {job.display_name} completed!",
                    title="Evaluation Complete",
                )
                # Store results for submission
                self._eval_results = mock_results

        # Use a timer to simulate async completion
        self.set_timer(2.0, complete_job)

    def _show_leaderboard_modal(self) -> None:
        """Push the LeaderboardModal and handle the result via callback."""
        self.app.push_screen(
            LeaderboardModal(),
            callback=self._on_leaderboard_closed,
        )

    def _on_leaderboard_closed(self, _result: None) -> None:
        """Handle the LeaderboardModal close (view-only, no return value)."""
        pass

    def _show_submit_modal(self) -> None:
        """Push the SubmitModal and handle the result via callback."""
        self.app.push_screen(
            SubmitModal(
                model_config=self._current_config,
                has_results=self._eval_results is not None,
            ),
            callback=self._on_submit_completed,
        )

    def _on_submit_completed(self, data: SubmitData | None) -> None:
        """Handle the result from SubmitModal."""
        if data is not None:
            self.notify(
                f"Submitted: {data.name}\nOrganization: {data.organization or 'N/A'}",
                title="Submission Complete",
            )

    def action_goto_evals(self) -> None:
        """Open Evals modal (quick key 1)."""
        self._show_evals_modal()

    def action_goto_leaderboard(self) -> None:
        """Open Leaderboard modal (quick key 2)."""
        self._show_leaderboard_modal()

    def action_goto_submit(self) -> None:
        """Open Submit modal (quick key 3)."""
        self._show_submit_modal()

    def action_goto_lab_apis(self) -> None:
        """Open Lab APIs model modal (quick key 4)."""
        self._show_model_modal("lab-apis", "Lab APIs")

    def action_goto_cloud_apis(self) -> None:
        """Open Cloud APIs model modal (quick key 5)."""
        self._show_model_modal("cloud-apis", "Cloud APIs")

    def action_goto_open_hosted(self) -> None:
        """Open Open (Hosted) model modal (quick key 6)."""
        self._show_model_modal("open-hosted", "Open (Hosted)")

    def action_goto_open_local(self) -> None:
        """Open Open (Local) model modal (quick key 7)."""
        self._show_model_modal("open-local", "Open (Local)")

    def action_help(self) -> None:
        """Show help."""
        self.notify(
            "Arrow keys: Navigate boxes\n"
            "Enter/Space: Select box\n"
            "1-3: Actions (Evals, Leaderboard, Submit)\n"
            "4-7: Models (Lab, Cloud, Hosted, Local)\n"
            "Escape: Close modal\n"
            "q: Quit",
            title="Help",
        )

    def action_quick_launch(self) -> None:
        """Handle quick launch for unassigned keys (5-9, a-f)."""
        self.notify("No action assigned to this key.", title="Quick Launch")

    def action_resume(self) -> None:
        """Resume a previous session (placeholder)."""
        self.notify(
            "No previous session to resume.",
            title="Resume",
        )

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
