"""Flash widget - toast notifications.

PATTERN DEMONSTRATED: Timer-based Visibility

Key concepts:
- set_timer() for delayed actions
- CSS classes for variants (success, warning, error)
- Auto-hide after timeout
"""

from textual.widgets import Static
from textual.timer import Timer


class Flash(Static):
    """Toast notification that auto-hides.

    Shows a message briefly, then disappears.
    Supports variants: success, warning, error.

    Usage:
        flash.show("Operation complete!", "success")
        flash.show("Something went wrong", "error")
    """

    DEFAULT_CSS = """
    Flash {
        height: 1;
        background: $primary 10%;
        dock: bottom;
        padding: 0 1;
        opacity: 0;
        offset-y: 1;
        transition: opacity 300ms out_cubic, offset-y 300ms out_cubic;
    }

    Flash.-visible {
        opacity: 1;
        offset-y: 0;
    }

    Flash.-success {
        background: $success 20%;
    }

    Flash.-warning {
        background: $warning 20%;
    }

    Flash.-error {
        background: $error 20%;
    }
    """

    _hide_timer: Timer | None = None

    def show(self, message: str, variant: str = "", timeout: float = 3.0) -> None:
        """Show a flash message.

        PATTERN: Timer-based visibility
        - Update content immediately
        - Add visibility class
        - Schedule auto-hide with set_timer()

        Args:
            message: Text to display
            variant: Style variant (success, warning, error)
            timeout: Seconds before auto-hide
        """
        # Cancel any pending hide timer
        if self._hide_timer:
            self._hide_timer.stop()

        # Update content
        self.update(message)

        # Clear previous variant classes
        self.remove_class("-success", "-warning", "-error")

        # Add new variant class if specified
        if variant:
            self.add_class(f"-{variant}")

        # Show the flash
        self.add_class("-visible")

        # Schedule auto-hide
        self._hide_timer = self.set_timer(timeout, self.hide)

    def hide(self) -> None:
        """Hide the flash message."""
        self.remove_class("-visible")
        if self._hide_timer:
            self._hide_timer.stop()
            self._hide_timer = None
