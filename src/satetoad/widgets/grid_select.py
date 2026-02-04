"""GridSelect widget - navigable grid of selectable items.

PATTERN DEMONSTRATED: Custom Container with Keyboard Navigation

Key concepts:
- Extending containers.ItemGrid for grid layout
- Keyboard navigation with cursor actions
- Highlight state management with reactive
- Custom messages for selection events
"""

from dataclasses import dataclass

from textual import containers
from textual.binding import Binding
from textual import events
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget


class GridSelect(containers.ItemGrid, can_focus=True):
    """A grid of items that can be navigated and selected.

    PATTERN: Keyboard-navigable container
    - Arrow keys move highlight
    - Enter/Space selects
    - Tab moves to next focusable widget

    Usage:
        with GridSelect():
            yield AgentCard(agent1)
            yield AgentCard(agent2)
    """

    FOCUS_ON_CLICK = False

    BINDINGS = [
        # Arrow keys for navigation - show combined in footer
        Binding("up", "cursor_up", "Select", show=True, key_display="↑↓←→"),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("left", "cursor_left", "Left", show=False),
        Binding("right", "cursor_right", "Right", show=False),
        # Enter and Space - separate actions to show both in footer
        Binding("enter", "details", "Details", key_display="⏎", show=False),
        Binding("space", "launch", "Launch"),
    ]

    # Currently highlighted item index
    highlighted: reactive[int | None] = reactive(None)

    @dataclass
    class Selected(Message):
        """Posted when an item is selected.

        PATTERN: Custom message with data
        - Include relevant widgets/data
        - Parent widgets handle with @on decorator
        """

        grid_select: "GridSelect"
        selected_widget: Widget

        @property
        def control(self) -> Widget:
            return self.grid_select

    @dataclass
    class LeaveUp(Message):
        """Posted when cursor moves up past the first row."""

        grid_select: "GridSelect"

        @property
        def control(self) -> Widget:
            return self.grid_select

    @dataclass
    class LeaveDown(Message):
        """Posted when cursor moves down past the last row."""

        grid_select: "GridSelect"

        @property
        def control(self) -> Widget:
            return self.grid_select

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        min_column_width: int = 30,
        max_column_width: int | None = None,
    ):
        super().__init__(
            name=name,
            id=id,
            classes=classes,
            min_column_width=min_column_width,
            max_column_width=max_column_width,
        )

    def on_focus(self) -> None:
        """Highlight first item when focused."""
        if self.highlighted is None and self.children:
            self.highlighted = 0

    def on_blur(self) -> None:
        """Clear highlight when blurred."""
        self.highlighted = None

    def watch_highlighted(self, old: int | None, new: int | None) -> None:
        """Update CSS classes when highlight changes.

        PATTERN: watch_* method
        - Called automatically when reactive property changes
        - Use to sync UI with state
        """
        if old is not None and old < len(self.children):
            self.children[old].remove_class("-highlight")
        if new is not None and new < len(self.children):
            self.children[new].add_class("-highlight")
            # Scroll to keep highlighted item visible
            self.children[new].scroll_visible()

    def validate_highlighted(self, value: int | None) -> int | None:
        """Clamp highlight to valid range.

        PATTERN: validate_* method
        - Called before setting reactive property
        - Return corrected value
        """
        if value is None or not self.children:
            return None
        return max(0, min(value, len(self.children) - 1))

    def _get_column_count(self) -> int:
        """Calculate current column count based on widget size.

        Uses the same formula as GridLayout.arrange() to ensure
        navigation matches the visual layout after resize.
        """
        if not self.children:
            return 1

        # Get current widget width
        width = self.size.width
        if width <= 0:
            return 1

        # Use min_column_width to calculate columns (same as GridLayout)
        min_col_width = self.min_column_width or 30
        columns = max(1, width // min_col_width)

        # Cap by number of children (can't have more columns than items)
        return min(columns, len(self.children))

    def action_cursor_up(self) -> None:
        """Move highlight up one row, or post LeaveUp if at top."""
        if self.highlighted is None:
            self.highlighted = 0
            return

        columns = self._get_column_count()
        if self.highlighted >= columns:
            self.highlighted -= columns
        else:
            self.post_message(self.LeaveUp(self))

    def action_cursor_down(self) -> None:
        """Move highlight down one row, or post LeaveDown if at bottom."""
        if self.highlighted is None:
            self.highlighted = 0
            return

        columns = self._get_column_count()
        if self.highlighted + columns < len(self.children):
            self.highlighted += columns
        else:
            self.post_message(self.LeaveDown(self))

    def action_cursor_left(self) -> None:
        """Move highlight left."""
        if self.highlighted is None:
            self.highlighted = 0
        elif self.highlighted > 0:
            self.highlighted -= 1

    def action_cursor_right(self) -> None:
        """Move highlight right."""
        if self.highlighted is None:
            self.highlighted = 0
        elif self.highlighted < len(self.children) - 1:
            self.highlighted += 1

    def on_click(self, event: events.Click) -> None:
        """Handle click to select item."""
        if event.widget is None:
            return

        # Find which child was clicked
        for widget in event.widget.ancestors_with_self:
            if widget in self.children:
                index = self.children.index(widget)
                if self.highlighted == index:
                    # Double-click selects
                    self.action_select()
                else:
                    self.highlighted = index
                break
        self.focus()

    def action_select(self) -> None:
        """Select the highlighted item."""
        if self.highlighted is not None and self.highlighted < len(self.children):
            self.post_message(self.Selected(self, self.children[self.highlighted]))

    def action_details(self) -> None:
        """Show details for the highlighted item (same as select)."""
        self.action_select()

    def action_launch(self) -> None:
        """Launch the highlighted item (same as select)."""
        self.action_select()
