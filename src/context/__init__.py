"""Context provider modules for external data sources."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ContextDocument:
    """Represents a document retrieved from a context source."""

    id: str
    source: str  # e.g., "linear", "notion", "github"
    title: str
    content: str
    url: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "metadata": self.metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_context_string(self) -> str:
        """Format as context string for LLM."""
        parts = [f"[{self.source.upper()}] {self.title}"]
        if self.url:
            parts.append(f"URL: {self.url}")
        parts.append(self.content)
        return "\n".join(parts)
