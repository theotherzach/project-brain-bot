"""OpenAI embeddings for semantic search."""

import tiktoken
from openai import OpenAI

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmbeddingClient:
    """Client for generating text embeddings using OpenAI."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.model = self.settings.embedding_model
        # text-embedding-3-small has 1536 dimensions
        self.dimensions = 1536
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model)
        except KeyError:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        if not text.strip():
            logger.warning("empty_text_for_embedding")
            return [0.0] * self.dimensions

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            embedding = response.data[0].embedding
            logger.debug(
                "text_embedded",
                tokens=response.usage.total_tokens,
            )
            return embedding

        except Exception as e:
            logger.error("embedding_error", error=str(e))
            raise

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter empty texts
        valid_texts = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if not valid_texts:
            return [[0.0] * self.dimensions for _ in texts]

        try:
            indices, batch_texts = zip(*valid_texts)
            response = self.client.embeddings.create(
                model=self.model,
                input=list(batch_texts),
            )

            # Map embeddings back to original positions
            embeddings = [[0.0] * self.dimensions for _ in texts]
            for i, embedding_data in enumerate(response.data):
                original_idx = indices[i]
                embeddings[original_idx] = embedding_data.embedding

            logger.info(
                "batch_embedded",
                count=len(valid_texts),
                tokens=response.usage.total_tokens,
            )
            return embeddings

        except Exception as e:
            logger.error("batch_embedding_error", error=str(e))
            raise


# Singleton instance
_client: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    """Get or create embedding client instance."""
    global _client
    if _client is None:
        _client = EmbeddingClient()
    return _client
