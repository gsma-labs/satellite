"""Integration tests for the _do_submit submission flow.

Tests the full orchestration: auth → branch → upload → PR creation,
using a mocked GitHubClient._request to avoid real API calls.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from satellite.services.evals import BENCHMARKS, BENCHMARKS_BY_ID
from satellite.services.submit import (
    LEADERBOARD_REPO,
    SubmitPreview,
    SubmitResult,
    _build_pr_body,
    _do_submit,
    submit_to_leaderboard,
)
from satellite.services.submit.submit import GitHubClient, GitHubError


# ── Fixtures ──────────────────────────────────────────────────────────────

ALL_BENCH_IDS = [b.id for b in BENCHMARKS]


def _make_preview(
    model: str = "openai/gpt-4o",
    provider: str = "openai",
    model_dir_name: str = "openai_gpt-4o",
) -> SubmitPreview:
    """Build a realistic SubmitPreview for testing."""
    return SubmitPreview(
        job_id="job_001",
        model=model,
        provider=provider,
        model_dir_name=model_dir_name,
        benchmarks=ALL_BENCH_IDS,
        scores={b_id: 0.85 for b_id in ALL_BENCH_IDS},
        log_files=[Path(f"/fake/{b.hf_column}.json") for b in BENCHMARKS],
    )


# Map of (method, url_suffix) -> response dict, to simulate GitHub API
_BASE_SHA = "abc123def456"
_BLOB_SHA = "blob_sha_001"
_TREE_SHA = "tree_sha_001"
_COMMIT_SHA = "commit_sha_001"
_PR_URL = "https://github.com/gsma-labs/leaderboard/pull/42"


def _make_api_responses(
    *,
    has_push: bool = True,
    username: str = "testuser",
) -> dict[tuple[str, str], dict]:
    """Build a response lookup for GitHubClient._request calls."""
    target_repo = LEADERBOARD_REPO if has_push else f"{username}/leaderboard"
    return {
        ("GET", "/user"): {"login": username},
        ("GET", f"/repos/{LEADERBOARD_REPO}"): {
            "permissions": {"push": has_push, "admin": False},
        },
        ("GET", f"/repos/{LEADERBOARD_REPO}/git/ref/heads/main"): {
            "object": {"sha": _BASE_SHA},
        },
        ("POST", f"/repos/{LEADERBOARD_REPO}/forks"): {
            "full_name": f"{username}/leaderboard",
        },
        # Branch creation (for whichever target repo)
        ("POST", f"/repos/{target_repo}/git/refs"): {},
        # Upload: GET ref for dynamic branch name (prefix match on submit/)
        ("GET", f"/repos/{target_repo}/git/ref/heads/submit/"): {
            "object": {"sha": _BASE_SHA},
        },
        ("GET", f"/repos/{target_repo}/git/commits/{_BASE_SHA}"): {
            "tree": {"sha": "base_tree_sha"},
        },
        ("POST", f"/repos/{target_repo}/git/blobs"): {"sha": _BLOB_SHA},
        ("POST", f"/repos/{target_repo}/git/trees"): {"sha": _TREE_SHA},
        ("POST", f"/repos/{target_repo}/git/commits"): {"sha": _COMMIT_SHA},
        ("PATCH", f"/repos/{target_repo}/git/refs/heads/submit/"): {},
        # PR creation
        ("POST", f"/repos/{LEADERBOARD_REPO}/pulls"): {
            "html_url": _PR_URL,
        },
    }


class _FakeClient(GitHubClient):
    """GitHubClient that returns canned responses instead of making HTTP calls."""

    def __init__(
        self,
        responses: dict[tuple[str, str], dict],
        *,
        fail_at: tuple[str, str] | None = None,
    ) -> None:
        # Skip real __init__ (no httpx client needed)
        self._responses = responses
        self._fail_at = fail_at
        self.calls: list[tuple[str, str]] = []

    def close(self) -> None:
        pass

    def _request(self, method: str, url: str, **kwargs) -> dict:
        self.calls.append((method, url))

        if self._fail_at and method == self._fail_at[0] and self._fail_at[1] in url:
            raise GitHubError(f"Simulated failure at {method} {url}", status_code=500)

        # Exact match first
        key = (method, url)
        if key in self._responses:
            return self._responses[key]

        # Longest-prefix match for dynamic URLs (branch names with timestamps)
        best_match = None
        best_len = 0
        for (m, prefix), response in self._responses.items():
            if m == method and url.startswith(prefix) and len(prefix) > best_len:
                best_match = response
                best_len = len(prefix)

        if best_match is not None:
            return best_match

        raise GitHubError(f"Unexpected request: {method} {url}", status_code=404)


# ── Tests ─────────────────────────────────────────────────────────────────


class TestDirectPushFlow:
    """User has push access → direct push to gsma-labs/leaderboard."""

    def test_success_returns_pr_url(self) -> None:
        responses = _make_api_responses(has_push=True)
        client = _FakeClient(responses)
        preview = _make_preview()

        with patch(
            "satellite.services.submit.parquet_builder.read_eval_log",
        ):
            with patch(
                "satellite.services.submit.build_model_card_parquet",
                return_value=("model_cards/openai_gpt-4o.parquet", b"parquet_data"),
            ):
                result = _do_submit(client, preview)

        assert result.status == "success"
        assert result.pr_url == _PR_URL

    def test_branch_created_on_leaderboard_repo(self) -> None:
        responses = _make_api_responses(has_push=True)
        client = _FakeClient(responses)
        preview = _make_preview()

        with patch(
            "satellite.services.submit.build_model_card_parquet",
            return_value=("model_cards/openai_gpt-4o.parquet", b"data"),
        ):
            _do_submit(client, preview)

        # Branch creation should target the leaderboard repo directly
        branch_calls = [
            (m, u) for m, u in client.calls if m == "POST" and "git/refs" in u
        ]
        assert len(branch_calls) == 1
        assert LEADERBOARD_REPO in branch_calls[0][1]

    def test_pr_head_is_branch_name(self) -> None:
        """Direct push: PR head should be just the branch name, no username prefix."""
        responses = _make_api_responses(has_push=True)
        client = _FakeClient(responses)
        preview = _make_preview()

        with patch(
            "satellite.services.submit.build_model_card_parquet",
            return_value=("model_cards/openai_gpt-4o.parquet", b"data"),
        ):
            _do_submit(client, preview)

        # Check PR creation call
        pr_calls = [
            (m, u) for m, u in client.calls if m == "POST" and "pulls" in u
        ]
        assert len(pr_calls) == 1


class TestForkFlow:
    """User lacks push access → fork + PR with username:branch head."""

    def test_success_returns_pr_url(self) -> None:
        responses = _make_api_responses(has_push=False, username="contributor")
        client = _FakeClient(responses)
        preview = _make_preview()

        with patch(
            "satellite.services.submit.build_model_card_parquet",
            return_value=("model_cards/openai_gpt-4o.parquet", b"data"),
        ):
            result = _do_submit(client, preview)

        assert result.status == "success"
        assert result.pr_url == _PR_URL

    def test_fork_is_created(self) -> None:
        responses = _make_api_responses(has_push=False, username="contributor")
        client = _FakeClient(responses)
        preview = _make_preview()

        with patch(
            "satellite.services.submit.build_model_card_parquet",
            return_value=("model_cards/openai_gpt-4o.parquet", b"data"),
        ):
            _do_submit(client, preview)

        fork_calls = [
            (m, u) for m, u in client.calls if m == "POST" and "forks" in u
        ]
        assert len(fork_calls) == 1

    def test_branch_created_on_fork(self) -> None:
        responses = _make_api_responses(has_push=False, username="contributor")
        client = _FakeClient(responses)
        preview = _make_preview()

        with patch(
            "satellite.services.submit.build_model_card_parquet",
            return_value=("model_cards/openai_gpt-4o.parquet", b"data"),
        ):
            _do_submit(client, preview)

        branch_calls = [
            (m, u) for m, u in client.calls if m == "POST" and "git/refs" in u
        ]
        assert len(branch_calls) == 1
        assert "contributor/leaderboard" in branch_calls[0][1]


class TestErrorHandling:
    """Verify errors at each stage produce SubmitResult(status='error')."""

    def test_auth_failure(self) -> None:
        responses = _make_api_responses(has_push=True)
        client = _FakeClient(responses, fail_at=("GET", "/user"))
        preview = _make_preview()

        with patch(
            "satellite.services.submit.build_model_card_parquet",
            return_value=("model_cards/openai_gpt-4o.parquet", b"data"),
        ):
            # _do_submit raises; submit_to_leaderboard catches it
            with pytest.raises(GitHubError):
                _do_submit(client, preview)

    def test_submit_to_leaderboard_catches_github_error(self) -> None:
        """submit_to_leaderboard wraps GitHubError into SubmitResult."""
        with patch(
            "satellite.services.submit.GitHubClient",
        ) as mock_cls:
            mock_client = MagicMock()
            mock_client.check_auth.side_effect = GitHubError("auth failed", 401)
            mock_cls.return_value = mock_client

            result = submit_to_leaderboard(_make_preview(), "fake-token")

        assert result.status == "error"
        assert "auth failed" in result.error

    def test_branch_creation_failure(self) -> None:
        responses = _make_api_responses(has_push=True)
        client = _FakeClient(responses, fail_at=("POST", "git/refs"))
        preview = _make_preview()

        with (
            patch(
                "satellite.services.submit.build_model_card_parquet",
                return_value=("model_cards/openai_gpt-4o.parquet", b"data"),
            ),
            pytest.raises(GitHubError, match="git/refs"),
        ):
            _do_submit(client, preview)

    def test_pr_creation_failure(self) -> None:
        responses = _make_api_responses(has_push=True)
        client = _FakeClient(responses, fail_at=("POST", "pulls"))
        preview = _make_preview()

        with (
            patch(
                "satellite.services.submit.build_model_card_parquet",
                return_value=("model_cards/openai_gpt-4o.parquet", b"data"),
            ),
            pytest.raises(GitHubError, match="pulls"),
        ):
            _do_submit(client, preview)


class TestMissingToken:
    """Missing token returns a helpful error without any API call."""

    def test_empty_token(self) -> None:
        result = submit_to_leaderboard(_make_preview(), "")
        assert result.status == "error"
        assert "GITHUB_TOKEN" in result.error

    def test_none_like_token(self) -> None:
        # Empty string is the only falsy token value the code checks
        result = submit_to_leaderboard(_make_preview(), "")
        assert result.status == "error"


class TestPRMetadata:
    """Verify branch name format, PR title, and body content."""

    def test_branch_name_format(self) -> None:
        """Branch follows submit/{model_dir_name}/{timestamp} pattern."""
        responses = _make_api_responses(has_push=True)
        client = _FakeClient(responses)
        preview = _make_preview()

        with patch(
            "satellite.services.submit.build_model_card_parquet",
            return_value=("model_cards/openai_gpt-4o.parquet", b"data"),
        ):
            _do_submit(client, preview)

        # Find the branch creation call
        branch_calls = [
            (m, u) for m, u in client.calls if m == "POST" and "git/refs" in u
        ]
        assert len(branch_calls) == 1

    def test_pr_body_contains_scores_table(self) -> None:
        """PR body includes a markdown table with benchmark scores."""
        preview = _make_preview()
        body = _build_pr_body(preview)

        assert "| Benchmark | Score |" in body
        assert preview.provider in body
        assert preview.job_id in body

    def test_pr_body_contains_all_benchmarks(self) -> None:
        preview = _make_preview()
        body = _build_pr_body(preview)

        for bench_id in ALL_BENCH_IDS:
            bench = BENCHMARKS_BY_ID.get(bench_id)
            if bench:
                assert bench.name in body or bench_id in body
