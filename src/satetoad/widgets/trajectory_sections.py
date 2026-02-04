"""Trajectory section widgets for displaying evaluation data.

Widgets for the TrajectoriesScreen:
- PromptSection: Truncated prompt with expand capability
- ReasoningSection: Agent reasoning (hidden if encrypted)
- AnswerSection: Agent's final answer
- ComparisonSection: Side-by-side Target vs LLM comparison
"""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Markdown
from textual.reactive import var


class PromptSection(Vertical, can_focus=True):
    """Truncated prompt with expand capability.

    Click or press space to expand/collapse.
    Based on toad-reference AgentThought pattern.
    """

    expanded: var[bool] = var(False, toggle_class="-expanded")

    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

    def compose(self) -> ComposeResult:
        yield Static("[bold]PROMPT:[/]", classes="section-label")
        yield Markdown(self.content, id="prompt-content")

    def on_click(self) -> None:
        """Toggle expanded state on click."""
        self.expanded = not self.expanded

    def key_space(self) -> None:
        """Toggle expanded state on space."""
        self.expanded = not self.expanded


class ReasoningSection(Vertical):
    """Formatted reasoning display.

    Hidden entirely if reasoning is encrypted or unavailable.
    """

    def __init__(self, reasoning: str) -> None:
        super().__init__()
        self.reasoning = reasoning
        # Hide if empty or encrypted
        is_encrypted = "encrypted" in reasoning.lower() if reasoning else True
        self.display = not is_encrypted and bool(reasoning)

    def compose(self) -> ComposeResult:
        yield Static("[bold]REASONING:[/]", classes="section-label")
        yield Static(self.reasoning, id="reasoning-content")


class AnswerSection(Vertical):
    """Agent's final answer."""

    def __init__(self, answer: str) -> None:
        super().__init__()
        self.answer = answer

    def compose(self) -> ComposeResult:
        yield Static("[bold]ANSWER:[/]", classes="section-label")
        yield Static(self.answer, id="answer-content")


class ComparisonSection(Horizontal):
    """Side-by-side Target vs LLM comparison."""

    def __init__(self, target: str, llm_answer: str) -> None:
        super().__init__()
        self.target = target
        self.llm_answer = llm_answer

    def compose(self) -> ComposeResult:
        is_correct = self.target == self.llm_answer
        icon = "[green]✓[/]" if is_correct else "[red]✗[/]"

        yield Static(f"[bold]Target:[/] {self.target}", id="target")
        yield Static(f"[bold]LLM:[/] {self.llm_answer} {icon}", id="llm")
