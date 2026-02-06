"""Tests for model persistence across category modals.

Bug 2: When saving models from one category modal, models from other
categories may be lost.

Scenario:
1. User has openrouter/openai/gpt-4o-mini in .env (from open-hosted category)
2. User opens Lab APIs modal (key 4)
3. User adds openai/gpt-oss-120b
4. User clicks "Save All"
5. Bug: openrouter model disappears from .env

This test should FAIL until the bug is fixed.
"""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from satetoad.services.config import EnvConfigManager, ModelConfig


class TestModelPersistence:
    """Test that models persist correctly across save operations."""

    def test_models_from_multiple_providers_persist(self, tmp_path: Path) -> None:
        """Models from different providers should all persist when saving.

        This tests the core persistence logic without UI.
        """
        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENROUTER_API_KEY=sk-or-test\n"
            "INSPECT_EVAL_MODEL=openrouter/openai/gpt-4o-mini\n"
        )

        manager = EnvConfigManager(env_file)

        # Load existing models
        loaded = manager.load_models()
        assert len(loaded) == 1, "Should load 1 existing model"
        assert loaded[0].model == "openrouter/openai/gpt-4o-mini"

        # Simulate adding a new model from a different provider
        # Bug: If we only save the new model, the old one is lost
        new_configs = [
            ModelConfig(model="openrouter/openai/gpt-4o-mini", provider="openrouter", api_key="sk-or-test"),
            ModelConfig(model="openai/gpt-oss-120b", provider="openai", api_key="sk-openai-test"),
        ]
        manager.save_models(new_configs)

        # Verify both models are saved
        content = env_file.read_text()
        assert "openrouter/openai/gpt-4o-mini" in content
        assert "openai/gpt-oss-120b" in content

    def test_loaded_models_should_be_passed_to_modal(self) -> None:
        """When opening a modal, all loaded models should be passed as initial_models.

        Bug: If _load_models_from_env() doesn't run (e.g., app not restarted),
        or if initial_models isn't passed correctly, models can be lost.

        This is a documentation test showing the expected flow.
        """
        # This test documents the expected behavior
        # The actual bug is in the integration between:
        # 1. MainScreen._load_models_from_env() - loads on startup
        # 2. MainScreen._show_model_modal() - should pass ALL loaded models
        # 3. SetModelModal - receives initial_models and shows them
        # 4. MainScreen._on_model_config_saved() - saves what modal returns

        # If any step fails, models can be lost
        pass  # This is a documentation placeholder

    def test_env_manager_preserves_all_env_vars(self, tmp_path: Path) -> None:
        """EnvConfigManager should preserve env vars not related to models.

        When saving, HF_TOKEN and other env vars should not be lost.
        """
        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENROUTER_API_KEY=sk-or-test\n"
            "HF_TOKEN=hf_test_token\n"
            "SOME_OTHER_VAR=some_value\n"
            "INSPECT_EVAL_MODEL=openrouter/openai/gpt-4o-mini\n"
        )

        manager = EnvConfigManager(env_file)
        configs = [ModelConfig(model="openai/gpt-4o", provider="openai", api_key="sk-openai-test")]
        manager.save_models(configs)

        content = env_file.read_text()
        # Values are now wrapped in quotes
        assert "HF_TOKEN='hf_test_token'" in content, "HF_TOKEN should be preserved"
        assert "SOME_OTHER_VAR='some_value'" in content, "Other env vars should be preserved"

    def test_save_replaces_entire_model_list(self, tmp_path: Path) -> None:
        """Saving models replaces the entire INSPECT_EVAL_MODEL list.

        This documents the CURRENT behavior which causes the bug.
        When you save [model_b], model_a is lost even if it was in .env.

        This test PASSES with current code but documents problematic behavior.
        """
        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENROUTER_API_KEY=sk-or-test\n"
            "INSPECT_EVAL_MODEL=openrouter/openai/gpt-4o-mini\n"
        )

        manager = EnvConfigManager(env_file)

        # User only provides the NEW model, not the existing one
        # This simulates what happens when initial_models is empty
        new_configs = [ModelConfig(model="openai/gpt-oss-120b", provider="openai", api_key="sk-openai-test")]
        manager.save_models(new_configs)

        content = env_file.read_text()

        # This PASSES but shows the bug - old model is gone!
        assert "openrouter/openai/gpt-4o-mini" not in content, (
            "Old model was lost (this is the bug!)"
        )
        assert "openai/gpt-oss-120b" in content


class TestModelLoadingOnStartup:
    """Test that models are correctly loaded from .env on startup."""

    def test_load_models_infers_provider_from_prefix(self, tmp_path: Path) -> None:
        """Provider should be inferred from model prefix."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENAI_API_KEY=sk-openai-test\n"
            "OPENROUTER_API_KEY=sk-or-test\n"
            "INSPECT_EVAL_MODEL=openai/gpt-4o,openrouter/anthropic/claude-3\n"
        )

        manager = EnvConfigManager(env_file)
        loaded = manager.load_models()

        assert len(loaded) == 2

        # First model
        assert loaded[0].model == "openai/gpt-4o"
        assert loaded[0].provider == "openai"
        assert loaded[0].api_key == "sk-openai-test"

        # Second model
        assert loaded[1].model == "openrouter/anthropic/claude-3"
        assert loaded[1].provider == "openrouter"
        assert loaded[1].api_key == "sk-or-test"

    def test_load_models_with_missing_api_key(self, tmp_path: Path) -> None:
        """Models should load even if API key is missing (empty string)."""
        env_file = tmp_path / ".env"
        env_file.write_text("INSPECT_EVAL_MODEL=openai/gpt-4o\n")

        manager = EnvConfigManager(env_file)
        loaded = manager.load_models()

        assert len(loaded) == 1
        assert loaded[0].model == "openai/gpt-4o"
        assert loaded[0].provider == "openai"
        assert loaded[0].api_key == ""  # Empty because OPENAI_API_KEY not in .env
