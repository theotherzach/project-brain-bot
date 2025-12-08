"""Claude client for generating responses."""

import anthropic

from src.config import get_settings
from src.llm.prompts import ANSWER_WITH_CONTEXT_PROMPT, SYSTEM_PROMPT
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ClaudeClient:
    """Client for interacting with Claude API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)

    def generate_response(
        self,
        question: str,
        context: str,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """
        Generate a response to a question using provided context.

        Args:
            question: The user's question
            context: Retrieved context from various sources
            conversation_history: Optional previous messages for context

        Returns:
            Generated response text
        """
        logger.info("generating_response", question=question[:100])

        # Build messages
        messages: list[dict] = []

        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)

        # Add current question with context
        user_message = ANSWER_WITH_CONTEXT_PROMPT.format(
            question=question,
            context=context if context else "No relevant context found.",
        )
        messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.messages.create(
                model=self.settings.claude_model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=messages,
            )

            answer = response.content[0].text
            logger.info(
                "response_generated",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            return answer

        except anthropic.APIError as e:
            logger.error("claude_api_error", error=str(e))
            return (
                "I'm sorry, I encountered an error while processing your question. "
                "Please try again in a moment."
            )

    def generate_search_queries(self, question: str) -> list[str]:
        """
        Generate optimized search queries for RAG retrieval.

        Args:
            question: The user's question

        Returns:
            List of search queries
        """
        from src.llm.prompts import RAG_QUERY_PROMPT
        import json

        logger.debug("generating_search_queries", question=question[:100])

        try:
            response = self.client.messages.create(
                model=self.settings.claude_model,
                max_tokens=256,
                messages=[
                    {
                        "role": "user",
                        "content": RAG_QUERY_PROMPT.format(question=question),
                    }
                ],
            )

            response_text = response.content[0].text.strip()

            try:
                queries = json.loads(response_text)
                if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
                    return queries[:3]  # Limit to 3 queries
            except json.JSONDecodeError:
                pass

            # Fallback: use the question itself
            return [question]

        except anthropic.APIError as e:
            logger.error("query_generation_error", error=str(e))
            return [question]


# Singleton instance
_client: ClaudeClient | None = None


def get_claude_client() -> ClaudeClient:
    """Get or create Claude client instance."""
    global _client
    if _client is None:
        _client = ClaudeClient()
    return _client
