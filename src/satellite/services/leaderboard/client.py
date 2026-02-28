"""Leaderboard client: fetch, collect, and merge leaderboard data."""

import ast
import csv
import logging
import math
from dataclasses import dataclass, field
from statistics import mean

from huggingface_hub import hf_hub_download

from satellite.services.evals import BENCHMARKS_BY_ID, JobManager
from satellite.services.evals.registry import BENCHMARKS

_log = logging.getLogger(__name__)

DATASET_ID = "GSMA/leaderboard"
CSV_FILE = "leaderboard_scores.csv"


def score_rank(entry: "LeaderboardEntry") -> tuple[bool, float]:
    no_score = entry.avg_score is None
    descending = -(entry.avg_score or 0)
    return (no_score, descending)


@dataclass
class LeaderboardEntry:
    """A single entry in the leaderboard."""

    model: str
    provider: str
    avg_score: float | None = None
    scores: dict[str, float | None] = field(default_factory=dict)
    is_local: bool = False


def fetch_leaderboard() -> list[LeaderboardEntry]:
    """Fetch leaderboard entries from the GSMA/leaderboard dataset."""
    path = hf_hub_download(
        repo_id=DATASET_ID, filename=CSV_FILE, repo_type="dataset"
    )

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = set(reader.fieldnames or [])
        # Remote CSV columns match benchmark IDs (e.g. "three_gpp"),
        # not hf_column (e.g. "3gpp_tsg"), so look up by b.id.
        score_cols = [b.id for b in BENCHMARKS if b.id in fieldnames]
        entries = [_parse_row_csv(row, score_cols) for row in reader]

    entries.sort(key=score_rank)
    return entries


def split_model_name(model_id: str) -> tuple[str, str]:
    """Split a model identifier into (provider, short_name).

    Examples:
        "openai/gpt-4-turbo" -> ("Openai", "gpt-4-turbo")
        "gpt-4o"             -> ("Unknown", "gpt-4o")
    """
    if "/" in model_id:
        provider, _, short_name = model_id.partition("/")
        return (provider.capitalize(), short_name)
    return ("Unknown", model_id)


def collect_local_entries(
    job_manager: JobManager,
) -> list[LeaderboardEntry]:
    """Collect leaderboard entries from locally completed evaluation jobs.

    A model qualifies only if a single job covers ALL benchmarks in the
    registry and has actual scores for each. If the same model qualifies
    in multiple jobs, only the most recent job's results are used.
    """
    bench_ids = set(BENCHMARKS_BY_ID)
    seen: dict[str, LeaderboardEntry] = {}

    for job in job_manager.list_jobs():
        job_results = job_manager.get_job_results(job.id)

        for model_id, ran_evals in job.evals.items():
            if model_id in seen:
                continue

            if not bench_ids.issubset(ran_evals):
                continue

            model_scores = job_results.get(model_id, {})
            if not bench_ids.issubset(model_scores):
                continue

            provider, short_name = split_model_name(model_id)
            pct_scores = {
                bench_id: model_scores[bench_id] * 100 for bench_id in bench_ids
            }
            avg_score = mean(pct_scores.values())

            seen[model_id] = LeaderboardEntry(
                model=short_name,
                provider=provider,
                avg_score=avg_score,
                scores=pct_scores,
                is_local=True,
            )

    return list(seen.values())


def merge_leaderboard(
    remote: list[LeaderboardEntry],
    local: list[LeaderboardEntry],
) -> list[LeaderboardEntry]:
    combined = [*remote, *local]
    combined.sort(key=score_rank)
    return combined


def _compute_avg(scores: dict[str, float | None]) -> float | None:
    """Compute average from individual benchmark scores, ignoring None values."""
    valid = [v for v in scores.values() if v is not None]
    if not valid:
        return None
    return mean(valid)


def _parse_row_csv(
    row: dict[str, str], score_cols: list[str]
) -> LeaderboardEntry:
    """Parse a single CSV row into a LeaderboardEntry.

    The remote CSV has separate ``model`` and ``provider`` columns, and stores
    scores as string-encoded lists like ``"[0.852, 0.0112]"`` in 0-1 range.
    """
    model = row.get("model", "").strip() or "Unknown"
    provider = row.get("provider", "").strip() or "Unknown"

    scores: dict[str, float | None] = {}
    for col in score_cols:
        scores[col] = _parse_csv_score(row.get(col, ""))

    return LeaderboardEntry(
        model=model,
        provider=provider,
        avg_score=_compute_avg(scores),
        scores=scores,
    )


def _parse_csv_score(raw: str) -> float | None:
    """Parse a CSV score cell.

    Values are string-encoded lists like ``"[0.852, 0.0112]"`` where the first
    element is the accuracy in 0-1 range. Returns percentage (0-100) or None.
    """
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return None
    if isinstance(value, list):
        if not value:
            return None
        val = float(value[0])
    else:
        val = float(value)
    if math.isnan(val) or math.isinf(val):
        _log.warning("Discarding NaN/Inf score: %s", raw)
        return None
    return val * 100


def _parse_score(raw_value: float | list | None) -> float | None:
    """Parse a score from a pydict/list format (used by local entries)."""
    if raw_value is None:
        return None
    if isinstance(raw_value, list):
        val = float(raw_value[0]) if raw_value else None
        if val is not None and (math.isnan(val) or math.isinf(val)):
            _log.warning("Discarding NaN/Inf score from list value: %s", raw_value)
            return None
        return val
    val = float(raw_value)
    if math.isnan(val) or math.isinf(val):
        _log.warning("Discarding NaN/Inf score: %s", raw_value)
        return None
    return val
