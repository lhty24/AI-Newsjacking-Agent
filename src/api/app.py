import logging
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from src.models.content import ContentVariant
from src.models.distribution import DistributionRecord
from src.models.news import NewsItem
from src.models.pipeline import PipelineRun
from src.modules.ingestion import fetch_news
from src.pipeline import run_pipeline

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Newsjacking Agent")

# In-memory stores keyed by run ID (cleared on restart, persistence deferred to P6-T3)
_runs: dict[str, PipelineRun] = {}
_variants: dict[str, list[ContentVariant]] = {}


def _all_variants() -> list[ContentVariant]:
    """Flatten all stored variants into a single list."""
    return [v for vs in _variants.values() for v in vs]


def _execute_pipeline(run_id: str) -> None:
    """Background task: run the pipeline and update the stored run/variants."""
    try:
        run, top_variants = run_pipeline(trigger="api")
        # Copy results into the pre-created run entry
        stored = _runs[run_id]
        stored.status = run.status
        stored.news_count = run.news_count
        stored.variants_generated = run.variants_generated
        stored.completed_at = run.completed_at
        stored.error = run.error
        _variants[run_id] = top_variants
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


class RunResponse(BaseModel):
    run: PipelineRun
    top_variants: list[ContentVariant]


@app.post("/run")
def post_run(background_tasks: BackgroundTasks) -> RunResponse:
    """Trigger a full pipeline run (executes in the background)."""
    run = PipelineRun(trigger="api")
    _runs[run.id] = run
    _variants[run.id] = []
    background_tasks.add_task(_execute_pipeline, run.id)
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
    """Post a specific content variant (stub until P4 wires up Twitter)."""
    variant = next((v for v in _all_variants() if v.id == req.variant_id), None)
    if variant is None:
        raise HTTPException(status_code=404, detail=f"Variant {req.variant_id} not found")
    return DistributionRecord(variant_id=req.variant_id, status="pending")


class BatchPostRequest(BaseModel):
    variant_ids: list[str]


class BatchPostResponse(BaseModel):
    results: list[DistributionRecord]


@app.post("/post/batch")
def post_variants_batch(req: BatchPostRequest) -> BatchPostResponse:
    """Post multiple content variants at once. Missing IDs get status='failed'."""
    known_ids = {v.id for v in _all_variants()}
    results: list[DistributionRecord] = []
    for vid in req.variant_ids:
        if vid in known_ids:
            results.append(DistributionRecord(variant_id=vid, status="pending"))
        else:
            results.append(DistributionRecord(variant_id=vid, status="failed", error=f"Variant {vid} not found"))
    return BatchPostResponse(results=results)
