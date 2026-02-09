"""AgentList widget - navigable list of agent items."""

from dataclasses import dataclass

from textual import containers
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from satellite.widgets.agent_item import AgentItem


class AgentList(containers.VerticalScroll, can_focus=True):
    """Navigable list of AI agents."""

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("enter", "launch", "Launch", show=False),
        Binding("space", "launch", "Launch", show=False),
    ]

    highlighted: reactive[int | None] = reactive(None)

    @dataclass
    class AgentSelected(Message):
        """Posted when an agent is selected for launch."""

        agent_list: "AgentList"
        agent_id: str
        agent_name: str

        @property
        def control(self) -> Widget:
            return self.agent_list

    def __init__(
        self,
        agents: list[dict],
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._agents = agents

    def compose(self):
        """Compose the agent items."""
        for agent in self._agents:
            yield AgentItem(
                agent_id=agent["id"],
                name=agent["name"],
                author_name=agent["author_name"],
                description=agent["description"],
                agent_type=agent["type"],
            )

    def on_focus(self) -> None:
        """Highlight first item when focused."""
        if self.highlighted is None and self._agents:
            self.highlighted = 0

    def on_blur(self) -> None:
        """Clear highlight when blurred."""
        self.highlighted = None

    def watch_highlighted(self, old: int | None, new: int | None) -> None:
        """Update CSS classes when highlight changes."""
        children = list(self.query(AgentItem))
        if old is not None and old < len(children):
            children[old].remove_class("-highlight")
        if new is not None and new < len(children):
            children[new].add_class("-highlight")
            children[new].scroll_visible()

    def validate_highlighted(self, value: int | None) -> int | None:
        """Clamp highlight to valid range."""
        if value is None or not self._agents:
            return None
        return max(0, min(value, len(self._agents) - 1))

    def action_cursor_up(self) -> None:
        """Move highlight up."""
        if self.highlighted is None:
            self.highlighted = 0
            return
        if self.highlighted > 0:
            self.highlighted -= 1

    def action_cursor_down(self) -> None:
        """Move highlight down."""
        if self.highlighted is None:
            self.highlighted = 0
            return
        if self.highlighted < len(self._agents) - 1:
            self.highlighted += 1

    def action_launch(self) -> None:
        """Launch the highlighted agent."""
        if self.highlighted is None:
            return
        agent = self._agents[self.highlighted]
        self.post_message(self.AgentSelected(self, agent["id"], agent["name"]))

    def on_click(self, event) -> None:
        """Handle click to highlight and launch agent."""
        for widget in event.widget.ancestors_with_self:
            if isinstance(widget, AgentItem):
                children = list(self.query(AgentItem))
                if widget in children:
                    index = children.index(widget)
                    self.highlighted = index
                    self.action_launch()
                break
        self.focus()
