"""Tests for EvalSettings serialization and backward compatibility."""

import json

import pytest

from satellite.services.config import EvalSettings, EvalSettingsManager


class TestEvalSettingsFullBenchmark:
    """Tests for the full_benchmark field on EvalSettings."""

    def test_full_benchmark_defaults_false(self) -> None:
        """EvalSettings() defaults full_benchmark to False."""
        assert EvalSettings().full_benchmark is False

    @pytest.mark.parametrize(
        "value",
        [pytest.param(True, id="true"), pytest.param(False, id="false")],
    )
    def test_full_benchmark_round_trip(self, tmp_path, value: bool) -> None:
        """full_benchmark survives save/load round-trip."""
        path = tmp_path / "eval_settings.json"
        manager = EvalSettingsManager(settings_path=path)

        manager.save(EvalSettings(full_benchmark=value))

        assert manager.load().full_benchmark is value

    def test_backward_compat_missing_field(self, tmp_path) -> None:
        """Loading a legacy settings file without full_benchmark defaults to False."""
        path = tmp_path / "eval_settings.json"
        legacy = {
            "limit": None,
            "epochs": 1,
            "max_connections": 10,
            "token_limit": None,
            "message_limit": None,
        }
        path.write_text(json.dumps(legacy))

        assert EvalSettingsManager(settings_path=path).load().full_benchmark is False
