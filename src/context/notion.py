"""Notion API integration for documentation context."""

from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.context import ContextDocument
from src.utils.cache import cached
from src.utils.logging import get_logger

logger = get_logger(__name__)

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Client for Notion API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.headers = {
            "Authorization": f"Bearer {self.settings.notion_api_key}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _request(
        self, method: str, endpoint: str, json_data: dict | None = None
    ) -> dict[str, Any]:
        """Make a request to Notion API."""
        with httpx.Client(timeout=30) as client:
            response = client.request(
                method,
                f"{NOTION_API_URL}{endpoint}",
                headers=self.headers,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()

    def _extract_text_from_rich_text(self, rich_text: list[dict]) -> str:
        """Extract plain text from Notion rich text array."""
        return "".join(item.get("plain_text", "") for item in rich_text)

    def _extract_page_content(self, blocks: list[dict]) -> str:
        """Extract text content from page blocks."""
        content_parts = []

        for block in blocks:
            block_type = block.get("type", "")

            if block_type == "paragraph":
                text = self._extract_text_from_rich_text(
                    block.get("paragraph", {}).get("rich_text", [])
                )
                if text:
                    content_parts.append(text)

            elif block_type in ("heading_1", "heading_2", "heading_3"):
                text = self._extract_text_from_rich_text(
                    block.get(block_type, {}).get("rich_text", [])
                )
                if text:
                    prefix = "#" * int(block_type[-1])
                    content_parts.append(f"{prefix} {text}")

            elif block_type == "bulleted_list_item":
                text = self._extract_text_from_rich_text(
                    block.get("bulleted_list_item", {}).get("rich_text", [])
                )
                if text:
                    content_parts.append(f"* {text}")

            elif block_type == "numbered_list_item":
                text = self._extract_text_from_rich_text(
                    block.get("numbered_list_item", {}).get("rich_text", [])
                )
                if text:
                    content_parts.append(f"- {text}")

            elif block_type == "to_do":
                text = self._extract_text_from_rich_text(
                    block.get("to_do", {}).get("rich_text", [])
                )
                checked = block.get("to_do", {}).get("checked", False)
                checkbox = "[x]" if checked else "[ ]"
                if text:
                    content_parts.append(f"{checkbox} {text}")

            elif block_type == "code":
                text = self._extract_text_from_rich_text(
                    block.get("code", {}).get("rich_text", [])
                )
                language = block.get("code", {}).get("language", "")
                if text:
                    content_parts.append(f"```{language}\n{text}\n```")

            elif block_type == "quote":
                text = self._extract_text_from_rich_text(
                    block.get("quote", {}).get("rich_text", [])
                )
                if text:
                    content_parts.append(f"> {text}")

        return "\n\n".join(content_parts)

    @cached(prefix="notion_pages", ttl_seconds=300)
    def get_database_pages(self, database_id: str, limit: int = 50) -> list[ContextDocument]:
        """
        Fetch pages from a Notion database.

        Args:
            database_id: The Notion database ID
            limit: Maximum pages to fetch

        Returns:
            List of ContextDocument objects
        """
        if not self.settings.notion_api_key:
            logger.warning("notion_api_key_not_configured")
            return []

        try:
            result = self._request(
                "POST",
                f"/databases/{database_id}/query",
                json_data={"page_size": min(limit, 100)},
            )

            documents = []
            for page in result.get("results", []):
                page_id = page["id"]

                # Extract title from properties
                title = "Untitled"
                for prop_name, prop_value in page.get("properties", {}).items():
                    if prop_value.get("type") == "title":
                        title_items = prop_value.get("title", [])
                        if title_items:
                            title = self._extract_text_from_rich_text(title_items)
                        break

                # Fetch page content
                try:
                    blocks_result = self._request("GET", f"/blocks/{page_id}/children")
                    content = self._extract_page_content(blocks_result.get("results", []))
                except httpx.HTTPError:
                    content = ""

                doc = ContextDocument(
                    id=f"notion-{page_id}",
                    source="notion",
                    title=title,
                    content=content or "No content",
                    url=page.get("url"),
                    metadata={
                        "database_id": database_id,
                    },
                    created_at=datetime.fromisoformat(
                        page["created_time"].replace("Z", "+00:00")
                    )
                    if page.get("created_time")
                    else None,
                    updated_at=datetime.fromisoformat(
                        page["last_edited_time"].replace("Z", "+00:00")
                    )
                    if page.get("last_edited_time")
                    else None,
                )
                documents.append(doc)

            logger.info("notion_pages_fetched", database_id=database_id, count=len(documents))
            return documents

        except httpx.HTTPError as e:
            logger.error("notion_api_error", error=str(e))
            return []

    def get_all_database_pages(self) -> list[ContextDocument]:
        """Fetch pages from all configured databases."""
        all_documents = []
        for db_id in self.settings.notion_database_id_list:
            documents = self.get_database_pages(db_id)
            all_documents.extend(documents)
        return all_documents

    @cached(prefix="notion_search", ttl_seconds=300)
    def search(self, query: str, limit: int = 10) -> list[ContextDocument]:
        """
        Search Notion for pages matching query.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching ContextDocument objects
        """
        if not self.settings.notion_api_key:
            return []

        try:
            result = self._request(
                "POST",
                "/search",
                json_data={
                    "query": query,
                    "page_size": min(limit, 100),
                    "filter": {"property": "object", "value": "page"},
                },
            )

            documents = []
            for page in result.get("results", []):
                page_id = page["id"]

                # Extract title
                title = "Untitled"
                for prop_name, prop_value in page.get("properties", {}).items():
                    if prop_value.get("type") == "title":
                        title_items = prop_value.get("title", [])
                        if title_items:
                            title = self._extract_text_from_rich_text(title_items)
                        break

                # Fetch content
                try:
                    blocks_result = self._request("GET", f"/blocks/{page_id}/children")
                    content = self._extract_page_content(blocks_result.get("results", []))
                except httpx.HTTPError:
                    content = ""

                doc = ContextDocument(
                    id=f"notion-{page_id}",
                    source="notion",
                    title=title,
                    content=content or "No content",
                    url=page.get("url"),
                )
                documents.append(doc)

            return documents

        except httpx.HTTPError as e:
            logger.error("notion_search_error", error=str(e))
            return []


# Singleton instance
_client: NotionClient | None = None


def get_notion_client() -> NotionClient:
    """Get or create Notion client instance."""
    global _client
    if _client is None:
        _client = NotionClient()
    return _client
