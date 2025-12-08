"""Pytest configuration and fixtures."""

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
