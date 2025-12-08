"""Linear sync to vector store."""

from src.context.linear import get_linear_client
from src.retrieval.vectorstore import get_vector_store
from src.sync.chunking import get_chunker
from src.utils.logging import get_logger

logger = get_logger(__name__)


def sync_linear() -> int:
    """
    Sync Linear issues to the vector store.

    Returns:
        Number of documents synced
    """
    logger.info("linear_sync_started")

    try:
        linear_client = get_linear_client()
        vector_store = get_vector_store()
        chunker = get_chunker()

        # Fetch recent issues
        issues = linear_client.get_recent_issues(limit=100)

        if not issues:
            logger.info("linear_sync_no_issues")
            return 0

        # Chunk and prepare documents
        documents = []
        for issue in issues:
            chunks = chunker.chunk_document(
                doc_id=issue.id,
                text=f"{issue.title}\n\n{issue.content}",
                source="linear",
                title=issue.title,
                url=issue.url,
                metadata={
                    "source": "linear",
                    "title": issue.title,
                    "url": issue.url,
                    **(issue.metadata or {}),
                },
            )

            for chunk in chunks:
                documents.append(
                    {
                        "id": chunk.id,
                        "text": chunk.text,
                        "metadata": {
                            "source": chunk.source,
                            "title": chunk.title,
                            "url": chunk.url,
                            "chunk_index": chunk.chunk_index,
                            "total_chunks": chunk.total_chunks,
                            **(chunk.metadata or {}),
                        },
                    }
                )

        # Upsert to vector store
        count = vector_store.upsert_documents(documents)

        logger.info("linear_sync_completed", documents=count)
        return count

    except Exception as e:
        logger.error("linear_sync_error", error=str(e))
        return 0
