"""AgentItem widget - display card for an AI agent.

Matches Toad's visual design.
"""

from textual import containers, widgets
from textual.app import ComposeResult
from textual.content import Content


# Pill colors by type (Dracula theme)
TYPE_COLORS = {
    "coding": ("#BD93F9", "#282A36"),   # Purple
    "general": ("#FFB86C", "#282A36"),  # Orange
    "chat": ("#50FA7B", "#282A36"),     # Green
    "mix": ("#8BE9FD", "#282A36"),      # Cyan
}


def pill(text: str, background: str, foreground: str) -> Content:
    """Format text as a pill (half block ends)."""
    main_style = f"{foreground} on {background}"
    end_style = f"{background} on transparent r"
    return Content.assemble(
        ("▌", end_style),
        (text, main_style),
        ("▐", end_style),
    )


class AgentItem(containers.VerticalGroup):
    """An entry in the Agent grid select."""

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        author_name: str,
        description: str,
        agent_type: str,
    ) -> None:
        super().__init__()
        self.agent_id = agent_id
        self._agent_name = agent_name
        self._author_name = author_name
        self._description = description
        self._type = agent_type

    def compose(self) -> ComposeResult:
        bg, fg = TYPE_COLORS.get(self._type, TYPE_COLORS["coding"])
        with containers.Grid():
            yield widgets.Label(self._agent_name, id="name")
            tag = pill(self._type, bg, fg)
            yield widgets.Label(tag, id="type")
        yield widgets.Label(self._author_name, id="author")
        yield widgets.Static(self._description, id="description")
