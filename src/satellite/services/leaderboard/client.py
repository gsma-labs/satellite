"""Leaderboard client: fetch, collect, and merge leaderboard data."""

from dataclasses import dataclass, field
from statistics import mean

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from satellite.services.evals import BENCHMARKS_BY_ID, JobManager
from satellite.services.evals.registry import BENCHMARKS

DATASET_ID = "GSMA/leaderboard"
PARQUET_FILE = "data/train-00000-of-00001.parquet"


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
        repo_id=DATASET_ID, filename=PARQUET_FILE, repo_type="dataset"
    )
    dataset = pq.read_table(path).to_pydict()

    score_cols = {b.id: b.hf_column for b in BENCHMARKS if b.hf_column in dataset}
    row_count = len(dataset["model"])

    entries = [_parse_row(dataset, row, score_cols) for row in range(row_count)]
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


def _parse_row(
    dataset: dict, row: int, score_cols: dict[str, str]
) -> LeaderboardEntry:
    raw_model = dataset["model"][row] or "Unknown"
    name, _, provider = raw_model.partition(" (")

    scores = {
        bench_id: _parse_score(dataset[col_name][row])
        for bench_id, col_name in score_cols.items()
    }

    return LeaderboardEntry(
        model=name,
        provider=provider.rstrip(")") or "Unknown",
        avg_score=_compute_avg(scores),
        scores=scores,
    )


def _parse_score(raw_value: float | list | None) -> float | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, list):
        return float(raw_value[0]) if raw_value else None
    return float(raw_value)
