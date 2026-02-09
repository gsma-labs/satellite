"""Build a single-row model card parquet from completed eval logs.

Converts Inspect AI log files into the leaderboard's parquet schema,
bypassing the GitHub blob size limit that raw JSON trajectories hit.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import pyarrow as pa
import pyarrow.parquet as pq
from inspect_ai.log import EvalLog, read_eval_log

from satellite.services.evals import BENCHMARKS_BY_ID

if TYPE_CHECKING:
    from satellite.services.submit import SubmitPreview

MODEL_CARDS_DIR = "model_cards"

# Parquet columns in leaderboard order
SCORE_COLUMNS = ("teleqna", "telelogs", "telemath", "3gpp_tsg", "teletables")


def build_model_card_parquet(preview: SubmitPreview) -> tuple[str, bytes]:
    """Build a parquet file matching the leaderboard schema.

    Reads each log file with header_only=True (fast — skips full
    trajectory data), extracts per-benchmark accuracy, stderr, and
    sample count, then writes a single-row parquet.

    Args:
        preview: The submission preview containing model info and log paths.

    Returns:
        Tuple of (remote_path, parquet_bytes) ready for upload.

    Raises:
        ValueError: If no valid benchmark scores can be extracted.
    """
    benchmark_scores = _collect_benchmark_scores(preview.log_files)

    if not benchmark_scores:
        raise ValueError("No valid benchmark scores found in log files")

    model_display = _format_model_display(preview)
    row = _build_row(model_display, benchmark_scores)
    parquet_bytes = _write_parquet(row)

    remote_path = f"{MODEL_CARDS_DIR}/{preview.model_dir_name}.parquet"
    return (remote_path, parquet_bytes)


def _collect_benchmark_scores(
    log_files: list[Path],
) -> dict[str, tuple[float, float, int]]:
    """Extract (score_pct, stderr_pct, n_samples) per benchmark column.

    Returns:
        Dict mapping hf_column name to (score, stderr, n_samples).
    """
    scores: dict[str, tuple[float, float, int]] = {}

    for log_path in log_files:
        log = read_eval_log(str(log_path), header_only=True)
        extracted = _extract_score(log)
        if extracted is None:
            continue
        hf_column, score_pct, stderr_pct, n_samples = extracted
        scores[hf_column] = (score_pct, stderr_pct, n_samples)

    return scores


def _extract_score(log: EvalLog) -> tuple[str, float, float, int] | None:
    """Extract (hf_column, score_pct, stderr_pct, n_samples) from one log."""
    if not log.eval or not log.eval.task:
        return None
    if not log.results or not log.results.scores:
        return None

    task_id = log.eval.task.rsplit("/", 1)[-1]
    bench = BENCHMARKS_BY_ID.get(task_id)
    if bench is None:
        return None

    accuracy = log.results.scores[0].metrics.get("accuracy")
    if accuracy is None:
        return None

    score_pct = round(accuracy.value * 100, 2)

    stderr_metric = log.results.scores[0].metrics.get("stderr")
    stderr_pct = round(stderr_metric.value * 100, 6) if stderr_metric else 0.0

    n_samples = log.results.total_samples

    return (bench.hf_column, score_pct, stderr_pct, n_samples)


def _format_model_display(preview: SubmitPreview) -> str:
    """Format model name as 'short_name (Provider)' for the parquet row."""
    _, model_name = preview.model.split("/", 1)
    provider_display = preview.provider.capitalize()
    return f"{model_name} ({provider_display})"


def _build_row(
    model_display: str,
    benchmark_scores: dict[str, tuple[float, float, int]],
) -> dict[str, object]:
    """Build a single-row dict matching the leaderboard schema."""
    row: dict[str, object] = {
        "model": model_display,
        "date": date.today().isoformat(),
    }

    for col in SCORE_COLUMNS:
        if col not in benchmark_scores:
            row[col] = None
            continue
        score, stderr, n_samples = benchmark_scores[col]
        row[col] = [score, stderr, float(n_samples)]

    return row


def _write_parquet(row: dict[str, object]) -> bytes:
    """Serialize a single-row dict to parquet bytes using pyarrow."""
    score_type = pa.list_(pa.float64())
    schema = pa.schema(
        [pa.field("model", pa.string())]
        + [pa.field(col, score_type) for col in SCORE_COLUMNS]
        + [pa.field("date", pa.string())]
    )

    arrays = []
    for field in schema:
        value = row.get(field.name)
        if field.name in SCORE_COLUMNS:
            arrays.append(pa.array([value], type=score_type))
            continue
        arrays.append(pa.array([value], type=field.type))

    table = pa.table(arrays, schema=schema)

    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()
