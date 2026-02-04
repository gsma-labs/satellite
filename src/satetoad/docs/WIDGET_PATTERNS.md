# Widget Patterns in Textual

This document explains the key patterns used in satetoad widgets.

## 1. Widget Composition

The `compose()` method defines a widget's structure by yielding child widgets.

### Basic Pattern

```python
from textual.widget import Widget
from textual.app import ComposeResult

class MyWidget(Widget):
    def compose(self) -> ComposeResult:
        yield ChildWidget()
        yield AnotherWidget()
```

### With Containers

```python
from textual.containers import Horizontal, Vertical

class MyWidget(Widget):
    def compose(self) -> ComposeResult:
        with Horizontal():
            yield LeftWidget()
            yield RightWidget()
        with Vertical():
            yield TopWidget()
            yield BottomWidget()
```

### Example: Prompt Widget

```python
class Prompt(Widget):
    def compose(self) -> ComposeResult:
        with Horizontal(id="prompt-header"):
            yield Label("Agent:")
            yield Select(MOCK_AGENTS, id="agent-select")
        yield TextArea(id="prompt-input")
```

---

## 2. Reactive Properties

Reactive properties automatically trigger updates when changed.

### Basic Pattern

```python
from textual.reactive import var

class MyWidget(Widget):
    # Declare reactive property
    busy: var[bool] = var(False)

    # Watch method - called when property changes
    def watch_busy(self, busy: bool) -> None:
        self.query_one(Throbber).set_class(busy, "-busy")
```

### Usage

```python
# Setting the property triggers watch_busy()
widget.busy = True   # → watch_busy(True) called
widget.busy = False  # → watch_busy(False) called
```

### Example: Conversation Widget

```python
class Conversation(Widget):
    busy: var[bool] = var(False)

    def watch_busy(self, busy: bool) -> None:
        # Update throbber visibility when busy changes
        self.query_one(Throbber).set_class(busy, "-busy")
```

---

## 3. CSS Class Manipulation

CSS classes control styling and visibility.

### Methods

```python
# Add a class
self.add_class("-active")

# Remove a class
self.remove_class("-active")

# Toggle a class
self.toggle_class("-hidden")

# Set class based on condition
self.set_class(is_busy, "-busy")  # Add if True, remove if False
```

### Example: Sidebar Toggle

```python
class SideBar(Widget):
    def toggle_visibility(self) -> None:
        self.toggle_class("-hidden")
```

CSS:
```css
SideBar.-hidden {
    display: none;
}
```

---

## 4. Custom Messages

Messages enable communication between widgets.

### Define a Message

```python
from textual.message import Message

class MyWidget(Widget):
    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()
```

### Post a Message

```python
def submit(self) -> None:
    self.post_message(self.Submitted("Hello"))
```

### Handle a Message

```python
from textual import on

class ParentWidget(Widget):
    @on(MyWidget.Submitted)
    def handle_submitted(self, event: MyWidget.Submitted) -> None:
        print(f"Received: {event.text}")
```

### Example: Prompt Submission

```python
class Prompt(Widget):
    class Submitted(Message):
        def __init__(self, text: str, agent_id: str) -> None:
            self.text = text
            self.agent_id = agent_id
            super().__init__()

    def submit(self) -> None:
        text = self.query_one(TextArea).text
        agent = self.query_one(Select).value
        self.post_message(self.Submitted(text, agent))
```

---

## 5. Timer-Based Actions

Timers schedule delayed actions.

### Basic Pattern

```python
def show(self, message: str, timeout: float = 3.0) -> None:
    self.update(message)
    self.add_class("-visible")
    # Schedule hide() to run after timeout
    self.set_timer(timeout, self.hide)

def hide(self) -> None:
    self.remove_class("-visible")
```

### Example: Flash Notifications

```python
class Flash(Static):
    _hide_timer: Timer | None = None

    def show(self, message: str, timeout: float = 3.0) -> None:
        # Cancel previous timer if any
        if self._hide_timer:
            self._hide_timer.stop()

        self.update(message)
        self.add_class("-visible")
        self._hide_timer = self.set_timer(timeout, self.hide)

    def hide(self) -> None:
        self.remove_class("-visible")
```

---

## 6. Custom Rendering

Override `render()` for custom visual output.

### Basic Pattern

```python
from rich.console import RenderableType

class MyWidget(Widget):
    def render(self) -> RenderableType:
        return "Custom content here"
```

### With Rich Formatting

```python
from rich.text import Text
from rich.style import Style

class Throbber(Widget):
    def render(self) -> RenderableType:
        text = Text()
        colors = ["red", "green", "blue"]
        for i, color in enumerate(colors):
            text.append("█", Style(color=color))
        return text
```

---

## 7. Querying Widgets

Find child widgets with query methods.

### Methods

```python
# By type
widget = self.query_one(TextArea)

# By ID
widget = self.query_one("#prompt-input")

# By class
widgets = self.query(".active")

# By ID with type check
widget = self.query_one("#prompt-input", TextArea)
```

### Example

```python
class Prompt(Widget):
    def get_text(self) -> str:
        return self.query_one("#prompt-input", TextArea).text

    def clear(self) -> None:
        self.query_one("#prompt-input", TextArea).clear()
```

---

## 8. Lifecycle Hooks

Special methods called at different stages.

### Common Hooks

```python
class MyWidget(Widget):
    def on_mount(self) -> None:
        """Called when widget is added to the DOM."""
        self.query_one(TextArea).focus()

    def on_unmount(self) -> None:
        """Called when widget is removed from the DOM."""
        pass

    def on_show(self) -> None:
        """Called when widget becomes visible."""
        pass
```

---

## 9. Key Bindings

Bind keyboard shortcuts to actions.

### Define Bindings

```python
class MainScreen(Screen):
    BINDINGS = [
        ("ctrl+b", "toggle_sidebar", "Toggle Sidebar"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def action_toggle_sidebar(self) -> None:
        self.query_one(SideBar).toggle_class("-hidden")
```

### Binding Tuple Format

```python
BINDINGS = [
    (key, action, description),
    # key: Key combination (e.g., "ctrl+b", "f1", "escape")
    # action: Method name without "action_" prefix
    # description: Shown in Footer
]
```

---

## Pattern Summary

| Pattern | Use Case | Key Element |
|---------|----------|-------------|
| Composition | Build widget structure | `compose()` |
| Reactive | State-driven updates | `var()`, `watch_*()` |
| CSS Classes | Styling/visibility | `add_class()`, `toggle_class()` |
| Messages | Widget communication | `Message`, `post_message()` |
| Timers | Delayed actions | `set_timer()` |
| Rendering | Custom visuals | `render()` |
| Queries | Find widgets | `query_one()`, `query()` |
| Lifecycle | Initialization | `on_mount()` |
| Bindings | Keyboard shortcuts | `BINDINGS`, `action_*()` |

## Learning Path

1. **Start simple**: `user_input.py` - composition only
2. **Add state**: `flash.py` - timers and classes
3. **Custom render**: `throbber.py` - Rich formatting
4. **Messages**: `prompt.py` - widget communication
5. **Full widget**: `conversation.py` - all patterns together
