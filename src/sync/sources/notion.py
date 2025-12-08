"""Notion sync to vector store."""

from src.context.notion import get_notion_client
from src.retrieval.vectorstore import get_vector_store
from src.sync.chunking import get_chunker
from src.utils.logging import get_logger

logger = get_logger(__name__)


def sync_notion() -> int:
    """
    Sync Notion pages to the vector store.

    Returns:
        Number of documents synced
    """
    logger.info("notion_sync_started")

    try:
        notion_client = get_notion_client()
        vector_store = get_vector_store()
        chunker = get_chunker()

        # Fetch pages from all configured databases
        pages = notion_client.get_all_database_pages()

        if not pages:
            logger.info("notion_sync_no_pages")
            return 0

        # Chunk and prepare documents
        documents = []
        for page in pages:
            chunks = chunker.chunk_document(
                doc_id=page.id,
                text=f"{page.title}\n\n{page.content}",
                source="notion",
                title=page.title,
                url=page.url,
                metadata={
                    "source": "notion",
                    "title": page.title,
                    "url": page.url,
                    **(page.metadata or {}),
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

        logger.info("notion_sync_completed", documents=count)
        return count

    except Exception as e:
        logger.error("notion_sync_error", error=str(e))
        return 0
