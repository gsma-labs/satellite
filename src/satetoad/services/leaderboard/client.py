"""Leaderboard client for fetching data from HuggingFace."""

from dataclasses import dataclass, field

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from satetoad.services.evals.registry import BENCHMARKS

DATASET_ID = "GSMA/leaderboard"
PARQUET_FILE = "data/train-00000-of-00001.parquet"


@dataclass
class LeaderboardEntry:
    """A single entry in the leaderboard.

    Attributes:
        model: Model name (e.g., "gpt-4o", "claude-3-opus")
        provider: Provider name (e.g., "OpenAI", "Anthropic")
        tci: Telecom Capability Index score (overall ranking metric)
        scores: Dynamic dict mapping eval_id to score (e.g., {"teleqna": 85.5})
    """

    model: str
    provider: str
    tci: float | None = None
    scores: dict[str, float | None] = field(default_factory=dict)


def fetch_leaderboard() -> list[LeaderboardEntry]:
    """Fetch leaderboard entries from the GSMA/leaderboard dataset."""
    path = hf_hub_download(repo_id=DATASET_ID, filename=PARQUET_FILE, repo_type="dataset")
    data = pq.read_table(path).to_pydict()

    columns = {
        b.id: b.hf_column
        for b in BENCHMARKS
        if b.hf_column in data
    }

    entries = [_build_entry(data, i, columns) for i in range(len(data["model"]))]
    entries.sort(key=lambda e: (e.tci is None, -(e.tci or 0)))
    return entries


def _build_entry(data: dict, i: int, columns: dict[str, str]) -> LeaderboardEntry:
    """Build a LeaderboardEntry from row i of the data."""
    model_raw = data["model"][i] or "Unknown"
    model, _, provider = model_raw.partition(" (")

    return LeaderboardEntry(
        model=model,
        provider=provider.rstrip(")") or "Unknown",
        tci=_extract_score(data["tci"][i]),
        scores={eval_id: _extract_score(data[col][i]) for eval_id, col in columns.items()},
    )


def _extract_score(value) -> float | None:
    """Extract numeric score from HuggingFace format."""
    if value is None:
        return None
    if isinstance(value, list):
        return float(value[0]) if value else None
    return float(value)
