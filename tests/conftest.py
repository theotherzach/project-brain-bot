"""Pytest configuration and fixtures."""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set up test environment variables."""
    env_vars = {
        "SLACK_BOT_TOKEN": "xoxb-test-token",
        "SLACK_APP_TOKEN": "xapp-test-token",
        "SLACK_SIGNING_SECRET": "test-signing-secret",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "OPENAI_API_KEY": "test-openai-key",
        "PINECONE_API_KEY": "test-pinecone-key",
        "PINECONE_INDEX_NAME": "test-index",
        "REDIS_URL": "redis://localhost:6379",
        "LINEAR_API_KEY": "test-linear-key",
        "NOTION_API_KEY": "test-notion-key",
        "GITHUB_TOKEN": "test-github-token",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def mock_anthropic():
    """Mock the Anthropic client."""
    with patch("anthropic.Anthropic") as mock:
        client = MagicMock()
        mock.return_value = client

        # Mock message creation
        message = MagicMock()
        message.content = [MagicMock(text="Test response")]
        message.usage = MagicMock(input_tokens=100, output_tokens=50)
        client.messages.create.return_value = message

        yield client


@pytest.fixture
def mock_openai():
    """Mock the OpenAI client."""
    with patch("openai.OpenAI") as mock:
        client = MagicMock()
        mock.return_value = client

        # Mock embedding creation
        embedding_response = MagicMock()
        embedding_data = MagicMock()
        embedding_data.embedding = [0.1] * 1536
        embedding_response.data = [embedding_data]
        embedding_response.usage = MagicMock(total_tokens=10)
        client.embeddings.create.return_value = embedding_response

        yield client


@pytest.fixture
def mock_pinecone():
    """Mock the Pinecone client."""
    with patch("pinecone.Pinecone") as mock:
        client = MagicMock()
        mock.return_value = client

        # Mock index operations
        index = MagicMock()
        client.Index.return_value = index
        client.list_indexes.return_value = [MagicMock(name="test-index")]

        # Mock query results
        match = MagicMock()
        match.id = "test-doc-1"
        match.score = 0.9
        match.metadata = {"text": "Test content", "source": "linear", "title": "Test"}
        query_result = MagicMock()
        query_result.matches = [match]
        index.query.return_value = query_result

        yield client


@pytest.fixture
def mock_redis():
    """Mock the Redis client."""
    with patch("redis.from_url") as mock:
        client = MagicMock()
        mock.return_value = client
        client.get.return_value = None  # Cache miss by default
        yield client


@pytest.fixture
def mock_httpx():
    """Mock httpx for API calls."""
    with patch("httpx.Client") as mock:
        client = MagicMock()
        mock.return_value.__enter__ = MagicMock(return_value=client)
        mock.return_value.__exit__ = MagicMock(return_value=False)
        yield client
