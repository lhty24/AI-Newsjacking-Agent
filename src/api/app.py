import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.models.content import ContentVariant
from src.models.distribution import DistributionRecord
from src.models.news import NewsItem
from src.models.pipeline import PipelineRun
from src.modules.ingestion import fetch_news
from src.pipeline import run_pipeline

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Newsjacking Agent")

# In-memory stores (cleared on restart, persistence deferred to P6-T3)
_runs: list[PipelineRun] = []
_variants: list[ContentVariant] = []


@app.get("/news")
def get_news() -> list[NewsItem]:
    """Fetch latest crypto news from CoinGecko."""
    return fetch_news()


class RunResponse(BaseModel):
    run: PipelineRun
    top_variants: list[ContentVariant]


@app.post("/run")
def post_run() -> RunResponse:
    """Trigger a full pipeline run."""
    run, top_variants = run_pipeline(trigger="api")
    _runs.append(run)
    _variants.extend(top_variants)
    return RunResponse(run=run, top_variants=top_variants)


class PostRequest(BaseModel):
    variant_id: str


@app.post("/post")
def post_variant(req: PostRequest) -> DistributionRecord:
    """Post a specific content variant (stub until P4 wires up Twitter)."""
    variant = next((v for v in _variants if v.id == req.variant_id), None)
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
    known_ids = {v.id for v in _variants}
    results: list[DistributionRecord] = []
    for vid in req.variant_ids:
        if vid in known_ids:
            results.append(DistributionRecord(variant_id=vid, status="pending"))
        else:
            results.append(DistributionRecord(variant_id=vid, status="failed", error=f"Variant {vid} not found"))
    return BatchPostResponse(results=results)


@app.get("/runs")
def get_runs(limit: int = 10) -> list[PipelineRun]:
    """List recent pipeline runs, most recent first."""
    return list(reversed(_runs))[:limit]
