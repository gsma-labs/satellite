"""EvalList widget - navigable multi-select list of evaluations.

PATTERN DEMONSTRATED: To-do list style with arrow key navigation

Key concepts:
- Radio-style selection indicators (○/●)
- Cursor indicator (►) for highlighted item
- Arrow key navigation with reactive highlight
- Multi-select with toggle behavior
- Custom messages for selection and run events
"""

from dataclasses import dataclass

from textual import containers
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static


class EvalListItem(containers.HorizontalGroup):
    """Individual evaluation item with selection state.

    Visual structure:
        ►  ●  TeleQnA
              Question answering benchmark for telecom

    The cursor (►) is visible only when highlighted.
    The selection indicator shows ○ (unselected) or ● (selected).
    """

    ALLOW_SELECT = False

    DEFAULT_CSS = """
    EvalListItem {
        height: auto;
        padding: 0 1;

        #cursor {
            width: 3;
            color: $primary;
            visibility: hidden;
        }

        #selection {
            width: 3;
            color: $text-muted;
        }

        .item-content {
            width: 1fr;
        }

        #name {
            text-style: bold;
        }

        #description {
            color: $text-muted;
            padding-left: 0;
        }

        &.-highlighted {
            background: $surface;

            #cursor {
                visibility: visible;
            }
        }

        &.-selected {
            #selection {
                color: $success;
            }
        }

        &:hover {
            background: $boost;
        }
    }
    """

    selected: reactive[bool] = reactive(False, init=False)

    def __init__(
        self,
        eval_id: str,
        name: str,
        description: str,
        selected: bool = False,
    ) -> None:
        super().__init__()
        self.eval_id = eval_id
        self._name = name
        self._description = description
        self._initial_selected = selected

    def compose(self):
        """Compose the item layout."""
        yield Static("►", id="cursor")
        yield Static("○", id="selection")
        with containers.VerticalGroup(classes="item-content"):
            yield Label(self._name, id="name")
            yield Static(self._description, id="description")

    def on_mount(self) -> None:
        """Set initial selection state after mount."""
        self.selected = self._initial_selected

    def watch_selected(self, selected: bool) -> None:
        """Update selection indicator when selected state changes."""
        selection_widget = self.query_one("#selection", Static)
        selection_widget.update("●" if selected else "○")
        self.set_class(selected, "-selected")


class EvalList(containers.VerticalGroup, can_focus=True):
    """Navigable multi-select list of evaluations.

    PATTERN: To-do list with arrow key navigation

    Features:
    - Arrow up/down to navigate
    - Enter/Space to toggle selection
    - 'r' key to run selected evaluations
    - Multi-select support

    Usage:
        yield EvalList(BENCHMARKS, id="eval-list")
    """

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("enter,space", "toggle", "Toggle"),
        Binding("r", "run_selected", "Run"),
    ]

    DEFAULT_CSS = """
    EvalList {
        height: auto;
        max-height: 15;
        border: solid $primary 30%;
        padding: 0;

        &:focus {
            border: solid $primary;
        }

        &:blur {
            EvalListItem.-highlighted {
                background: transparent;

                #cursor {
                    opacity: 0.3;
                }
            }
        }
    }
    """

    # Currently highlighted item index
    highlighted: reactive[int | None] = reactive(None)

    @dataclass
    class SelectionChanged(Message):
        """Posted when selection state changes."""

        eval_list: "EvalList"
        selected: set[str]

        @property
        def control(self) -> Widget:
            return self.eval_list

    @dataclass
    class RunRequested(Message):
        """Posted when run action is triggered."""

        eval_list: "EvalList"
        selected: list[str]

        @property
        def control(self) -> Widget:
            return self.eval_list

    def __init__(
        self,
        items: list[dict],
        selected: set[str] | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._items = items
        self._selected: set[str] = selected.copy() if selected else set()

    def compose(self):
        """Compose the list items."""
        for item in self._items:
            yield EvalListItem(
                eval_id=item["id"],
                name=item["name"],
                description=item["description"],
                selected=item["id"] in self._selected,
            )

    def on_focus(self) -> None:
        """Highlight first item when focused."""
        if self.highlighted is None and self._items:
            self.highlighted = 0

    def on_blur(self) -> None:
        """Keep highlight visible but dimmed when blurred."""
        # Don't clear highlight - CSS handles dimming
        pass

    def watch_highlighted(self, old: int | None, new: int | None) -> None:
        """Update CSS classes when highlight changes."""
        children = list(self.query(EvalListItem))
        if old is not None and old < len(children):
            children[old].remove_class("-highlighted")
        if new is not None and new < len(children):
            children[new].add_class("-highlighted")
            children[new].scroll_visible()

    def validate_highlighted(self, value: int | None) -> int | None:
        """Clamp highlight to valid range."""
        if value is None or not self._items:
            return None
        return max(0, min(value, len(self._items) - 1))

    def action_cursor_up(self) -> None:
        """Move highlight up, or move focus to previous widget if at start."""
        if self.highlighted is None:
            self.highlighted = 0
        elif self.highlighted > 0:
            self.highlighted -= 1
        else:
            # At the first item - move focus to previous focusable widget
            self.app.action_focus_previous()

    def action_cursor_down(self) -> None:
        """Move highlight down, or move focus to next widget if at end."""
        if self.highlighted is None:
            self.highlighted = 0
        elif self.highlighted < len(self._items) - 1:
            self.highlighted += 1
        else:
            # At the last item - move focus to next focusable widget
            self.app.action_focus_next()

    def action_toggle(self) -> None:
        """Toggle selection of highlighted item."""
        if self.highlighted is None:
            return

        children = list(self.query(EvalListItem))
        if self.highlighted >= len(children):
            return

        item = children[self.highlighted]
        item.selected = not item.selected

        # Update selection set - use set operations directly
        (self._selected.add if item.selected else self._selected.discard)(item.eval_id)

        self.post_message(self.SelectionChanged(self, self._selected.copy()))

    def action_run_selected(self) -> None:
        """Trigger run action with selected items."""
        selected_list = self.get_selected()
        if selected_list:
            self.post_message(self.RunRequested(self, selected_list))
        else:
            self.notify(
                "Please select at least one benchmark",
                title="No Selection",
                severity="warning",
            )

    def select_all(self) -> None:
        """Select all items."""
        for item in self.query(EvalListItem):
            item.selected = True
            self._selected.add(item.eval_id)
        self.post_message(self.SelectionChanged(self, self._selected.copy()))

    def clear_all(self) -> None:
        """Deselect all items."""
        for item in self.query(EvalListItem):
            item.selected = False
        self._selected.clear()
        self.post_message(self.SelectionChanged(self, self._selected.copy()))

    def get_selected(self) -> list[str]:
        """Get list of selected evaluation IDs."""
        return list(self._selected)

    def on_click(self, event) -> None:
        """Handle click to highlight and toggle item."""
        # Find which EvalListItem was clicked
        for widget in event.widget.ancestors_with_self:
            if isinstance(widget, EvalListItem):
                children = list(self.query(EvalListItem))
                if widget in children:
                    index = children.index(widget)
                    self.highlighted = index
                    self.action_toggle()
                break
        self.focus()
