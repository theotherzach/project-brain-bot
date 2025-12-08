"""Datadog API integration for monitoring context."""

from datetime import datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.context import ContextDocument
from src.utils.cache import cached
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DatadogClient:
    """Client for Datadog API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = f"https://api.{self.settings.datadog_site}"
        self.headers = {
            "DD-API-KEY": self.settings.datadog_api_key,
            "DD-APPLICATION-KEY": self.settings.datadog_app_key,
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> Any:
        """Make a request to Datadog API."""
        with httpx.Client(timeout=30) as client:
            response = client.request(
                method,
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()

    @cached(prefix="datadog_monitors", ttl_seconds=300)
    def get_monitors(self, limit: int = 50) -> list[ContextDocument]:
        """
        Get monitor status and alerts.

        Args:
            limit: Maximum monitors to fetch

        Returns:
            List of ContextDocument objects
        """
        if not self.settings.datadog_api_key or not self.settings.datadog_app_key:
            logger.warning("datadog_keys_not_configured")
            return []

        try:
            result = self._request(
                "GET",
                "/api/v1/monitor",
                params={"page_size": limit},
            )

            documents = []
            for monitor in result:
                content_parts = []

                content_parts.append(f"Type: {monitor.get('type', 'Unknown')}")
                content_parts.append(f"Status: {monitor.get('overall_state', 'Unknown')}")

                if monitor.get("message"):
                    content_parts.append(f"Message: {monitor['message']}")

                if monitor.get("query"):
                    content_parts.append(f"Query: {monitor['query']}")

                tags = monitor.get("tags", [])
                if tags:
                    content_parts.append(f"Tags: {', '.join(tags)}")

                # Get alert status
                state = monitor.get("overall_state", "")
                if state in ("Alert", "Warn"):
                    content_parts.append(f"Alert Status: {state}")

                doc = ContextDocument(
                    id=f"datadog-monitor-{monitor['id']}",
                    source="datadog",
                    title=f"Monitor: {monitor.get('name', 'Unnamed')}",
                    content="\n".join(content_parts),
                    url=f"https://app.{self.settings.datadog_site}/monitors/{monitor['id']}",
                    metadata={
                        "type": "monitor",
                        "monitor_id": monitor["id"],
                        "monitor_type": monitor.get("type"),
                        "status": state,
                        "tags": tags,
                    },
                    created_at=datetime.fromtimestamp(monitor["created"] / 1000)
                    if monitor.get("created")
                    else None,
                    updated_at=datetime.fromtimestamp(monitor["modified"] / 1000)
                    if monitor.get("modified")
                    else None,
                )
                documents.append(doc)

            logger.info("datadog_monitors_fetched", count=len(documents))
            return documents

        except httpx.HTTPError as e:
            logger.error("datadog_api_error", error=str(e))
            return []

    @cached(prefix="datadog_incidents", ttl_seconds=300)
    def get_recent_incidents(self, days: int = 7) -> list[ContextDocument]:
        """
        Get recent incidents.

        Args:
            days: Number of days to look back

        Returns:
            List of ContextDocument objects
        """
        if not self.settings.datadog_api_key or not self.settings.datadog_app_key:
            return []

        try:
            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            result = self._request(
                "GET",
                "/api/v2/incidents",
                params={
                    "filter[created][start]": start_time.isoformat(),
                    "filter[created][end]": end_time.isoformat(),
                    "page[size]": 50,
                },
            )

            documents = []
            for incident in result.get("data", []):
                attrs = incident.get("attributes", {})

                content_parts = []
                content_parts.append(f"Status: {attrs.get('state', 'Unknown')}")
                content_parts.append(f"Severity: {attrs.get('severity', 'Unknown')}")

                if attrs.get("title"):
                    content_parts.append(f"Title: {attrs['title']}")

                if attrs.get("customer_impact_scope"):
                    content_parts.append(f"Impact: {attrs['customer_impact_scope']}")

                if attrs.get("postmortem_id"):
                    content_parts.append("Postmortem: Available")

                doc = ContextDocument(
                    id=f"datadog-incident-{incident['id']}",
                    source="datadog",
                    title=f"Incident: {attrs.get('title', 'Unnamed')}",
                    content="\n".join(content_parts),
                    url=attrs.get("public_id"),
                    metadata={
                        "type": "incident",
                        "incident_id": incident["id"],
                        "severity": attrs.get("severity"),
                        "state": attrs.get("state"),
                    },
                    created_at=datetime.fromisoformat(attrs["created"].replace("Z", "+00:00"))
                    if attrs.get("created")
                    else None,
                )
                documents.append(doc)

            logger.info("datadog_incidents_fetched", count=len(documents))
            return documents

        except httpx.HTTPError as e:
            logger.error("datadog_incidents_error", error=str(e))
            return []

    @cached(prefix="datadog_alerts", ttl_seconds=60)
    def get_active_alerts(self) -> list[ContextDocument]:
        """
        Get currently active alerts.

        Returns:
            List of ContextDocument objects for active alerts
        """
        if not self.settings.datadog_api_key or not self.settings.datadog_app_key:
            return []

        try:
            # Get monitors that are currently alerting
            result = self._request(
                "GET",
                "/api/v1/monitor",
                params={
                    "group_states": "alert,warn",
                    "page_size": 50,
                },
            )

            documents = []
            for monitor in result:
                state = monitor.get("overall_state", "")
                if state not in ("Alert", "Warn"):
                    continue

                content_parts = [
                    f"Status: {state}",
                    f"Type: {monitor.get('type', 'Unknown')}",
                ]

                if monitor.get("message"):
                    content_parts.append(f"Message: {monitor['message'][:500]}")

                doc = ContextDocument(
                    id=f"datadog-alert-{monitor['id']}",
                    source="datadog",
                    title=f"Active {state}: {monitor.get('name', 'Unnamed')}",
                    content="\n".join(content_parts),
                    url=f"https://app.{self.settings.datadog_site}/monitors/{monitor['id']}",
                    metadata={
                        "type": "active_alert",
                        "monitor_id": monitor["id"],
                        "severity": state.lower(),
                    },
                )
                documents.append(doc)

            return documents

        except httpx.HTTPError as e:
            logger.error("datadog_alerts_error", error=str(e))
            return []

    def get_monitoring_summary(self) -> list[ContextDocument]:
        """Get a summary of monitoring data."""
        documents = []
        documents.extend(self.get_monitors())
        documents.extend(self.get_active_alerts())
        documents.extend(self.get_recent_incidents())
        return documents


# Singleton instance
_client: DatadogClient | None = None


def get_datadog_client() -> DatadogClient:
    """Get or create Datadog client instance."""
    global _client
    if _client is None:
        _client = DatadogClient()
    return _client
