"""Main entry point for Project Brain Bot."""

import signal
import sys

from slack_bolt.adapter.socket_mode import SocketModeHandler

from src.bot.handlers import create_app
from src.config import get_settings
from src.sync.scheduler import start_scheduler, stop_scheduler
from src.utils.logging import configure_logging, get_logger


def main() -> None:
    """Start the Project Brain Bot."""
    # Configure logging
    configure_logging()
    logger = get_logger(__name__)

    logger.info("starting_project_brain_bot")

    # Load settings
    settings = get_settings()

    # Create Slack app
    app = create_app()

    # Start background sync scheduler
    logger.info("starting_sync_scheduler")
    start_scheduler()

    # Set up signal handlers for graceful shutdown
    def shutdown_handler(signum, frame):
        logger.info("shutdown_signal_received", signal=signum)
        stop_scheduler()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start the bot using Socket Mode
    logger.info("starting_slack_socket_mode")
    handler = SocketModeHandler(app, settings.slack_app_token)

    try:
        handler.start()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    finally:
        stop_scheduler()
        logger.info("bot_shutdown_complete")


if __name__ == "__main__":
    main()
