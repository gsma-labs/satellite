"""Satellite - Minimal Textual App for learning TUI patterns.

This is the main application entry point. It demonstrates:
- How to create a Textual App
- How to load CSS styles
- How to push screens
"""

import atexit
import os
import signal
import subprocess
from pathlib import Path

from textual.app import App
from textual.binding import Binding
from textual.reactive import var

from satellite.screens.main import MainScreen
from satellite.services.evals import EvalRunner, JobManager

INSPECT_VIEW_PORT = 7575
INSPECT_VIEW_CMD = ("uv", "run", "inspect", "view")
VIEW_SHUTDOWN_TIMEOUT = 3
VIEW_HEALTH_CHECK_DELAY = 1.0


class SatelliteApp(App):
    """Main application - multi-screen configuration.

    Key patterns demonstrated:
    - CSS_PATH: Load styles from a .tcss file
    - TITLE: Set the terminal window title
    - BINDINGS: App-level keyboard shortcuts
    - on_mount: Called when app is ready, push the initial screen
    """

    # Class-level singleton tracker for cleanup
    _instance: "SatelliteApp | None" = None

    CSS_PATH = "main.tcss"
    TITLE = "Satellite v0.1.0"
    ENABLE_COMMAND_PALETTE = False

    # Terminal tab title (reactive to ensure driver is ready)
    terminal_title: var[str] = var("Satellite")
    terminal_title_icon: var[str] = var("📡")

    BINDINGS = [
        Binding("f1", "toggle_help", "Help"),
        Binding("f2", "settings", "Settings", show=False),
    ]

    def __init__(self) -> None:
        """Initialize app with subprocess tracking."""
        super().__init__()
        self._eval_runner: EvalRunner | None = None
        self._view_process: subprocess.Popen[bytes] | None = None

        # Singleton pattern: cleanup previous instance's subprocess
        if SatelliteApp._instance is not None:
            SatelliteApp._instance._stop_view_process()
        SatelliteApp._instance = self

        # Register atexit handler for crash/force-kill recovery
        atexit.register(self._cleanup_subprocess)
        self._atexit_registered = True

    def on_mount(self) -> None:
        """Push the main screen and launch inspect view when the app mounts."""
        self.push_screen(MainScreen())
        self.call_later(self._update_terminal_title)

        # Launch inspect view pointing to logs directory
        self._launch_inspect_view()

    def _launch_inspect_view(self) -> None:
        """Launch inspect view on app startup.

        Points to logs/jobs/ so inspect view shows job_1, job_2, etc.
        """
        job_manager = JobManager()
        self._eval_runner = EvalRunner(job_manager.jobs_dir)
        self._launch_view(job_manager.jobs_dir)

    def _launch_view(self, log_dir: Path) -> None:
        """Launch inspect view subprocess pointing to logs directory."""
        self._stop_view_process()

        cmd = [
            *INSPECT_VIEW_CMD,
            "--log-dir",
            str(log_dir),
            "--port",
            str(INSPECT_VIEW_PORT),
        ]
        try:
            self._view_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except (FileNotFoundError, PermissionError, subprocess.SubprocessError) as exc:
            self.notify(f"Could not launch inspect view: {exc}", severity="warning")
            return

        self.set_timer(VIEW_HEALTH_CHECK_DELAY, self._check_view_health)

    def _check_view_health(self) -> None:
        """Verify inspect view process is still alive after launch."""
        if self._view_process is None:
            return
        if self._view_process.poll() is not None:
            self.notify("Inspect view exited unexpectedly", severity="warning")
            self._view_process = None

    def _stop_view_process(self) -> None:
        """Stop the inspect view subprocess with graceful shutdown."""
        if self._view_process is None:
            return

        if self._view_process.poll() is not None:
            self._view_process = None
            return

        self._signal_process_group(signal.SIGTERM)
        if not self._wait_for_exit():
            self._signal_process_group(signal.SIGKILL)
            self._view_process.wait()

        self._view_process = None

    def _signal_process_group(self, sig: signal.Signals) -> None:
        """Send a signal to the view process group, falling back to direct signal."""
        try:
            os.killpg(os.getpgid(self._view_process.pid), sig)
        except (ProcessLookupError, PermissionError, OSError):
            if sig == signal.SIGTERM:
                self._view_process.terminate()
                return
            if sig == signal.SIGKILL:
                self._view_process.kill()

    def _wait_for_exit(self) -> bool:
        """Wait for the view process to exit within the shutdown timeout.

        Returns True if the process exited, False if it timed out.
        """
        try:
            self._view_process.wait(timeout=VIEW_SHUTDOWN_TIMEOUT)
            return True
        except subprocess.TimeoutExpired:
            return False

    def on_unmount(self) -> None:
        """Clean up subprocess when app closes."""
        self._stop_view_process()

    def _cleanup_subprocess(self) -> None:
        """Cleanup subprocess - called by atexit handler."""
        self._stop_view_process()

    def watch_terminal_title(self, title: str) -> None:
        """Update terminal tab title when title changes."""
        self._update_terminal_title()

    def _update_terminal_title(self) -> None:
        """Write terminal title via driver (only when ready)."""
        if driver := self._driver:
            driver.write(f"\033]0;{self.terminal_title_icon} {self.terminal_title}\007")

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
            "Settings not yet implemented.\nConfigure model via option 1.",
            title="Settings",
        )


def main() -> None:
    """Entry point for the application."""
    # ─────────────────────────────────────────────────────────────────
    # CRITICAL: Import ALL dependencies BEFORE Textual takes terminal.
    # inspect-ai has terminal handling that conflicts with Textual's driver.
    # Loading these modules early prevents runtime conflicts.
    # ─────────────────────────────────────────────────────────────────

    # Standard library modules used lazily elsewhere
    import webbrowser  # noqa: F401 - Used by main.py action handlers

    # Inspect AI modules
    try:
        from inspect_ai.log import read_eval_log  # noqa: F401
    except ImportError:
        pass  # inspect-ai not installed

    # Evals registry - triggers full inspect-ai initialization
    try:
        from evals._registry import (  # noqa: F401
            telelogs,
            telemath,
            teleqna,
            teletables,
            three_gpp,
        )
    except ImportError:
        pass  # evals not installed, will use fallback metadata

    app = SatelliteApp()
    app.run()


if __name__ == "__main__":
    main()
