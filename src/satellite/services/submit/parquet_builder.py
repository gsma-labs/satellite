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

from satellite.services.evals import BENCHMARKS, BENCHMARKS_BY_ID

if TYPE_CHECKING:
    from satellite.services.submit import SubmitPreview

MODEL_CARDS_DIR = "model_cards"

# Parquet score columns in registry order (deduplicated by benchmark id).
# Uses b.id (e.g. "three_gpp") to match the HuggingFace dataset schema,
# NOT b.hf_column which is the evals dataset config name (e.g. "3gpp_tsg").
SCORE_COLUMNS = tuple(dict.fromkeys(b.id for b in BENCHMARKS))

_PATH_TRAVERSAL_PATTERNS = ("..", "/", "\\")


def _validate_safe_path_component(name: str) -> str:
    """Reject path traversal sequences in a filename component.

    Raises:
        ValueError: If name contains '..', '/', or backslash.
    """
    for pattern in _PATH_TRAVERSAL_PATTERNS:
        if pattern in name:
            raise ValueError(
                f"Unsafe character '{pattern}' in model directory name: {name}"
            )
    return name


def build_model_card_parquet(preview: SubmitPreview) -> tuple[str, bytes]:
    """Build a parquet file matching the HuggingFace leaderboard schema.

    Reads each log file with header_only=True (fast — skips full
    trajectory data), extracts per-benchmark accuracy and stderr,
    then writes a single-row parquet with string-encoded scores.

    Args:
        preview: The submission preview containing model info and log paths.

    Returns:
        Tuple of (remote_path, parquet_bytes) ready for upload.

    Raises:
        ValueError: If no valid benchmark scores can be extracted,
            or if the model directory name contains unsafe path characters.
    """
    safe_dir_name = _validate_safe_path_component(preview.model_dir_name)
    benchmark_scores = _collect_benchmark_scores(preview.log_files)

    if not benchmark_scores:
        raise ValueError("No valid benchmark scores found in log files")

    _, model_name = preview.model.split("/", 1)
    provider_display = preview.provider.capitalize()
    row = _build_row(model_name, provider_display, benchmark_scores)
    parquet_bytes = _write_parquet(row)

    remote_path = f"{MODEL_CARDS_DIR}/{safe_dir_name}.parquet"
    return (remote_path, parquet_bytes)


def _collect_benchmark_scores(
    log_files: list[Path],
) -> dict[str, tuple[float, float]]:
    """Extract (score_01, stderr_01) per benchmark id.

    Returns:
        Dict mapping benchmark id to (score, stderr) in 0-1 scale.
    """
    scores: dict[str, tuple[float, float]] = {}

    for log_path in log_files:
        log = read_eval_log(str(log_path), header_only=True)
        extracted = _extract_score(log)
        if extracted is None:
            continue
        bench_id, score_01, stderr_01 = extracted
        scores[bench_id] = (score_01, stderr_01)

    return scores


def _extract_score(log: EvalLog) -> tuple[str, float, float] | None:
    """Extract (bench_id, score_01, stderr_01) from one log.

    Scores are kept in 0-1 scale to match the HuggingFace dataset schema.
    """
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

    score_01 = round(accuracy.value, 6)

    stderr_metric = log.results.scores[0].metrics.get("stderr")
    stderr_01 = round(stderr_metric.value, 6) if stderr_metric else 0.0

    return (bench.id, score_01, stderr_01)


def _build_row(
    model_name: str,
    provider: str,
    benchmark_scores: dict[str, tuple[float, float]],
) -> dict[str, object]:
    """Build a single-row dict matching the HuggingFace leaderboard schema.

    Scores are stored as string-encoded "[score, stderr]" at 0-1 scale.
    """
    row: dict[str, object] = {
        "model": model_name,
        "provider": provider,
    }

    for col in SCORE_COLUMNS:
        if col not in benchmark_scores:
            row[col] = None
            continue
        score, stderr = benchmark_scores[col]
        row[col] = str([score, stderr])

    row["date"] = date.today().isoformat()
    return row


def _write_parquet(row: dict[str, object]) -> bytes:
    """Serialize a single-row dict to parquet bytes using pyarrow.

    All columns are strings to match the HuggingFace dataset schema.
    """
    schema = pa.schema(
        [pa.field("model", pa.string()), pa.field("provider", pa.string())]
        + [pa.field(col, pa.string()) for col in SCORE_COLUMNS]
        + [pa.field("date", pa.string())]
    )

    arrays = []
    for field in schema:
        value = row.get(field.name)
        arrays.append(pa.array([value], type=pa.string()))

    table = pa.table(arrays, schema=schema)

    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()
