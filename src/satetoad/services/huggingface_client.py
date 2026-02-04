"""HuggingFace dataset client for fetching leaderboard data.

This module provides a simple interface to fetch leaderboard data from
the GSMA/leaderboard dataset on HuggingFace using the datasets library.

Authentication:
    Set HF_TOKEN environment variable for private datasets.
"""

from __future__ import annotations

import os
import re
from typing import Any

from satetoad.services.eval_registry import get_available_evals
from satetoad.services.leaderboard_types import LeaderboardEntry

DATASET_REPO = "GSMA/leaderboard"


class HuggingFaceError(Exception):
    """Error fetching from HuggingFace API."""

    pass


def _parse_model_provider(combined: str) -> tuple[str, str]:
    """Parse 'model (Provider)' format into (model, provider) tuple.

    Args:
        combined: Combined model string like "gpt-4o (Openai)"

    Returns:
        Tuple of (model_name, provider)
    """
    match = re.match(r"^(.+?)\s*\(([^)]+)\)$", combined)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return combined, "Unknown"


def _extract_score(value: list[float] | None) -> float | None:
    """Extract score from HuggingFace format [score, stderr, n_samples].

    Args:
        value: List of [score, stderr, n_samples] or None

    Returns:
        The score value or None
    """
    if value is None or not isinstance(value, list) or len(value) < 1:
        return None
    return value[0]


def _transform_row(row: dict[str, Any]) -> LeaderboardEntry:
    """Transform a HuggingFace row to LeaderboardEntry.

    Args:
        row: Raw row from HuggingFace dataset

    Returns:
        LeaderboardEntry with scores populated dynamically from registry
    """
    model_str = row.get("model", "Unknown")
    model, provider = _parse_model_provider(model_str)

    # Build scores dict dynamically from registry
    scores = {}
    for eval_info in get_available_evals():
        scores[eval_info.id] = _extract_score(row.get(eval_info.hf_column))

    return LeaderboardEntry(
        model=model,
        provider=provider,
        tci=_extract_score(row.get("tci")),
        scores=scores,
    )


def fetch_leaderboard(token: str | None = None) -> list[LeaderboardEntry]:
    """Fetch leaderboard data from HuggingFace and transform to entries.

    Uses huggingface_hub + pyarrow directly to avoid multiprocessing issues
    with the datasets library on Python 3.13+.

    Args:
        token: HuggingFace API token (falls back to HF_TOKEN env var)

    Returns:
        List of LeaderboardEntry objects sorted by TCI descending

    Raises:
        HuggingFaceError: On network errors or invalid response
    """
    # Import here to avoid slow startup
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq

    hf_token = token or os.environ.get("HF_TOKEN")

    try:
        parquet_path = hf_hub_download(
            repo_id=DATASET_REPO,
            filename="data/train-00000-of-00001.parquet",
            repo_type="dataset",
            token=hf_token,
        )
    except Exception as e:
        raise HuggingFaceError(f"Failed to download leaderboard data: {e}")

    try:
        table = pq.read_table(parquet_path)
        rows = table.to_pydict()
    except Exception as e:
        raise HuggingFaceError(f"Failed to parse leaderboard data: {e}")

    # Transform rows from columnar to row format
    num_rows = len(rows.get("model", []))
    entries = []
    for i in range(num_rows):
        row = {col: rows[col][i] for col in rows}
        entries.append(_transform_row(row))

    # Sort by TCI descending (entries with None TCI go to the end)
    entries.sort(key=lambda e: (e.tci is None, -(e.tci or 0)))

    return entries
