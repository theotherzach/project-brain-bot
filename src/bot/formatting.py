"""Message formatting utilities for Slack."""

import re
from typing import Any


def format_response_blocks(
    answer: str,
    sources: list[str] | None = None,
    context_count: int = 0,
) -> list[dict[str, Any]]:
    """
    Format a response into Slack Block Kit format.

    Args:
        answer: The answer text
        sources: List of source URLs
        context_count: Number of context documents used

    Returns:
        List of Slack blocks
    """
    blocks: list[dict[str, Any]] = []

    # Main answer section
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": answer,
        },
    })

    # Add sources if available
    if sources:
        blocks.append({"type": "divider"})

        source_links = []
        for i, url in enumerate(sources[:5], 1):
            # Extract a readable name from URL
            name = _extract_source_name(url)
            source_links.append(f"{i}. <{url}|{name}>")

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*Sources:*\n" + "\n".join(source_links),
                }
            ],
        })

    # Add context info
    if context_count > 0:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Based on {context_count} document(s) from project sources_",
                }
            ],
        })

    return blocks


def _extract_source_name(url: str) -> str:
    """Extract a readable name from a URL."""
    # Handle common URL patterns
    patterns = [
        (r"linear\.app/.*?/issue/([A-Z]+-\d+)", r"Linear \1"),
        (r"notion\.so/.*?([a-f0-9]{32})", "Notion page"),
        (r"github\.com/([^/]+/[^/]+)/(?:pull|issues)/(\d+)", r"GitHub \1#\2"),
        (r"github\.com/([^/]+/[^/]+)", r"GitHub \1"),
        (r"app\.datadoghq\.com/monitors/(\d+)", r"Datadog Monitor \1"),
    ]

    for pattern, replacement in patterns:
        match = re.search(pattern, url)
        if match:
            return re.sub(pattern, replacement, url)

    # Fallback: use domain name
    domain_match = re.search(r"https?://([^/]+)", url)
    if domain_match:
        return domain_match.group(1)

    return url[:50]


def format_error_message(error: str) -> list[dict[str, Any]]:
    """
    Format an error message for Slack.

    Args:
        error: Error description

    Returns:
        List of Slack blocks
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":warning: *Something went wrong*\n{error}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_Please try again or contact support if the issue persists._",
                }
            ],
        },
    ]


def format_thinking_message() -> list[dict[str, Any]]:
    """
    Format a "thinking" status message.

    Returns:
        List of Slack blocks
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":brain: *Thinking...*\n_Searching project context and generating response_",
            },
        },
    ]


def format_help_message() -> list[dict[str, Any]]:
    """
    Format a help message explaining bot capabilities.

    Returns:
        List of Slack blocks
    """
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Project Brain Bot Help",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "I'm *Project Brain*, your AI assistant for understanding project context. "
                    "I can help you find information across multiple sources:"
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Sources I search:*\n"
                    "• :ticket: *Linear* - Tasks, issues, and project status\n"
                    "• :notebook: *Notion* - Documentation, meeting notes, and specs\n"
                    "• :github: *GitHub* - PRs, issues, and code\n"
                    "• :chart_with_upwards_trend: *Mixpanel* - Analytics and user metrics\n"
                    "• :dog: *Datadog* - Monitoring alerts and incidents"
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*How to use:*\n"
                    "• @mention me with a question in any channel\n"
                    "• Send me a direct message\n"
                    "• Ask natural language questions about your project"
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Example questions:*\n"
                    "• \"What's the status of the auth refactor?\"\n"
                    "• \"Who's working on the payment integration?\"\n"
                    "• \"What did we decide in the last sprint planning?\"\n"
                    "• \"Are there any active alerts right now?\""
                ),
            },
        },
    ]


def truncate_text(text: str, max_length: int = 3000) -> str:
    """
    Truncate text to fit within Slack's limits.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - 3] + "..."
