"""EvalBox widget - display card for an evaluation action.

PATTERN DEMONSTRATED: Compound Widget Composition

Key concepts:
- HorizontalGroup for side-by-side layout
- Data-driven composition
- CSS classes for styling variants
"""

from textual.app import ComposeResult
from textual.containers import HorizontalGroup, VerticalGroup
from textual.widgets import Label, Static, Digits


class EvalBox(HorizontalGroup):
    """Display card for an evaluation action box.

    Shows digit shortcut, name, and description in a compact layout.

    Layout:
    +-------------------------------+
    |  1  | Set Model               |
    |     | Configure API keys...   |
    +-------------------------------+
    """

    DEFAULT_CSS = """
    EvalBox {
        width: 1fr;
        padding: 0 1;
        border: none;
        height: auto;
        min-height: 3;

        &:hover {
            background: $surface;
        }

        &.-highlight {
            border: tall $primary;
            background: $surface;
        }

        Digits {
            width: 4;
            margin-right: 1;
        }

        VerticalGroup {
            width: 1fr;
        }

        #name {
            text-style: bold;
            color: $text;
        }

        #description {
            color: $text-muted;
        }
    }
    """

    def __init__(
        self,
        digit: str = "",
        name: str = "",
        description: str = "",
        box_id: str = "",
    ) -> None:
        super().__init__()
        self._digit = digit or ""
        self._name = name or ""
        self._description = description or ""
        self._box_id = box_id or name.lower().replace(" ", "-")

    @property
    def box_id(self) -> str:
        """Return the box identifier."""
        return self._box_id

    def compose(self) -> ComposeResult:
        """Compose the eval box layout.

        PATTERN: Compound composition
        - Use containers to arrange child widgets
        - Widgets yield other widgets
        """
        if self._digit:
            yield Digits(self._digit)
        with VerticalGroup():
            yield Label(self._name if self._name else " ", id="name")
            yield Static(
                self._description if self._description else " ", id="description"
            )
