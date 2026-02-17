"""Tests for Makefile setup-target safety.

Verifies that ``make setup`` handles sudo safely, resolves uv reliably,
and keeps system package installation in the separate ``deps`` target.
"""

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _dry_run_target(target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "-n", target],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=10,
    )


# ============================================================================
# Sudo handling
# ============================================================================


class TestSetupSudoFlow:
    """``make setup`` should support sudo while preventing direct-root usage."""

    def test_setup_runs_python_setup_as_sudo_user(self) -> None:
        result = _dry_run_target("setup")
        assert 'sudo -u "$SUDO_USER" -H sh -lc' in result.stdout

    def test_setup_rejects_direct_root_without_sudo_user(self) -> None:
        result = _dry_run_target("setup")
        assert "directly as root is not supported" in result.stdout
        assert "exit 1" in result.stdout


# ============================================================================
# uv path resolution
# ============================================================================


class TestUvPathResolution:
    """After a fresh uv install, setup must still run ``uv sync --dev``."""

    def test_setup_references_local_uv_binary(self) -> None:
        result = _dry_run_target("setup")
        assert ".local/bin/uv" in result.stdout

    def test_setup_runs_uv_sync_dev(self) -> None:
        result = _dry_run_target("setup")
        assert "sync --dev" in result.stdout


# ============================================================================
# Separate deps target
# ============================================================================


class TestDepsTarget:
    """System dependencies must live in a separate ``deps`` target."""

    def test_deps_target_exists(self) -> None:
        result = _dry_run_target("deps")
        assert result.returncode == 0

    def test_setup_does_not_install_system_packages(self) -> None:
        deps_output = _dry_run_target("deps").stdout.strip()
        setup_output = _dry_run_target("setup").stdout.strip()
        setup_only = setup_output.replace(deps_output, "")
        non_echo = [line for line in setup_only.splitlines() if not line.lstrip().startswith("echo ")]
        assert "apt-get" not in "\n".join(non_echo)


# ============================================================================
# Venv ownership (runtime)
# ============================================================================


class TestVenvNotRootOwned:
    """The venv Python must be accessible by the current user."""

    VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

    def test_venv_python_not_under_root_home(self) -> None:
        """The resolved Python must not live inside /root/ (inaccessible to normal users)."""
        if not self.VENV_PYTHON.exists():
            pytest.skip(".venv/bin/python does not exist")
        resolved = self.VENV_PYTHON.resolve()
        assert not str(resolved).startswith("/root/"), (
            f"venv Python resolves to {resolved}, which is under /root/ "
            "and inaccessible to non-root users"
        )

    def test_venv_python_accessible_by_current_user(self) -> None:
        if not self.VENV_PYTHON.exists():
            pytest.skip(".venv/bin/python does not exist")
        resolved = self.VENV_PYTHON.resolve()
        assert os.access(resolved, os.R_OK | os.X_OK)
