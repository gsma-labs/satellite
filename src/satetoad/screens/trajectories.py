"""Trajectories screen - displays evaluation data from Inspect AI JSON logs.

This screen displays evaluation trajectories in a structured format:
- PROMPT: The user's question (truncated, expandable)
- REASONING: Agent's thinking process (hidden if encrypted)
- ANSWER: Agent's final response
- COMPARISON: Side-by-side Target vs LLM Answer
"""

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Static, Button
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.reactive import reactive

from satetoad.widgets.trajectory_sections import (
    PromptSection,
    ReasoningSection,
    AnswerSection,
    ComparisonSection,
)


# Hardcoded path for demo
DEFAULT_LOG_PATH = Path(
    "/Users/emolero/Documents/GitHub/ot/evals/logs/"
    "2026-01-15T19-47-30+00-00_three-gpp_nkJ4nWLjSvHLiFtHYELGDj.json"
)

# Security: Allowed directory for log files
ALLOWED_LOG_DIR = Path("/Users/emolero/Documents/GitHub/ot/evals/logs/")

# Security: Maximum JSON file size (10MB)
MAX_JSON_SIZE = 10 * 1024 * 1024


class TrajectoriesScreen(Screen):
    """Screen for viewing evaluation trajectories.

    Layout:
    +---------------------------------------------+
    | Trajectory Viewer          Sample 1 of 10   |
    | three-gpp_nkJ4nWLj...json        [<] [>]    |
    +---------------------------------------------+
    |                                             |
    | PROMPT:                                     |
    | +------------------------------------------+|
    | | As a distinguished expert in telecom...  ||
    | | ... [truncated - click to expand]        ||
    | +------------------------------------------+|
    |                                             |
    | REASONING:                                  |
    | +------------------------------------------+|
    | | (Agent reasoning if available)           ||
    | +------------------------------------------+|
    |                                             |
    | ANSWER:                                     |
    | +------------------------------------------+|
    | | {"WORKING GROUP": "SA5"}                 ||
    | +------------------------------------------+|
    |                                             |
    | +--------------------+---------------------+|
    | |  Target: SA5       |  LLM: SA5      V    ||
    | +--------------------+---------------------+|
    +---------------------------------------------+
    """

    BINDINGS = [
        Binding("left", "prev_sample", "Previous", show=True),
        Binding("right", "next_sample", "Next", show=True),
        Binding("escape", "back", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    current_sample_index: reactive[int] = reactive(0)

    def __init__(self, log_path: Path | None = None) -> None:
        super().__init__()
        self.log_path = self._validate_log_path(log_path)
        self.samples: list[dict] = []
        self._load_data()

    def _validate_log_path(self, log_path: Path | None) -> Path:
        """Validate and sanitize the log path to prevent path traversal.

        Args:
            log_path: User-provided path or None for default

        Returns:
            Validated path within the allowed directory

        Raises:
            ValueError: If path is outside allowed directory
        """
        if log_path is None:
            return DEFAULT_LOG_PATH

        try:
            resolved = log_path.resolve()
            allowed = ALLOWED_LOG_DIR.resolve()
            # Ensure path is within allowed directory
            resolved.relative_to(allowed)
            return resolved
        except ValueError:
            # Path is outside allowed directory - use default
            return DEFAULT_LOG_PATH

    def _load_data(self) -> None:
        """Load JSON log file with size validation."""
        try:
            # Security: Check file size before loading
            file_size = self.log_path.stat().st_size
            if file_size > MAX_JSON_SIZE:
                raise ValueError(f"File too large: {file_size} bytes (max {MAX_JSON_SIZE})")

            with open(self.log_path) as f:
                data = json.load(f)
            self.samples = data.get("samples", [])
        except (FileNotFoundError, json.JSONDecodeError, ValueError, OSError) as e:
            self.samples = []
            self.notify(f"Error loading log: {e}", severity="error")

    @property
    def total_samples(self) -> int:
        return len(self.samples)

    @property
    def current_sample(self) -> dict | None:
        if 0 <= self.current_sample_index < self.total_samples:
            return self.samples[self.current_sample_index]
        return None

    def compose(self) -> ComposeResult:
        # Header with navigation
        with Horizontal(id="trajectory-header"):
            with Vertical(id="header-info"):
                yield Static("[bold]Trajectory Viewer[/]", id="title")
                yield Static(f"[dim]{self.log_path.name}[/]", id="file-info")
            with Horizontal(id="header-nav"):
                yield Static("", id="sample-counter")
                yield Button("<", id="prev-btn", classes="-nav-btn")
                yield Button(">", id="next-btn", classes="-nav-btn")

        # Main content - sections
        yield VerticalScroll(id="trajectory-content")

        yield Footer()

    def on_mount(self) -> None:
        """Render initial sample."""
        self._render_sample()
        self._update_navigation()

    def watch_current_sample_index(self, new_index: int) -> None:
        """Re-render when sample changes."""
        self._render_sample()
        self._update_navigation()

    def _render_sample(self) -> None:
        """Render sections for current sample."""
        try:
            content = self.query_one("#trajectory-content", VerticalScroll)
        except Exception:
            return

        content.remove_children()

        sample = self.current_sample
        if not sample:
            content.mount(Static("[dim]No samples available[/]"))
            return

        # Extract data from sample
        prompt = sample.get("input", "")
        target = sample.get("target", "")

        # Extract reasoning and answer from assistant message
        reasoning, answer = self._extract_assistant_content(sample)

        # Extract LLM's answer from scores (default to raw answer)
        scores = sample.get("scores", {})
        llm_answer = answer
        for scorer_name in ["pattern", "match", "accuracy"]:
            if scorer_name in scores:
                llm_answer = scores[scorer_name].get("answer", "")
                break

        # Mount sections
        content.mount(PromptSection(prompt))

        # Only mount reasoning if it's available and not encrypted
        reasoning_section = ReasoningSection(reasoning)
        if reasoning_section.display:
            content.mount(reasoning_section)

        content.mount(AnswerSection(answer))
        content.mount(ComparisonSection(target=target, llm_answer=llm_answer))

    def _extract_assistant_content(self, sample: dict) -> tuple[str, str]:
        """Extract reasoning and answer from assistant message.

        Returns:
            tuple of (reasoning, answer)
        """
        messages = sample.get("messages", [])
        for msg in messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", [])
                if isinstance(content, list):
                    reasoning = ""
                    answer = ""
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get("type", "")
                            if block_type == "reasoning":
                                reasoning = self._parse_reasoning(block.get("reasoning", ""))
                            elif block_type == "text":
                                answer = block.get("text", "")
                    return reasoning, answer
                else:
                    # Simple string content
                    return "", str(content)
        return "", ""

    def _parse_reasoning(self, reasoning_data: str) -> str:
        """Parse reasoning data, handling encrypted or JSON formats.

        Returns empty string for encrypted reasoning.
        """
        if not reasoning_data:
            return ""

        # Check if it's encrypted
        if "encrypted" in reasoning_data.lower():
            return ""

        # Try to parse as JSON
        try:
            data = json.loads(reasoning_data)
            if isinstance(data, list):
                # Check for encrypted type in list
                for item in data:
                    if isinstance(item, dict):
                        if "encrypted" in item.get("type", "").lower():
                            return ""
                        # Extract actual reasoning text if available
                        if "text" in item:
                            return item["text"]
            elif isinstance(data, dict):
                if "encrypted" in data.get("type", "").lower():
                    return ""
                return data.get("text", str(data))
        except json.JSONDecodeError:
            pass

        # Return as-is if not JSON
        return reasoning_data

    def _update_navigation(self) -> None:
        """Update navigation bar state."""
        try:
            counter = self.query_one("#sample-counter", Static)
            counter.update(f"Sample {self.current_sample_index + 1} of {self.total_samples}")

            prev_btn = self.query_one("#prev-btn", Button)
            next_btn = self.query_one("#next-btn", Button)

            prev_btn.disabled = self.current_sample_index <= 0
            next_btn.disabled = self.current_sample_index >= self.total_samples - 1
        except Exception:
            pass

    def action_prev_sample(self) -> None:
        """Navigate to previous sample."""
        if self.current_sample_index > 0:
            self.current_sample_index -= 1

    def action_next_sample(self) -> None:
        """Navigate to next sample."""
        if self.current_sample_index < self.total_samples - 1:
            self.current_sample_index += 1

    def action_back(self) -> None:
        """Return to previous screen."""
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Return to previous screen."""
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle navigation button presses."""
        if event.button.id == "prev-btn":
            self.action_prev_sample()
            return
        if event.button.id == "next-btn":
            self.action_next_sample()
