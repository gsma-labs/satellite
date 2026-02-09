"""Tests that EnvConfigManager reads .env correctly for submission."""

from pathlib import Path

import pytest

from satellite.services.config.env_config_manager import EnvConfigManager


@pytest.fixture
def manager(tmp_path: Path) -> EnvConfigManager:
    return EnvConfigManager(tmp_path / ".env")


class TestGetVar:
    """get_var reads directly from the .env file."""

    def test_returns_value_when_set(self, manager: EnvConfigManager) -> None:
        manager.set_var("GITHUB_TOKEN", "ghp_abc123")
        assert manager.get_var("GITHUB_TOKEN") == "ghp_abc123"

    def test_returns_empty_when_missing(self, manager: EnvConfigManager) -> None:
        assert manager.get_var("NONEXISTENT") == ""

    def test_reflects_latest_write(self, manager: EnvConfigManager) -> None:
        manager.set_var("GITHUB_TOKEN", "old")
        manager.set_var("GITHUB_TOKEN", "new")
        assert manager.get_var("GITHUB_TOKEN") == "new"

    def test_returns_empty_after_delete(self, manager: EnvConfigManager) -> None:
        manager.set_var("GITHUB_TOKEN", "ghp_abc123")
        manager.delete_var("GITHUB_TOKEN")
        assert manager.get_var("GITHUB_TOKEN") == ""
