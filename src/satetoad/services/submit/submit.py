"""GitHub API client for leaderboard submission via Git Data API.

Uses httpx to interact with GitHub's REST API for forking, branching,
uploading files, and creating pull requests — no git CLI required.
"""

import base64

import httpx

GITHUB_API_BASE = "https://api.github.com"


class GitHubError(Exception):
    """Error from GitHub API interaction."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class GitHubClient:
    """HTTP client for GitHub REST API operations."""

    def __init__(self, token: str) -> None:
        self._client = httpx.Client(
            base_url=GITHUB_API_BASE,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """Extract human-readable message from a GitHub error response.

        Avoids leaking raw response bodies that may contain internal details.
        """
        try:
            return response.json().get("message", f"HTTP {response.status_code}")
        except (ValueError, KeyError):
            return f"HTTP {response.status_code}"

    def _request(self, method: str, url: str, **kwargs) -> dict:
        """Make an API request and return JSON, raising on errors."""
        response = self._client.request(method, url, **kwargs)
        if response.status_code >= 400:
            message = self._extract_error_message(response)
            raise GitHubError(
                f"GitHub API error {response.status_code}: {message}",
                status_code=response.status_code,
            )
        if response.status_code == 204:
            return {}
        return response.json()

    def check_auth(self) -> str:
        """Validate token and return authenticated username."""
        data = self._request("GET", "/user")
        return data["login"]

    def has_push_access(self, repo: str) -> bool:
        """Check if the authenticated user can push to the repo."""
        try:
            data = self._request("GET", f"/repos/{repo}")
        except GitHubError as exc:
            # 403 (forbidden) and 404 (not found / hidden) mean no access
            if exc.status_code in (403, 404):
                return False
            raise
        return data.get("permissions", {}).get("push", False)

    def ensure_fork(self, repo: str) -> str:
        """Fork a repo (idempotent — returns existing fork if present)."""
        data = self._request("POST", f"/repos/{repo}/forks")
        return data["full_name"]

    def get_default_branch_sha(self, repo: str) -> str:
        """Get the SHA of the default branch (main) HEAD."""
        data = self._request("GET", f"/repos/{repo}/git/ref/heads/main")
        return data["object"]["sha"]

    def create_branch(self, repo: str, branch_name: str, base_sha: str) -> None:
        """Create a new branch from a base SHA."""
        self._request(
            "POST",
            f"/repos/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        )

    def upload_files(
        self, repo: str, branch: str, files: list[tuple[str, bytes]]
    ) -> str:
        """Upload files to a branch using the Git Data API (blobs -> tree -> commit -> ref update).

        Returns:
            SHA of the new commit.
        """
        ref_data = self._request("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        base_sha = ref_data["object"]["sha"]

        commit_data = self._request("GET", f"/repos/{repo}/git/commits/{base_sha}")
        base_tree_sha = commit_data["tree"]["sha"]

        tree_items = []
        for path, content in files:
            blob_data = self._request(
                "POST",
                f"/repos/{repo}/git/blobs",
                json={
                    "content": base64.b64encode(content).decode("ascii"),
                    "encoding": "base64",
                },
            )
            tree_items.append(
                {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_data["sha"],
                }
            )

        tree_data = self._request(
            "POST",
            f"/repos/{repo}/git/trees",
            json={"base_tree": base_tree_sha, "tree": tree_items},
        )

        commit_result = self._request(
            "POST",
            f"/repos/{repo}/git/commits",
            json={
                "message": f"Add trajectory files ({len(files)} files)",
                "tree": tree_data["sha"],
                "parents": [base_sha],
            },
        )

        new_sha = commit_result["sha"]
        self._request(
            "PATCH",
            f"/repos/{repo}/git/refs/heads/{branch}",
            json={"sha": new_sha},
        )

        return new_sha

    def create_pr(self, base_repo: str, head: str, title: str, body: str) -> str:
        """Create a pull request and return its URL."""
        data = self._request(
            "POST",
            f"/repos/{base_repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": "main",
            },
        )
        return data["html_url"]
