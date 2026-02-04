# Satetoad Widgets

This directory contains all custom widgets for satetoad. Each widget demonstrates specific Textual TUI patterns.

## Widget Overview

| Widget | File | Pattern |
|--------|------|---------|
| **Conversation** | `conversation.py` | Composition, reactive vars |
| **Prompt** | `prompt.py` | TextArea, Select, Messages |
| **SideBar** | `sidebar.py` | Collapsible, CSS classes |
| **Throbber** | `throbber.py` | Custom render |
| **Flash** | `flash.py` | Timer, visibility |
| **AgentResponse** | `agent_response.py` | Markdown wrapper |
| **UserInput** | `user_input.py` | Static with prefix |
| **Plan** | `plan.py` | List, status indicators |
| **ProjectTree** | `project_tree.py` | Tree widget |

## Pattern Quick Reference

### 1. Composition (`compose()`)
```python
def compose(self) -> ComposeResult:
    yield ChildWidget()
    with Container():
        yield AnotherWidget()
```

### 2. Reactive Properties (`var`)
```python
busy: var[bool] = var(False)

def watch_busy(self, busy: bool) -> None:
    # Called when 'busy' changes
    pass
```

### 3. CSS Classes
```python
self.add_class("-active")
self.remove_class("-active")
self.toggle_class("-hidden")
self.set_class(condition, "-busy")
```

### 4. Custom Messages
```python
class MyWidget(Widget):
    class Submitted(Message):
        def __init__(self, data: str) -> None:
            self.data = data
            super().__init__()

    def submit(self) -> None:
        self.post_message(self.Submitted("data"))
```

### 5. Timer Actions
```python
self.set_timer(3.0, self.hide)  # Call hide() after 3 seconds
```

### 6. Query Widgets
```python
self.query_one(WidgetType)        # By type
self.query_one("#id")             # By ID
self.query_one(".class")          # By class
self.query_one("#id", WidgetType) # By ID with type check
```

## Reading Order

1. Start with **`user_input.py`** - simplest widget
2. Move to **`flash.py`** - introduces timers
3. Then **`throbber.py`** - custom rendering
4. Then **`prompt.py`** - composition + messages
5. Then **`conversation.py`** - brings it all together

## See Also

- `docs/WIDGET_PATTERNS.md` - Detailed pattern explanations
- `docs/EXTENDING.md` - How to add real functionality
- Textual documentation: https://textual.textualize.io/
