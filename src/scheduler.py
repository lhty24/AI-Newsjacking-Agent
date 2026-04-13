import logging
from collections.abc import Callable
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_callback: Callable | None = None
_interval_hours: float = 12
_max_articles: int = 3
_JOB_ID = "pipeline_scheduled_run"

ALLOWED_INTERVALS = [1, 3, 8, 12, 24]
ALLOWED_ARTICLE_COUNTS = [1, 3, 5, 10]


def init_scheduler(callback: Callable, interval_hours: int = 12) -> None:
    """Create the scheduler and add the pipeline job (initially paused)."""
    global _scheduler, _callback, _interval_hours

    _callback = callback
    _interval_hours = interval_hours
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_job,
        trigger=IntervalTrigger(hours=interval_hours),
        id=_JOB_ID,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
        next_run_time=None,  # Start paused (no initial run scheduled)
    )
    _scheduler.start()
    logger.info("Scheduler initialized (interval: %dh, paused)", interval_hours)


def _run_job() -> None:
    """Internal wrapper that invokes the callback with error handling."""
    if _callback is None:
        logger.error("Scheduler callback not set")
        return
    try:
        logger.info("Scheduler triggering pipeline run")
        _callback()
    except Exception as exc:
        logger.error("Scheduled pipeline run failed: %s", exc, exc_info=True)


def start_scheduler() -> None:
    """Resume the scheduled job."""
    if _scheduler is None:
        logger.warning("Scheduler not initialized")
        return
    job = _scheduler.get_job(_JOB_ID)
    if job is None:
        return
    if job.next_run_time is None:
        # Job is paused — reschedule to start running
        job.modify(next_run_time=datetime.now(timezone.utc))
    logger.info("Scheduler started (interval: %dh)", _interval_hours)


def stop_scheduler() -> None:
    """Pause the scheduled job (does not shut down the scheduler)."""
    if _scheduler is None:
        return
    job = _scheduler.get_job(_JOB_ID)
    if job is not None and job.next_run_time is not None:
        job.modify(next_run_time=None)
    logger.info("Scheduler stopped")


def shutdown_scheduler() -> None:
    """Fully shut down the scheduler (call on app exit)."""
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")


def update_max_articles(max_articles: int) -> None:
    """Update the number of articles the scheduler processes per run."""
    global _max_articles
    _max_articles = max_articles
    logger.info("Scheduler max_articles updated to %d", max_articles)


def update_interval(interval_hours: int) -> None:
    """Reschedule the job with a new interval."""
    global _interval_hours

    if _scheduler is None:
        logger.warning("Scheduler not initialized")
        return
    _interval_hours = interval_hours
    job = _scheduler.get_job(_JOB_ID)
    if job is None:
        return
    was_running = job.next_run_time is not None
    _scheduler.reschedule_job(
        _JOB_ID,
        trigger=IntervalTrigger(hours=interval_hours),
    )
    if not was_running:
        # Rescheduling reactivates the job; pause it again if it was paused
        job = _scheduler.get_job(_JOB_ID)
        if job is not None:
            job.modify(next_run_time=None)
    logger.info("Scheduler interval updated to %dh", interval_hours)


def get_scheduler_status() -> dict:
    """Return current scheduler state."""
    if _scheduler is None:
        return {"running": False, "interval_hours": _interval_hours, "max_articles": _max_articles, "next_run_time": None}
    job = _scheduler.get_job(_JOB_ID)
    running = job is not None and job.next_run_time is not None
    next_run = None
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()
    return {
        "running": running,
        "interval_hours": _interval_hours,
        "max_articles": _max_articles,
        "next_run_time": next_run,
    }
