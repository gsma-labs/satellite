"""Tests for submit eligibility, model naming, and model identity parsing."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from satellite.services.evals import BENCHMARKS
from satellite.services.evals.job_manager import Job
from satellite.services.submit import (
    RECOGNIZED_PROVIDERS,
    REQUIRED_BENCHMARK_IDS,
    REQUIRED_SAMPLE_COUNTS,
    build_submit_preview,
    get_eligible_models,
    is_model_eligible,
    model_dir_name,
    parse_model_identity,
)

ALL_BENCH_IDS = [b.id for b in BENCHMARKS]


class TestParseModelIdentity:
    """Tests for parsing model strings into (provider, model_name)."""

    @pytest.mark.parametrize(
        ("model_string", "expected"),
        [
            pytest.param(
                "openai/gpt-4o",
                ("openai", "gpt-4o"),
                id="simple_openai",
            ),
            pytest.param(
                "anthropic/claude-3-opus",
                ("anthropic", "claude-3-opus"),
                id="simple_anthropic",
            ),
            pytest.param(
                "google/gemini-pro",
                ("google", "gemini-pro"),
                id="simple_google",
            ),
            pytest.param(
                "openrouter/anthropic/claude-3-opus",
                ("anthropic", "claude-3-opus"),
                id="openrouter_proxy_stripped",
            ),
            pytest.param(
                "bedrock/anthropic/claude-3-haiku",
                ("anthropic", "claude-3-haiku"),
                id="bedrock_proxy_stripped",
            ),
            pytest.param(
                "vertex/google/gemini-1.5-pro",
                ("google", "gemini-1.5-pro"),
                id="vertex_proxy_stripped",
            ),
            pytest.param(
                "ollama/llama3",
                ("ollama", "llama3"),
                id="local_ollama",
            ),
        ],
    )
    def test_valid_models(self, model_string: str, expected: tuple[str, str]) -> None:
        assert parse_model_identity(model_string) == expected

    @pytest.mark.parametrize(
        "model_string",
        [
            pytest.param("justmodelname", id="no_slash"),
            pytest.param("openai/", id="empty_model_name"),
            pytest.param("", id="empty_string"),
        ],
    )
    def test_invalid_format_raises(self, model_string: str) -> None:
        with pytest.raises(ValueError, match="Invalid model format"):
            parse_model_identity(model_string)

    def test_unrecognized_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized provider"):
            parse_model_identity("fakeprovider/some-model")


class TestModelDirName:
    """Tests for directory name generation."""

    @pytest.mark.parametrize(
        ("provider", "model_name", "expected"),
        [
            pytest.param(
                "anthropic",
                "claude-haiku-4.5",
                "anthropic_claude-haiku-4_5",
                id="dots_to_underscores",
            ),
            pytest.param(
                "openai",
                "gpt-4o",
                "openai_gpt-4o",
                id="simple_model",
            ),
            pytest.param(
                "google",
                "gemini-1.5-pro",
                "google_gemini-1_5-pro",
                id="version_dots",
            ),
            pytest.param(
                "groq",
                "llama-3.1-70b",
                "groq_llama-3_1-70b",
                id="groq_model",
            ),
        ],
    )
    def test_dir_name_generation(
        self, provider: str, model_name: str, expected: str
    ) -> None:
        assert model_dir_name(provider, model_name) == expected


def _all_scores(value: float = 0.85) -> dict[str, float]:
    """Create scores dict with all required benchmarks."""
    return {b_id: value for b_id in ALL_BENCH_IDS}


def _all_sample_counts() -> dict[str, int]:
    """Create sample counts at required sizes for all benchmarks."""
    return {b.id: b.total_samples for b in BENCHMARKS}


class TestIsModelEligible:
    """Tests for model eligibility checking."""

    def test_eligible_with_all_benchmarks(self) -> None:
        assert is_model_eligible("openai/gpt-4o", _all_scores(), _all_sample_counts())

    def test_ineligible_missing_benchmark(self) -> None:
        scores = _all_scores()
        del scores[ALL_BENCH_IDS[0]]
        assert not is_model_eligible("openai/gpt-4o", scores, _all_sample_counts())

    def test_ineligible_unrecognized_provider(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized provider"):
            is_model_eligible("fakeprovider/model", _all_scores(), _all_sample_counts())

    def test_ineligible_invalid_model_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid model format"):
            is_model_eligible("noSlash", _all_scores(), _all_sample_counts())

    def test_required_benchmark_ids_matches_registry(self) -> None:
        """REQUIRED_BENCHMARK_IDS stays in sync with the registry."""
        assert REQUIRED_BENCHMARK_IDS == frozenset(ALL_BENCH_IDS)
        assert len(REQUIRED_BENCHMARK_IDS) == len(BENCHMARKS)

    def test_required_sample_counts_matches_registry(self) -> None:
        """REQUIRED_SAMPLE_COUNTS stays in sync with the registry."""
        assert REQUIRED_SAMPLE_COUNTS == {b.id: b.total_samples for b in BENCHMARKS}
        assert len(REQUIRED_SAMPLE_COUNTS) == len(BENCHMARKS)


class FakeJobManager:
    """Minimal stub for testing get_eligible_models."""

    def __init__(
        self,
        jobs: list[Job],
        results: dict[str, dict[str, dict[str, float]]],
        sample_counts: dict[str, dict[str, dict[str, int]]] | None = None,
    ) -> None:
        self._jobs = jobs
        self._results = results
        self._sample_counts = sample_counts or {}

    def list_jobs(self) -> list[Job]:
        return self._jobs

    def get_job_results(self, job_id: str) -> dict[str, dict[str, float]]:
        return self._results.get(job_id, {})

    def get_job_sample_counts(self, job_id: str) -> dict[str, dict[str, int]]:
        return self._sample_counts.get(job_id, {})


def _make_job(job_id: str, status: str = "success") -> Job:
    return Job(
        id=job_id,
        evals={"openai/gpt-4o": ALL_BENCH_IDS},
        created_at=datetime.now(),
        status=status,
    )


class TestGetEligibleModels:
    """Tests for scanning jobs for eligible models."""

    def test_returns_eligible_model(self) -> None:
        job = _make_job("job_001")
        manager = FakeJobManager(
            jobs=[job],
            results={"job_001": {"openai/gpt-4o": _all_scores()}},
            sample_counts={"job_001": {"openai/gpt-4o": _all_sample_counts()}},
        )
        eligible = get_eligible_models(manager)
        assert len(eligible) == 1
        assert eligible[0][1] == "openai/gpt-4o"

    def test_skips_running_jobs(self) -> None:
        job = _make_job("job_002", status="running")
        manager = FakeJobManager(
            jobs=[job],
            results={"job_002": {"openai/gpt-4o": _all_scores()}},
        )
        assert get_eligible_models(manager) == []

    def test_skips_incomplete_models(self) -> None:
        job = _make_job("job_003")
        partial_scores = {ALL_BENCH_IDS[0]: 0.8}
        manager = FakeJobManager(
            jobs=[job],
            results={"job_003": {"openai/gpt-4o": partial_scores}},
        )
        assert get_eligible_models(manager) == []

    def test_skips_model_with_insufficient_samples(self) -> None:
        job = _make_job("job_004")
        insufficient_counts = {b_id: 10 for b_id in ALL_BENCH_IDS}
        manager = FakeJobManager(
            jobs=[job],
            results={"job_004": {"openai/gpt-4o": _all_scores()}},
            sample_counts={"job_004": {"openai/gpt-4o": insufficient_counts}},
        )
        assert get_eligible_models(manager) == []

    def test_empty_jobs(self) -> None:
        manager = FakeJobManager(jobs=[], results={})
        assert get_eligible_models(manager) == []


class TestSampleCountEligibility:
    """Tests for sample count validation in eligibility."""

    @pytest.mark.parametrize(
        ("counts", "expected"),
        [
            pytest.param(
                _all_sample_counts(),
                True,
                id="all_full_counts",
            ),
            pytest.param(
                {**_all_sample_counts(), "teleqna": 999},
                False,
                id="one_benchmark_short_by_one",
            ),
            pytest.param(
                {b_id: 10 for b_id in ALL_BENCH_IDS},
                False,
                id="all_benchmarks_short",
            ),
            pytest.param(
                {**_all_sample_counts(), "teleqna": 1000},
                True,
                id="exact_boundary_accepted",
            ),
            pytest.param(
                {**_all_sample_counts(), "teleqna": 1001},
                True,
                id="above_required_accepted",
            ),
            pytest.param(
                {**_all_sample_counts(), "teleqna": 0},
                False,
                id="zero_samples_one_benchmark",
            ),
            pytest.param(
                {b_id: 100 for b_id in ALL_BENCH_IDS if b_id != "teleqna"},
                False,
                id="missing_benchmark_count",
            ),
        ],
    )
    def test_sample_count_eligibility(
        self, counts: dict[str, int], expected: bool
    ) -> None:
        assert is_model_eligible("openai/gpt-4o", _all_scores(), counts) is expected


class TestRecognizedProviders:
    """Verify recognized providers include key entries."""

    @pytest.mark.parametrize(
        "provider_id",
        [
            pytest.param("openai", id="openai"),
            pytest.param("anthropic", id="anthropic"),
            pytest.param("google", id="google"),
            pytest.param("groq", id="groq"),
            pytest.param("ollama", id="ollama"),
        ],
    )
    def test_known_provider_recognized(self, provider_id: str) -> None:
        assert provider_id in RECOGNIZED_PROVIDERS


@dataclass
class FakeEvalLogInfo:
    """Mimics inspect_ai.log.EvalLogInfo with a file:/// URI name."""

    name: str


class TestBuildSubmitPreview:
    """Tests for build_submit_preview log file discovery."""

    def test_collects_log_files_from_uri(self, tmp_path: Path) -> None:
        """Log files with file:/// URIs are correctly resolved to paths."""
        job_dir = tmp_path / "job_001"
        job_dir.mkdir()
        log_file = job_dir / "eval_log.json"
        log_file.write_text("{}")

        uri = f"file://{log_file}"
        fake_logs = [FakeEvalLogInfo(name=uri)]

        job = _make_job("job_001")
        with patch(
            "satellite.services.submit.list_eval_logs", return_value=fake_logs
        ):
            preview = build_submit_preview(
                job, "openai/gpt-4o", _all_scores(), tmp_path
            )

        assert len(preview.log_files) == 1
        assert preview.log_files[0] == log_file

    def test_skips_nonexistent_log_files(self, tmp_path: Path) -> None:
        """URIs pointing to missing files are excluded."""
        uri = f"file://{tmp_path}/gone.json"
        fake_logs = [FakeEvalLogInfo(name=uri)]

        job = _make_job("job_001")
        with patch(
            "satellite.services.submit.list_eval_logs", return_value=fake_logs
        ):
            preview = build_submit_preview(
                job, "openai/gpt-4o", _all_scores(), tmp_path
            )

        assert preview.log_files == []

    def test_handles_percent_encoded_uri(self, tmp_path: Path) -> None:
        """Percent-encoded characters in URIs are decoded correctly."""
        spaced_dir = tmp_path / "my dir"
        spaced_dir.mkdir()
        log_file = spaced_dir / "log.json"
        log_file.write_text("{}")

        uri = f"file://{str(log_file).replace(' ', '%20')}"
        fake_logs = [FakeEvalLogInfo(name=uri)]

        job = _make_job("job_001")
        with patch(
            "satellite.services.submit.list_eval_logs", return_value=fake_logs
        ):
            preview = build_submit_preview(
                job, "openai/gpt-4o", _all_scores(), tmp_path
            )

        assert len(preview.log_files) == 1
        assert preview.log_files[0] == log_file
