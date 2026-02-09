# Extending Satellite

This guide explains how to replace mock implementations with real functionality.

## Overview

Satellite is designed as a learning scaffold. Each mock component can be replaced:

| Component | Current | Real Implementation |
|-----------|---------|---------------------|
| Agent List | Static list | ACP agent discovery |
| Conversation | Mock messages | Agent communication |
| Plan | Static entries | Agent task updates |
| Project Tree | Mock structure | Real filesystem |

## Step 1: Real Agent Communication

### Current (Mock)

```python
# In prompt.py
MOCK_AGENTS = [
    ("claude-code", "Claude Code"),
    ("openhands", "OpenHands"),
]
```

### Real Implementation

1. **Add ACP dependencies**:
```toml
# pyproject.toml
dependencies = [
    "textual>=7.0.0",
    "httpx>=0.28.0",  # For ACP HTTP client
]
```

2. **Create agent registry**:
```python
# src/satellite/agents.py
import httpx

async def discover_agents() -> list[dict]:
    """Discover available ACP agents."""
    # Implementation depends on your agent protocol
    pass
```

3. **Update Prompt widget**:
```python
class Prompt(Widget):
    agents: var[list] = var([])

    async def on_mount(self) -> None:
        self.agents = await discover_agents()

    def compose(self) -> ComposeResult:
        yield Select(
            [(a["id"], a["name"]) for a in self.agents],
            id="agent-select",
        )
```

---

## Step 2: Real Conversation History

### Current (Mock)

```python
# In conversation.py
def compose(self) -> ComposeResult:
    with VerticalScroll(id="history"):
        yield UserInput("Hello!")
        yield AgentResponse("Hi there!")
```

### Real Implementation

1. **Create message store**:
```python
# src/satellite/history.py
from dataclasses import dataclass
from typing import Literal

@dataclass
class Message:
    role: Literal["user", "agent"]
    content: str
    timestamp: float

class History:
    def __init__(self):
        self._messages: list[Message] = []

    def add(self, role: str, content: str) -> None:
        self._messages.append(Message(role, content, time.time()))

    def get_all(self) -> list[Message]:
        return self._messages.copy()
```

2. **Update Conversation**:
```python
class Conversation(Widget):
    history: var[History] = var(lambda: History())

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="history"):
            for msg in self.history.get_all():
                if msg.role == "user":
                    yield UserInput(msg.content)
                else:
                    yield AgentResponse(msg.content)

    @on(Prompt.Submitted)
    def handle_submission(self, event: Prompt.Submitted) -> None:
        self.history.add("user", event.text)
        # Send to agent and await response...
        self.refresh(recompose=True)
```

---

## Step 3: Real Project Tree

### Current (Mock)

```python
# In project_tree.py
def compose(self) -> ComposeResult:
    tree = Tree("📁 satellite/")
    tree.root.add_leaf("📄 app.py")
    yield tree
```

### Real Implementation

Use Textual's `DirectoryTree`:

```python
from textual.widgets import DirectoryTree
from pathlib import Path

class ProjectTree(Widget):
    def __init__(self, path: Path = Path(".")):
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        yield DirectoryTree(self.path)
```

---

## Step 4: Real Plan Updates

### Current (Mock)

```python
# In plan.py
def __init__(self):
    self._entries = [
        PlanEntry("Analyze the codebase", "completed"),
        PlanEntry("Create widget stubs", "in_progress"),
    ]
```

### Real Implementation

1. **Create message type**:
```python
# src/satellite/messages.py
from textual.message import Message

class PlanUpdate(Message):
    def __init__(self, entries: list[dict]) -> None:
        self.entries = entries
        super().__init__()
```

2. **Handle agent plan updates**:
```python
class Plan(Widget):
    entries: var[list[PlanEntry]] = var([])

    @on(PlanUpdate)
    def handle_plan_update(self, event: PlanUpdate) -> None:
        self.entries = [
            PlanEntry(e["content"], e["status"])
            for e in event.entries
        ]
        self.refresh(recompose=True)
```

---

## Step 5: Streaming Responses

### Current (Mock)

```python
# AgentResponse shows complete text
yield AgentResponse("Full response here...")
```

### Real Implementation

1. **Update AgentResponse**:
```python
class AgentResponse(Widget):
    content: var[str] = var("")

    def watch_content(self, content: str) -> None:
        self.query_one(Markdown).update(content)

    def append(self, text: str) -> None:
        """Stream text incrementally."""
        self.content += text
```

2. **Stream from agent**:
```python
async def stream_response(response: AgentResponse):
    async for chunk in agent.stream():
        response.append(chunk)
```

---

## Step 6: Additional Screens

To add more screens (like Settings, Store):

1. **Create screen class**:
```python
# src/satellite/screens/settings.py
from textual.screen import Screen

class SettingsScreen(Screen):
    BINDINGS = [("escape", "dismiss", "Back")]

    def compose(self) -> ComposeResult:
        yield Label("Settings")

    def action_dismiss(self) -> None:
        self.app.pop_screen()
```

2. **Add navigation**:
```python
# In main.py
class MainScreen(Screen):
    BINDINGS = [
        ("f2", "show_settings", "Settings"),
    ]

    def action_show_settings(self) -> None:
        self.app.push_screen(SettingsScreen())
```

---

## Reference: Toad Implementation

For full implementations, see `toad-reference/`:

| Feature | Toad File |
|---------|-----------|
| Agent communication | `src/toad/acp/agent.py` |
| Conversation logic | `src/toad/widgets/conversation.py` |
| Plan updates | `src/toad/widgets/plan.py` |
| Directory tree | `src/toad/widgets/project_directory_tree.py` |
| Settings screen | `src/toad/screens/settings.py` |
| Agent store | `src/toad/screens/store.py` |

---

## Checklist

When extending satellite:

- [ ] Replace mock agent list with discovery
- [ ] Add real message history storage
- [ ] Implement agent communication protocol
- [ ] Add streaming response support
- [ ] Replace mock project tree with DirectoryTree
- [ ] Add plan update message handling
- [ ] Consider adding Settings screen
- [ ] Consider adding Agent Store screen

## Tips

1. **Incremental changes**: Replace one mock at a time
2. **Test each step**: Ensure UI still works after changes
3. **Study toad-reference**: See how full features are implemented
4. **Keep learning docs**: Update documentation as you extend
