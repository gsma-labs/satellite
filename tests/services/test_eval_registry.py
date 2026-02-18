"""Tests for benchmark registry sample count helpers."""

from types import SimpleNamespace

import pytest

from satellite.services.evals import registry


def test_get_total_samples_uses_split_specific_overrides() -> None:
    """Known eval IDs return split-appropriate hardcoded sample counts."""
    assert registry.get_total_samples("teleqna", full=False) == 1000
    assert registry.get_total_samples("teleqna", full=True) == 10_000


def test_get_total_samples_falls_back_to_discovered_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown override IDs fall back to discovered BenchmarkConfig totals."""
    monkeypatch.setattr(
        registry,
        "BENCHMARKS_BY_ID",
        {"custom_eval": SimpleNamespace(total_samples=321)},
    )

    assert registry.get_total_samples("custom_eval", full=False) == 321
    assert registry.get_total_samples("custom_eval", full=True) == 321


def test_get_total_samples_returns_zero_when_unknown() -> None:
    """Unknown eval IDs with no metadata return 0."""
    assert registry.get_total_samples("__missing_eval__", full=False) == 0
