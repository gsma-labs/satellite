"""BadgeLabel widget - displays a count with pulse animation.

Shows a compact badge with a number (e.g., "[3]") that pulses
when the count increases. Hidden when count is zero.

PATTERN: Timer-based CSS class animation (like Flash widget)
"""

from textual.reactive import reactive
from textual.widgets import Static


class BadgeLabel(Static):
    """Compact badge showing a count with pulse animation.

    The badge is hidden when count is 0, visible otherwise.
    When count increases, a pulse animation plays.

    Example:
        badge = BadgeLabel()
        badge.count = 3  # Shows "[3]" with pulse animation
    """

    DEFAULT_CSS = """
    BadgeLabel {
        width: auto;
        height: 1;
        padding: 0 1;
        background: #BD93F9 30%;
        color: #F8F8F2;
        text-style: bold;
        display: none;

        &.-visible {
            display: block;
        }

        &.-pulse {
            background: #50FA7B 60%;
        }
    }
    """

    count: reactive[int] = reactive(0)
    _previous_count: int = 0

    def __init__(
        self,
        count: int = 0,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the badge.

        Args:
            count: Initial count to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._previous_count = count
        self.count = count

    def render(self) -> str:
        """Render the badge content."""
        if self.count <= 0:
            return ""
        return f"[{self.count}]"

    def watch_count(self, new_count: int) -> None:
        """React to count changes - show/hide and trigger pulse."""
        # Update visibility
        if new_count > 0:
            self.add_class("-visible")
        else:
            self.remove_class("-visible")

        # Pulse if count increased
        if new_count > self._previous_count:
            self._trigger_pulse()

        self._previous_count = new_count

    def _trigger_pulse(self) -> None:
        """Trigger the pulse animation."""
        self.add_class("-pulse")
        # Remove pulse class after animation duration
        self.set_timer(0.5, self._end_pulse)

    def _end_pulse(self) -> None:
        """End the pulse animation."""
        self.remove_class("-pulse")

    def increment(self, amount: int = 1) -> None:
        """Increment the count by the given amount.

        Args:
            amount: Amount to add to count (default 1)
        """
        self.count += amount

    def decrement(self, amount: int = 1) -> None:
        """Decrement the count by the given amount.

        Args:
            amount: Amount to subtract from count (default 1)
        """
        self.count = max(0, self.count - amount)

    def reset(self) -> None:
        """Reset the count to zero."""
        self.count = 0
