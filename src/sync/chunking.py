"""Document chunking for embedding."""

from dataclasses import dataclass

import tiktoken

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    """A chunk of text with metadata."""

    id: str
    text: str
    source: str
    title: str
    url: str | None = None
    metadata: dict | None = None
    chunk_index: int = 0
    total_chunks: int = 1


class DocumentChunker:
    """Splits documents into chunks for embedding."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.chunk_size = self.settings.chunk_size
        self.chunk_overlap = self.settings.chunk_overlap
        try:
            self.tokenizer = tiktoken.encoding_for_model("text-embedding-3-small")
        except KeyError:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    def _split_text(self, text: str) -> list[str]:
        """
        Split text into chunks based on token count.

        Uses a simple sentence-based splitting strategy with overlap.
        """
        if not text:
            return []

        # If text is small enough, return as single chunk
        if self._count_tokens(text) <= self.chunk_size:
            return [text]

        chunks = []
        sentences = self._split_into_sentences(text)

        current_chunk: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)

            # If single sentence exceeds chunk size, split it further
            if sentence_tokens > self.chunk_size:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0

                # Split long sentence by words
                words = sentence.split()
                word_chunk: list[str] = []
                word_tokens = 0

                for word in words:
                    word_token_count = self._count_tokens(word + " ")
                    if word_tokens + word_token_count > self.chunk_size:
                        if word_chunk:
                            chunks.append(" ".join(word_chunk))
                        word_chunk = [word]
                        word_tokens = word_token_count
                    else:
                        word_chunk.append(word)
                        word_tokens += word_token_count

                if word_chunk:
                    current_chunk = word_chunk
                    current_tokens = word_tokens
                continue

            # Check if adding sentence exceeds chunk size
            if current_tokens + sentence_tokens > self.chunk_size:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))

                    # Keep overlap from end of current chunk
                    overlap_sentences: list[str] = []
                    overlap_tokens = 0
                    for s in reversed(current_chunk):
                        s_tokens = self._count_tokens(s)
                        if overlap_tokens + s_tokens > self.chunk_overlap:
                            break
                        overlap_sentences.insert(0, s)
                        overlap_tokens += s_tokens

                    current_chunk = overlap_sentences + [sentence]
                    current_tokens = overlap_tokens + sentence_tokens
                else:
                    current_chunk = [sentence]
                    current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting - handles common cases
        import re

        # Split on sentence-ending punctuation followed by space or newline
        sentences = re.split(r"(?<=[.!?])\s+", text)

        # Also split on double newlines (paragraph breaks)
        result = []
        for sentence in sentences:
            parts = sentence.split("\n\n")
            result.extend([p.strip() for p in parts if p.strip()])

        return result

    def chunk_document(
        self,
        doc_id: str,
        text: str,
        source: str,
        title: str,
        url: str | None = None,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        Chunk a document into smaller pieces for embedding.

        Args:
            doc_id: Unique document identifier
            text: Document text
            source: Source name (e.g., 'linear', 'notion')
            title: Document title
            url: Optional URL
            metadata: Optional additional metadata

        Returns:
            List of Chunk objects
        """
        text_chunks = self._split_text(text)

        if not text_chunks:
            return []

        chunks = []
        for i, chunk_text in enumerate(text_chunks):
            chunk = Chunk(
                id=f"{doc_id}-chunk-{i}",
                text=chunk_text,
                source=source,
                title=title,
                url=url,
                metadata=metadata,
                chunk_index=i,
                total_chunks=len(text_chunks),
            )
            chunks.append(chunk)

        logger.debug(
            "document_chunked",
            doc_id=doc_id,
            chunks=len(chunks),
            total_tokens=sum(self._count_tokens(c.text) for c in chunks),
        )

        return chunks


# Singleton instance
_chunker: DocumentChunker | None = None


def get_chunker() -> DocumentChunker:
    """Get or create document chunker instance."""
    global _chunker
    if _chunker is None:
        _chunker = DocumentChunker()
    return _chunker
