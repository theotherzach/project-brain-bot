"""Tests for question classification."""

from unittest.mock import MagicMock, patch

import pytest


class TestQuestionClassifier:
    """Tests for the question classifier."""

    @patch("src.llm.classifier.anthropic.Anthropic")
    def test_classify_returns_valid_sources(self, mock_anthropic, mock_env_vars):
        """Test that classifier returns valid source types."""
        from src.llm.classifier import QuestionClassifier

        # Mock the API response
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        message = MagicMock()
        message.content = [MagicMock(text='{"sources": ["linear", "github"], "reasoning": "test"}')]
        mock_client.messages.create.return_value = message

        classifier = QuestionClassifier()
        result = classifier.classify("What is the status of the auth feature?")

        assert "linear" in result
        assert "github" in result
        assert len(result) == 2

    @patch("src.llm.classifier.anthropic.Anthropic")
    def test_classify_handles_invalid_json(self, mock_anthropic, mock_env_vars):
        """Test that classifier handles invalid JSON gracefully."""
        from src.llm.classifier import QuestionClassifier

        # Mock invalid JSON response
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        message = MagicMock()
        message.content = [MagicMock(text="invalid json")]
        mock_client.messages.create.return_value = message

        classifier = QuestionClassifier()
        result = classifier.classify("Test question")

        # Should return default fallback
        assert "notion" in result
        assert "linear" in result

    @patch("src.llm.classifier.anthropic.Anthropic")
    def test_classify_filters_invalid_sources(self, mock_anthropic, mock_env_vars):
        """Test that classifier filters out invalid source names."""
        from src.llm.classifier import QuestionClassifier

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        message = MagicMock()
        message.content = [
            MagicMock(text='{"sources": ["linear", "invalid_source", "notion"], "reasoning": "test"}')
        ]
        mock_client.messages.create.return_value = message

        classifier = QuestionClassifier()
        result = classifier.classify("Test question")

        assert "linear" in result
        assert "notion" in result
        assert "invalid_source" not in result

    @patch("src.llm.classifier.anthropic.Anthropic")
    def test_classify_handles_api_error(self, mock_anthropic, mock_env_vars):
        """Test that classifier handles API errors gracefully."""
        import anthropic

        from src.llm.classifier import QuestionClassifier

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="API Error",
            request=MagicMock(),
            body=None,
        )

        classifier = QuestionClassifier()
        result = classifier.classify("Test question")

        # Should return default fallback
        assert "notion" in result
        assert "linear" in result
