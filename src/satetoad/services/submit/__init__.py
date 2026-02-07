"""Submission services for the leaderboard.

Business logic for model naming, eligibility checking, and submission
orchestration. HTTP transport lives in github_client.py.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse

from inspect_ai.log import list_eval_logs

from satetoad.examples.eval_data import MODEL_PROVIDERS
from satetoad.services.config.env_config_manager import normalize_model_path
from satetoad.services.evals import BENCHMARKS, BENCHMARKS_BY_ID
from satetoad.services.evals.job_manager import Job, JobManager
from satetoad.services.submit.submit import GitHubClient, GitHubError

# ── Constants ────────────────────────────────────────────────────────────

LEADERBOARD_REPO = "gsma-labs/leaderboard"
TRAJECTORIES_DIR = "trajectories"
GITHUB_TOKEN_ENV_VAR = "GITHUB_TOKEN"

RECOGNIZED_PROVIDERS = frozenset(p["id"] for p in MODEL_PROVIDERS)
REQUIRED_BENCHMARK_IDS = frozenset(b.id for b in BENCHMARKS)

_UNSAFE_CHARS = re.compile(r"[^a-z0-9_-]")

# ── Types ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SubmitResult:
    """Result of a leaderboard submission attempt."""

    status: Literal["success", "error"]
    pr_url: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class SubmitPreview:
    """Preview of what will be submitted to the leaderboard."""

    job_id: str
    model: str
    provider: str
    model_dir_name: str
    benchmarks: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    log_files: list[Path] = field(default_factory=list)


# ── Model naming ─────────────────────────────────────────────────────────


def parse_model_identity(model_string: str) -> tuple[str, str]:
    """Parse a model string into (provider, model_name).

    Strips proxy prefixes via normalize_model_path, then splits on
    the first slash to separate provider from model name.

    Raises:
        ValueError: If provider is unrecognized or format is invalid.
    """
    normalized = normalize_model_path(model_string)
    parts = normalized.split("/", 1)
    if len(parts) < 2 or not parts[1]:
        raise ValueError(
            f"Invalid model format (expected 'provider/model'): {model_string}"
        )

    provider, model_name = parts
    if provider not in RECOGNIZED_PROVIDERS:
        raise ValueError(
            f"Unrecognized provider '{provider}' from model: {model_string}"
        )

    return provider, model_name


def model_dir_name(provider: str, model_name: str) -> str:
    """Convert provider and model name to a leaderboard directory name.

    Replaces dots and slashes with underscores, removes other unsafe chars.

    Examples:
        ("anthropic", "claude-haiku-4.5") -> "anthropic_claude-haiku-4_5"
        ("openai", "gpt-4o") -> "openai_gpt-4o"
    """
    raw = f"{provider}_{model_name}"
    raw = raw.replace(".", "_").replace("/", "_")
    return _UNSAFE_CHARS.sub("", raw.lower())


# ── Eligibility ──────────────────────────────────────────────────────────


def is_model_eligible(model: str, scores: dict[str, float]) -> bool:
    """Check if a model has completed all required benchmarks with valid scores.

    Raises:
        ValueError: If the model string has an unrecognized provider or bad format.
    """
    # Validates provider/format; raises ValueError on bad input
    _provider, _name = parse_model_identity(model)
    return REQUIRED_BENCHMARK_IDS.issubset(scores.keys())


def get_eligible_models(
    job_manager: JobManager,
) -> list[tuple[Job, str, dict[str, float]]]:
    """Find all eligible (job, model, scores) tuples across all jobs."""
    eligible: list[tuple[Job, str, dict[str, float]]] = []
    for job in job_manager.list_jobs():
        if job.status != "success":
            continue
        results = job_manager.get_job_results(job.id)
        for model, scores in results.items():
            try:
                if is_model_eligible(model, scores):
                    eligible.append((job, model, scores))
            except ValueError:
                continue
    return eligible


def build_submit_preview(
    job: Job,
    model: str,
    scores: dict[str, float],
    jobs_dir: Path,
) -> SubmitPreview:
    """Build a preview of what will be submitted."""
    provider, name = parse_model_identity(model)
    dir_name = model_dir_name(provider, name)

    job_dir = jobs_dir / job.id
    log_files = []
    for log_ref in list_eval_logs(str(job_dir), recursive=True):
        log_path = Path(unquote(urlparse(log_ref.name).path))
        if log_path.exists():
            log_files.append(log_path)

    return SubmitPreview(
        job_id=job.id,
        model=model,
        provider=provider,
        model_dir_name=dir_name,
        benchmarks=sorted(scores.keys()),
        scores=scores,
        log_files=log_files,
    )


# ── Submission orchestration ─────────────────────────────────────────────


def _build_pr_body(preview: SubmitPreview) -> str:
    """Build markdown PR body with scores table."""
    lines = [
        f"## Submission: {preview.model}",
        f"**Provider:** {preview.provider}",
        f"**Job ID:** {preview.job_id}",
        f"**Files:** {len(preview.log_files)} trajectory file(s)",
        "",
        "### Benchmark Scores",
        "",
        "| Benchmark | Score |",
        "|-----------|-------|",
    ]
    for bench_id, score in sorted(preview.scores.items()):
        bench = BENCHMARKS_BY_ID.get(bench_id)
        display = bench.name if bench else bench_id
        lines.append(f"| {display} | {score:.4f} |")

    lines.extend(["", "---", "*Submitted via Satetoad TUI*"])
    return "\n".join(lines)


def submit_to_leaderboard(preview: SubmitPreview, token: str) -> SubmitResult:
    """Submit evaluation trajectories to the leaderboard via GitHub PR."""
    if not token:
        return SubmitResult(
            status="error",
            error=f"Missing {GITHUB_TOKEN_ENV_VAR}. "
            "Set it in your .env file (press 'c' to open Env Vars).",
        )

    client = GitHubClient(token)
    try:
        return _do_submit(client, preview)
    except GitHubError as e:
        return SubmitResult(status="error", error=str(e))
    finally:
        client.close()


def _do_submit(client: GitHubClient, preview: SubmitPreview) -> SubmitResult:
    """Execute the submission flow: authenticate, branch, upload, PR.

    Pushes directly to the leaderboard repo if the user has write access,
    otherwise falls back to the fork workflow.
    """
    username = client.check_auth()
    can_push = client.has_push_access(LEADERBOARD_REPO)
    base_sha = client.get_default_branch_sha(LEADERBOARD_REPO)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    branch_name = f"submit/{preview.model_dir_name}/{timestamp}"

    target_repo = LEADERBOARD_REPO if can_push else client.ensure_fork(LEADERBOARD_REPO)
    client.create_branch(target_repo, branch_name, base_sha)

    files = [
        (
            f"{TRAJECTORIES_DIR}/{preview.model_dir_name}/{log_path.name}",
            log_path.read_bytes(),
        )
        for log_path in preview.log_files
    ]

    if not files:
        return SubmitResult(
            status="error", error="No trajectory files found to upload."
        )

    client.upload_files(target_repo, branch_name, files)

    title = f"Add {preview.provider}/{preview.model_dir_name} trajectories"
    body = _build_pr_body(preview)
    head = branch_name if can_push else f"{username}:{branch_name}"
    pr_url = client.create_pr(LEADERBOARD_REPO, head, title, body)

    return SubmitResult(status="success", pr_url=pr_url)


__all__ = [
    "RECOGNIZED_PROVIDERS",
    "REQUIRED_BENCHMARK_IDS",
    "SubmitPreview",
    "SubmitResult",
    "build_submit_preview",
    "get_eligible_models",
    "is_model_eligible",
    "model_dir_name",
    "parse_model_identity",
    "submit_to_leaderboard",
]
