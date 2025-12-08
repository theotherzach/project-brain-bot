"""Background sync scheduler using APScheduler."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import get_settings
from src.sync.sources.github import sync_github
from src.sync.sources.linear import sync_linear
from src.sync.sources.notion import sync_notion
from src.utils.logging import get_logger

logger = get_logger(__name__)

_scheduler: BackgroundScheduler | None = None


def run_full_sync() -> dict[str, int]:
    """
    Run a full sync of all sources.

    Returns:
        Dict mapping source names to document counts
    """
    logger.info("full_sync_started")

    results = {}

    # Sync each source
    results["linear"] = sync_linear()
    results["notion"] = sync_notion()
    results["github"] = sync_github()

    total = sum(results.values())
    logger.info("full_sync_completed", results=results, total=total)

    return results


def start_scheduler() -> BackgroundScheduler:
    """
    Start the background sync scheduler.

    Returns:
        The scheduler instance
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("scheduler_already_running")
        return _scheduler

    settings = get_settings()
    _scheduler = BackgroundScheduler()

    # Add sync job
    _scheduler.add_job(
        run_full_sync,
        trigger=IntervalTrigger(minutes=settings.sync_interval_minutes),
        id="full_sync",
        name="Full source sync",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "scheduler_started",
        interval_minutes=settings.sync_interval_minutes,
    )

    # Run initial sync
    logger.info("running_initial_sync")
    try:
        run_full_sync()
    except Exception as e:
        logger.error("initial_sync_error", error=str(e))

    return _scheduler


def stop_scheduler() -> None:
    """Stop the background sync scheduler."""
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("scheduler_stopped")


def get_scheduler() -> BackgroundScheduler | None:
    """Get the current scheduler instance."""
    return _scheduler
