"""Tests for SatetoadApp subprocess cleanup behavior.

This test verifies that the inspect view subprocess is properly
terminated when the app closes, preventing orphan processes.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestAppSubprocessCleanup:
    """Tests for subprocess cleanup on app exit."""

    def test_inspect_view_terminated_on_unmount(self, tmp_path: Path) -> None:
        """Subprocess should be terminated when app unmounts.

        This test verifies the fix for the orphan subprocess bug:
        - App launches `uv run inspect view` on startup
        - When app closes, the subprocess must be terminated
        - Without the fix, the subprocess reference is lost and cannot be cleaned up
        """
        with patch("satetoad.app.subprocess.Popen") as popen_mock, \
             patch("satetoad.app.MainScreen"):
            # Setup mocks
            process = MagicMock()
            process.poll.return_value = None  # Process running
            popen_mock.return_value = process

            # Import after patching to ensure patches apply
            from satetoad.app import SatetoadApp

            app = SatetoadApp()

            # Directly launch view (avoids JobManager dependency)
            app._launch_view(tmp_path)

            # Verify subprocess was started
            assert popen_mock.called, "Subprocess should be started on launch"

            # Simulate app closing - this should terminate the subprocess
            app.on_unmount()

            # THE KEY ASSERTION: terminate() must be called on the subprocess
            process.terminate.assert_called_once()
