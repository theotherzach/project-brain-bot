"""GitHub API integration for code and PR context."""

from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.context import ContextDocument
from src.utils.cache import cached
from src.utils.logging import get_logger

logger = get_logger(__name__)

GITHUB_API_URL = "https://api.github.com"


class GitHubClient:
    """Client for GitHub REST API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.headers = {
            "Authorization": f"Bearer {self.settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _request(self, method: str, endpoint: str, params: dict | None = None) -> Any:
        """Make a request to GitHub API."""
        with httpx.Client(timeout=30) as client:
            response = client.request(
                method,
                f"{GITHUB_API_URL}{endpoint}",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    @cached(prefix="github_prs", ttl_seconds=300)
    def get_recent_prs(
        self, owner: str, repo: str, state: str = "all", limit: int = 30
    ) -> list[ContextDocument]:
        """
        Fetch recent pull requests from a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            state: PR state (open, closed, all)
            limit: Maximum PRs to fetch

        Returns:
            List of ContextDocument objects
        """
        if not self.settings.github_token:
            logger.warning("github_token_not_configured")
            return []

        try:
            prs = self._request(
                "GET",
                f"/repos/{owner}/{repo}/pulls",
                params={"state": state, "per_page": limit, "sort": "updated"},
            )

            documents = []
            for pr in prs:
                content_parts = []
                if pr.get("body"):
                    content_parts.append(pr["body"])

                content_parts.append(f"State: {pr['state']}")
                content_parts.append(f"Author: {pr['user']['login']}")

                if pr.get("merged_at"):
                    content_parts.append("Merged: Yes")

                if pr.get("labels"):
                    labels = [label["name"] for label in pr["labels"]]
                    content_parts.append(f"Labels: {', '.join(labels)}")

                doc = ContextDocument(
                    id=f"github-pr-{owner}-{repo}-{pr['number']}",
                    source="github",
                    title=f"PR #{pr['number']}: {pr['title']}",
                    content="\n".join(content_parts),
                    url=pr["html_url"],
                    metadata={
                        "type": "pull_request",
                        "repo": f"{owner}/{repo}",
                        "number": pr["number"],
                        "state": pr["state"],
                        "author": pr["user"]["login"],
                    },
                    created_at=datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
                    if pr.get("created_at")
                    else None,
                    updated_at=datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
                    if pr.get("updated_at")
                    else None,
                )
                documents.append(doc)

            logger.info("github_prs_fetched", repo=f"{owner}/{repo}", count=len(documents))
            return documents

        except httpx.HTTPError as e:
            logger.error("github_api_error", error=str(e))
            return []

    @cached(prefix="github_issues", ttl_seconds=300)
    def get_recent_issues(
        self, owner: str, repo: str, state: str = "all", limit: int = 30
    ) -> list[ContextDocument]:
        """
        Fetch recent issues from a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            state: Issue state (open, closed, all)
            limit: Maximum issues to fetch

        Returns:
            List of ContextDocument objects
        """
        if not self.settings.github_token:
            return []

        try:
            issues = self._request(
                "GET",
                f"/repos/{owner}/{repo}/issues",
                params={"state": state, "per_page": limit, "sort": "updated"},
            )

            documents = []
            for issue in issues:
                # Skip pull requests (they also appear in issues endpoint)
                if "pull_request" in issue:
                    continue

                content_parts = []
                if issue.get("body"):
                    content_parts.append(issue["body"])

                content_parts.append(f"State: {issue['state']}")
                content_parts.append(f"Author: {issue['user']['login']}")

                if issue.get("labels"):
                    labels = [label["name"] for label in issue["labels"]]
                    content_parts.append(f"Labels: {', '.join(labels)}")

                if issue.get("assignee"):
                    content_parts.append(f"Assignee: {issue['assignee']['login']}")

                doc = ContextDocument(
                    id=f"github-issue-{owner}-{repo}-{issue['number']}",
                    source="github",
                    title=f"Issue #{issue['number']}: {issue['title']}",
                    content="\n".join(content_parts),
                    url=issue["html_url"],
                    metadata={
                        "type": "issue",
                        "repo": f"{owner}/{repo}",
                        "number": issue["number"],
                        "state": issue["state"],
                    },
                    created_at=datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
                    if issue.get("created_at")
                    else None,
                    updated_at=datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00"))
                    if issue.get("updated_at")
                    else None,
                )
                documents.append(doc)

            logger.info("github_issues_fetched", repo=f"{owner}/{repo}", count=len(documents))
            return documents

        except httpx.HTTPError as e:
            logger.error("github_issues_error", error=str(e))
            return []

    def get_all_repo_documents(self) -> list[ContextDocument]:
        """Fetch documents from all configured repositories."""
        all_documents = []
        for repo in self.settings.github_repo_list:
            parts = repo.split("/")
            if len(parts) == 2:
                owner, repo_name = parts
                all_documents.extend(self.get_recent_prs(owner, repo_name))
                all_documents.extend(self.get_recent_issues(owner, repo_name))
        return all_documents

    @cached(prefix="github_search", ttl_seconds=300)
    def search_code(self, query: str, limit: int = 10) -> list[ContextDocument]:
        """
        Search code across configured repositories.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching ContextDocument objects
        """
        if not self.settings.github_token:
            return []

        # Build repo filter for search
        repo_filter = " ".join([f"repo:{repo}" for repo in self.settings.github_repo_list])
        if not repo_filter:
            return []

        try:
            result = self._request(
                "GET",
                "/search/code",
                params={"q": f"{query} {repo_filter}", "per_page": limit},
            )

            documents = []
            for item in result.get("items", []):
                doc = ContextDocument(
                    id=f"github-code-{item['sha'][:8]}",
                    source="github",
                    title=f"{item['repository']['full_name']}/{item['path']}",
                    content=f"File: {item['path']}\nRepository: {item['repository']['full_name']}",
                    url=item["html_url"],
                    metadata={
                        "type": "code",
                        "repo": item["repository"]["full_name"],
                        "path": item["path"],
                    },
                )
                documents.append(doc)

            return documents

        except httpx.HTTPError as e:
            logger.error("github_search_error", error=str(e))
            return []


# Singleton instance
_client: GitHubClient | None = None


def get_github_client() -> GitHubClient:
    """Get or create GitHub client instance."""
    global _client
    if _client is None:
        _client = GitHubClient()
    return _client
