"""Tests for parquet builder -- schema, score conversion, and edge cases."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

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


ALL_LOGS: dict[str, _EvalLog] = {
    "/fake/teleqna.json": _EvalLog("teleqna", 0.85, 1000, stderr=0.012),
    "/fake/telelogs.json": _EvalLog("telelogs", 0.90, 100, stderr=0.03),
    "/fake/telemath.json": _EvalLog("telemath", 0.75, 100, stderr=0.04),
    "/fake/teletables.json": _EvalLog("teletables", 0.80, 100, stderr=0.04),
    "/fake/3gpp_tsg.json": _EvalLog("three_gpp", 0.70, 100, stderr=0.05),
}

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
        benchmarks=["teleqna", "telelogs", "telemath", "teletables", "three_gpp"],
        scores={
            "teleqna": 0.85,
            "telelogs": 0.90,
            "telemath": 0.75,
            "teletables": 0.80,
            "three_gpp": 0.70,
        },
        log_files=log_files or [Path(f"/fake/{b}.json") for b in SCORE_COLUMNS],
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
    """Verify the output parquet matches the leaderboard schema."""

    def test_has_required_columns(self) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        expected = {"model", "teleqna", "telelogs", "telemath", "3gpp_tsg", "teletables", "date"}
        assert set(table.column_names) == expected

    def test_single_row(self) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        assert table.num_rows == 1

    def test_remote_path_format(self) -> None:
        remote_path, _ = build_model_card_parquet(_make_preview())
        assert remote_path == "model_cards/openai_gpt-4o.parquet"

    def test_model_display_format(self) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        model_name = table.column("model").to_pylist()[0]
        assert model_name == "gpt-4o (Openai)"

    def test_date_is_today_iso(self) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        parquet_date = table.column("date").to_pylist()[0]
        assert parquet_date == date.today().isoformat()


@pytest.mark.usefixtures("_mock_logs")
class TestScoreConversion:
    """Verify 0-1 accuracy is converted to 0-100 percentage."""

    SCORE_INDEX = 0
    STDERR_INDEX = 1
    SAMPLES_INDEX = 2

    @pytest.mark.parametrize(
        ("column", "index", "expected"),
        [
            pytest.param("teleqna", SCORE_INDEX, 85.0, id="accuracy_pct"),
            pytest.param("teleqna", STDERR_INDEX, 1.2, id="stderr_pct"),
            pytest.param("teleqna", SAMPLES_INDEX, 1000.0, id="n_samples"),
        ],
    )
    def test_teleqna_score_triplet(
        self, column: str, index: int, expected: float
    ) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        arr = table.column(column).to_pylist()[0]
        assert arr[index] == pytest.approx(expected, abs=0.01)

    @pytest.mark.parametrize(
        ("column", "expected_score"),
        [
            pytest.param("teleqna", 85.0, id="teleqna"),
            pytest.param("telelogs", 90.0, id="telelogs"),
            pytest.param("telemath", 75.0, id="telemath"),
            pytest.param("teletables", 80.0, id="teletables"),
            pytest.param("3gpp_tsg", 70.0, id="3gpp_tsg"),
        ],
    )
    def test_all_benchmarks_scored(
        self, column: str, expected_score: float
    ) -> None:
        _, parquet_bytes = build_model_card_parquet(_make_preview())

        table = _read_parquet(parquet_bytes)
        arr = table.column(column).to_pylist()[0]
        assert arr[self.SCORE_INDEX] == expected_score


class TestMissingStderr:
    """Verify stderr defaults to 0.0 when not present in metrics."""

    def test_no_stderr_defaults_to_zero(self) -> None:
        logs_no_stderr = {
            "/fake/teleqna.json": _EvalLog("teleqna", 0.85, 1000),
        }

        def mock_read(path: str, header_only: bool = False) -> _EvalLog:
            return logs_no_stderr[path]

        preview = _make_preview(log_files=[Path("/fake/teleqna.json")])

        with patch(MOCK_PATCH_TARGET, side_effect=mock_read):
            _, parquet_bytes = build_model_card_parquet(preview)

        table = _read_parquet(parquet_bytes)
        arr = table.column("teleqna").to_pylist()[0]
        assert arr[1] == 0.0


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
