"""TabHeader - Horizontal container for tab navigation.

Manages multiple TabItem widgets with keyboard navigation.
"""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive

from satellite.widgets.tab_item import TabItem


class TabHeader(Horizontal):
    """Horizontal container holding TabItem widgets with keyboard navigation.

    Layout:
    +-----------------------------------------------+
    | [Run Evals] | [View Progress] | [job_1] [x]   |
    +-----------------------------------------------+
    """

    DEFAULT_CSS = """
    TabHeader {
        width: 1fr;
        height: auto;
        min-height: 3;
        padding: 0;
        background: transparent;

        &:focus {
            background: transparent;
        }
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("left", "prev_tab", "Previous Tab", show=False),
        Binding("right", "next_tab", "Next Tab", show=False),
        Binding("1", "goto_tab_1", "Tab 1", show=False),
        Binding("2", "goto_tab_2", "Tab 2", show=False),
        Binding("3", "goto_tab_3", "Tab 3", show=False),
    ]

    class TabChanged(Message):
        """Posted when active tab changes."""

        def __init__(self, old_tab_id: str | None, new_tab_id: str) -> None:
            super().__init__()
            self.old_tab_id = old_tab_id
            self.new_tab_id = new_tab_id

    class TabClosed(Message):
        """Posted when a closable tab is closed."""

        def __init__(self, tab_id: str) -> None:
            super().__init__()
            self.tab_id = tab_id

    active_tab: reactive[str | None] = reactive(None)

    def __init__(self, **kwargs) -> None:
        """Initialize the tab header."""
        super().__init__(**kwargs)
        self._tab_order: list[str] = []  # Maintains order of tabs
        self.can_focus = True

    def compose(self) -> ComposeResult:
        """Yield nothing - tabs added dynamically."""
        yield from []

    def add_tab(
        self,
        tab_id: str,
        label: str,
        closable: bool = False,
        activate: bool = True,
    ) -> TabItem:
        """Add a new tab to the header.

        Args:
            tab_id: Unique identifier for the tab
            label: Display text
            closable: Whether tab can be closed
            activate: Whether to activate this tab immediately

        Returns:
            The created TabItem widget
        """
        tab = TabItem(label=label, tab_id=tab_id, closable=closable)
        self._tab_order.append(tab_id)
        self.mount(tab)

        if activate or self.active_tab is None:
            self.activate_tab(tab_id)

        return tab

    def remove_tab(self, tab_id: str) -> bool:
        """Remove a tab from the header.

        Args:
            tab_id: ID of tab to remove

        Returns:
            True if tab was removed, False if not found
        """
        if tab_id not in self._tab_order:
            return False

        # Find and remove the tab widget
        for tab in self.query(TabItem):
            if tab.tab_id == tab_id:
                tab.remove()
                break

        self._tab_order.remove(tab_id)

        # If we removed the active tab, switch to previous or first tab
        if self.active_tab == tab_id and self._tab_order:
            self.activate_tab(self._tab_order[-1])
        if self.active_tab == tab_id and not self._tab_order:
            self.active_tab = None

        self.post_message(self.TabClosed(tab_id))
        return True

    def activate_tab(self, tab_id: str) -> bool:
        """Activate a specific tab.

        Args:
            tab_id: ID of tab to activate

        Returns:
            True if tab was activated, False if not found
        """
        if tab_id not in self._tab_order:
            return False

        old_tab_id = self.active_tab
        if old_tab_id == tab_id:
            return True  # Already active

        self.active_tab = tab_id
        return True

    def watch_active_tab(self, old_value: str | None, new_value: str | None) -> None:
        """React to active tab changes - update tab styling."""
        # Update TabItem active states
        for tab in self.query(TabItem):
            tab.active = tab.tab_id == new_value

        # Post change message
        if new_value is not None:
            self.post_message(self.TabChanged(old_value, new_value))

    def get_tab(self, tab_id: str) -> TabItem | None:
        """Get a tab by ID.

        Args:
            tab_id: ID of tab to find

        Returns:
            TabItem if found, None otherwise
        """
        for tab in self.query(TabItem):
            if tab.tab_id == tab_id:
                return tab
        return None

    def get_tab_ids(self) -> list[str]:
        """Get ordered list of tab IDs."""
        return self._tab_order.copy()

    def _get_tab_index(self, tab_id: str) -> int | None:
        """Get index of a tab in the order list."""
        try:
            return self._tab_order.index(tab_id)
        except ValueError:
            return None

    def on_tab_item_activated(self, event: TabItem.Activated) -> None:
        """Handle tab activation from TabItem click."""
        event.stop()
        self.activate_tab(event.tab_id)

    def on_tab_item_close_requested(self, event: TabItem.CloseRequested) -> None:
        """Handle close request from TabItem."""
        event.stop()
        self.remove_tab(event.tab_id)

    def on_click(self, event) -> None:
        """Handle click - find which TabItem was clicked and activate it."""
        for widget in event.widget.ancestors_with_self:
            if isinstance(widget, TabItem):
                self.activate_tab(widget.tab_id)
                break

    def action_prev_tab(self) -> None:
        """Navigate to previous tab."""
        if not self._tab_order or self.active_tab is None:
            return

        current_idx = self._get_tab_index(self.active_tab)
        if current_idx is None:
            return

        new_idx = (current_idx - 1) % len(self._tab_order)
        self.activate_tab(self._tab_order[new_idx])

    def action_next_tab(self) -> None:
        """Navigate to next tab."""
        if not self._tab_order or self.active_tab is None:
            return

        current_idx = self._get_tab_index(self.active_tab)
        if current_idx is None:
            return

        new_idx = (current_idx + 1) % len(self._tab_order)
        self.activate_tab(self._tab_order[new_idx])

    def action_goto_tab_1(self) -> None:
        """Jump to tab 1."""
        if len(self._tab_order) >= 1:
            self.activate_tab(self._tab_order[0])

    def action_goto_tab_2(self) -> None:
        """Jump to tab 2."""
        if len(self._tab_order) >= 2:
            self.activate_tab(self._tab_order[1])

    def action_goto_tab_3(self) -> None:
        """Jump to tab 3."""
        if len(self._tab_order) >= 3:
            self.activate_tab(self._tab_order[2])
