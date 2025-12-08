"""Slack event handlers."""

import re

from slack_bolt import App
from slack_sdk.web import WebClient

from src.bot.formatting import (
    format_error_message,
    format_help_message,
    format_response_blocks,
    format_thinking_message,
    truncate_text,
)
from src.config import get_settings
from src.retrieval.query import get_rag_engine
from src.utils.logging import get_logger

logger = get_logger(__name__)


def create_app() -> App:
    """Create and configure the Slack Bolt app."""
    settings = get_settings()

    app = App(
        token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
    )

    # Register event handlers
    register_handlers(app)

    return app


def register_handlers(app: App) -> None:
    """Register all event handlers on the app."""

    @app.event("app_mention")
    def handle_mention(event: dict, client: WebClient, say) -> None:
        """Handle @mentions of the bot."""
        logger.info("app_mention_received", channel=event.get("channel"))

        try:
            # Extract the question (remove the mention)
            text = event.get("text", "")
            question = _extract_question(text)

            if not question or question.lower() in ("help", "?"):
                say(blocks=format_help_message())
                return

            # Send thinking message
            thinking_response = say(blocks=format_thinking_message())

            # Process the question
            _process_question(
                question=question,
                channel=event["channel"],
                thread_ts=event.get("thread_ts") or event.get("ts"),
                client=client,
                thinking_ts=thinking_response.get("ts"),
            )

        except Exception as e:
            logger.error("mention_handler_error", error=str(e))
            say(blocks=format_error_message("Failed to process your question."))

    @app.event("message")
    def handle_dm(event: dict, client: WebClient, say) -> None:
        """Handle direct messages to the bot."""
        # Ignore bot messages and messages in channels
        if event.get("bot_id") or event.get("channel_type") != "im":
            return

        logger.info("dm_received", user=event.get("user"))

        try:
            question = event.get("text", "").strip()

            if not question or question.lower() in ("help", "?"):
                say(blocks=format_help_message())
                return

            # Send thinking message
            thinking_response = say(blocks=format_thinking_message())

            # Process the question
            _process_question(
                question=question,
                channel=event["channel"],
                thread_ts=event.get("thread_ts") or event.get("ts"),
                client=client,
                thinking_ts=thinking_response.get("ts"),
            )

        except Exception as e:
            logger.error("dm_handler_error", error=str(e))
            say(blocks=format_error_message("Failed to process your question."))

    @app.command("/brain")
    def handle_slash_command(ack, command: dict, client: WebClient) -> None:
        """Handle /brain slash command."""
        ack()

        logger.info("slash_command_received", command=command.get("text"))

        try:
            question = command.get("text", "").strip()
            channel = command["channel_id"]
            user = command["user_id"]

            if not question or question.lower() in ("help", "?"):
                client.chat_postEphemeral(
                    channel=channel,
                    user=user,
                    blocks=format_help_message(),
                )
                return

            # Post thinking message (visible to everyone)
            thinking_response = client.chat_postMessage(
                channel=channel,
                blocks=format_thinking_message(),
            )

            # Process the question
            _process_question(
                question=question,
                channel=channel,
                thread_ts=None,
                client=client,
                thinking_ts=thinking_response.get("ts"),
            )

        except Exception as e:
            logger.error("slash_command_error", error=str(e))
            client.chat_postMessage(
                channel=command["channel_id"],
                blocks=format_error_message("Failed to process your question."),
            )


def _extract_question(text: str) -> str:
    """Extract the question from a mention message."""
    # Remove the @mention
    question = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    return question


def _process_question(
    question: str,
    channel: str,
    thread_ts: str | None,
    client: WebClient,
    thinking_ts: str | None = None,
) -> None:
    """
    Process a question and send the response.

    Args:
        question: The user's question
        channel: Slack channel ID
        thread_ts: Thread timestamp for replies
        client: Slack WebClient
        thinking_ts: Timestamp of thinking message to update
    """
    logger.info("processing_question", question=question[:100])

    try:
        # Get RAG engine and process query
        rag_engine = get_rag_engine()
        result = rag_engine.query(question)

        # Format response
        answer = truncate_text(result["answer"], max_length=3000)
        blocks = format_response_blocks(
            answer=answer,
            sources=result.get("sources"),
            context_count=result.get("context_documents", 0),
        )

        # Update or send response
        if thinking_ts:
            client.chat_update(
                channel=channel,
                ts=thinking_ts,
                blocks=blocks,
                text=answer,  # Fallback text
            )
        else:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                blocks=blocks,
                text=answer,
            )

        logger.info(
            "question_answered",
            sources=result.get("classified_sources"),
            context_docs=result.get("context_documents"),
        )

    except Exception as e:
        logger.error("question_processing_error", error=str(e))

        error_blocks = format_error_message(
            "I encountered an error while searching for context. Please try again."
        )

        if thinking_ts:
            client.chat_update(
                channel=channel,
                ts=thinking_ts,
                blocks=error_blocks,
                text="Error processing question",
            )
        else:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                blocks=error_blocks,
            )
