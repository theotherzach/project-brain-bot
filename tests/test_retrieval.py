"""Tests for RAG retrieval."""

from unittest.mock import MagicMock, patch

import pytest


class TestEmbeddings:
    """Tests for embedding generation."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        with patch("openai.OpenAI") as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    def test_embed_text_success(self, mock_env_vars, mock_openai_client):
        """Test successful text embedding."""
        mock_response = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 1536
        mock_response.data = [mock_embedding]
        mock_response.usage = MagicMock(total_tokens=10)
        mock_openai_client.embeddings.create.return_value = mock_response

        from src.retrieval.embeddings import EmbeddingClient

        client = EmbeddingClient()
        result = client.embed_text("Test text")

        assert len(result) == 1536
        assert all(isinstance(v, float) for v in result)

    def test_embed_text_empty(self, mock_env_vars, mock_openai_client):
        """Test embedding empty text returns zero vector."""
        from src.retrieval.embeddings import EmbeddingClient

        client = EmbeddingClient()
        result = client.embed_text("")

        assert len(result) == 1536
        assert all(v == 0.0 for v in result)

    def test_embed_batch(self, mock_env_vars, mock_openai_client):
        """Test batch embedding."""
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * 1536),
            MagicMock(embedding=[0.2] * 1536),
        ]
        mock_response.usage = MagicMock(total_tokens=20)
        mock_openai_client.embeddings.create.return_value = mock_response

        from src.retrieval.embeddings import EmbeddingClient

        client = EmbeddingClient()
        result = client.embed_batch(["Text 1", "Text 2"])

        assert len(result) == 2
        assert all(len(emb) == 1536 for emb in result)


class TestVectorStore:
    """Tests for vector store operations."""

    @pytest.fixture
    def mock_pinecone_client(self):
        """Create a mock Pinecone client."""
        with patch("pinecone.Pinecone") as mock:
            pc = MagicMock()
            mock.return_value = pc
            pc.list_indexes.return_value = [MagicMock(name="project-brain")]
            yield pc

    @patch("src.retrieval.vectorstore.get_embedding_client")
    def test_query_filters_by_threshold(
        self, mock_get_embedding, mock_env_vars, mock_pinecone_client
    ):
        """Test that query filters results below similarity threshold."""
        # Mock embedding client
        mock_embed_client = MagicMock()
        mock_embed_client.embed_text.return_value = [0.1] * 1536
        mock_get_embedding.return_value = mock_embed_client

        mock_index = MagicMock()
        mock_pinecone_client.Index.return_value = mock_index

        # Create matches with different scores
        high_score_match = MagicMock()
        high_score_match.id = "doc-1"
        high_score_match.score = 0.9
        high_score_match.metadata = {"text": "High score"}

        low_score_match = MagicMock()
        low_score_match.id = "doc-2"
        low_score_match.score = 0.5  # Below default threshold of 0.7
        low_score_match.metadata = {"text": "Low score"}

        mock_results = MagicMock()
        mock_results.matches = [high_score_match, low_score_match]
        mock_index.query.return_value = mock_results

        from src.retrieval.vectorstore import VectorStore

        store = VectorStore()
        results = store.query("test query")

        # Should only return high score match
        assert len(results) == 1
        assert results[0]["id"] == "doc-1"


class TestChunking:
    """Tests for document chunking."""

    def test_chunk_small_document(self, mock_env_vars):
        """Test that small documents are not chunked."""
        from src.sync.chunking import DocumentChunker

        chunker = DocumentChunker()
        chunks = chunker.chunk_document(
            doc_id="test-1",
            text="Short text",
            source="linear",
            title="Test Document",
        )

        assert len(chunks) == 1
        assert chunks[0].text == "Short text"

    def test_chunk_large_document(self, mock_env_vars):
        """Test that large documents are split into chunks."""
        from src.sync.chunking import DocumentChunker

        chunker = DocumentChunker()
        # Create a long document (500 sentences = ~3000 words)
        long_text = " ".join(["This is a test sentence."] * 500)

        chunks = chunker.chunk_document(
            doc_id="test-1",
            text=long_text,
            source="notion",
            title="Long Document",
        )

        assert len(chunks) > 1
        # All chunks should have the same doc_id prefix
        assert all(c.id.startswith("test-1") for c in chunks)
        # Check chunk indices
        assert chunks[0].chunk_index == 0
        assert chunks[-1].chunk_index == len(chunks) - 1

    def test_chunk_metadata_preserved(self, mock_env_vars):
        """Test that metadata is preserved in chunks."""
        from src.sync.chunking import DocumentChunker

        chunker = DocumentChunker()
        chunks = chunker.chunk_document(
            doc_id="test-1",
            text="Test content",
            source="github",
            title="Test Title",
            url="https://example.com",
            metadata={"custom": "value"},
        )

        assert chunks[0].source == "github"
        assert chunks[0].title == "Test Title"
        assert chunks[0].url == "https://example.com"
        assert chunks[0].metadata == {"custom": "value"}
