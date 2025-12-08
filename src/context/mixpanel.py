"""Mixpanel API integration for analytics context."""

import base64
from datetime import datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.context import ContextDocument
from src.utils.cache import cached
from src.utils.logging import get_logger

logger = get_logger(__name__)

MIXPANEL_API_URL = "https://mixpanel.com/api/2.0"
MIXPANEL_DATA_URL = "https://data.mixpanel.com/api/2.0"


class MixpanelClient:
    """Client for Mixpanel API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        # Mixpanel uses basic auth with API secret
        auth_string = f"{self.settings.mixpanel_api_secret}:"
        auth_bytes = base64.b64encode(auth_string.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {auth_bytes}",
            "Accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _request(
        self,
        endpoint: str,
        params: dict | None = None,
        base_url: str = MIXPANEL_API_URL,
    ) -> Any:
        """Make a request to Mixpanel API."""
        with httpx.Client(timeout=60) as client:
            response = client.get(
                f"{base_url}{endpoint}",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    @cached(prefix="mixpanel_insights", ttl_seconds=600)
    def get_top_events(self, days: int = 30, limit: int = 20) -> list[ContextDocument]:
        """
        Get top events by volume.

        Args:
            days: Number of days to look back
            limit: Maximum events to return

        Returns:
            List of ContextDocument objects with event insights
        """
        if not self.settings.mixpanel_api_secret:
            logger.warning("mixpanel_api_secret_not_configured")
            return []

        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")

        try:
            result = self._request(
                "/events",
                params={
                    "project_id": self.settings.mixpanel_project_id,
                    "from_date": from_date,
                    "to_date": to_date,
                    "limit": limit,
                },
            )

            documents = []
            events_data = result.get("data", {}).get("values", {})

            for event_name, event_data in events_data.items():
                # Calculate total count across the period
                total_count = sum(event_data.values()) if isinstance(event_data, dict) else 0

                content = f"Event: {event_name}\n"
                content += f"Total occurrences (last {days} days): {total_count:,}\n"

                doc = ContextDocument(
                    id=f"mixpanel-event-{event_name}",
                    source="mixpanel",
                    title=f"Event: {event_name}",
                    content=content,
                    metadata={
                        "type": "event_summary",
                        "event_name": event_name,
                        "total_count": total_count,
                        "period_days": days,
                    },
                )
                documents.append(doc)

            logger.info("mixpanel_events_fetched", count=len(documents))
            return documents

        except httpx.HTTPError as e:
            logger.error("mixpanel_api_error", error=str(e))
            return []

    @cached(prefix="mixpanel_funnels", ttl_seconds=600)
    def get_funnel_data(self, funnel_id: int, days: int = 30) -> ContextDocument | None:
        """
        Get funnel conversion data.

        Args:
            funnel_id: The funnel ID
            days: Number of days to analyze

        Returns:
            ContextDocument with funnel data or None
        """
        if not self.settings.mixpanel_api_secret:
            return None

        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")

        try:
            result = self._request(
                "/funnels",
                params={
                    "project_id": self.settings.mixpanel_project_id,
                    "funnel_id": funnel_id,
                    "from_date": from_date,
                    "to_date": to_date,
                },
            )

            funnel_data = result.get("data", {})
            funnel_name = result.get("meta", {}).get("funnel_name", f"Funnel {funnel_id}")

            content_parts = [f"Funnel: {funnel_name}", f"Period: {from_date} to {to_date}", ""]

            steps = funnel_data.get("steps", [])
            for i, step in enumerate(steps):
                step_name = step.get("event", f"Step {i + 1}")
                count = step.get("count", 0)
                conversion = step.get("step_conv_ratio", 0) * 100 if i > 0 else 100

                content_parts.append(f"Step {i + 1}: {step_name}")
                content_parts.append(f"  Count: {count:,}")
                if i > 0:
                    content_parts.append(f"  Conversion: {conversion:.1f}%")
                content_parts.append("")

            overall_conversion = funnel_data.get("overall_conv_ratio", 0) * 100
            content_parts.append(f"Overall Conversion: {overall_conversion:.1f}%")

            return ContextDocument(
                id=f"mixpanel-funnel-{funnel_id}",
                source="mixpanel",
                title=f"Funnel: {funnel_name}",
                content="\n".join(content_parts),
                metadata={
                    "type": "funnel",
                    "funnel_id": funnel_id,
                    "overall_conversion": overall_conversion,
                },
            )

        except httpx.HTTPError as e:
            logger.error("mixpanel_funnel_error", error=str(e), funnel_id=funnel_id)
            return None

    def get_analytics_summary(self) -> list[ContextDocument]:
        """Get a summary of analytics data."""
        documents = []
        documents.extend(self.get_top_events())
        return documents


# Singleton instance
_client: MixpanelClient | None = None


def get_mixpanel_client() -> MixpanelClient:
    """Get or create Mixpanel client instance."""
    global _client
    if _client is None:
        _client = MixpanelClient()
    return _client
