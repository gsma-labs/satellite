"""Leaderboard data types for satetoad."""

from __future__ import annotations

from dataclasses import dataclass, field


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
