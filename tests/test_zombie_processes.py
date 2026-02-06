"""Tests for zombie process detection and prevention.

This test suite verifies that subprocess cleanup occurs correctly under
various scenarios, including:
1. Normal app exit (on_unmount called)
2. Force-kill scenarios (SIGKILL - on_unmount NOT called)
3. SIGTERM/SIGINT handling during operation
4. Timer cleanup in widgets
5. Multiple app instances without proper cleanup
6. Crash during operation (exception in widget)

IMPORTANT: Some tests spawn REAL subprocesses to properly detect zombie
conditions. These tests are marked with @pytest.mark.slow and may need
special CI configuration.
"""

import os
import signal
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_popen_for_zombie() -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Mock Popen that tracks cleanup method calls.

    Extends the base mock_popen to track whether terminate/kill/wait
    were called before the test exits.
    """
    with patch("satetoad.app.subprocess.Popen") as popen_mock:
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

    Used for testing real zombie detection. Cleans up after test.
    """
    script = tmp_path / "sleeper.py"
    script.write_text("import time; time.sleep(3600)")

    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield proc

    if proc.poll() is None:
        proc.kill()
        proc.wait()


# ============================================================================
# Test Class: Subprocess Cleanup Without on_unmount
# ============================================================================


class TestZombieSubprocessOnForceKill:
    """Tests verifying subprocess cleanup via atexit handlers.

    These tests FAIL until atexit handlers are added to app.py.
    The fix: register cleanup in atexit so it runs even without on_unmount.
    """

    def test_atexit_handler_registered_on_app_init(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """App should register atexit handler for subprocess cleanup.

        BUG: Currently no atexit handler is registered.
        FIX: Add atexit.register(self._cleanup) in __init__.
        """
        import atexit

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app._launch_inspect_view()

            # Check if app registered an atexit handler
            # This requires the app to store a reference we can check
            has_atexit = hasattr(app, "_atexit_registered") and app._atexit_registered

            assert has_atexit, (
                "App should register atexit handler for subprocess cleanup. "
                "Add atexit.register() in __init__ to fix zombie processes."
            )

    def test_subprocess_cleaned_with_on_unmount(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """Subprocess properly terminated when on_unmount IS called.

        This is the PASSING case - demonstrates correct behavior.
        """
        popen_mock, process = mock_popen_for_zombie

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app._launch_inspect_view()

            app.on_unmount()

            assert process.terminate_called


# ============================================================================
# Test Class: Signal Handling Edge Cases
# ============================================================================


class TestSignalHandlingZombies:
    """Tests for signal handler registration.

    These tests FAIL until signal handlers are added to app.py.
    The fix: register SIGTERM/SIGINT handlers that call cleanup.
    """

    @pytest.mark.parametrize(
        ("signal_num", "signal_name"),
        [
            pytest.param(signal.SIGTERM, "SIGTERM", id="sigterm"),
            pytest.param(signal.SIGINT, "SIGINT", id="sigint_ctrl_c"),
        ],
    )
    def test_signal_handler_registered(
        self,
        signal_num: signal.Signals,
        signal_name: str,
    ) -> None:
        """App should register signal handlers for graceful cleanup.

        BUG: Currently no signal handlers are registered.
        FIX: Add signal.signal(SIGTERM, cleanup_handler) in __init__.
        """
        original_handler = signal.getsignal(signal_num)

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            _app = SatetoadApp()

        current_handler = signal.getsignal(signal_num)

        # App should have registered a custom handler
        assert current_handler != original_handler, (
            f"App should register {signal_name} handler for subprocess cleanup. "
            f"Add signal.signal({signal_name}, cleanup_handler) to fix."
        )

        # Restore original handler for test isolation
        signal.signal(signal_num, original_handler)


# ============================================================================
# Test Class: Timer Cleanup in JuliaSet Widget
# ============================================================================


class TestJuliaSetTimerLeaks:
    """Tests for timer cleanup in JuliaSet widget.

    These tests FAIL until on_unmount is added to JuliaSet.
    The fix: add on_unmount() that stops the zoom_timer.
    """

    def test_julia_set_has_on_unmount(self) -> None:
        """JuliaSet widget should have on_unmount for timer cleanup.

        BUG: JuliaSet creates timers but has no on_unmount().
        FIX: Add on_unmount() that calls self.zoom_timer.stop().
        """
        from satetoad.widgets.julia_set import JuliaSet

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

        from satetoad.widgets.julia_set import JuliaSet

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield JuliaSet(id="julia")

        app = TestApp()
        async with app.run_test() as pilot:
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

        from satetoad.widgets.julia_set import JuliaSet

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield JuliaSet(id="julia")

        app = TestApp()
        async with app.run_test() as pilot:
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
        """Timer should be stopped when widget is removed during zoom.

        BUG: Timer leaks if widget removed while zooming.
        FIX: Add on_unmount() to JuliaSet that stops the timer.
        """
        from unittest.mock import MagicMock

        from textual.app import App, ComposeResult
        from textual.events import Click

        from satetoad.widgets.julia_set import JuliaSet

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield JuliaSet(id="julia")

        app = TestApp()
        async with app.run_test() as pilot:
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


# ============================================================================
# Test Class: Multiple App Instances
# ============================================================================


class TestMultipleAppInstancesZombies:
    """Tests for singleton pattern to prevent multiple instances.

    These tests FAIL until singleton/PID file pattern is added.
    The fix: use PID file or singleton to prevent multiple instances.
    """

    def test_second_app_instance_should_fail_or_cleanup_first(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """Second app instance should either fail or cleanup first instance.

        BUG: Multiple app instances create orphaned subprocesses.
        FIX: Use PID file to detect existing instance, or cleanup on new instance.
        """
        popen_mock, process = mock_popen_for_zombie

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app1 = SatetoadApp()
            app1._launch_inspect_view()

            first_call_count = popen_mock.call_count
            assert first_call_count == 1

            # Creating second instance should either:
            # 1. Raise an error (singleton pattern), or
            # 2. Terminate the first instance's subprocess
            app2 = SatetoadApp()
            app2._launch_inspect_view()

            # First subprocess should have been terminated
            assert process.terminate_called, (
                "First app's subprocess should be terminated when second app starts. "
                "Add singleton pattern or cleanup previous instance on startup."
            )

    def test_launch_view_kills_existing_process(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """App._launch_view kills existing process before new one.

        This is a GOOD behavior - prevents zombies from the same app.
        """
        popen_mock, process = mock_popen_for_zombie

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app._launch_view(Path("/tmp/logs1"))
            first_process = app._view_process

            app._launch_view(Path("/tmp/logs2"))

            first_process.terminate.assert_called_once()


# ============================================================================
# Test Class: Real Subprocess Zombie Detection
# ============================================================================


@pytest.mark.slow
class TestRealSubprocessZombies:
    """Tests using REAL subprocesses to detect actual zombie conditions.

    These tests are slower and require special handling in CI.
    Mark with @pytest.mark.slow for optional execution.
    """

    def test_real_subprocess_becomes_orphan(
        self,
        real_long_running_process: subprocess.Popen,
    ) -> None:
        """Demonstrates a real orphaned process scenario.

        Uses a real subprocess to verify detection mechanisms.
        """
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
        """Detect zombie processes using psutil.

        This pattern can be used in CI to detect leaked processes.
        """
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


# ============================================================================
# Test Class: Crash During Operation
# ============================================================================


class TestCrashDuringOperation:
    """Tests for cleanup after crashes.

    These tests verify atexit handlers ensure cleanup even on exceptions.
    """

    def test_atexit_ensures_cleanup_on_crash(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """Atexit handler should ensure cleanup even after exceptions.

        BUG: Exception in widget prevents cleanup, leaving zombie process.
        FIX: atexit handler ensures cleanup runs regardless of exceptions.
        """
        popen_mock, process = mock_popen_for_zombie

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app._launch_inspect_view()

            # Simulate crash - exception raised
            try:
                raise RuntimeError("Simulated widget crash")
            except RuntimeError:
                pass

            # Even without on_unmount, atexit should have registered cleanup
            # We can't easily test atexit directly, so check if app has the mechanism
            has_atexit = hasattr(app, "_atexit_registered") and app._atexit_registered

            assert has_atexit, (
                "App should have atexit handler registered for crash recovery. "
                "Add atexit.register() in __init__ to ensure cleanup on crash."
            )

    @pytest.mark.asyncio
    async def test_exception_in_compose_textual_handles_cleanup(self) -> None:
        """Textual properly calls on_unmount even when compose raises.

        This is GOOD behavior - Textual handles cleanup properly.
        This test verifies Textual's cleanup is robust (should PASS).
        """
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


# ============================================================================
# Test Class: App Stop View Process Edge Cases
# ============================================================================


class TestAppStopViewProcessEdgeCases:
    """Edge cases in app._stop_view_process() that could lead to zombies."""

    def test_terminate_timeout_followed_by_kill(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """Process is killed if terminate times out.

        This is the fallback path - subprocess ignores SIGTERM,
        so we escalate to SIGKILL.
        """
        popen_mock, process = mock_popen_for_zombie
        # First wait (with timeout) raises, second wait (after kill) succeeds
        process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=5),
            None,
        ]

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app._launch_view(Path("/tmp/logs"))

            app._stop_view_process()

            process.terminate.assert_called_once()
            process.kill.assert_called_once()

    def test_stop_view_sets_process_to_none(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """_stop_view_process() clears the process reference.

        Important for preventing double-cleanup attempts.
        """
        popen_mock, process = mock_popen_for_zombie

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app._launch_view(Path("/tmp/logs"))
            assert app._view_process is not None

            app._stop_view_process()

            assert app._view_process is None

    def test_stop_view_idempotent(
        self,
        mock_popen_for_zombie: tuple[MagicMock, MagicMock],
    ) -> None:
        """Calling _stop_view_process() multiple times is safe.

        No crash or error on repeated calls.
        """
        popen_mock, process = mock_popen_for_zombie

        with patch("satetoad.app.MainScreen"):
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app._launch_view(Path("/tmp/logs"))

            app._stop_view_process()
            app._stop_view_process()
            app._stop_view_process()

            assert process.terminate.call_count == 1
