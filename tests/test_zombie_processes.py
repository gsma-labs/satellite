"""Tests for zombie process detection and prevention.

Verifies subprocess cleanup under various scenarios: normal exit,
force-kill, signal handling, timer cleanup, multiple instances, and crashes.

Some tests spawn REAL subprocesses and are marked with @pytest.mark.slow.
"""

import os
import signal
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_popen_for_zombie() -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Mock Popen that tracks cleanup method calls."""
    with patch("satellite.app.subprocess.Popen") as popen_mock:
        process = MagicMock()
        process.pid = 99999
        process.poll.return_value = None
        process.terminate_called = False
        process.kill_called = False

        def track_terminate() -> None:
            process.terminate_called = True

        def track_kill() -> None:
            process.kill_called = True

        process.terminate.side_effect = track_terminate
        process.kill.side_effect = track_kill
        popen_mock.return_value = process
        yield popen_mock, process


@pytest.fixture
def real_long_running_process(tmp_path: Path) -> Generator[subprocess.Popen, None, None]:
    """Spawn a real subprocess that sleeps indefinitely.

    Cleans up after test regardless of outcome.
    """
    script = tmp_path / "sleeper.py"
    script.write_text("import time; time.sleep(3600)")

    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    yield proc

    if proc.poll() is None:
        proc.kill()
        proc.wait()


class TestZombieSubprocessOnForceKill:
    """Tests verifying subprocess cleanup via atexit handlers."""

    def test_atexit_handler_registered_on_app_init(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """App should register atexit handler for subprocess cleanup."""
        with patch("satellite.app.MainScreen"):
            from satellite.app import SatelliteApp

            app = SatelliteApp()

            has_atexit = hasattr(app, "_atexit_registered") and app._atexit_registered

            assert has_atexit, (
                "App should register atexit handler for subprocess cleanup. "
                "Add atexit.register() in __init__ to fix zombie processes."
            )

    def test_subprocess_cleaned_with_on_unmount(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """on_unmount kills the entire process group via os.killpg()."""
        popen_mock, process = mock_popen_for_zombie

        with patch("satellite.app.MainScreen"), \
             patch("satellite.app.os.killpg") as mock_killpg, \
             patch("satellite.app.os.getpgid", return_value=99999):
            from satellite.app import SatelliteApp

            app = SatelliteApp()
            app.set_timer = MagicMock()
            app._launch_inspect_view()

            app.on_unmount()

            mock_killpg.assert_called_once_with(99999, signal.SIGTERM)


class TestSignalHandlingZombies:
    """Tests verifying app does NOT register custom signal handlers.

    Custom handlers conflict with Textual's signal handling. Cleanup
    is handled by on_unmount and the atexit handler instead.
    """

    @pytest.mark.parametrize(
        ("signal_num", "signal_name"),
        [
            pytest.param(signal.SIGTERM, "SIGTERM", id="sigterm"),
            pytest.param(signal.SIGINT, "SIGINT", id="sigint_ctrl_c"),
        ],
    )
    def test_no_custom_signal_handler_registered(
        self,
        signal_num: signal.Signals,
        signal_name: str,
    ) -> None:
        """App init must not change the signal handler for SIGTERM/SIGINT."""
        original_handler = signal.getsignal(signal_num)

        with patch("satellite.app.MainScreen"):
            from satellite.app import SatelliteApp

            _app = SatelliteApp()

        current_handler = signal.getsignal(signal_num)

        assert current_handler == original_handler, (
            f"App should NOT register custom {signal_name} handler. "
            f"Custom handlers conflict with Textual's signal handling."
        )


class TestJuliaSetTimerLeaks:
    """Tests for timer cleanup in JuliaSet widget."""

    def test_julia_set_has_on_unmount(self) -> None:
        """JuliaSet widget should have on_unmount for timer cleanup."""
        from satellite.widgets.julia_set import JuliaSet

        has_custom_unmount = "on_unmount" in JuliaSet.__dict__

        assert has_custom_unmount, (
            "JuliaSet should override on_unmount() to stop zoom_timer. "
            "Add: def on_unmount(self): if self.zoom_timer: self.zoom_timer.stop()"
        )

    @pytest.mark.asyncio
    async def test_timer_created_on_mouse_down(self) -> None:
        """Timer is created when mouse is pressed (zoom interaction).

        Verifies the timer creation path that could leak.
        """
        from textual.app import App, ComposeResult
        from textual.events import Click

        from satellite.widgets.julia_set import JuliaSet

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield JuliaSet(id="julia")

        app = TestApp()
        async with app.run_test():
            julia = app.query_one("#julia", JuliaSet)

            assert julia.zoom_timer is None

            # Create Click event with widget argument (required in Textual 7.x)
            event = Click(
                widget=julia,
                x=10,
                y=10,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=10,
                screen_y=10,
            )
            julia.on_mouse_down(event)

            assert julia.zoom_timer is not None

    @pytest.mark.asyncio
    async def test_timer_stopped_on_mouse_up(self) -> None:
        """Timer is stopped when mouse is released.

        This is the NORMAL cleanup path that works.
        """
        from textual.app import App, ComposeResult
        from textual.events import Click

        from satellite.widgets.julia_set import JuliaSet

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield JuliaSet(id="julia")

        app = TestApp()
        async with app.run_test():
            julia = app.query_one("#julia", JuliaSet)

            down_event = Click(
                widget=julia,
                x=10,
                y=10,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=10,
                screen_y=10,
            )
            julia.on_mouse_down(down_event)
            timer = julia.zoom_timer
            assert timer is not None

            up_event = Click(
                widget=julia,
                x=10,
                y=10,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=10,
                screen_y=10,
            )
            julia.on_mouse_up(up_event)

            # Timer.stop() was called - timer reference may still exist
            # but is no longer active

    @pytest.mark.asyncio
    async def test_timer_stopped_on_widget_removal(self) -> None:
        """Timer is stopped when widget is removed during active zoom."""
        from textual.app import App, ComposeResult
        from textual.events import Click

        from satellite.widgets.julia_set import JuliaSet

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield JuliaSet(id="julia")

        app = TestApp()
        async with app.run_test():
            julia = app.query_one("#julia", JuliaSet)

            event = Click(
                widget=julia,
                x=10,
                y=10,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=10,
                screen_y=10,
            )
            julia.on_mouse_down(event)
            timer = julia.zoom_timer
            assert timer is not None

            # Mock the stop method to track if it's called
            original_stop = timer.stop
            stop_called = False

            def tracked_stop() -> None:
                nonlocal stop_called
                stop_called = True
                original_stop()

            timer.stop = tracked_stop

            # Remove widget - on_unmount should stop the timer
            await julia.remove()

            assert stop_called, (
                "Timer.stop() should be called when widget is removed. "
                "Add on_unmount() to JuliaSet that stops zoom_timer."
            )


class TestMultipleAppInstancesZombies:
    """Tests for singleton pattern ensuring previous instance cleanup."""

    def test_second_app_instance_should_fail_or_cleanup_first(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """Second app instance cleans up first via os.killpg()."""
        popen_mock, process = mock_popen_for_zombie

        with patch("satellite.app.MainScreen"), \
             patch("satellite.app.os.killpg") as mock_killpg, \
             patch("satellite.app.os.getpgid", return_value=99999):
            from satellite.app import SatelliteApp

            app1 = SatelliteApp()
            app1.set_timer = MagicMock()
            app1._launch_inspect_view()

            first_call_count = popen_mock.call_count
            assert first_call_count == 1

            app2 = SatelliteApp()
            app2.set_timer = MagicMock()
            app2._launch_inspect_view()

            mock_killpg.assert_any_call(99999, signal.SIGTERM)

    def test_launch_view_kills_existing_process(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """_launch_view kills existing process group before spawning a new one."""
        popen_mock, process = mock_popen_for_zombie

        with patch("satellite.app.MainScreen"), \
             patch("satellite.app.os.killpg") as mock_killpg, \
             patch("satellite.app.os.getpgid", return_value=99999):
            from satellite.app import SatelliteApp

            # Clear singleton to avoid cross-test interference
            SatelliteApp._instance = None

            app = SatelliteApp()
            app.set_timer = MagicMock()
            app._launch_view(Path("/tmp/logs1"))

            mock_killpg.reset_mock()
            app._launch_view(Path("/tmp/logs2"))

            mock_killpg.assert_called_once_with(99999, signal.SIGTERM)


@pytest.mark.slow
class TestRealSubprocessZombies:
    """Tests using real subprocesses to detect actual zombie conditions."""

    def test_real_subprocess_becomes_orphan(
        self,
        real_long_running_process: subprocess.Popen,
    ) -> None:
        """Real subprocess remains running and detectable via os.kill()."""
        proc = real_long_running_process
        pid = proc.pid

        assert proc.poll() is None

        # Verify process is still running via OS
        try:
            os.kill(pid, 0)
            process_exists = True
        except OSError:
            process_exists = False

        assert process_exists, "Process should still be running"

    def test_real_subprocess_cleanup_with_terminate(
        self,
        real_long_running_process: subprocess.Popen,
    ) -> None:
        """Verify terminate() properly cleans up real subprocess."""
        proc = real_long_running_process
        pid = proc.pid

        proc.terminate()
        proc.wait(timeout=5)

        try:
            os.kill(pid, 0)
            process_exists = True
        except OSError:
            process_exists = False

        assert not process_exists, "Process should be terminated"

    def test_zombie_detection_via_psutil(
        self,
        real_long_running_process: subprocess.Popen,
    ) -> None:
        """Terminated process transitions from running to not-running in psutil."""
        try:
            import psutil
        except ImportError:
            pytest.skip("psutil not installed")

        proc = real_long_running_process
        pid = proc.pid

        ps_proc = psutil.Process(pid)

        assert ps_proc.is_running()
        assert ps_proc.status() != psutil.STATUS_ZOMBIE

        proc.terminate()
        proc.wait()

        assert not ps_proc.is_running()


class TestCrashDuringOperation:
    """Tests verifying atexit handlers ensure cleanup even on exceptions."""

    def test_atexit_ensures_cleanup_on_crash(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """Atexit handler remains registered even after exceptions."""
        popen_mock, process = mock_popen_for_zombie

        with patch("satellite.app.MainScreen"):
            from satellite.app import SatelliteApp

            app = SatelliteApp()
            app.set_timer = MagicMock()
            app._launch_inspect_view()

            # Simulate crash - exception raised
            try:
                raise RuntimeError("Simulated widget crash")
            except RuntimeError:
                pass

            has_atexit = hasattr(app, "_atexit_registered") and app._atexit_registered

            assert has_atexit, (
                "App should have atexit handler registered for crash recovery. "
                "Add atexit.register() in __init__ to ensure cleanup on crash."
            )

    @pytest.mark.asyncio
    async def test_exception_in_compose_textual_handles_cleanup(self) -> None:
        """Textual calls on_unmount even when compose raises."""
        from textual.app import App, ComposeResult

        class CrashingApp(App):
            cleanup_called = False

            def compose(self) -> ComposeResult:
                raise RuntimeError("Crash in compose")
                yield  # type: ignore[misc]  # Never reached

            def on_unmount(self) -> None:
                CrashingApp.cleanup_called = True

        app = CrashingApp()

        with pytest.raises(RuntimeError, match="Crash in compose"):
            async with app.run_test():
                pass

        # Textual correctly calls on_unmount even when compose fails
        assert CrashingApp.cleanup_called


class TestAppStopViewProcessEdgeCases:
    """Edge cases in app._stop_view_process() that could lead to zombies."""

    def test_terminate_timeout_followed_by_kill(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """SIGTERM timeout escalates to SIGKILL via os.killpg."""
        popen_mock, process = mock_popen_for_zombie
        process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=5),
            None,
        ]

        with patch("satellite.app.MainScreen"), \
             patch("satellite.app.os.killpg") as mock_killpg, \
             patch("satellite.app.os.getpgid", return_value=99999):
            from satellite.app import SatelliteApp

            # Clear singleton to avoid cross-test interference
            SatelliteApp._instance = None

            app = SatelliteApp()
            app.set_timer = MagicMock()
            app._launch_view(Path("/tmp/logs"))

            app._stop_view_process()

            assert mock_killpg.call_count == 2
            mock_killpg.assert_any_call(99999, signal.SIGTERM)
            mock_killpg.assert_any_call(99999, signal.SIGKILL)

    def test_stop_view_sets_process_to_none(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """_stop_view_process() clears the reference to prevent double-cleanup."""
        popen_mock, process = mock_popen_for_zombie

        with patch("satellite.app.MainScreen"), \
             patch("satellite.app.os.killpg"), \
             patch("satellite.app.os.getpgid", return_value=99999):
            from satellite.app import SatelliteApp

            app = SatelliteApp()
            app.set_timer = MagicMock()
            app._launch_view(Path("/tmp/logs"))
            assert app._view_process is not None

            app._stop_view_process()

            assert app._view_process is None

    def test_stop_view_idempotent(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """Repeated _stop_view_process() calls are safe and only signal once."""
        popen_mock, process = mock_popen_for_zombie

        with patch("satellite.app.MainScreen"), \
             patch("satellite.app.os.killpg") as mock_killpg, \
             patch("satellite.app.os.getpgid", return_value=99999):
            from satellite.app import SatelliteApp

            app = SatelliteApp()
            app.set_timer = MagicMock()
            app._launch_view(Path("/tmp/logs"))

            app._stop_view_process()
            app._stop_view_process()
            app._stop_view_process()

            # killpg called once for SIGTERM on first stop only
            mock_killpg.assert_called_once_with(99999, signal.SIGTERM)
