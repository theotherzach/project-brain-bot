"""AppSignal API integration for monitoring context."""

from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.context import ContextDocument
from src.utils.cache import cached
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AppSignalClient:
    """Client for AppSignal API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = "https://appsignal.com/api"
        self.headers = {
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
        """Make a request to AppSignal API."""
        request_params = params.copy() if params else {}
        request_params["token"] = self.settings.appsignal_api_key

        with httpx.Client(timeout=30) as client:
            response = client.request(
                method,
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=request_params,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()

    @cached(prefix="appsignal_incidents", ttl_seconds=300)
    def get_incidents(self, limit: int = 50) -> list[ContextDocument]:
        """
        Get recent incidents/alerts.

        Args:
            limit: Maximum incidents to fetch

        Returns:
            List of ContextDocument objects
        """
        if not self.settings.appsignal_api_key or not self.settings.appsignal_app_id:
            logger.warning("appsignal_keys_not_configured")
            return []

        try:
            result = self._request(
                "GET",
                f"/{self.settings.appsignal_app_id}/incidents.json",
                params={"limit": limit},
            )

            documents = []
            for incident in result.get("incidents", result) if isinstance(result, dict) else result:
                content_parts = []

                content_parts.append(f"Status: {incident.get('state', 'Unknown')}")
                content_parts.append(f"Severity: {incident.get('severity', 'Unknown')}")

                if incident.get("message"):
                    content_parts.append(f"Message: {incident['message']}")

                if incident.get("error_class"):
                    content_parts.append(f"Error: {incident['error_class']}")

                if incident.get("action"):
                    content_parts.append(f"Action: {incident['action']}")

                tags = incident.get("tags", [])
                if tags:
                    content_parts.append(f"Tags: {', '.join(tags)}")

                doc = ContextDocument(
                    id=f"appsignal-incident-{incident.get('id', 'unknown')}",
                    source="appsignal",
                    title=f"Incident: {incident.get('message', incident.get('error_class', 'Unnamed'))[:100]}",
                    content="\n".join(content_parts),
                    url=f"https://appsignal.com/apps/{self.settings.appsignal_app_id}/incidents/{incident.get('id')}",
                    metadata={
                        "type": "incident",
                        "incident_id": incident.get("id"),
                        "severity": incident.get("severity"),
                        "state": incident.get("state"),
                        "tags": tags,
                    },
                    created_at=datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
                    if incident.get("created_at")
                    else None,
                    updated_at=datetime.fromisoformat(incident["updated_at"].replace("Z", "+00:00"))
                    if incident.get("updated_at")
                    else None,
                )
                documents.append(doc)

            logger.info("appsignal_incidents_fetched", count=len(documents))
            return documents

        except httpx.HTTPError as e:
            logger.error("appsignal_api_error", error=str(e))
            return []

    @cached(prefix="appsignal_deploys", ttl_seconds=300)
    def get_recent_deploys(self, days: int = 7) -> list[ContextDocument]:
        """
        Get recent deploy markers.

        Args:
            days: Number of days to look back

        Returns:
            List of ContextDocument objects
        """
        if not self.settings.appsignal_api_key or not self.settings.appsignal_app_id:
            return []

        try:
            result = self._request(
                "GET",
                f"/{self.settings.appsignal_app_id}/markers.json",
                params={"limit": 50},
            )

            documents = []
            cutoff_time = datetime.now() - timedelta(days=days)

            for marker in result.get("markers", result) if isinstance(result, dict) else result:
                # Parse created_at and filter by date
                created_at = None
                if marker.get("created_at"):
                    created_at = datetime.fromisoformat(marker["created_at"].replace("Z", "+00:00"))
                    if created_at.replace(tzinfo=None) < cutoff_time:
                        continue

                content_parts = []

                if marker.get("revision"):
                    content_parts.append(f"Revision: {marker['revision']}")

                if marker.get("user"):
                    content_parts.append(f"Deployed by: {marker['user']}")

                if marker.get("environment"):
                    content_parts.append(f"Environment: {marker['environment']}")

                if marker.get("repository"):
                    content_parts.append(f"Repository: {marker['repository']}")

                doc = ContextDocument(
                    id=f"appsignal-deploy-{marker.get('id', 'unknown')}",
                    source="appsignal",
                    title=f"Deploy: {marker.get('revision', 'Unknown')[:12]}",
                    content="\n".join(content_parts),
                    url=f"https://appsignal.com/apps/{self.settings.appsignal_app_id}/markers",
                    metadata={
                        "type": "deploy",
                        "marker_id": marker.get("id"),
                        "revision": marker.get("revision"),
                        "user": marker.get("user"),
                        "environment": marker.get("environment"),
                    },
                    created_at=created_at,
                )
                documents.append(doc)

            logger.info("appsignal_deploys_fetched", count=len(documents))
            return documents

        except httpx.HTTPError as e:
            logger.error("appsignal_deploys_error", error=str(e))
            return []

    @cached(prefix="appsignal_alerts", ttl_seconds=60)
    def get_active_alerts(self) -> list[ContextDocument]:
        """
        Get currently active/open incidents.

        Returns:
            List of ContextDocument objects for active alerts
        """
        if not self.settings.appsignal_api_key or not self.settings.appsignal_app_id:
            return []

        try:
            result = self._request(
                "GET",
                f"/{self.settings.appsignal_app_id}/incidents.json",
                params={"state": "open", "limit": 50},
            )

            documents = []
            for incident in result.get("incidents", result) if isinstance(result, dict) else result:
                state = incident.get("state", "")
                if state != "open":
                    continue

                severity = incident.get("severity", "unknown")
                content_parts = [
                    "Status: Active",
                    f"Severity: {severity}",
                ]

                if incident.get("message"):
                    content_parts.append(f"Message: {incident['message'][:500]}")

                if incident.get("error_class"):
                    content_parts.append(f"Error: {incident['error_class']}")

                if incident.get("count"):
                    content_parts.append(f"Occurrences: {incident['count']}")

                doc = ContextDocument(
                    id=f"appsignal-alert-{incident.get('id', 'unknown')}",
                    source="appsignal",
                    title=f"Active Alert: {incident.get('message', incident.get('error_class', 'Unnamed'))[:80]}",
                    content="\n".join(content_parts),
                    url=f"https://appsignal.com/apps/{self.settings.appsignal_app_id}/incidents/{incident.get('id')}",
                    metadata={
                        "type": "active_alert",
                        "incident_id": incident.get("id"),
                        "severity": severity,
                    },
                )
                documents.append(doc)

            return documents

        except httpx.HTTPError as e:
            logger.error("appsignal_alerts_error", error=str(e))
            return []

    @cached(prefix="appsignal_errors", ttl_seconds=300)
    def get_error_samples(self, limit: int = 20) -> list[ContextDocument]:
        """
        Get recent error samples.

        Args:
            limit: Maximum error samples to fetch

        Returns:
            List of ContextDocument objects
        """
        if not self.settings.appsignal_api_key or not self.settings.appsignal_app_id:
            return []

        try:
            result = self._request(
                "GET",
                f"/{self.settings.appsignal_app_id}/samples.json",
                params={"limit": limit, "kind": "exception"},
            )

            documents = []
            for sample in result.get("samples", result) if isinstance(result, dict) else result:
                content_parts = []

                if sample.get("exception_class"):
                    content_parts.append(f"Error: {sample['exception_class']}")

                if sample.get("exception_message"):
                    content_parts.append(f"Message: {sample['exception_message']}")

                if sample.get("action"):
                    content_parts.append(f"Action: {sample['action']}")

                if sample.get("path"):
                    content_parts.append(f"Path: {sample['path']}")

                if sample.get("hostname"):
                    content_parts.append(f"Host: {sample['hostname']}")

                doc = ContextDocument(
                    id=f"appsignal-error-{sample.get('id', 'unknown')}",
                    source="appsignal",
                    title=f"Error: {sample.get('exception_class', 'Unknown')}",
                    content="\n".join(content_parts),
                    url=f"https://appsignal.com/apps/{self.settings.appsignal_app_id}/samples/{sample.get('id')}",
                    metadata={
                        "type": "error_sample",
                        "sample_id": sample.get("id"),
                        "exception_class": sample.get("exception_class"),
                        "action": sample.get("action"),
                    },
                    created_at=datetime.fromisoformat(sample["time"].replace("Z", "+00:00"))
                    if sample.get("time")
                    else None,
                )
                documents.append(doc)

            logger.info("appsignal_errors_fetched", count=len(documents))
            return documents

        except httpx.HTTPError as e:
            logger.error("appsignal_errors_error", error=str(e))
            return []

    def get_monitoring_summary(self) -> list[ContextDocument]:
        """Get a summary of monitoring data."""
        documents = []
        documents.extend(self.get_incidents())
        documents.extend(self.get_active_alerts())
        documents.extend(self.get_recent_deploys())
        documents.extend(self.get_error_samples())
        return documents


@lru_cache(maxsize=1)
def get_appsignal_client() -> AppSignalClient:
    """Get or create AppSignal client instance."""
    return AppSignalClient()
