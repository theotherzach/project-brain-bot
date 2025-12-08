"""RAG query logic for retrieving and formatting context."""

from typing import Any

from src.config import get_settings
from src.context import ContextDocument
from src.context.datadog import get_datadog_client
from src.context.github import get_github_client
from src.context.linear import get_linear_client
from src.context.mixpanel import get_mixpanel_client
from src.context.notion import get_notion_client
from src.llm.classifier import SourceType, get_classifier
from src.llm.client import get_claude_client
from src.retrieval.vectorstore import get_vector_store
from src.utils.cache import cached
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RAGQueryEngine:
    """Engine for RAG-based question answering."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.classifier = get_classifier()
        self.claude_client = get_claude_client()
        self.vector_store = get_vector_store()

    def _get_live_context(self, sources: list[SourceType], query: str) -> list[ContextDocument]:
        """
        Fetch live context from configured sources.

        Args:
            sources: List of source types to query
            query: Original user query for search

        Returns:
            List of context documents
        """
        documents: list[ContextDocument] = []

        for source in sources:
            try:
                if source == "linear":
                    client = get_linear_client()
                    docs = client.search_issues(query, limit=5)
                    if not docs:
                        docs = client.get_recent_issues(limit=10)
                    documents.extend(docs)

                elif source == "notion":
                    client = get_notion_client()
                    docs = client.search(query, limit=5)
                    documents.extend(docs)

                elif source == "github":
                    client = get_github_client()
                    docs = client.search_code(query, limit=5)
                    documents.extend(docs)

                elif source == "mixpanel":
                    client = get_mixpanel_client()
                    docs = client.get_analytics_summary()
                    documents.extend(docs)

                elif source == "datadog":
                    client = get_datadog_client()
                    docs = client.get_active_alerts()
                    documents.extend(docs)

            except Exception as e:
                logger.error("live_context_error", source=source, error=str(e))

        return documents

    def _format_context(self, documents: list[dict[str, Any]]) -> str:
        """
        Format retrieved documents into context string.

        Args:
            documents: List of document dicts from vector store

        Returns:
            Formatted context string
        """
        if not documents:
            return ""

        context_parts = []
        for i, doc in enumerate(documents, 1):
            metadata = doc.get("metadata", {})
            source = metadata.get("source", "unknown")
            title = metadata.get("title", "Untitled")
            text = metadata.get("text", "")
            url = metadata.get("url", "")

            part = f"[{i}] [{source.upper()}] {title}"
            if url:
                part += f"\nURL: {url}"
            part += f"\n{text[:2000]}"  # Limit text length

            context_parts.append(part)

        return "\n\n---\n\n".join(context_parts)

    @cached(prefix="rag_query", ttl_seconds=60)
    def query(self, question: str, use_live_context: bool = True) -> dict[str, Any]:
        """
        Process a question using RAG.

        Args:
            question: User's question
            use_live_context: Whether to fetch live data from sources

        Returns:
            Dict with 'answer', 'sources', and 'context_documents'
        """
        logger.info("rag_query_started", question=question[:100])

        # 1. Classify the question to determine relevant sources
        sources = self.classifier.classify(question)
        logger.info("question_classified", sources=sources)

        # 2. Generate search queries
        search_queries = self.claude_client.generate_search_queries(question)

        # 3. Query vector store for each search query
        all_results: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for query in search_queries:
            # Build source filter
            source_filter = {"source": {"$in": sources}} if sources else None

            results = self.vector_store.query(
                query_text=query,
                top_k=self.settings.retrieval_top_k,
                filter_dict=source_filter,
            )

            for result in results:
                if result["id"] not in seen_ids:
                    seen_ids.add(result["id"])
                    all_results.append(result)

        # Sort by score and take top results
        all_results.sort(key=lambda x: x["score"], reverse=True)
        top_results = all_results[: self.settings.retrieval_top_k]

        # 4. Optionally fetch live context
        live_documents: list[ContextDocument] = []
        if use_live_context and len(top_results) < 3:
            live_documents = self._get_live_context(sources, question)

        # 5. Format context
        context = self._format_context(top_results)

        # Add live context if available
        if live_documents:
            live_context = "\n\n---\n\nLive Context:\n\n"
            live_context += "\n\n".join(doc.to_context_string() for doc in live_documents[:5])
            context += live_context

        # 6. Generate answer
        answer = self.claude_client.generate_response(question, context)

        # 7. Extract source URLs for citation
        source_urls = []
        for result in top_results:
            url = result.get("metadata", {}).get("url")
            if url:
                source_urls.append(url)

        for doc in live_documents:
            if doc.url and doc.url not in source_urls:
                source_urls.append(doc.url)

        logger.info(
            "rag_query_completed",
            context_docs=len(top_results),
            live_docs=len(live_documents),
        )

        return {
            "answer": answer,
            "sources": source_urls[:10],
            "context_documents": len(top_results) + len(live_documents),
            "classified_sources": sources,
        }


# Singleton instance
_engine: RAGQueryEngine | None = None


def get_rag_engine() -> RAGQueryEngine:
    """Get or create RAG query engine instance."""
    global _engine
    if _engine is None:
        _engine = RAGQueryEngine()
    return _engine
