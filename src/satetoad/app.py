"""Satellite - Minimal Textual App for learning TUI patterns.

This is the main application entry point. It demonstrates:
- How to create a Textual App
- How to load CSS styles
- How to push screens
"""

from textual.app import App
from textual.binding import Binding
from textual.reactive import var

from satetoad.screens.main import MainScreen
from satetoad.screens.trajectories import TrajectoriesScreen


class SatetoadApp(App):
    """Main application - multi-screen configuration.

    Key patterns demonstrated:
    - CSS_PATH: Load styles from a .tcss file
    - TITLE: Set the terminal window title
    - BINDINGS: App-level keyboard shortcuts
    - on_mount: Called when app is ready, push the initial screen
    """

    CSS_PATH = "main.tcss"
    TITLE = "Satellite v0.1.0"
    ENABLE_COMMAND_PALETTE = False

    # Terminal tab title (reactive to ensure driver is ready)
    terminal_title: var[str] = var("Satellite")
    terminal_title_icon: var[str] = var("🛰️")

    BINDINGS = [
        Binding("t", "trajectories", "Trajectories", show=False),
        Binding("f1", "toggle_help", "Help"),
        Binding("f2", "settings", "Settings", show=False),
    ]

    def on_mount(self) -> None:
        """Push the main screen when the app mounts."""
        self.push_screen(MainScreen())
        self.call_later(self._update_terminal_title)

    def watch_terminal_title(self, title: str) -> None:
        """Update terminal tab title when title changes."""
        self._update_terminal_title()

    def _update_terminal_title(self) -> None:
        """Write terminal title via driver (only when ready)."""
        if driver := self._driver:
            driver.write(f"\033]0;{self.terminal_title_icon} {self.terminal_title}\007")

    def action_trajectories(self) -> None:
        """Navigate to trajectories screen."""
        self.push_screen(TrajectoriesScreen())

    def action_toggle_help(self) -> None:
        """Toggle help panel display."""
        self.notify(
            "Arrow keys: Navigate\n"
            "Enter/Space: Select\n"
            "1-4: Quick access\n"
            "Tab: Cycle focus\n"
            "Ctrl+R: Resume\n"
            "F2: Settings\n"
            "Q: Quit",
            title="Keyboard Shortcuts",
        )

    def action_settings(self) -> None:
        """Open settings (placeholder)."""
        self.notify(
            "Settings not yet implemented.\n"
            "Configure model via option 1.",
            title="Settings",
        )


def main() -> None:
    """Entry point for the application."""
    # Import evals/inspect-ai BEFORE Textual takes terminal control.
    # inspect-ai has terminal handling that conflicts with Textual's driver.
    # By importing here (before app.run()), inspect-ai initializes on a
    # normal terminal, then Textual takes over cleanly.
    try:
        # Import all evals (triggers full inspect-ai initialization)
        from evals._registry import (  # noqa: F401
            telelogs,
            telemath,
            teleqna,
            teletables,
            three_gpp,
        )
    except ImportError:
        pass  # evals not installed, will use fallback metadata

    app = SatetoadApp()
    app.run()


if __name__ == "__main__":
    main()
