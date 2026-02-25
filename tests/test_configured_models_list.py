"""Tests for ConfiguredModelsList widget.

Bug 3 (FIXED): Button IDs with slashes caused BadIdentifier errors.

Model paths like "openai/gpt-4o" were used directly in button IDs,
causing Textual's DOM to reject them because "/" is not a valid
identifier character.

Fix: Replace "/" with "-" when creating button IDs.

This is a regression suite to ensure invalid characters are sanitized.
"""

from satellite.widgets.configured_models_list import _sanitize_model_path_for_id


class TestButtonIdSanitization:
    """Test that model paths with slashes don't break button IDs."""

    def test_slash_replaced_in_sanitized_id(self) -> None:
        """Slashes in model paths should be replaced with hyphens for IDs.

        This tests the sanitization logic that was added to fix the bug.
        """
        normalized_path = "openai/gpt-4o"
        sanitized_id = _sanitize_model_path_for_id(normalized_path)

        assert "/" not in sanitized_id, "Sanitized ID should not contain slashes"
        assert sanitized_id == "openai-gpt-4o", "Slashes should become hyphens"

    def test_multiple_slashes_all_replaced(self) -> None:
        """Model paths with multiple slashes should have all replaced."""
        normalized_path = "openrouter/openai/gpt-4o-mini"
        sanitized_id = _sanitize_model_path_for_id(normalized_path)

        assert sanitized_id == "openrouter-openai-gpt-4o-mini"
        assert sanitized_id.count("/") == 0

    def test_button_id_format_without_dots(self) -> None:
        """Button ID should be valid when model has no dots."""
        normalized_path = "google/gemini-pro"
        sanitized_id = _sanitize_model_path_for_id(normalized_path)
        button_id = f"delete-{sanitized_id}"

        # Textual identifiers: letters, numbers, underscores, hyphens only
        # Must not begin with a number
        import re
        valid_id_pattern = r"^[a-zA-Z_][a-zA-Z0-9_-]*$"

        assert re.match(valid_id_pattern, button_id), (
            f"Button ID '{button_id}' should be a valid Textual identifier"
        )

    def test_button_id_with_dots_is_sanitized(self) -> None:
        """Model names with dots should be sanitized to valid Textual IDs."""
        normalized_path = "google/gemini-2.5-pro"
        sanitized_id = _sanitize_model_path_for_id(normalized_path)
        button_id = f"delete-{sanitized_id}"

        import re
        valid_id_pattern = r"^[a-zA-Z_][a-zA-Z0-9_-]*$"

        assert "." not in button_id, "Sanitized button ID should not contain dots"
        assert re.match(valid_id_pattern, button_id), (
            f"Button ID '{button_id}' should be a valid Textual identifier"
        )

    def test_colon_replaced_in_sanitized_id(self) -> None:
        """Colons in model paths should be replaced with hyphens for IDs."""
        normalized_path = "ollama/gpt-oss:120b"
        sanitized_id = _sanitize_model_path_for_id(normalized_path)
        button_id = f"delete-{sanitized_id}"

        import re
        valid_id_pattern = r"^[a-zA-Z_][a-zA-Z0-9_-]*$"

        assert ":" not in sanitized_id, "Sanitized ID should not contain colons"
        assert button_id == "delete-ollama-gpt-oss-120b"
        assert re.match(valid_id_pattern, button_id), (
            f"Button ID '{button_id}' should be a valid Textual identifier"
        )

    def test_original_path_preserved_for_delete_message(self) -> None:
        """The original normalized path should still be used for delete logic.

        The fix only sanitizes the button ID, not the path used for
        identifying which model to delete.
        """
        original_path = "openai/gpt-4o"
        sanitized_id = _sanitize_model_path_for_id(original_path)

        # These should be different
        assert original_path != sanitized_id

        # Original path is what gets passed to DeleteRequested message
        # Sanitized ID is only for the DOM
        assert "/" in original_path  # Original has slashes
        assert "/" not in sanitized_id  # Sanitized doesn't


class TestTextualIdentifierRules:
    """Document Textual's identifier rules for reference."""

    def test_valid_identifiers(self) -> None:
        """These are valid Textual identifiers."""
        import re
        valid_id_pattern = r"^[a-zA-Z_][a-zA-Z0-9_-]*$"

        valid_ids = [
            "delete-openai-gpt-4o",
            "delete-anthropic-claude-3",
            "my_button",
            "Button1",
            "_private",
        ]

        for id_ in valid_ids:
            assert re.match(valid_id_pattern, id_), f"'{id_}' should be valid"

    def test_invalid_identifiers(self) -> None:
        """These are INVALID Textual identifiers."""
        import re
        valid_id_pattern = r"^[a-zA-Z_][a-zA-Z0-9_-]*$"

        invalid_ids = [
            "delete-openai/gpt-4o",  # Contains slash (THE BUG)
            "1-starts-with-number",  # Starts with number
            "has spaces",  # Contains space
            "has.dot",  # Contains dot
        ]

        for id_ in invalid_ids:
            assert not re.match(valid_id_pattern, id_), f"'{id_}' should be invalid"

    def test_slash_is_invalid_character(self) -> None:
        """Forward slash is not allowed in Textual identifiers.

        This is the root cause of Bug 3.
        """
        buggy_id = "delete-openai/gpt-4o"

        # This would raise BadIdentifier in Textual
        assert "/" in buggy_id, "Slash makes the ID invalid"
