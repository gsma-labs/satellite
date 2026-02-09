"""Tests for SatetoadApp subprocess cleanup behavior.

This test verifies that the inspect view subprocess is properly
terminated when the app closes, preventing orphan processes.
"""

import signal
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestAppSubprocessCleanup:
    """Tests for subprocess cleanup on app exit."""

    def test_inspect_view_terminated_on_unmount(self, tmp_path: Path) -> None:
        """Process group should be killed when app unmounts.

        This test verifies the fix for the orphan subprocess bug:
        - App launches `uv run inspect view` on startup with start_new_session=True
        - When app closes, os.killpg() kills the entire process group
        - Without the fix, the subprocess reference is lost and cannot be cleaned up
        """
        with patch("satetoad.app.subprocess.Popen") as popen_mock, \
             patch("satetoad.app.MainScreen"), \
             patch("satetoad.app.os.killpg") as mock_killpg, \
             patch("satetoad.app.os.getpgid", return_value=12345):
            process = MagicMock()
            process.pid = 12345
            process.poll.return_value = None
            popen_mock.return_value = process

            # Import after patching to ensure patches apply
            from satetoad.app import SatetoadApp

            app = SatetoadApp()
            app.set_timer = MagicMock()

            # Directly launch view (avoids JobManager dependency)
            app._launch_view(tmp_path)

            assert popen_mock.called, "Subprocess should be started on launch"

            app.on_unmount()

            mock_killpg.assert_called_once_with(12345, signal.SIGTERM)
