"""Linear API integration for project management context."""

from datetime import datetime
from functools import lru_cache
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.context import ContextDocument
from src.utils.cache import cached
from src.utils.logging import get_logger

logger = get_logger(__name__)

LINEAR_API_URL = "https://api.linear.app/graphql"


class LinearClient:
    """Client for Linear GraphQL API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.headers = {
            "Authorization": self.settings.linear_api_key,
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _execute_query(self, query: str, variables: dict | None = None) -> dict[str, Any]:
        """Execute a GraphQL query against Linear API."""
        with httpx.Client(timeout=30) as client:
            response = client.post(
                LINEAR_API_URL,
                headers=self.headers,
                json={"query": query, "variables": variables or {}},
            )
            response.raise_for_status()
            return response.json()

    @cached(prefix="linear_issues", ttl_seconds=300)
    def get_recent_issues(self, limit: int = 50) -> list[ContextDocument]:
        """
        Fetch recent issues from Linear.

        Args:
            limit: Maximum number of issues to fetch

        Returns:
            List of ContextDocument objects
        """
        if not self.settings.linear_api_key:
            logger.warning("linear_api_key_not_configured")
            return []

        query = """
        query RecentIssues($limit: Int!, $teamId: String) {
            issues(
                first: $limit
                orderBy: updatedAt
                filter: { team: { id: { eq: $teamId } } }
            ) {
                nodes {
                    id
                    identifier
                    title
                    description
                    state { name }
                    priority
                    assignee { name }
                    labels { nodes { name } }
                    url
                    createdAt
                    updatedAt
                }
            }
        }
        """

        variables = {"limit": limit}
        if self.settings.linear_team_id:
            variables["teamId"] = self.settings.linear_team_id

        try:
            result = self._execute_query(query, variables)
            issues = result.get("data", {}).get("issues", {}).get("nodes", [])

            documents = []
            for issue in issues:
                content_parts = []
                if issue.get("description"):
                    content_parts.append(issue["description"])

                content_parts.append(f"Status: {issue.get('state', {}).get('name', 'Unknown')}")
                content_parts.append(f"Priority: {issue.get('priority', 'None')}")

                if issue.get("assignee"):
                    content_parts.append(f"Assignee: {issue['assignee']['name']}")

                labels = [label["name"] for label in issue.get("labels", {}).get("nodes", [])]
                if labels:
                    content_parts.append(f"Labels: {', '.join(labels)}")

                doc = ContextDocument(
                    id=f"linear-{issue['id']}",
                    source="linear",
                    title=f"{issue['identifier']}: {issue['title']}",
                    content="\n".join(content_parts),
                    url=issue.get("url"),
                    metadata={
                        "identifier": issue["identifier"],
                        "state": issue.get("state", {}).get("name"),
                        "priority": issue.get("priority"),
                        "labels": labels,
                    },
                    created_at=datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00"))
                    if issue.get("createdAt")
                    else None,
                    updated_at=datetime.fromisoformat(issue["updatedAt"].replace("Z", "+00:00"))
                    if issue.get("updatedAt")
                    else None,
                )
                documents.append(doc)

            logger.info("linear_issues_fetched", count=len(documents))
            return documents

        except httpx.HTTPError as e:
            logger.error("linear_api_error", error=str(e))
            return []

    @cached(prefix="linear_search", ttl_seconds=300)
    def search_issues(self, query_text: str, limit: int = 10) -> list[ContextDocument]:
        """
        Search issues by text.

        Args:
            query_text: Search query
            limit: Maximum results

        Returns:
            List of matching ContextDocument objects
        """
        if not self.settings.linear_api_key:
            return []

        query = """
        query SearchIssues($query: String!, $limit: Int!) {
            issueSearch(query: $query, first: $limit) {
                nodes {
                    id
                    identifier
                    title
                    description
                    state { name }
                    priority
                    assignee { name }
                    url
                    updatedAt
                }
            }
        }
        """

        try:
            result = self._execute_query(query, {"query": query_text, "limit": limit})
            issues = result.get("data", {}).get("issueSearch", {}).get("nodes", [])

            documents = []
            for issue in issues:
                content_parts = []
                if issue.get("description"):
                    content_parts.append(issue["description"])
                content_parts.append(f"Status: {issue.get('state', {}).get('name', 'Unknown')}")

                doc = ContextDocument(
                    id=f"linear-{issue['id']}",
                    source="linear",
                    title=f"{issue['identifier']}: {issue['title']}",
                    content="\n".join(content_parts),
                    url=issue.get("url"),
                    metadata={"identifier": issue["identifier"]},
                )
                documents.append(doc)

            return documents

        except httpx.HTTPError as e:
            logger.error("linear_search_error", error=str(e))
            return []


@lru_cache(maxsize=1)
def get_linear_client() -> LinearClient:
    """Get or create Linear client instance."""
    return LinearClient()
