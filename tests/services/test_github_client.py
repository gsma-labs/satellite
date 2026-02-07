"""Tests for the GitHub API client (mocked HTTP responses)."""

from unittest.mock import MagicMock, patch

import pytest

from satetoad.services.submit.submit import GitHubClient, GitHubError


@pytest.fixture
def mock_client() -> GitHubClient:
    """Create a GitHubClient with a fake token."""
    return GitHubClient(token="fake-token-for-testing")


class TestCheckAuth:
    """Tests for token validation."""

    def test_returns_username_on_success(self, mock_client: GitHubClient) -> None:
        with patch.object(
            mock_client, "_request", return_value={"login": "testuser"}
        ):
            assert mock_client.check_auth() == "testuser"

    def test_raises_on_invalid_token(self, mock_client: GitHubClient) -> None:
        with patch.object(
            mock_client,
            "_request",
            side_effect=GitHubError("GitHub API error 401: Bad credentials"),
        ):
            with pytest.raises(GitHubError, match="401"):
                mock_client.check_auth()


class TestHasPushAccess:
    """Tests for push access check."""

    @pytest.mark.parametrize(
        ("push_value", "expected"),
        [
            pytest.param(True, True, id="push_allowed"),
            pytest.param(False, False, id="read_only"),
        ],
    )
    def test_returns_push_permission(
        self, mock_client: GitHubClient, push_value: bool, expected: bool
    ) -> None:
        with patch.object(
            mock_client,
            "_request",
            return_value={"permissions": {"push": push_value}},
        ):
            assert mock_client.has_push_access("gsma-labs/leaderboard") is expected


class TestEnsureFork:
    """Tests for fork creation (fallback for users without push access)."""

    def test_returns_fork_name(self, mock_client: GitHubClient) -> None:
        with patch.object(
            mock_client,
            "_request",
            return_value={"full_name": "testuser/leaderboard"},
        ):
            assert mock_client.ensure_fork("gsma-labs/leaderboard") == "testuser/leaderboard"


class TestCreateBranch:
    """Tests for branch creation."""

    def test_creates_branch_ref(self, mock_client: GitHubClient) -> None:
        with patch.object(mock_client, "_request", return_value={}) as mock_req:
            mock_client.create_branch("testuser/leaderboard", "submit/test", "abc123")
            mock_req.assert_called_once_with(
                "POST",
                "/repos/testuser/leaderboard/git/refs",
                json={"ref": "refs/heads/submit/test", "sha": "abc123"},
            )


class TestUploadFiles:
    """Tests for file upload via Git Data API."""

    def test_upload_creates_blobs_and_commit(
        self, mock_client: GitHubClient
    ) -> None:
        responses = [
            # GET ref
            {"object": {"sha": "base-sha"}},
            # GET commit
            {"tree": {"sha": "tree-sha"}},
            # POST blob (file 1)
            {"sha": "blob-sha-1"},
            # POST tree
            {"sha": "new-tree-sha"},
            # POST commit
            {"sha": "new-commit-sha"},
            # PATCH ref
            {},
        ]
        with patch.object(
            mock_client, "_request", side_effect=responses
        ) as mock_req:
            result = mock_client.upload_files(
                "testuser/leaderboard",
                "submit/test",
                [("trajectories/model/file.json", b'{"data": true}')],
            )
            assert result == "new-commit-sha"
            assert mock_req.call_count == 6


class TestCreatePR:
    """Tests for pull request creation."""

    def test_returns_pr_url(self, mock_client: GitHubClient) -> None:
        with patch.object(
            mock_client,
            "_request",
            return_value={
                "html_url": "https://github.com/gsma-labs/leaderboard/pull/42"
            },
        ):
            url = mock_client.create_pr(
                "gsma-labs/leaderboard",
                "testuser:submit/test",
                "Add test trajectories",
                "## Submission\n...",
            )
            assert url == "https://github.com/gsma-labs/leaderboard/pull/42"


class TestRequestErrorHandling:
    """Tests for HTTP error handling."""

    def test_github_error_raised_on_4xx(self, mock_client: GitHubClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        with patch.object(
            mock_client._client, "request", return_value=mock_response
        ):
            with pytest.raises(GitHubError, match="403"):
                mock_client._request("GET", "/user")

    def test_returns_empty_dict_on_204(self, mock_client: GitHubClient) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 204
        with patch.object(
            mock_client._client, "request", return_value=mock_response
        ):
            assert mock_client._request("DELETE", "/some/resource") == {}
