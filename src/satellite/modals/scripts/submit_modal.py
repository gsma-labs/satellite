"""SubmitModal - Multi-state modal for submitting evaluation results to the leaderboard.

States:
1. Model Selection — pick an eligible model (or see "no eligible models" message)
2. Preview — review scores and file count before submitting
3. Submitting — loading indicator while PR is created
4. Result — success (PR URL) or error message

Uses CSS-driven state switching (same pattern as TabbedEvalsModal).
"""

from pathlib import Path
from typing import ClassVar

from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, LoadingIndicator, OptionList, Static
from textual.widgets.option_list import Option

from satellite.services.config.env_config_manager import EnvConfigManager
from satellite.services.evals import BENCHMARKS_BY_ID
from satellite.services.evals.job_manager import Job, JobManager
from satellite.services.submit import (
    GITHUB_TOKEN_ENV_VAR,
    SubmitPreview,
    SubmitResult,
    build_submit_preview,
    get_eligible_models,
    submit_to_leaderboard,
)

# States as CSS class names
_STATE_SELECT = "-state-select"
_STATE_PREVIEW = "-state-preview"
_STATE_SUBMITTING = "-state-submitting"
_STATE_RESULT = "-state-result"
_ALL_STATES = (_STATE_SELECT, _STATE_PREVIEW, _STATE_SUBMITTING, _STATE_RESULT)


class SubmitModal(ModalScreen[SubmitResult | None]):
    """Modal for submitting evaluation results to the leaderboard.

    Returns SubmitResult on successful submission, None on cancel.
    """

    CSS_PATH = "../styles/modal_base.tcss"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self, job_manager: JobManager, jobs_dir: Path, env_manager: EnvConfigManager
    ) -> None:
        super().__init__()
        self._job_manager = job_manager
        self._jobs_dir = jobs_dir
        self._env_manager = env_manager
        self._eligible_models: list[tuple[Job, str, dict[str, float]]] = []
        self._preview: SubmitPreview | None = None
        self._result: SubmitResult | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="container"):
            yield Static("Submit to Leaderboard", classes="modal-title")

            # State 1: Model Selection
            with Vertical(id="select-pane", classes="submit-pane"):
                yield Static("", id="select-description", classes="section-label")
                yield VerticalScroll(id="model-list-scroll")
                with Horizontal(id="select-buttons", classes="button-row"):
                    yield Button("Cancel", id="cancel-btn", variant="default")

            # State 2: Preview
            with Vertical(id="preview-pane", classes="submit-pane"):
                yield Static("", id="preview-info")
                yield VerticalScroll(id="scores-scroll")
                with Horizontal(id="preview-buttons", classes="button-row"):
                    yield Button("Back", id="back-btn", variant="default")
                    yield Button(
                        "Submit to Leaderboard", id="submit-btn", variant="primary"
                    )

            # State 3: Submitting
            with Vertical(id="submitting-pane", classes="submit-pane"):
                with Center(id="submit-loading-container"):
                    yield LoadingIndicator(id="submit-loading")
                    yield Static("Creating pull request...", id="submit-loading-text")

            # State 4: Result
            with Vertical(id="result-pane", classes="submit-pane"):
                yield Static("", id="result-message")
                yield Static("", id="result-pr-url")
                with Horizontal(id="result-buttons", classes="button-row"):
                    yield Button("Close", id="close-btn", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#container").styles.opacity = 1.0
        self._eligible_models = get_eligible_models(self._job_manager)
        self._populate_model_list()
        self._switch_state(_STATE_SELECT)

    def _switch_state(self, state: str) -> None:
        for s in _ALL_STATES:
            self.remove_class(s)
        self.add_class(state)

    def _populate_model_list(self) -> None:
        description = self.query_one("#select-description", Static)
        scroll = self.query_one("#model-list-scroll", VerticalScroll)

        if not self._eligible_models:
            description.update(
                "[warning]No eligible models found.[/]\n\n"
                "A model is eligible when it has completed [bold]all[/bold] "
                f"{len(BENCHMARKS_BY_ID)} benchmarks\n"
                "(TeleQnA, TeleLogs, TeleMath, TeleTables, 3GPP)\n"
                "with valid scores."
            )
            return

        description.update(
            f"[bold]{len(self._eligible_models)}[/bold] eligible model(s) found. "
            "Select one to submit:"
        )

        option_list = OptionList(id="model-options")
        scroll.mount(option_list)

        for index, (job, model, scores) in enumerate(self._eligible_models):
            avg_score = sum(scores.values()) / len(scores) if scores else 0
            label = f"{escape(model)}  [dim]({job.id}, {len(scores)} evals, avg {avg_score:.1%})[/dim]"
            option_list.add_option(Option(label, id=str(index)))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle model selection from the option list."""
        event.stop()
        index = int(str(event.option.id))
        job, model, scores = self._eligible_models[index]
        self._preview = build_submit_preview(job, model, scores, self._jobs_dir)
        self._show_preview()

    def _show_preview(self) -> None:
        if self._preview is None:
            return

        info_lines = [
            f"[bold]Model:[/bold] {escape(self._preview.model)}",
            f"[bold]Provider:[/bold] {escape(self._preview.provider)}",
            f"[bold]Directory:[/bold] {escape(self._preview.model_dir_name)}",
            f"[bold]Files:[/bold] {len(self._preview.log_files)} trajectory file(s)",
        ]
        self.query_one("#preview-info", Static).update("\n".join(info_lines))

        scores_scroll = self.query_one("#scores-scroll", VerticalScroll)
        scores_scroll.remove_children()

        for bench_id in sorted(self._preview.scores.keys()):
            score = self._preview.scores[bench_id]
            bench = BENCHMARKS_BY_ID.get(bench_id)
            name = bench.name if bench else bench_id
            scores_scroll.mount(Label(f"  {name}: [bold]{score:.4f}[/bold]"))

        self._switch_state(_STATE_PREVIEW)

    def _start_submit(self) -> None:
        if self._preview is None:
            return
        self._switch_state(_STATE_SUBMITTING)
        self._do_submit(self._preview)

    @work(exclusive=True, thread=True)
    def _do_submit(self, preview: SubmitPreview) -> None:
        token = self._env_manager.get_var(GITHUB_TOKEN_ENV_VAR)
        result = submit_to_leaderboard(preview, token)
        self.app.call_from_thread(self._show_result, result)

    def _show_result(self, result: SubmitResult) -> None:
        self._result = result
        message = self.query_one("#result-message", Static)
        pr_url = self.query_one("#result-pr-url", Static)

        match result.status:
            case "success":
                message.update("[bold #50FA7B]Submission successful![/]")
                pr_url.update(f"PR: {escape(result.pr_url or '')}")
            case "error":
                message.update(
                    f"[bold #FF5555]Submission failed[/]\n\n{escape(result.error or '')}"
                )
                pr_url.update("")

        self._switch_state(_STATE_RESULT)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        match event.button.id:
            case "cancel-btn":
                self.dismiss(None)
            case "back-btn":
                self._switch_state(_STATE_SELECT)
            case "submit-btn":
                self._start_submit()
            case "close-btn":
                self.dismiss(self._result)

    def action_cancel(self) -> None:
        self.dismiss(None)
