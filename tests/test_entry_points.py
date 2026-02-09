"""Tests that CLI entry points and subprocess commands resolve correctly.

These tests guard against regressions where renaming the package breaks
the venv entry point scripts or subprocess command paths. The shebangs
inside .venv/bin/ must point to an existing Python interpreter, and all
module-path commands (python -m satellite.xxx) must resolve to real modules.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from satellite.app import INSPECT_VIEW_CMD
from satellite.services.evals.runner import WORKER_CMD

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_BIN = PROJECT_ROOT / ".venv" / "bin"


# ============================================================================
# Entry point shebang validation
# ============================================================================


class TestEntryPointShebangs:
    """Verify that .venv/bin/ scripts have shebangs pointing to existing interpreters."""

    @pytest.mark.parametrize(
        "script_name",
        [
            pytest.param("satellite", id="satellite_cli"),
            pytest.param("inspect", id="inspect_cli"),
        ],
    )
    def test_entry_point_shebang_points_to_existing_python(
        self, script_name: str
    ) -> None:
        """Entry point script shebang must reference an existing Python interpreter.

        After a package/directory rename, `uv sync` can leave stale shebangs
        pointing to deleted venv paths. This test catches that.
        """
        script_path = VENV_BIN / script_name
        if not script_path.exists():
            pytest.skip(f"{script_name} not installed in venv")

        first_line = script_path.read_text().splitlines()[0]
        assert first_line.startswith("#!"), f"{script_name} missing shebang"

        interpreter = first_line[2:].strip()
        assert Path(interpreter).exists(), (
            f"{script_name} shebang points to non-existent interpreter: {interpreter}"
        )

    @pytest.mark.parametrize(
        "script_name",
        [
            pytest.param("satellite", id="satellite_cli"),
            pytest.param("inspect", id="inspect_cli"),
        ],
    )
    def test_entry_point_shebang_points_to_current_venv(
        self, script_name: str
    ) -> None:
        """Entry point shebang must point to THIS project's venv, not another project's."""
        script_path = VENV_BIN / script_name
        if not script_path.exists():
            pytest.skip(f"{script_name} not installed in venv")

        first_line = script_path.read_text().splitlines()[0]
        interpreter = first_line[2:].strip()
        venv_dir = str(PROJECT_ROOT / ".venv")

        assert interpreter.startswith(venv_dir), (
            f"{script_name} shebang points outside current venv.\n"
            f"  Expected prefix: {venv_dir}\n"
            f"  Got: {interpreter}"
        )


# ============================================================================
# CLI entry point execution
# ============================================================================


class TestCLIEntryPoints:
    """Verify that CLI entry points can actually execute."""

    def test_satellite_module_entry_point(self) -> None:
        """python -m satellite must be importable and resolve to our package."""
        result = subprocess.run(
            [sys.executable, "-c", "from satellite.app import main; print('OK')"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert "OK" in result.stdout

    def test_inspect_view_command_resolves(self) -> None:
        """The inspect CLI must be callable (--help as smoke test)."""
        result = subprocess.run(
            [*INSPECT_VIEW_CMD[:3], "--help"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"inspect --help failed (rc={result.returncode}).\n"
            f"stderr: {result.stderr}\n"
            f"Check that .venv/bin/inspect has a valid shebang."
        )

    def test_worker_module_is_importable(self) -> None:
        """The eval worker module path must resolve to a real module."""
        module_path = WORKER_CMD[-1]  # "satellite.services.evals.worker"
        result = subprocess.run(
            [sys.executable, "-c", f"import {module_path}; print('OK')"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"Worker module '{module_path}' not importable: {result.stderr}"
        )


# ============================================================================
# Subprocess command constants
# ============================================================================


class TestSubprocessCommandConstants:
    """Verify that hardcoded subprocess commands reference correct package name."""

    def test_inspect_view_cmd_uses_uv_run(self) -> None:
        """INSPECT_VIEW_CMD must start with 'uv run'."""
        assert INSPECT_VIEW_CMD[:2] == ("uv", "run")

    def test_inspect_view_cmd_calls_inspect(self) -> None:
        """INSPECT_VIEW_CMD must call the 'inspect' entry point."""
        assert INSPECT_VIEW_CMD[2] == "inspect"

    def test_worker_cmd_references_satellite_package(self) -> None:
        """WORKER_CMD module path must use 'satellite' package, not stale name."""
        module_path = WORKER_CMD[-1]
        assert module_path.startswith("satellite."), (
            f"WORKER_CMD references wrong package: {module_path}"
        )

    def test_worker_cmd_module_path_format(self) -> None:
        """WORKER_CMD must use python -m syntax."""
        assert WORKER_CMD[:3] == ["uv", "run", "python"]
        assert WORKER_CMD[3] == "-m"
