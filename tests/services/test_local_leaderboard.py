"""Tests for local model collection, remote CSV fetch, and leaderboard merge logic."""

import csv
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from satellite.services.evals.job_manager import Job
from satellite.services.leaderboard.client import (
    LeaderboardEntry,
    collect_local_entries,
    fetch_leaderboard,
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


# The real registry has 7 benchmarks; we mock it to 3 for isolation
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


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Helper: write a CSV file at *path*."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# Benchmark IDs that the real registry exposes (used to mock BENCHMARKS).
_ALL_BENCH_IDS = [
    "teleqna",
    "telelogs",
    "telemath",
    "teletables",
    "three_gpp",
    "oranbench",
    "srsranbench",
]


def _fake_benchmarks(ids: list[str]):
    """Build a minimal BENCHMARKS tuple with the given IDs."""
    from satellite.services.evals.registry import BenchmarkConfig

    return tuple(
        BenchmarkConfig(
            id=bid,
            name=bid,
            short_name=bid[:4],
            description="test",
            hf_column=bid,
            module_path="",
            function_name="",
            total_samples=100,
        )
        for bid in ids
    )


class TestFetchLeaderboard:
    """Tests for fetching and parsing the remote CSV leaderboard."""

    def test_fetch_parses_csv_scores(self, tmp_path: Path) -> None:
        """Scores are parsed from string-encoded lists and converted to percentages."""
        csv_path = tmp_path / "leaderboard_scores.csv"
        fieldnames = ["model", "provider", *_ALL_BENCH_IDS]
        rows = [
            {
                "model": "gpt-4o",
                "provider": "OpenAI",
                "teleqna": "[0.85, 0.01]",
                "telelogs": "[0.72, 0.02]",
                "telemath": "[0.65, 0.03]",
                "teletables": "[0.90, 0.005]",
                "three_gpp": "[0.78, 0.015]",
                "oranbench": "[0.60, 0.02]",
                "srsranbench": "[0.55, 0.025]",
            },
        ]
        _write_csv(csv_path, fieldnames, rows)

        benchmarks = _fake_benchmarks(_ALL_BENCH_IDS)
        with (
            patch(
                "satellite.services.leaderboard.client.hf_hub_download",
                return_value=str(csv_path),
            ),
            patch("satellite.services.leaderboard.client.BENCHMARKS", benchmarks),
        ):
            entries = fetch_leaderboard()

        assert len(entries) == 1
        entry = entries[0]
        assert entry.model == "gpt-4o"
        assert entry.provider == "OpenAI"
        assert entry.scores["teleqna"] == pytest.approx(85.0)
        assert entry.scores["three_gpp"] == pytest.approx(78.0)
        assert entry.scores["oranbench"] == pytest.approx(60.0)
        assert entry.scores["srsranbench"] == pytest.approx(55.0)
        assert len(entry.scores) == 7

    def test_fetch_handles_empty_scores(self, tmp_path: Path) -> None:
        """Empty CSV cells produce None scores."""
        csv_path = tmp_path / "leaderboard_scores.csv"
        fieldnames = ["model", "provider", "teleqna", "telelogs"]
        rows = [
            {"model": "empty-model", "provider": "Test", "teleqna": "", "telelogs": ""},
        ]
        _write_csv(csv_path, fieldnames, rows)

        benchmarks = _fake_benchmarks(["teleqna", "telelogs"])
        with (
            patch(
                "satellite.services.leaderboard.client.hf_hub_download",
                return_value=str(csv_path),
            ),
            patch("satellite.services.leaderboard.client.BENCHMARKS", benchmarks),
        ):
            entries = fetch_leaderboard()

        assert len(entries) == 1
        assert entries[0].scores["teleqna"] is None
        assert entries[0].scores["telelogs"] is None
        assert entries[0].avg_score is None

    def test_fetch_handles_missing_columns(self, tmp_path: Path) -> None:
        """Graceful when CSV has fewer benchmark columns than the registry."""
        csv_path = tmp_path / "leaderboard_scores.csv"
        # CSV only has 2 of 7 benchmark columns
        fieldnames = ["model", "provider", "teleqna", "telelogs"]
        rows = [
            {
                "model": "partial",
                "provider": "Test",
                "teleqna": "[0.80]",
                "telelogs": "[0.70]",
            },
        ]
        _write_csv(csv_path, fieldnames, rows)

        benchmarks = _fake_benchmarks(_ALL_BENCH_IDS)
        with (
            patch(
                "satellite.services.leaderboard.client.hf_hub_download",
                return_value=str(csv_path),
            ),
            patch("satellite.services.leaderboard.client.BENCHMARKS", benchmarks),
        ):
            entries = fetch_leaderboard()

        assert len(entries) == 1
        # Only the 2 columns present in CSV are parsed
        assert len(entries[0].scores) == 2
        assert entries[0].scores["teleqna"] == pytest.approx(80.0)
        assert entries[0].scores["telelogs"] == pytest.approx(70.0)

    def test_three_gpp_column_read_from_remote(self, tmp_path: Path) -> None:
        """Regression: three_gpp benchmark is read using b.id, not b.hf_column."""
        csv_path = tmp_path / "leaderboard_scores.csv"
        # The CSV uses "three_gpp" as the column name (matching b.id),
        # NOT "3gpp_tsg" (which is b.hf_column from the evals package).
        fieldnames = ["model", "provider", "three_gpp"]
        rows = [
            {"model": "test-model", "provider": "Test", "three_gpp": "[0.82, 0.01]"},
        ]
        _write_csv(csv_path, fieldnames, rows)

        # Simulate a benchmark whose hf_column differs from its id
        from satellite.services.evals.registry import BenchmarkConfig

        benchmarks = (
            BenchmarkConfig(
                id="three_gpp",
                name="3GPP",
                short_name="3GPP",
                description="test",
                hf_column="3gpp_tsg",  # differs from id!
                module_path="",
                function_name="",
                total_samples=100,
            ),
        )

        with (
            patch(
                "satellite.services.leaderboard.client.hf_hub_download",
                return_value=str(csv_path),
            ),
            patch("satellite.services.leaderboard.client.BENCHMARKS", benchmarks),
        ):
            entries = fetch_leaderboard()

        assert len(entries) == 1
        assert entries[0].scores["three_gpp"] == pytest.approx(82.0)
