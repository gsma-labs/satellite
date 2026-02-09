# Satellite Architecture

This document explains how satellite is structured and how components interact.

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        SatelliteApp                          │
│                         (app.py)                            │
│  - Loads CSS from main.tcss                                 │
│  - Pushes MainScreen on mount                               │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                       MainScreen                            │
│                    (screens/main.py)                        │
│  - Composes SideBar, Conversation, Footer                   │
│  - Handles keyboard bindings (Ctrl+B, Ctrl+Q)               │
└───────────────────────────┬─────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
    ┌───────────┐   ┌───────────────┐  ┌────────┐
    │  SideBar  │   │ Conversation  │  │ Footer │
    │           │   │               │  │        │
    │ ┌───────┐ │   │ ┌───────────┐ │  │ (key   │
    │ │ Plan  │ │   │ │ History   │ │  │ hints) │
    │ └───────┘ │   │ │ ┌───────┐ │ │  │        │
    │ ┌───────┐ │   │ │ │User   │ │ │  └────────┘
    │ │Project│ │   │ │ │Input  │ │ │
    │ │ Tree  │ │   │ │ └───────┘ │ │
    │ └───────┘ │   │ │ ┌───────┐ │ │
    └───────────┘   │ │ │Agent  │ │ │
                    │ │ │Resp   │ │ │
                    │ │ └───────┘ │ │
                    │ └───────────┘ │
                    │ ┌───────────┐ │
                    │ │ Throbber  │ │
                    │ └───────────┘ │
                    │ ┌───────────┐ │
                    │ │  Prompt   │ │
                    │ └───────────┘ │
                    │ ┌───────────┐ │
                    │ │   Flash   │ │
                    │ └───────────┘ │
                    └───────────────┘
```

## Component Relationships

### App → Screen

The `SatelliteApp` class:
1. Inherits from `textual.app.App`
2. Specifies `CSS_PATH` for styling
3. Pushes `MainScreen` in `on_mount()`

```python
class SatelliteApp(App):
    CSS_PATH = "main.tcss"

    def on_mount(self) -> None:
        self.push_screen(MainScreen())
```

### Screen → Widgets

The `MainScreen` class:
1. Inherits from `textual.screen.Screen`
2. Uses `compose()` to yield widgets
3. Uses containers for layout

```python
class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        with containers.Center():
            yield SideBar(...)
            yield Conversation()
        yield Footer()
```

### Widget → Child Widgets

Each widget can compose child widgets:

```python
class Conversation(Widget):
    def compose(self) -> ComposeResult:
        yield VerticalScroll(...)  # History
        yield Throbber()           # Loading
        yield Prompt()             # Input
        yield Flash()              # Notifications
```

## Data Flow

### User Input Flow

```
User types in Prompt
        │
        ▼
Prompt.Submitted message posted
        │
        ▼
Parent widget handles message
        │
        ▼
UserInput widget added to history
        │
        ▼
(In real app: Agent processes input)
        │
        ▼
AgentResponse widget added to history
```

### State Updates

```
Property changes (e.g., busy=True)
        │
        ▼
watch_busy() method called
        │
        ▼
CSS class updated (e.g., -busy)
        │
        ▼
Textual re-renders affected widgets
```

## File Organization

```
src/satellite/
├── app.py              # Entry point, App class
├── main.tcss           # All CSS styles
├── __main__.py         # python -m satellite
├── __init__.py         # Package init
│
├── screens/
│   ├── __init__.py
│   └── main.py         # MainScreen (the only screen)
│
├── widgets/
│   ├── __init__.py     # Widget exports
│   ├── README.md       # Widget patterns guide
│   │
│   │   # Core widgets
│   ├── conversation.py # Message container
│   ├── prompt.py       # User input
│   ├── sidebar.py      # Collapsible panels
│   │
│   │   # Display widgets
│   ├── agent_response.py
│   ├── user_input.py
│   ├── plan.py
│   ├── project_tree.py
│   │
│   │   # Utility widgets
│   ├── throbber.py
│   └── flash.py
│
├── docs/               # Documentation
│   ├── ARCHITECTURE.md # (this file)
│   ├── WIDGET_PATTERNS.md
│   └── EXTENDING.md
│
└── examples/
    └── mock_data.py    # Sample data
```

## Key Design Decisions

### 1. Single Screen

Satellite uses ONE screen only. This simplifies:
- Navigation logic
- State management
- Learning curve

### 2. Mock Data

All agent/conversation data is mocked. This allows:
- Focus on UI patterns
- No external dependencies
- Easy experimentation

### 3. CSS-Driven Visibility

Visibility states (busy, hidden) use CSS classes:
- `.add_class("-busy")` shows throbber
- `.add_class("-hidden")` hides sidebar
- Clean separation of state and presentation

### 4. Widget Composition

Widgets are composed hierarchically:
- `MainScreen` contains `Conversation`
- `Conversation` contains `Prompt`
- `Prompt` contains `TextArea` and `Select`

This mirrors Toad's architecture for easy transition.

## Next Steps

1. Read `WIDGET_PATTERNS.md` to understand patterns
2. Explore `widgets/` to see patterns in action
3. Read `EXTENDING.md` to add real functionality
