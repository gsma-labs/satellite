# Re-enabling the Agents Section

## Files to restore

1. **Move widget back:**
   ```bash
   mv future_work/agent_item.py src/satetoad/widgets/agent_item.py
   ```

2. **Append CSS** from `future_work/agent_boxes.tcss` to the end of `src/satetoad/main.tcss`.

3. **In `src/satetoad/screens/main.py`**, apply the diffs below.

## main.py changes

### Imports — add these lines

```python
from satetoad.examples.eval_data import (
    AGENTS,              # add
    AGENTS_BY_SHORTCUT,  # add
    ...
)
from satetoad.widgets.agent_item import AgentItem  # add
```

### BINDINGS — add after the model keys (4-7)

```python
        # Agent quick launch keys
        Binding("8", "launch_agent('8')", "React", show=False),
        Binding("9", "launch_agent('9')", "Claude Code", show=False),
        Binding("a", "launch_agent('a')", "Codex CLI", show=False),
        Binding("b", "launch_agent('b')", "Gemini CLI", show=False),
        Binding("d", "launch_agent('d')", "OpenHands", show=False),
        Binding("e", "launch_agent('e')", "OpenCode", show=False),
```

### compose() — add after the model-boxes GridSelect, before `yield Footer()`

```python
        # Agents section heading
        yield Static("Agents", classes="heading")

        # Agent grid (Choose your fighter)
        with GridSelect(id="agent-boxes", min_column_width=32, max_column_width=50):
            for agent in AGENTS:
                yield AgentItem(
                    agent_id=agent["id"],
                    agent_name=agent["name"],
                    author_name=agent["author_name"],
                    description=agent["description"],
                    agent_type=agent["type"],
                )
```

### Navigation handlers — add after `on_model_leave_up`

```python
    @on(GridSelect.LeaveDown, "#model-boxes")
    def on_model_leave_down(self, event: GridSelect.LeaveDown) -> None:
        """Move focus from model-boxes to agent-boxes when pressing down at bottom."""
        self.query_one("#agent-boxes", GridSelect).focus_at_column(
            event.column_x, from_direction="down"
        )

    @on(GridSelect.LeaveUp, "#agent-boxes")
    def on_agent_leave_up(self, event: GridSelect.LeaveUp) -> None:
        """Move focus from agent-boxes back to model-boxes when pressing up at top."""
        self.query_one("#model-boxes", GridSelect).focus_at_column(
            event.column_x, from_direction="up"
        )
```

### on_box_selected — add this block at the top of the method body

```python
        # Handle agent items
        if hasattr(widget, "agent_id"):
            self._launch_agent(widget.agent_id, widget._agent_name)
            return
```

### Action methods — add anywhere in the class

```python
    def action_launch_agent(self, shortcut: str) -> None:
        """Launch agent by shortcut key."""
        agent = AGENTS_BY_SHORTCUT.get(shortcut)
        if agent is None:
            return
        self._launch_agent(agent["id"], agent["name"])

    def _launch_agent(self, agent_id: str, agent_name: str) -> None:
        """Launch an agent (mock - just show notification)."""
        self.notify(
            f"Launching {agent_name}...",
            title="Agent Launch",
        )
```
