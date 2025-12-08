"""Tests for question classification."""

from unittest.mock import MagicMock, patch

import pytest


class TestQuestionClassifier:
    """Tests for the question classifier."""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Create a mock Anthropic client."""
        with patch("anthropic.Anthropic") as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    def test_classify_returns_valid_sources(self, mock_env_vars, mock_anthropic_client):
        """Test that classifier returns valid source types."""
        message = MagicMock()
        message.content = [MagicMock(text='{"sources": ["linear", "github"], "reasoning": "test"}')]
        mock_anthropic_client.messages.create.return_value = message

        from src.llm.classifier import QuestionClassifier

        classifier = QuestionClassifier()
        result = classifier.classify("What is the status of the auth feature?")

        assert "linear" in result
        assert "github" in result
        assert len(result) == 2

    def test_classify_handles_invalid_json(self, mock_env_vars, mock_anthropic_client):
        """Test that classifier handles invalid JSON gracefully."""
        message = MagicMock()
        message.content = [MagicMock(text="invalid json")]
        mock_anthropic_client.messages.create.return_value = message

        from src.llm.classifier import QuestionClassifier

        classifier = QuestionClassifier()
        result = classifier.classify("Test question")

        # Should return default fallback
        assert "notion" in result
        assert "linear" in result

    def test_classify_filters_invalid_sources(self, mock_env_vars, mock_anthropic_client):
        """Test that classifier filters out invalid source names."""
        message = MagicMock()
        message.content = [
            MagicMock(
                text='{"sources": ["linear", "invalid_source", "notion"], "reasoning": "test"}'
            )
        ]
        mock_anthropic_client.messages.create.return_value = message

        from src.llm.classifier import QuestionClassifier

        classifier = QuestionClassifier()
        result = classifier.classify("Test question")

        assert "linear" in result
        assert "notion" in result
        assert "invalid_source" not in result

    def test_classify_handles_api_error(self, mock_env_vars, mock_anthropic_client):
        """Test that classifier handles API errors gracefully."""
        import anthropic

        mock_anthropic_client.messages.create.side_effect = anthropic.APIError(
            message="API Error",
            request=MagicMock(),
            body=None,
        )

        from src.llm.classifier import QuestionClassifier

        classifier = QuestionClassifier()
        result = classifier.classify("Test question")

        # Should return default fallback
        assert "notion" in result
        assert "linear" in result
