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

# Weight multiplier for primary axis distance in navigation scoring
DIRECTION_PRIORITY_WEIGHT = 10000


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
        # Arrow keys for navigation (only up shown in footer with combined display)
        Binding("up", "cursor_up", "Select", show=True, key_display="↑↓←→"),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("left", "cursor_left", "Left", show=False),
        Binding("right", "cursor_right", "Right", show=False),
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
        column_x: int | None = None  # X-coordinate for column-aligned focus transfer

        @property
        def control(self) -> Widget:
            return self.grid_select

    @dataclass
    class LeaveDown(Message):
        """Posted when cursor moves down past the last row."""

        grid_select: "GridSelect"
        column_x: int | None = None  # X-coordinate for column-aligned focus transfer

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
        self._preferred_column_x: int | None = None

    def on_focus(self) -> None:
        """Highlight first item when focused."""
        if self.highlighted is None and self.children:
            self.highlighted = 0

    def focus_at_column(
        self, column_x: int | None, from_direction: str = "down"
    ) -> None:
        """Focus this grid and highlight the item closest to the given column.

        Args:
            column_x: X-coordinate to align to, or None for default (first item)
            from_direction: "down" to highlight top row, "up" to highlight bottom row
        """
        self.focus()
        if column_x is None or not self.children:
            return

        # Find items in the target row (top for "down", bottom for "up")
        all_y = [child.region.y for child in self.children]
        target_y = min(all_y) if from_direction == "down" else max(all_y)

        # Find item closest to column_x in the target row
        best_index = 0
        best_distance = float("inf")
        for i, child in enumerate(self.children):
            if child.region.y != target_y:
                continue
            child_center_x = child.region.x + child.region.width // 2
            distance = abs(child_center_x - column_x)
            if distance < best_distance:
                best_distance = distance
                best_index = i

        self.highlighted = best_index
        self._preferred_column_x = column_x

    def on_blur(self) -> None:
        """Clear highlight and column memory when blurred."""
        self.highlighted = None
        self._preferred_column_x = None

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

    def _get_preferred_x(self) -> int | None:
        """Get preferred x-coordinate for column alignment."""
        if self._preferred_column_x is not None:
            return self._preferred_column_x
        if self.highlighted is None or not self.children:
            return None
        current = self.children[self.highlighted]
        return current.region.x + current.region.width // 2

    def _find_column_aligned_item(self, direction: str) -> int | None:
        """Find nearest item in same column for vertical navigation.

        Prioritizes column alignment over proximity, enabling intuitive
        up/down navigation that maintains the user's column position.
        """
        if self.highlighted is None or not self.children:
            return None

        preferred_x = self._get_preferred_x()
        if preferred_x is None:
            return None

        current = self.children[self.highlighted]
        current_y = current.region.y

        candidates: list[tuple[int, int, int]] = []  # (index, x_distance, y_distance)

        for i, child in enumerate(self.children):
            if i == self.highlighted:
                continue

            child_y = child.region.y
            is_valid = (direction == "up" and child_y < current_y) or (
                direction == "down" and child_y > current_y
            )
            if not is_valid:
                continue

            child_center_x = child.region.x + child.region.width // 2
            x_distance = abs(child_center_x - preferred_x)
            y_distance = abs(child_y - current_y)
            candidates.append((i, x_distance, y_distance))

        if not candidates:
            return None

        # Sort by x_distance first (column), then y_distance (nearest row)
        return min(candidates, key=lambda c: (c[1], c[2]))[0]

    def _find_item_in_direction(self, direction: str) -> int | None:
        """Find the nearest item in the given direction using visual positions."""
        if self.highlighted is None or not self.children:
            return None

        current = self.children[self.highlighted]
        current_region = current.region
        current_center_x = current_region.x + current_region.width // 2
        current_center_y = current_region.y + current_region.height // 2

        best_match = None
        best_score = float("inf")

        for i, child in enumerate(self.children):
            if i == self.highlighted:
                continue

            child_region = child.region
            child_center_x = child_region.x + child_region.width // 2
            child_center_y = child_region.y + child_region.height // 2

            score = self._compute_direction_score(
                direction,
                current_region.x,
                current_region.y,
                current_center_x,
                current_center_y,
                child_region.x,
                child_region.y,
                child_center_x,
                child_center_y,
            )
            if score is None:
                continue

            if score < best_score:
                best_score = score
                best_match = i

        return best_match

    def _compute_direction_score(
        self,
        direction: str,
        current_x: int,
        current_y: int,
        current_center_x: int,
        current_center_y: int,
        child_x: int,
        child_y: int,
        child_center_x: int,
        child_center_y: int,
    ) -> float | None:
        """Compute navigation score for a child in the given direction.

        Returns None if the child is not in the specified direction.
        Lower scores indicate better matches.
        """
        match direction:
            case "up":
                if child_y >= current_y:
                    return None
                primary_dist = abs(child_y - current_y)
                secondary_dist = abs(child_center_x - current_center_x)
            case "down":
                if child_y <= current_y:
                    return None
                primary_dist = abs(child_y - current_y)
                secondary_dist = abs(child_center_x - current_center_x)
            case "left":
                if child_x >= current_x:
                    return None
                primary_dist = abs(child_x - current_x)
                secondary_dist = abs(child_center_y - current_center_y)
            case "right":
                if child_x <= current_x:
                    return None
                primary_dist = abs(child_x - current_x)
                secondary_dist = abs(child_center_y - current_center_y)
            case _:
                return None

        return primary_dist * DIRECTION_PRIORITY_WEIGHT + secondary_dist

    def action_cursor_up(self) -> None:
        """Move highlight up one row, maintaining column alignment."""
        if self.highlighted is None:
            self.highlighted = 0
            return

        target = self._find_column_aligned_item("up")
        if target is not None:
            self.highlighted = target
            # Update preferred column to new item's position
            new_item = self.children[target]
            self._preferred_column_x = new_item.region.x + new_item.region.width // 2
            return
        self.post_message(self.LeaveUp(self, column_x=self._get_preferred_x()))

    def action_cursor_down(self) -> None:
        """Move highlight down one row, maintaining column alignment."""
        if self.highlighted is None:
            self.highlighted = 0
            return

        target = self._find_column_aligned_item("down")
        if target is not None:
            self.highlighted = target
            # Update preferred column to new item's position
            new_item = self.children[target]
            self._preferred_column_x = new_item.region.x + new_item.region.width // 2
            return
        self.post_message(self.LeaveDown(self, column_x=self._get_preferred_x()))

    def action_cursor_left(self) -> None:
        """Move highlight to the nearest item visually to the left."""
        if self.highlighted is None:
            self.highlighted = 0
            return

        target = self._find_item_in_direction("left")
        if target is None:
            return
        self.highlighted = target
        new_item = self.children[target]
        self._preferred_column_x = new_item.region.x + new_item.region.width // 2

    def action_cursor_right(self) -> None:
        """Move highlight to the nearest item visually to the right."""
        if self.highlighted is None:
            self.highlighted = 0
            return

        target = self._find_item_in_direction("right")
        if target is None:
            return
        self.highlighted = target
        new_item = self.children[target]
        self._preferred_column_x = new_item.region.x + new_item.region.width // 2

    def on_click(self, event: events.Click) -> None:
        """Handle click to select item."""
        if event.widget is None:
            return

        for widget in event.widget.ancestors_with_self:
            if widget not in self.children:
                continue
            index = self.children.index(widget)
            if self.highlighted == index:
                self.action_select()
            self.highlighted = index
            self._preferred_column_x = widget.region.x + widget.region.width // 2
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
