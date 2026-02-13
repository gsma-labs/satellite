"""Tests for Makefile setup-target safety.

Verifies that ``make setup`` rejects root, sources the uv PATH correctly,
and keeps sudo-requiring commands in the separate ``deps`` target.
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
# Root guard
# ============================================================================


class TestSetupRejectsRoot:
    """``make setup`` must refuse to run as root."""

    def test_setup_contains_uid_check(self) -> None:
        result = _dry_run_target("setup")
        assert "id -u" in result.stdout

    def test_setup_exits_nonzero_for_root(self) -> None:
        result = _dry_run_target("setup")
        assert "exit 1" in result.stdout


# ============================================================================
# uv PATH resolution
# ============================================================================


class TestUvEnvSourced:
    """After a fresh uv install the env must be sourced before ``uv sync``."""

    def test_setup_sources_local_bin_env(self) -> None:
        result = _dry_run_target("setup")
        assert ".local/bin/env" in result.stdout

    def test_uv_sync_on_same_line_as_env_source(self) -> None:
        result = _dry_run_target("setup")
        lines = result.stdout.strip().splitlines()
        env_and_sync = [line for line in lines if ".local/bin/env" in line and "uv sync" in line]
        assert len(env_and_sync) == 1


# ============================================================================
# Separate deps target
# ============================================================================


class TestDepsTarget:
    """System dependencies must live in a separate ``deps`` target."""

    def test_deps_target_exists(self) -> None:
        result = _dry_run_target("deps")
        assert result.returncode == 0

    def test_setup_does_not_call_sudo(self) -> None:
        deps_output = _dry_run_target("deps").stdout.strip()
        setup_output = _dry_run_target("setup").stdout.strip()
        setup_only = setup_output.replace(deps_output, "")
        non_echo = [line for line in setup_only.splitlines() if not line.lstrip().startswith("echo ")]
        assert "sudo" not in "\n".join(non_echo)


# ============================================================================
# Venv ownership (runtime)
# ============================================================================


class TestVenvNotRootOwned:
    """The venv Python must be accessible by the current user."""

    VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

    def test_venv_python_not_owned_by_root(self) -> None:
        if not self.VENV_PYTHON.exists():
            pytest.skip(".venv/bin/python does not exist")
        resolved = self.VENV_PYTHON.resolve()
        assert resolved.stat().st_uid != 0

    def test_venv_python_accessible_by_current_user(self) -> None:
        if not self.VENV_PYTHON.exists():
            pytest.skip(".venv/bin/python does not exist")
        resolved = self.VENV_PYTHON.resolve()
        assert os.access(resolved, os.R_OK | os.X_OK)
