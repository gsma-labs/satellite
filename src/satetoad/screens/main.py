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

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, VerticalGroup
from textual.screen import Screen
from textual.widgets import Footer, Static

from satetoad.examples.eval_data import (
    APP_INFO,
    EVAL_BOXES,
    MODEL_BOXES,
)
from satetoad.modals import (
    EnvVarsModal,
    LeaderboardModal,
    ModelConfig,
    SetModelModal,
    SubmitModal,
    SubmitResult,
    TabbedEvalsModal,
)
from satetoad.services.config import EnvConfigManager, EvalSettingsManager
from satetoad.services.evals import EvalResult, Job, JobManager
from satetoad.services.evals.job_manager import DEFAULT_JOBS_DIR
from satetoad.widgets.eval_box import EvalBox
from satetoad.widgets.grid_select import GridSelect
from satetoad.widgets.julia_set import JuliaSet

# Project root (4 levels up from screens/main.py: screens → satetoad → src → root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"


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
        Binding("c", "env_vars", "Env Vars"),
        Binding("f", "quick_launch", "", show=False),
        # Resume
        Binding("ctrl+r", "resume", "Resume", show=False),
        Binding("?", "help", "Help", show=False),
    ]

    # Store configured models (set via modal, supports multi-model)
    _configured_models: list[ModelConfig] = []

    # Store evaluation results (benchmark_id -> score)
    _eval_results: dict[str, float] | None = None

    # Job manager for persistent job storage
    _job_manager: JobManager | None = None

    # Environment config manager for .env persistence
    _env_config_manager: EnvConfigManager | None = None

    # Eval settings manager for settings persistence
    _settings_manager: EvalSettingsManager | None = None

    def compose(self) -> ComposeResult:
        """Compose the evaluation interface layout.

        Layout:
        - Header with Julia set fractal + app info
        - Top row: Action boxes (Evals, Leaderboard, Submit)
        - "Models" heading with underline
        - Model category boxes (Lab APIs, Cloud APIs, Open Hosted, Open Local)
        """
        # Initialize managers
        self._job_manager = JobManager(DEFAULT_JOBS_DIR)
        self._settings_manager = EvalSettingsManager()

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
        """Initialize managers and load persisted models on mount."""
        self._env_config_manager = EnvConfigManager(_ENV_PATH)
        self._load_models_from_env()
        self.query_one("#action-boxes", GridSelect).focus()

    def _load_models_from_env(self) -> None:
        """Load models from .env file into _configured_models."""
        if self._env_config_manager is None:
            return
        self._configured_models = self._env_config_manager.load_models()

    def _get_info(self) -> str:
        """Generate app info text."""
        return f"""\
🛰️ [bold]{APP_INFO["name"]}[/bold] [dim]v{APP_INFO["version"]}[/dim]  [@click=screen.open_logs][underline]Logs[/underline][/]
[#50FA7B]{APP_INFO["tagline"]}[/#50FA7B]




[dim]Developed by [@click=screen.open_site][underline]GSMA Labs[/underline][/][/dim]
"""

    def action_open_logs(self) -> None:
        """Open the logs URL in browser."""
        import webbrowser

        webbrowser.open("http://localhost:7575")

    def action_open_site(self) -> None:
        """Open the GSMA Labs website."""
        import webbrowser

        webbrowser.open("https://www.gsma.com/")

    @on(GridSelect.LeaveDown, "#action-boxes")
    def on_action_leave_down(self, event: GridSelect.LeaveDown) -> None:
        """Move focus from action-boxes to model-boxes when pressing down at bottom."""
        self.query_one("#model-boxes", GridSelect).focus_at_column(
            event.column_x, from_direction="down"
        )

    @on(GridSelect.LeaveUp, "#model-boxes")
    def on_model_leave_up(self, event: GridSelect.LeaveUp) -> None:
        """Move focus from model-boxes back to action-boxes when pressing up at top."""
        self.query_one("#action-boxes", GridSelect).focus_at_column(
            event.column_x, from_direction="up"
        )

    @on(GridSelect.Selected)
    def on_box_selected(self, event: GridSelect.Selected) -> None:
        """Handle box selection - open corresponding modal overlay."""
        widget = event.selected_widget

        if not hasattr(widget, "box_id"):
            return

        # Model categories that open filtered modal
        model_categories = {"lab-apis", "cloud-apis", "open-hosted", "open-local"}

        if widget.box_id in model_categories:
            self._show_model_modal(widget.box_id)
            return

        handlers = {
            "evals": self._show_evals_modal,
            "leaderboard": self._show_leaderboard_modal,
            "submit": self._show_submit_modal,
        }
        handler = handlers.get(widget.box_id)
        if handler:
            handler()

    def _show_model_modal(self, category: str) -> None:
        """Push the SetModelModal filtered for the given category."""
        self._load_models_from_env()
        self.app.push_screen(
            SetModelModal(
                category=category,
                initial_models=self._configured_models,
                env_manager=self._env_config_manager,
            ),
            callback=self._on_model_config_saved,
        )

    def _on_model_config_saved(self, configs: list[ModelConfig] | None) -> None:
        """Handle the result from SetModelModal.

        Models are persisted immediately on Add/Delete in the modal.
        - If configs is None: user cancelled, .env already rolled back
        - If configs is not None: user saved, .env already up to date
        """
        if configs is None:
            # User cancelled - .env already rolled back by modal, refresh in-memory
            self._load_models_from_env()
            return

        # User saved - .env already up to date, just update in-memory
        self._configured_models = configs

        model_count = len(configs)
        if model_count == 1:
            self.notify(
                f"Provider: {configs[0].provider}\nModel: {configs[0].model}",
                title="Model Configured",
            )
            return

        if model_count > 1:
            model_names = ", ".join(c.model for c in configs[:3])
            if model_count > 3:
                model_names += f" (+{model_count - 3} more)"
            self.notify(
                f"{model_count} models configured:\n{model_names}",
                title="Models Configured",
            )

    def _show_evals_modal(self) -> None:
        """Push the TabbedEvalsModal for running evals and viewing progress."""
        self.app.push_screen(
            TabbedEvalsModal(
                job_manager=self._job_manager,
                settings_manager=self._settings_manager,
                model_configs=self._configured_models,
                on_start_job=self._start_job,
            ),
        )

    def _start_job(self, job: Job) -> None:
        """Start a job evaluation in a background thread."""
        model_count = len(job.evals)
        benchmark_count = len(next(iter(job.evals.values()), []))
        message = (
            f"Job {job.id}: {benchmark_count} benchmark(s) × {model_count} model(s)"
        )
        self.notify(message, title="Evaluation Started")
        self._run_job_evaluation(job)

    @work(exclusive=False, thread=True)
    def _run_job_evaluation(self, job: Job) -> None:
        """Run evaluation in background thread via subprocess."""
        if self._job_manager is None:
            return

        result = self.app._eval_runner.run_job(job)
        self.app.call_from_thread(self._on_job_evaluation_complete, job, result)

    def _on_job_evaluation_complete(self, job: Job, result: EvalResult) -> None:
        """Handle evaluation completion (called on main thread)."""
        if result.cancelled:
            self.notify(
                f"Job {job.id} was cancelled",
                title="Evaluation Cancelled",
                severity="warning",
            )
            return

        if result.success:
            self.notify(f"Job {job.id} completed!", title="Evaluation Complete")
            return

        error_msg = result.error or "Unknown error"
        self.notify(
            f"Job {job.id} failed: {error_msg}",
            title="Evaluation Failed",
            severity="error",
        )

    def _show_leaderboard_modal(self) -> None:
        """Push the LeaderboardModal for viewing rankings."""
        self.app.push_screen(LeaderboardModal(job_manager=self._job_manager))

    def _show_submit_modal(self) -> None:
        """Push the SubmitModal and handle the result via callback."""
        if self._job_manager is None:
            self.notify("Job manager not initialized", severity="error")
            return
        self.app.push_screen(
            SubmitModal(
                job_manager=self._job_manager,
                jobs_dir=self._job_manager.jobs_dir,
                env_manager=self._env_config_manager,
            ),
            callback=self._on_submit_completed,
        )

    def _on_submit_completed(self, result: SubmitResult | None) -> None:
        """Handle the result from SubmitModal."""
        if result is None:
            return
        if result.status == "success":
            self.notify(
                f"PR created: {result.pr_url}",
                title="Submission Complete",
            )
            return
        self.notify(
            f"Submission failed: {result.error}",
            title="Submission Error",
            severity="error",
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
        """Open Lab APIs modal (quick key 4)."""
        self._show_model_modal("lab-apis")

    def action_goto_cloud_apis(self) -> None:
        """Open Cloud APIs modal (quick key 5)."""
        self._show_model_modal("cloud-apis")

    def action_goto_open_hosted(self) -> None:
        """Open Open (Hosted) modal (quick key 6)."""
        self._show_model_modal("open-hosted")

    def action_goto_open_local(self) -> None:
        """Open Open (Local) modal (quick key 7)."""
        self._show_model_modal("open-local")

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
        """Handle quick launch for unassigned keys."""
        self.notify("No action assigned to this key.", title="Quick Launch")

    def action_env_vars(self) -> None:
        """Open Environment Variables modal (quick key c)."""
        if self._env_config_manager is None:
            self.notify("Environment manager not initialized", severity="error")
            return
        self.app.push_screen(
            EnvVarsModal(env_manager=self._env_config_manager),
            callback=self._on_env_vars_updated,
        )

    def _on_env_vars_updated(self, changes_made: bool) -> None:
        """Handle the result from EnvVarsModal."""
        if changes_made:
            # Reload models from .env since API keys may have changed
            self._load_models_from_env()
            self.notify("Environment variables updated", title="Saved")

    def action_resume(self) -> None:
        """Resume a previous session (placeholder)."""
        self.notify(
            "No previous session to resume.",
            title="Resume",
        )

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
