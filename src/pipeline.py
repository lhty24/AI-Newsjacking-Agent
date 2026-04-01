import logging
import time
from datetime import datetime, timezone

from src.models.content import ContentVariant
from src.models.pipeline import PipelineRun
from src.modules.analysis import analyze_news_batch
from src.modules.generation import generate_variants
from src.modules.ingestion import fetch_news
from src.modules.scoring import score_variants, select_top_n

logger = logging.getLogger(__name__)

TOP_N = 3


def run_pipeline(
    trigger: str = "cli",
) -> tuple[PipelineRun, list[ContentVariant]]:
    """Orchestrate the full newsjacking pipeline.

    Returns the PipelineRun record and the top-scoring content variants.
    """
    run = PipelineRun(trigger=trigger)
    logger.info("Pipeline run %s started (trigger: %s)", run.id[:8], trigger)
    pipeline_start = time.time()

    try:
        # --- Ingestion ---
        t0 = time.time()
        news_items = fetch_news()
        logger.info("Ingestion: fetched %d articles (%.1fs)", len(news_items), time.time() - t0)

        if not news_items:
            logger.warning("No news articles fetched, ending run early")
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            return run, []

        # --- Analysis ---
        t0 = time.time()
        analyses = analyze_news_batch(news_items)
        logger.info(
            "Analysis: processed %d/%d articles (%.1fs)",
            len(analyses), len(news_items), time.time() - t0,
        )

        if not analyses:
            logger.warning("No analyses produced, ending run early")
            run.news_count = len(news_items)
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            return run, []

        # --- Generation ---
        t0 = time.time()
        all_variants: list[ContentVariant] = []
        for analysis in analyses:
            variants = generate_variants(analysis)
            all_variants.extend(variants)
        logger.info(
            "Generation: created %d variants from %d analyses (%.1fs)",
            len(all_variants), len(analyses), time.time() - t0,
        )

        # --- Scoring ---
        t0 = time.time()
        try:
            scored = score_variants(all_variants)
            top_variants = select_top_n(scored, TOP_N)
        except Exception:
            logger.warning("Scoring failed, falling back to random selection")
            top_variants = all_variants[:TOP_N]

        top_score = max((v.score for v in top_variants if v.score is not None), default=0.0)
        logger.info(
            "Scoring: scored %d variants, top score %.1f (%.1fs)",
            len(all_variants), top_score, time.time() - t0,
        )

        # --- Finalize ---
        run.news_count = len(news_items)
        run.variants_generated = len(all_variants)
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)

    except Exception as exc:
        logger.error("Pipeline run %s failed: %s", run.id[:8], exc, exc_info=True)
        run.status = "failed"
        run.error = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        return run, []

    total = time.time() - pipeline_start
    logger.info("Pipeline run %s completed (%.1fs)", run.id[:8], total)
    return run, top_variants
