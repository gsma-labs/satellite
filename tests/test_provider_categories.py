"""Tests for provider category assignments.

Bug 1: OpenRouter should be in lab-apis category, not open-hosted.

This test should FAIL until the bug is fixed.
"""

import pytest

from satellite.examples.eval_data import PROVIDERS_BY_CATEGORY


class TestProviderCategories:
    """Test that providers are in the correct categories."""

    def test_openrouter_in_lab_apis(self) -> None:
        """OpenRouter should be available in the Lab APIs category.

        Bug: OpenRouter is currently in 'open-hosted' but users expect
        it in 'lab-apis' since it's a primary API provider for accessing
        models from OpenAI, Anthropic, etc.

        This test SHOULD FAIL until the bug is fixed.
        """
        lab_apis = PROVIDERS_BY_CATEGORY.get("lab-apis", [])
        provider_ids = [p["id"] for p in lab_apis]

        assert "openrouter" in provider_ids, (
            "OpenRouter should be in lab-apis category. "
            f"Currently lab-apis contains: {provider_ids}"
        )

    def test_openrouter_not_in_open_hosted(self) -> None:
        """After fix, OpenRouter should NOT be in open-hosted.

        This test documents the current (buggy) state where OpenRouter
        IS in open-hosted. After the fix, this test should PASS.
        """
        open_hosted = PROVIDERS_BY_CATEGORY.get("open-hosted", [])
        provider_ids = [p["id"] for p in open_hosted]

        # This assertion will FAIL after the fix (which is correct)
        # We want openrouter to NOT be in open-hosted
        assert "openrouter" not in provider_ids, (
            "OpenRouter should NOT be in open-hosted category after fix. "
            f"Currently open-hosted contains: {provider_ids}"
        )

    def test_lab_apis_has_major_providers(self) -> None:
        """Lab APIs should contain major model providers."""
        lab_apis = PROVIDERS_BY_CATEGORY.get("lab-apis", [])
        provider_ids = [p["id"] for p in lab_apis]

        # These should all be in lab-apis
        expected_providers = [
            "openai",
            "anthropic",
            "google",
            "openrouter",  # Bug: This one is missing
        ]

        for provider in expected_providers:
            assert provider in provider_ids, (
                f"{provider} should be in lab-apis category"
            )
