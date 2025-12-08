"""Pinecone vector store for document retrieval."""

import time
from functools import lru_cache
from typing import Any

from pinecone import Pinecone, ServerlessSpec

from src.config import get_settings
from src.retrieval.embeddings import get_embedding_client
from src.utils.logging import get_logger

logger = get_logger(__name__)


class VectorStore:
    """Pinecone vector store wrapper."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.pc = Pinecone(api_key=self.settings.pinecone_api_key)
        self.index_name = self.settings.pinecone_index_name
        self.namespace = self.settings.pinecone_namespace
        self._index = None

    @property
    def index(self):
        """Get or create the Pinecone index."""
        if self._index is None:
            # Check if index exists
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]

            if self.index_name not in existing_indexes:
                logger.info("creating_pinecone_index", name=self.index_name)
                self.pc.create_index(
                    name=self.index_name,
                    dimension=1536,  # text-embedding-3-small dimensions
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1",
                    ),
                )
                # Wait for index to be ready (async creation)
                for _ in range(60):  # Wait up to 60 seconds
                    desc = self.pc.describe_index(self.index_name)
                    if desc.status.ready:
                        break
                    logger.debug("waiting_for_index", name=self.index_name)
                    time.sleep(1)

            self._index = self.pc.Index(self.index_name)
        return self._index

    def upsert_documents(
        self,
        documents: list[dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """
        Upsert documents into the vector store.

        Args:
            documents: List of documents with 'id', 'text', 'metadata' keys
            batch_size: Number of documents to upsert per batch

        Returns:
            Number of documents upserted
        """
        if not documents:
            return 0

        embedding_client = get_embedding_client()

        # Generate embeddings for all documents
        texts = [doc["text"] for doc in documents]
        embeddings = embedding_client.embed_batch(texts)

        # Prepare vectors for upsert
        vectors = []
        for doc, embedding in zip(documents, embeddings, strict=True):
            vector = {
                "id": doc["id"],
                "values": embedding,
                "metadata": {
                    **doc.get("metadata", {}),
                    "text": doc["text"][:40000],  # Pinecone metadata limit
                },
            }
            vectors.append(vector)

        # Upsert in batches
        total_upserted = 0
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            self.index.upsert(vectors=batch, namespace=self.namespace)
            total_upserted += len(batch)
            logger.debug("vectors_upserted", count=len(batch), total=total_upserted)

        logger.info("documents_upserted", count=total_upserted)
        return total_upserted

    def query(
        self,
        query_text: str,
        top_k: int | None = None,
        filter_dict: dict | None = None,
        include_metadata: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Query the vector store for similar documents.

        Args:
            query_text: Query text
            top_k: Number of results to return
            filter_dict: Metadata filter
            include_metadata: Whether to include metadata in results

        Returns:
            List of matching documents with scores
        """
        if top_k is None:
            top_k = self.settings.retrieval_top_k

        embedding_client = get_embedding_client()
        query_embedding = embedding_client.embed_text(query_text)

        try:
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                namespace=self.namespace,
                filter=filter_dict,
                include_metadata=include_metadata,
            )

            documents = []
            for match in results.matches:
                if match.score >= self.settings.similarity_threshold:
                    doc = {
                        "id": match.id,
                        "score": match.score,
                        "metadata": match.metadata or {},
                    }
                    documents.append(doc)

            logger.info(
                "vector_query_completed",
                query_length=len(query_text),
                results=len(documents),
            )
            return documents

        except Exception as e:
            logger.error("vector_query_error", error=str(e))
            return []

    def delete_by_source(self, source: str) -> None:
        """
        Delete all vectors for a given source.

        Args:
            source: Source name (e.g., 'linear', 'notion')
        """
        try:
            # Pinecone requires deletion by ID or filter
            # For serverless, we need to fetch IDs first
            self.index.delete(
                filter={"source": {"$eq": source}},
                namespace=self.namespace,
            )
            logger.info("vectors_deleted_by_source", source=source)
        except Exception as e:
            logger.error("vector_delete_error", error=str(e), source=source)

    def delete_by_ids(self, ids: list[str]) -> None:
        """
        Delete vectors by their IDs.

        Args:
            ids: List of vector IDs to delete
        """
        if not ids:
            return

        try:
            self.index.delete(ids=ids, namespace=self.namespace)
            logger.info("vectors_deleted", count=len(ids))
        except Exception as e:
            logger.error("vector_delete_error", error=str(e))

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "namespaces": stats.namespaces,
            }
        except Exception as e:
            logger.error("stats_error", error=str(e))
            return {}


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    """Get or create vector store instance."""
    return VectorStore()
