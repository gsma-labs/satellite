"""Tests for local model collection and leaderboard merge logic."""

from datetime import datetime
from unittest.mock import patch

import pytest

from satellite.services.evals.job_manager import Job
from satellite.services.leaderboard.client import (
    LeaderboardEntry,
    collect_local_entries,
    merge_leaderboard,
    split_model_name,
)



class FakeJobManager:
    """Minimal job manager stub for testing collect_local_entries."""

    def __init__(
        self,
        jobs: list[Job],
        results: dict[str, dict[str, dict[str, float]]],
    ) -> None:
        self._jobs = jobs
        self._results = results

    def list_jobs(self) -> list[Job]:
        return self._jobs

    def get_job_results(self, job_id: str) -> dict[str, dict[str, float]]:
        return self._results.get(job_id, {})


def _make_job(
    job_id: str,
    evals: dict[str, list[str]],
    ts: float = 0.0,
) -> Job:
    return Job(
        id=job_id,
        evals=evals,
        created_at=datetime.fromtimestamp(ts),
        status="success",
    )



class TestSplitModelName:
    """Tests for parsing provider/model strings."""

    @pytest.mark.parametrize(
        ("model_id", "expected"),
        [
            pytest.param("openai/gpt-4o", ("Openai", "gpt-4o"), id="slash_provider"),
            pytest.param("anthropic/claude-3", ("Anthropic", "claude-3"), id="anthropic"),
            pytest.param("gpt-4o", ("Unknown", "gpt-4o"), id="no_slash"),
            pytest.param("meta/llama/3.1", ("Meta", "llama/3.1"), id="multi_slash"),
        ],
    )
    def test_split(self, model_id: str, expected: tuple[str, str]) -> None:
        assert split_model_name(model_id) == expected


# The real registry has 5 benchmarks; we mock it to 3 for isolation
MOCK_BENCHMARKS = {"b1": None, "b2": None, "b3": None}


class TestCollectLocalEntries:
    """Tests for scanning jobs and building local leaderboard entries."""

    @patch(
        "satellite.services.leaderboard.client.BENCHMARKS_BY_ID",
        MOCK_BENCHMARKS,
    )
    def test_collect_requires_all_benchmarks(self) -> None:
        """A job missing benchmarks produces no entries."""
        job = _make_job("j1", {"openai/gpt-4o": ["b1", "b2"]})
        mgr = FakeJobManager(
            jobs=[job],
            results={"j1": {"openai/gpt-4o": {"b1": 0.9, "b2": 0.8}}},
        )

        entries = collect_local_entries(mgr)

        assert entries == []

    @patch(
        "satellite.services.leaderboard.client.BENCHMARKS_BY_ID",
        MOCK_BENCHMARKS,
    )
    def test_collect_score_normalization(self) -> None:
        """Accuracy 0.85 becomes 85.0 on the leaderboard scale."""
        job = _make_job("j1", {"openai/gpt-4o": ["b1", "b2", "b3"]})
        mgr = FakeJobManager(
            jobs=[job],
            results={"j1": {"openai/gpt-4o": {"b1": 0.85, "b2": 0.85, "b3": 0.85}}},
        )

        entries = collect_local_entries(mgr)

        assert len(entries) == 1
        assert entries[0].scores["b1"] == pytest.approx(85.0)

    @patch(
        "satellite.services.leaderboard.client.BENCHMARKS_BY_ID",
        MOCK_BENCHMARKS,
    )
    def test_collect_avg_score_is_mean(self) -> None:
        """avg_score is the simple average of all benchmark scores."""
        job = _make_job("j1", {"openai/gpt-4o": ["b1", "b2", "b3"]})
        mgr = FakeJobManager(
            jobs=[job],
            results={"j1": {"openai/gpt-4o": {"b1": 0.80, "b2": 0.90, "b3": 0.70}}},
        )

        entries = collect_local_entries(mgr)

        assert len(entries) == 1
        assert entries[0].avg_score == pytest.approx(80.0)

    @patch(
        "satellite.services.leaderboard.client.BENCHMARKS_BY_ID",
        MOCK_BENCHMARKS,
    )
    def test_collect_requires_actual_scores(self) -> None:
        """A job with all benchmarks listed but missing results produces no entries."""
        job = _make_job("j1", {"openai/gpt-4o": ["b1", "b2", "b3"]})
        mgr = FakeJobManager(
            jobs=[job],
            results={"j1": {"openai/gpt-4o": {"b1": 0.9, "b2": 0.8}}},
        )

        entries = collect_local_entries(mgr)

        assert entries == []

    @patch(
        "satellite.services.leaderboard.client.BENCHMARKS_BY_ID",
        MOCK_BENCHMARKS,
    )
    def test_collect_deduplicates_by_recency(self) -> None:
        """If the same model qualifies in multiple jobs, only the first (most recent) is used."""
        job_old = _make_job("j_old", {"openai/gpt-4o": ["b1", "b2", "b3"]}, ts=100)
        job_new = _make_job("j_new", {"openai/gpt-4o": ["b1", "b2", "b3"]}, ts=200)
        mgr = FakeJobManager(
            jobs=[job_new, job_old],  # list_jobs returns most recent first
            results={
                "j_new": {"openai/gpt-4o": {"b1": 0.95, "b2": 0.95, "b3": 0.95}},
                "j_old": {"openai/gpt-4o": {"b1": 0.50, "b2": 0.50, "b3": 0.50}},
            },
        )

        entries = collect_local_entries(mgr)

        assert len(entries) == 1
        assert entries[0].avg_score == pytest.approx(95.0)

    @patch(
        "satellite.services.leaderboard.client.BENCHMARKS_BY_ID",
        MOCK_BENCHMARKS,
    )
    def test_collect_uses_registry_dynamically(self) -> None:
        """Verifies qualification against the mocked registry, not a hardcoded list."""
        job = _make_job("j1", {"openai/gpt-4o": ["b1", "b2", "b3"]})
        mgr = FakeJobManager(
            jobs=[job],
            results={"j1": {"openai/gpt-4o": {"b1": 0.8, "b2": 0.8, "b3": 0.8}}},
        )

        entries = collect_local_entries(mgr)

        # With the 3-benchmark mock registry, this qualifies
        assert len(entries) == 1
        assert entries[0].is_local is True

    @patch(
        "satellite.services.leaderboard.client.BENCHMARKS_BY_ID",
        {"b1": None, "b2": None, "b3": None, "b4": None},
    )
    def test_collect_fails_with_larger_registry(self) -> None:
        """Same job that passed with 3 benchmarks fails when registry has 4."""
        job = _make_job("j1", {"openai/gpt-4o": ["b1", "b2", "b3"]})
        mgr = FakeJobManager(
            jobs=[job],
            results={"j1": {"openai/gpt-4o": {"b1": 0.8, "b2": 0.8, "b3": 0.8}}},
        )

        entries = collect_local_entries(mgr)

        assert entries == []



class TestMergeLeaderboard:
    """Tests for merging local entries into the remote leaderboard."""

    def test_merge_ranking(self) -> None:
        """Local avg_score 80 slots between remote 85 and 75."""
        remote = [
            LeaderboardEntry(model="top", provider="A", avg_score=85.0),
            LeaderboardEntry(model="bot", provider="B", avg_score=75.0),
        ]
        local = [
            LeaderboardEntry(model="mine", provider="Me", avg_score=80.0, is_local=True),
        ]

        merged = merge_leaderboard(remote, local)

        assert [e.model for e in merged] == ["top", "mine", "bot"]

    def test_merge_empty_local(self) -> None:
        """Returns remote unchanged when there are no local entries."""
        remote = [
            LeaderboardEntry(model="a", provider="A", avg_score=90.0),
            LeaderboardEntry(model="b", provider="B", avg_score=80.0),
        ]

        merged = merge_leaderboard(remote, [])

        assert merged == remote

    def test_merge_preserves_none_avg_score_last(self) -> None:
        """Entries with None avg_score sort to the end."""
        remote = [
            LeaderboardEntry(model="scored", provider="A", avg_score=50.0),
            LeaderboardEntry(model="unscored", provider="B", avg_score=None),
        ]
        local = [
            LeaderboardEntry(model="local", provider="C", avg_score=60.0, is_local=True),
        ]

        merged = merge_leaderboard(remote, local)

        assert merged[-1].model == "unscored"
        assert merged[0].model == "local"
