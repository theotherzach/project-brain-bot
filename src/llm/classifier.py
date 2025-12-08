"""Question classification for routing to appropriate data sources."""

import json
from typing import Literal

import anthropic

from src.config import get_settings
from src.llm.prompts import CLASSIFICATION_PROMPT
from src.utils.cache import cached
from src.utils.logging import get_logger

logger = get_logger(__name__)

SourceType = Literal["linear", "notion", "github", "mixpanel", "datadog"]
ALL_SOURCES: list[SourceType] = ["linear", "notion", "github", "mixpanel", "datadog"]


class QuestionClassifier:
    """Classifies questions to determine relevant data sources."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)

    @cached(prefix="classify", ttl_seconds=3600)
    def classify(self, question: str) -> list[SourceType]:
        """
        Classify a question to determine which data sources to query.

        Args:
            question: The user's question

        Returns:
            List of relevant source types
        """
        logger.info("classifying_question", question=question[:100])

        try:
            message = self.client.messages.create(
                model=self.settings.claude_model,
                max_tokens=256,
                messages=[
                    {
                        "role": "user",
                        "content": CLASSIFICATION_PROMPT.format(question=question),
                    }
                ],
            )

            response_text = message.content[0].text.strip()

            # Parse JSON response
            try:
                result = json.loads(response_text)
                sources = result.get("sources", [])

                # Validate sources
                valid_sources: list[SourceType] = [
                    s for s in sources if s in ALL_SOURCES
                ]

                if not valid_sources:
                    logger.warning(
                        "no_valid_sources_classified",
                        raw_response=response_text,
                    )
                    return ["notion", "linear"]  # Default fallback

                logger.info(
                    "question_classified",
                    sources=valid_sources,
                    reasoning=result.get("reasoning", ""),
                )
                return valid_sources

            except json.JSONDecodeError:
                logger.warning(
                    "classification_parse_error",
                    raw_response=response_text,
                )
                return ["notion", "linear"]  # Default fallback

        except anthropic.APIError as e:
            logger.error("classification_api_error", error=str(e))
            return ["notion", "linear"]  # Default fallback


# Singleton instance
_classifier: QuestionClassifier | None = None


def get_classifier() -> QuestionClassifier:
    """Get or create classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = QuestionClassifier()
    return _classifier
