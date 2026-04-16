import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.config import ALLOWED_CHAR_LIMITS, SCHEDULER_ENABLED, SCHEDULER_INTERVAL_HOURS, validate_config
from src.models.content import ContentVariant
from src.models.distribution import DistributionRecord
from src.models.news import NewsItem
from src.models.pipeline import PipelineRun
from src.modules.distribution import post_tweet
from src.modules.ingestion import fetch_news
from src.pipeline import run_pipeline
from src.scheduler import (
    ALLOWED_ARTICLE_COUNTS,
    ALLOWED_INTERVALS,
    get_scheduler_status,
    init_scheduler,
    shutdown_scheduler,
    start_scheduler,
    stop_scheduler,
    update_interval,
    update_max_articles,
    update_max_chars,
)

logger = logging.getLogger(__name__)


def _scheduler_pipeline_callback() -> None:
    """Callback invoked by APScheduler to run the pipeline."""
    status = get_scheduler_status()
    run = PipelineRun(trigger="scheduler", max_chars=status["max_chars"])
    _runs[run.id] = run
    _variants[run.id] = []
    _execute_pipeline(run.id, max_articles=status["max_articles"], max_chars=status["max_chars"], trigger="scheduler")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration and initialize scheduler on startup."""
    validate_config()
    logger.info("Configuration validated, starting API server")
    init_scheduler(_scheduler_pipeline_callback, SCHEDULER_INTERVAL_HOURS)
    if SCHEDULER_ENABLED:
        start_scheduler()
        logger.info("Scheduler auto-started (interval: %dh)", SCHEDULER_INTERVAL_HOURS)
    yield
    shutdown_scheduler()


app = FastAPI(title="AI Newsjacking Agent", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions."""
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# In-memory stores keyed by run ID (cleared on restart, persistence deferred to P6-T3)
_runs: dict[str, PipelineRun] = {}
_variants: dict[str, list[ContentVariant]] = {}
_distributions: dict[str, DistributionRecord] = {}  # keyed by variant_id


def _all_variants() -> list[ContentVariant]:
    """Flatten all stored variants into a single list."""
    return [v for vs in _variants.values() for v in vs]


def _execute_pipeline(run_id: str, max_articles: int = 3, max_chars: int = 280, trigger: str = "api") -> None:
    """Background task: run the pipeline and update the stored run/variants."""
    try:
        run, top_variants, dist_records = run_pipeline(trigger=trigger, max_articles=max_articles, max_chars=max_chars)
        # Copy results into the pre-created run entry
        stored = _runs[run_id]
        stored.status = run.status
        stored.news_count = run.news_count
        stored.variants_generated = run.variants_generated
        stored.variants_posted = run.variants_posted
        stored.max_chars = run.max_chars
        stored.completed_at = run.completed_at
        stored.error = run.error
        _variants[run_id] = top_variants
        for record in dist_records:
            _distributions[record.variant_id] = record
    except Exception as exc:
        logger.error("Background pipeline run %s failed: %s", run_id[:8], exc, exc_info=True)
        stored = _runs[run_id]
        stored.status = "failed"
        stored.error = str(exc)
        stored.completed_at = datetime.now(timezone.utc)


# --- Endpoints ---


@app.get("/news")
def get_news() -> list[NewsItem]:
    """Fetch latest crypto news from CoinGecko."""
    return fetch_news()


class RunRequest(BaseModel):
    max_articles: int = 3
    max_chars: int = 280


class RunResponse(BaseModel):
    run: PipelineRun
    top_variants: list[ContentVariant]


@app.post("/run")
def post_run(background_tasks: BackgroundTasks, body: RunRequest = RunRequest()) -> RunResponse:
    """Trigger a full pipeline run (executes in the background)."""
    run = PipelineRun(trigger="api", max_chars=body.max_chars)
    _runs[run.id] = run
    _variants[run.id] = []
    background_tasks.add_task(_execute_pipeline, run.id, body.max_articles, body.max_chars)
    return RunResponse(run=run, top_variants=[])


@app.get("/runs")
def get_runs(limit: int = 10) -> list[PipelineRun]:
    """List recent pipeline runs, most recent first."""
    return list(reversed(_runs.values()))[:limit]


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> RunResponse:
    """Get a specific pipeline run and its variants."""
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return RunResponse(run=run, top_variants=_variants.get(run_id, []))


@app.get("/variants")
def get_variants(run_id: str | None = None, limit: int = 50) -> list[ContentVariant]:
    """List content variants, optionally filtered by run ID."""
    if run_id is not None:
        if run_id not in _runs:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return _variants.get(run_id, [])[:limit]
    return _all_variants()[:limit]


class PostRequest(BaseModel):
    variant_id: str


@app.post("/post")
def post_variant(req: PostRequest) -> DistributionRecord:
    """Post a specific content variant to Twitter/X."""
    variant = next((v for v in _all_variants() if v.id == req.variant_id), None)
    if variant is None:
        raise HTTPException(status_code=404, detail=f"Variant {req.variant_id} not found")
    record = post_tweet(variant)
    _distributions[record.variant_id] = record
    return record


class BatchPostRequest(BaseModel):
    variant_ids: list[str]


class BatchPostResponse(BaseModel):
    results: list[DistributionRecord]


@app.post("/post/batch")
def post_variants_batch(req: BatchPostRequest) -> BatchPostResponse:
    """Post multiple content variants at once. Missing IDs get status='failed'."""
    variants_by_id = {v.id: v for v in _all_variants()}
    results: list[DistributionRecord] = []
    for vid in req.variant_ids:
        variant = variants_by_id.get(vid)
        if variant is not None:
            record = post_tweet(variant)
            _distributions[record.variant_id] = record
            results.append(record)
        else:
            results.append(DistributionRecord(variant_id=vid, status="failed", error=f"Variant {vid} not found"))
    return BatchPostResponse(results=results)


# --- Scheduler Endpoints ---


class SchedulerStatus(BaseModel):
    running: bool
    interval_hours: int
    max_articles: int
    max_chars: int
    next_run_time: str | None


class IntervalRequest(BaseModel):
    interval_hours: int


@app.get("/scheduler/status")
def get_scheduler() -> SchedulerStatus:
    """Return current scheduler state."""
    return SchedulerStatus(**get_scheduler_status())


@app.post("/scheduler/start")
def post_scheduler_start() -> SchedulerStatus:
    """Start the scheduler."""
    start_scheduler()
    return SchedulerStatus(**get_scheduler_status())


@app.post("/scheduler/stop")
def post_scheduler_stop() -> SchedulerStatus:
    """Stop the scheduler."""
    stop_scheduler()
    return SchedulerStatus(**get_scheduler_status())


class MaxArticlesRequest(BaseModel):
    max_articles: int


@app.post("/scheduler/max-articles")
def post_scheduler_max_articles(req: MaxArticlesRequest) -> SchedulerStatus:
    """Update the number of articles the scheduler processes per run."""
    if req.max_articles not in ALLOWED_ARTICLE_COUNTS:
        raise HTTPException(
            status_code=422,
            detail=f"max_articles must be one of {ALLOWED_ARTICLE_COUNTS}",
        )
    update_max_articles(req.max_articles)
    return SchedulerStatus(**get_scheduler_status())


class MaxCharsRequest(BaseModel):
    max_chars: int


@app.post("/scheduler/max-chars")
def post_scheduler_max_chars(req: MaxCharsRequest) -> SchedulerStatus:
    """Update the max character limit for scheduled pipeline runs."""
    if req.max_chars not in ALLOWED_CHAR_LIMITS:
        raise HTTPException(
            status_code=422,
            detail=f"max_chars must be one of {ALLOWED_CHAR_LIMITS}",
        )
    update_max_chars(req.max_chars)
    return SchedulerStatus(**get_scheduler_status())


@app.post("/scheduler/interval")
def post_scheduler_interval(req: IntervalRequest) -> SchedulerStatus:
    """Update the scheduler interval. Must be one of [1, 3, 8, 12, 24]."""
    if req.interval_hours not in ALLOWED_INTERVALS:
        raise HTTPException(
            status_code=422,
            detail=f"interval_hours must be one of {ALLOWED_INTERVALS}",
        )
    update_interval(req.interval_hours)
    return SchedulerStatus(**get_scheduler_status())
