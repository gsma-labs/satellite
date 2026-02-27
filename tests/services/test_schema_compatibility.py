"""Schema compatibility tests between Satellite's parquet output and the leaderboard.

These tests act as a contract: if the leaderboard's expected schema changes,
these tests must be updated — preventing silent drift.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from satellite.services.evals import BENCHMARKS, BENCHMARKS_BY_ID
from satellite.services.submit import SubmitPreview
from satellite.services.submit.parquet_builder import (
    SCORE_COLUMNS,
    build_model_card_parquet,
)

# Reuse mock helpers from the parquet builder tests
from tests.services.test_parquet_builder import (
    ALL_LOGS,
    MOCK_PATCH_TARGET,
    _mock_read_eval_log,
)

# ── Leaderboard expectations (kept in sync manually) ─────────────────────

# These are the columns the leaderboard validation script expects.
# The original 5 + 2 new benchmarks (oranbench, srsranbench).
LEADERBOARD_REQUIRED_COLUMNS = {"model", "date"}
LEADERBOARD_SCORE_COLUMNS = {b.hf_column for b in BENCHMARKS}

# Model display format: "model_name (Provider)"
MODEL_DISPLAY_PATTERN = re.compile(r"^.+ \([A-Z][a-z-]+\)$")


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_preview() -> SubmitPreview:
    return SubmitPreview(
        job_id="job_001",
        model="openai/gpt-4o",
        provider="openai",
        model_dir_name="openai_gpt-4o",
        benchmarks=[b.id for b in BENCHMARKS],
        scores={b.id: 0.85 for b in BENCHMARKS},
        log_files=[Path(f"/fake/{b.hf_column}.json") for b in BENCHMARKS],
    )


def _build_parquet() -> pa.Table:
    with patch(MOCK_PATCH_TARGET, side_effect=_mock_read_eval_log):
        _, parquet_bytes = build_model_card_parquet(_make_preview())
    return pq.read_table(pa.BufferReader(parquet_bytes))


# ── Tests ────────────────────────────────────────────────────────────────


class TestLeaderboardColumns:
    """Verify parquet has all columns the leaderboard requires."""

    def test_has_model_and_date(self) -> None:
        table = _build_parquet()
        assert "model" in table.column_names
        assert "date" in table.column_names

    def test_has_all_benchmark_score_columns(self) -> None:
        table = _build_parquet()
        for col in LEADERBOARD_SCORE_COLUMNS:
            assert col in table.column_names, f"Missing score column: {col}"

    def test_no_extra_unexpected_columns(self) -> None:
        """All columns should be model, date, or known score columns."""
        table = _build_parquet()
        expected = LEADERBOARD_REQUIRED_COLUMNS | LEADERBOARD_SCORE_COLUMNS
        actual = set(table.column_names)
        unexpected = actual - expected
        assert not unexpected, f"Unexpected columns in parquet: {unexpected}"

    def test_score_columns_match_registry(self) -> None:
        """SCORE_COLUMNS in parquet_builder stays in sync with BENCHMARKS."""
        expected = tuple(dict.fromkeys(b.hf_column for b in BENCHMARKS))
        assert SCORE_COLUMNS == expected


class TestScoreTripletFormat:
    """Verify each score cell is a [float, float, float] triplet."""

    @pytest.mark.parametrize(
        "column",
        [pytest.param(b.hf_column, id=b.hf_column) for b in BENCHMARKS],
    )
    def test_score_is_three_element_list(self, column: str) -> None:
        table = _build_parquet()
        value = table.column(column).to_pylist()[0]
        assert isinstance(value, list), f"{column} should be a list"
        assert len(value) == 3, f"{column} should have 3 elements (score, stderr, n)"

    @pytest.mark.parametrize(
        "column",
        [pytest.param(b.hf_column, id=b.hf_column) for b in BENCHMARKS],
    )
    def test_triplet_values_are_floats(self, column: str) -> None:
        table = _build_parquet()
        value = table.column(column).to_pylist()[0]
        for i, v in enumerate(value):
            assert isinstance(v, float), f"{column}[{i}] should be float, got {type(v)}"

    @pytest.mark.parametrize(
        "column",
        [pytest.param(b.hf_column, id=b.hf_column) for b in BENCHMARKS],
    )
    def test_score_percentage_is_reasonable(self, column: str) -> None:
        """Score (index 0) should be between 0 and 100 (percentage)."""
        table = _build_parquet()
        value = table.column(column).to_pylist()[0]
        score = value[0]
        assert 0 <= score <= 100, f"{column} score {score} not in [0, 100]"

    @pytest.mark.parametrize(
        "column",
        [pytest.param(b.hf_column, id=b.hf_column) for b in BENCHMARKS],
    )
    def test_n_samples_is_positive(self, column: str) -> None:
        """Sample count (index 2) should be positive."""
        table = _build_parquet()
        value = table.column(column).to_pylist()[0]
        n_samples = value[2]
        assert n_samples > 0, f"{column} n_samples should be positive"


class TestModelDisplayFormat:
    """Verify model name matches leaderboard's expected pattern."""

    def test_model_format_matches_pattern(self) -> None:
        table = _build_parquet()
        model_name = table.column("model").to_pylist()[0]
        assert MODEL_DISPLAY_PATTERN.match(model_name), (
            f"Model '{model_name}' doesn't match 'name (Provider)' pattern"
        )

    def test_provider_is_capitalized(self) -> None:
        table = _build_parquet()
        model_name = table.column("model").to_pylist()[0]
        # Extract provider from "model_name (Provider)"
        provider = model_name.split("(")[1].rstrip(")")
        assert provider[0].isupper(), f"Provider '{provider}' should be capitalized"


class TestDateFormat:
    """Verify date is ISO format string."""

    def test_date_is_iso_format(self) -> None:
        table = _build_parquet()
        date_val = table.column("date").to_pylist()[0]
        # Should be parseable as ISO date
        parsed = date.fromisoformat(date_val)
        assert parsed == date.today()


class TestParquetSchemaTypes:
    """Verify PyArrow schema types match leaderboard expectations."""

    def test_model_is_string_type(self) -> None:
        table = _build_parquet()
        assert table.schema.field("model").type == pa.string()

    def test_date_is_string_type(self) -> None:
        table = _build_parquet()
        assert table.schema.field("date").type == pa.string()

    def test_score_columns_are_list_of_float64(self) -> None:
        table = _build_parquet()
        expected_type = pa.list_(pa.float64())
        for col in SCORE_COLUMNS:
            actual_type = table.schema.field(col).type
            assert actual_type == expected_type, (
                f"{col}: expected {expected_type}, got {actual_type}"
            )
