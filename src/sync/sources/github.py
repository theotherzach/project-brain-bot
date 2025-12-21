"""GitHub sync to vector store."""

from src.context.github import get_github_client
from src.retrieval.vectorstore import get_vector_store
from src.sync.chunking import get_chunker
from src.utils.logging import get_logger

logger = get_logger(__name__)


def sync_github() -> int:
    """
    Sync GitHub PRs and issues to the vector store.

    Returns:
        Number of documents synced
    """
    logger.info("github_sync_started")

    try:
        github_client = get_github_client()
        vector_store = get_vector_store()
        chunker = get_chunker()

        # Clear old vectors for this source before syncing
        logger.info("github_clearing_old_vectors")
        vector_store.delete_by_source("github")

        # Fetch documents from all configured repos
        items = github_client.get_all_repo_documents()

        if not items:
            logger.info("github_sync_no_items")
            return 0

        # Chunk and prepare documents
        documents = []
        for item in items:
            chunks = chunker.chunk_document(
                doc_id=item.id,
                text=f"{item.title}\n\n{item.content}",
                source="github",
                title=item.title,
                url=item.url,
                metadata={
                    "source": "github",
                    "title": item.title,
                    "url": item.url,
                    **(item.metadata or {}),
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

        logger.info("github_sync_completed", documents=count)
        return count

    except Exception as e:
        logger.error("github_sync_error", error=str(e))
        return 0
