"""Tests for parquet builder -- schema, score conversion, and edge cases."""

from __future__ import annotations

import ast
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


# -- Mock EvalLog helpers --------------------------------------------------


class _Metric:
    def __init__(self, value: float) -> None:
        self.value = value


class _Score:
    def __init__(self, accuracy: float, stderr: float | None = None) -> None:
        self.metrics: dict[str, _Metric] = {"accuracy": _Metric(accuracy)}
        if stderr is not None:
            self.metrics["stderr"] = _Metric(stderr)


class _Results:
    def __init__(self, scores: list[_Score], total_samples: int) -> None:
        self.scores = scores
        self.total_samples = total_samples


class _Eval:
    def __init__(self, model: str, task: str) -> None:
        self.model = model
        self.task = task


class _EvalLog:
    def __init__(
        self,
        task: str,
        accuracy: float,
        total_samples: int,
        stderr: float | None = None,
        model: str = "openai/gpt-4o",
    ) -> None:
        self.eval = _Eval(model=model, task=task)
        self.results = _Results(
            scores=[_Score(accuracy, stderr)],
            total_samples=total_samples,
        )


_KNOWN_ACCURACY_BY_BENCH_ID: dict[str, float] = {
    "teleqna": 0.85,
    "telelogs": 0.90,
    "telemath": 0.75,
    "teletables": 0.80,
    "three_gpp": 0.70,
}

_KNOWN_STDERR_BY_BENCH_ID: dict[str, float] = {
    "teleqna": 0.012,
    "telelogs": 0.03,
    "telemath": 0.04,
    "teletables": 0.04,
    "three_gpp": 0.05,
}

_ACCURACY_BY_BENCH_ID: dict[str, float] = {}
_STDERR_BY_BENCH_ID: dict[str, float] = {}
for index, benchmark in enumerate(BENCHMARKS):
    _ACCURACY_BY_BENCH_ID[benchmark.id] = _KNOWN_ACCURACY_BY_BENCH_ID.get(
        benchmark.id,
        round(0.60 + (0.03 * index), 4),
    )
    _STDERR_BY_BENCH_ID[benchmark.id] = _KNOWN_STDERR_BY_BENCH_ID.get(
        benchmark.id,
        round(0.01 + (0.002 * index), 6),
    )

# Log file paths keyed by benchmark id (not hf_column).
ALL_LOGS: dict[str, _EvalLog] = {
    f"/fake/{benchmark.id}.json": _EvalLog(
        benchmark.id,
        _ACCURACY_BY_BENCH_ID[benchmark.id],
        benchmark.total_samples or 100,
        stderr=_STDERR_BY_BENCH_ID[benchmark.id],
    )
    for benchmark in BENCHMARKS
}

PRIMARY_BENCH_ID = "teleqna" if "teleqna" in BENCHMARKS_BY_ID else BENCHMARKS[0].id
PRIMARY_BENCH = BENCHMARKS_BY_ID[PRIMARY_BENCH_ID]

BENCHMARK_SCORE_PARAMS = [
    pytest.param(
        bench_id,
        _ACCURACY_BY_BENCH_ID[bench_id],
        id=bench_id,
    )
    for bench_id in _ACCURACY_BY_BENCH_ID
]

MOCK_PATCH_TARGET = "satellite.services.submit.parquet_builder.read_eval_log"


def _mock_read_eval_log(path: str, header_only: bool = False) -> _EvalLog:
    return ALL_LOGS[path]


def _make_preview(
    log_files: list[Path] | None = None,
    model: str = "openai/gpt-4o",
    provider: str = "openai",
    model_dir_name: str = "openai_gpt-4o",
) -> SubmitPreview:
    return SubmitPreview(
        job_id="job_001",
        model=model,
        provider=provider,
        model_dir_name=model_dir_name,
        benchmarks=[benchmark.id for benchmark in BENCHMARKS],
        scores={bench_id: score for bench_id, score in _ACCURACY_BY_BENCH_ID.items()},
        log_files=log_files
        or [Path(f"/fake/{benchmark.id}.json") for benchmark in BENCHMARKS],
    )


@pytest.fixture()
def _mock_logs() -> object:
    """Patch read_eval_log to return pre-built mock logs."""
    with patch(MOCK_PATCH_TARGET, side_effect=_mock_read_eval_log) as mock:
        yield mock


def _read_parquet(parquet_bytes: bytes) -> pa.Table:
    return pq.read_table(pa.BufferReader(parquet_bytes))


# -- Tests -----------------------------------------------------------------


@pytest.mark.usefixtures("_mock_logs")
class TestParquetSchema:
    """Verify the output parquet matches the HF leaderboard schema."""

    def test_has_required_columns(self) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        expected = {"model", "provider", *SCORE_COLUMNS, "date"}
        assert set(table.column_names) == expected

    def test_schema_column_order(self) -> None:
        """Verify columns are in the order expected by the leaderboard."""
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        expected_order = ["model", "provider", *SCORE_COLUMNS, "date"]
        assert table.column_names == expected_order

    def test_single_row(self) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        assert table.num_rows == 1

    def test_remote_path_format(self) -> None:
        remote_path, _ = build_model_card_parquet(_make_preview())
        assert remote_path == "model_cards/openai_gpt-4o.parquet"

    def test_model_is_short_name(self) -> None:
        """Model column should be short name only, not 'name (Provider)'."""
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        model_name = table.column("model").to_pylist()[0]
        assert model_name == "gpt-4o"

    def test_provider_column(self) -> None:
        """Provider column should be capitalized provider name."""
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        provider = table.column("provider").to_pylist()[0]
        assert provider == "Openai"

    def test_date_is_today_iso(self) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        parquet_date = table.column("date").to_pylist()[0]
        assert parquet_date == date.today().isoformat()

    def test_score_columns_use_benchmark_id(self) -> None:
        """SCORE_COLUMNS should use benchmark IDs, not hf_column names."""
        for col in SCORE_COLUMNS:
            assert col in BENCHMARKS_BY_ID, f"{col} not a benchmark id"

    def test_all_columns_are_strings(self) -> None:
        """All parquet columns should be string type to match HF dataset."""
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        for field in table.schema:
            assert field.type == pa.string(), (
                f"Column {field.name} should be string, got {field.type}"
            )


@pytest.mark.usefixtures("_mock_logs")
class TestScoreConversion:
    """Verify scores are string-encoded [score, stderr] at 0-1 scale."""

    def test_score_is_string_encoded(self) -> None:
        """Score columns should be string-encoded '[score, stderr]'."""
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        raw = table.column(PRIMARY_BENCH_ID).to_pylist()[0]
        assert isinstance(raw, str)
        parsed = ast.literal_eval(raw)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_primary_score_value(self) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        raw = table.column(PRIMARY_BENCH_ID).to_pylist()[0]
        parsed = ast.literal_eval(raw)
        assert parsed[0] == pytest.approx(
            _ACCURACY_BY_BENCH_ID[PRIMARY_BENCH_ID], abs=1e-4
        )

    def test_primary_stderr_value(self) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        raw = table.column(PRIMARY_BENCH_ID).to_pylist()[0]
        parsed = ast.literal_eval(raw)
        assert parsed[1] == pytest.approx(
            _STDERR_BY_BENCH_ID[PRIMARY_BENCH_ID], abs=1e-4
        )

    @pytest.mark.parametrize(
        ("column", "expected_score"),
        BENCHMARK_SCORE_PARAMS,
    )
    def test_all_benchmarks_scored(
        self, column: str, expected_score: float
    ) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        raw = table.column(column).to_pylist()[0]
        parsed = ast.literal_eval(raw)
        assert parsed[0] == pytest.approx(expected_score, abs=1e-4)


class TestMissingStderr:
    """Verify stderr defaults to 0.0 when not present in metrics."""

    def test_no_stderr_defaults_to_zero(self) -> None:
        logs_no_stderr = {
            f"/fake/{PRIMARY_BENCH_ID}.json": _EvalLog(
                PRIMARY_BENCH_ID,
                _ACCURACY_BY_BENCH_ID[PRIMARY_BENCH_ID],
                PRIMARY_BENCH.total_samples or 100,
            ),
        }

        def mock_read(path: str, header_only: bool = False) -> _EvalLog:
            return logs_no_stderr[path]

        preview = _make_preview(log_files=[Path(f"/fake/{PRIMARY_BENCH_ID}.json")])

        with patch(MOCK_PATCH_TARGET, side_effect=mock_read):
            _, parquet_bytes = build_model_card_parquet(preview)

        table = _read_parquet(parquet_bytes)
        raw = table.column(PRIMARY_BENCH_ID).to_pylist()[0]
        parsed = ast.literal_eval(raw)
        assert parsed[1] == 0.0


class TestErrorCases:
    """Verify proper error handling for invalid inputs."""

    def test_no_valid_logs_raises(self) -> None:
        """Logs with no eval data should raise ValueError."""

        class _BadLog:
            def __init__(self) -> None:
                self.eval = None
                self.results = None

        def mock_read(path: str, header_only: bool = False) -> _BadLog:
            return _BadLog()

        preview = _make_preview()

        with (
            patch(MOCK_PATCH_TARGET, side_effect=mock_read),
            pytest.raises(ValueError, match="No valid benchmark scores"),
        ):
            build_model_card_parquet(preview)

    @pytest.mark.parametrize(
        "bad_name",
        [
            pytest.param("../etc/passwd", id="dot_dot_slash"),
            pytest.param("model/../../escape", id="embedded_traversal"),
            pytest.param("model\\name", id="backslash"),
        ],
    )
    def test_path_traversal_rejected(self, bad_name: str) -> None:
        """model_dir_name with path traversal sequences must raise ValueError."""
        preview = _make_preview(model_dir_name=bad_name)

        with pytest.raises(ValueError, match="Unsafe character"):
            build_model_card_parquet(preview)
