"""Tests for Slack event handlers."""

from unittest.mock import MagicMock, patch


class TestSlackHandlers:
    """Tests for Slack bot handlers."""

    def test_extract_question_removes_mention(self, mock_env_vars):
        """Test that @mentions are removed from questions."""
        from src.bot.handlers import _extract_question

        text = "<@U12345678> What is the status of the project?"
        result = _extract_question(text)
        assert result == "What is the status of the project?"

    def test_extract_question_handles_multiple_mentions(self, mock_env_vars):
        """Test handling of multiple mentions."""
        from src.bot.handlers import _extract_question

        text = "<@U12345678> <@U87654321> Hello"
        result = _extract_question(text)
        assert result == "Hello"

    def test_extract_question_handles_empty_text(self, mock_env_vars):
        """Test handling of empty text after mention removal."""
        from src.bot.handlers import _extract_question

        text = "<@U12345678>"
        result = _extract_question(text)
        assert result == ""

    @patch("src.bot.handlers.get_rag_engine")
    def test_process_question_success(self, mock_get_rag, mock_env_vars):
        """Test successful question processing."""
        from src.bot.handlers import _process_question

        # Mock RAG engine
        mock_engine = MagicMock()
        mock_engine.query.return_value = {
            "answer": "Test answer",
            "sources": ["https://example.com"],
            "context_documents": 3,
            "classified_sources": ["linear", "notion"],
        }
        mock_get_rag.return_value = mock_engine

        # Mock Slack client
        mock_client = MagicMock()

        _process_question(
            question="What is the status?",
            channel="C12345",
            thread_ts="123.456",
            client=mock_client,
            thinking_ts="789.012",
        )

        # Verify RAG engine was called
        mock_engine.query.assert_called_once_with("What is the status?")

        # Verify Slack client was called to update message
        mock_client.chat_update.assert_called_once()

    @patch("src.bot.handlers.get_rag_engine")
    def test_process_question_handles_error(self, mock_get_rag, mock_env_vars):
        """Test error handling in question processing."""
        from src.bot.handlers import _process_question

        # Mock RAG engine to raise an error
        mock_engine = MagicMock()
        mock_engine.query.side_effect = Exception("Test error")
        mock_get_rag.return_value = mock_engine

        # Mock Slack client
        mock_client = MagicMock()

        _process_question(
            question="What is the status?",
            channel="C12345",
            thread_ts="123.456",
            client=mock_client,
            thinking_ts="789.012",
        )

        # Verify error message was sent
        mock_client.chat_update.assert_called_once()
        call_kwargs = mock_client.chat_update.call_args[1]
        assert "blocks" in call_kwargs


class TestFormatting:
    """Tests for message formatting."""

    def test_format_response_blocks_basic(self, mock_env_vars):
        """Test basic response formatting."""
        from src.bot.formatting import format_response_blocks

        blocks = format_response_blocks("Test answer")
        assert len(blocks) >= 1
        assert blocks[0]["type"] == "section"
        assert "Test answer" in blocks[0]["text"]["text"]

    def test_format_response_blocks_with_sources(self, mock_env_vars):
        """Test response formatting with sources."""
        from src.bot.formatting import format_response_blocks

        blocks = format_response_blocks(
            "Test answer",
            sources=["https://linear.app/team/issue/TEST-123"],
            context_count=3,
        )

        # Should have divider and context blocks
        assert len(blocks) >= 3
        assert any(b["type"] == "divider" for b in blocks)

    def test_format_error_message(self, mock_env_vars):
        """Test error message formatting."""
        from src.bot.formatting import format_error_message

        blocks = format_error_message("Something went wrong")
        assert len(blocks) >= 1
        assert ":warning:" in blocks[0]["text"]["text"]

    def test_truncate_text_short(self, mock_env_vars):
        """Test that short text is not truncated."""
        from src.bot.formatting import truncate_text

        text = "Short text"
        result = truncate_text(text, max_length=100)
        assert result == text

    def test_truncate_text_long(self, mock_env_vars):
        """Test that long text is truncated with ellipsis."""
        from src.bot.formatting import truncate_text

        text = "A" * 200
        result = truncate_text(text, max_length=100)
        assert len(result) == 100
        assert result.endswith("...")
