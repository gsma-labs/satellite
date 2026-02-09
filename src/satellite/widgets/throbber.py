"""Throbber widget - loading indicator.

PATTERN DEMONSTRATED: Custom Visual Render

Key concepts:
- Visual class for custom rendering
- render() returns Rich renderables
- CSS controls visibility via -busy class
"""

from rich.console import RenderableType
from rich.style import Style
from rich.text import Text

from textual.widget import Widget


class Throbber(Widget):
    """Animated loading indicator.

    Shows a colored gradient bar when visible.
    Visibility controlled by CSS class '-busy'.

    Usage:
        throbber.set_class(True, "-busy")   # Show
        throbber.set_class(False, "-busy")  # Hide
    """

    # PATTERN: Default CSS for the widget
    # Can be overridden in main.tcss
    DEFAULT_CSS = """
    Throbber {
        width: 100%;
        height: 1;
        visibility: hidden;
    }

    Throbber.-busy {
        visibility: visible;
    }
    """

    def render(self) -> RenderableType:
        """Render the throbber bar.

        PATTERN: Custom rendering
        - render() returns any Rich renderable
        - Text, Table, Panel, etc.
        - Called automatically when widget updates
        """
        # Create a gradient loading bar
        width = self.size.width
        if width <= 0:
            return ""

        # Build colored segments for visual effect
        colors = ["#3498db", "#2ecc71", "#e74c3c", "#f39c12", "#9b59b6"]
        segments = []

        for i in range(width):
            color = colors[i % len(colors)]
            segments.append(("█", Style(color=color)))

        text = Text()
        for char, style in segments:
            text.append(char, style)

        return text

    def show(self) -> None:
        """Show the throbber."""
        self.add_class("-busy")

    def hide(self) -> None:
        """Hide the throbber."""
        self.remove_class("-busy")
