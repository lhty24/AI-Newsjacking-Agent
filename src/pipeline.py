import logging
import time
from datetime import datetime, timezone

from src.models.content import ContentVariant
from src.models.distribution import DistributionRecord
from src.models.pipeline import PipelineRun
from src.modules.analysis import analyze_news_batch
from src.modules.distribution import post_tweet
from src.modules.generation import generate_variants
from src.modules.ingestion import fetch_news
from src.modules.scoring import score_variants, select_top_n

logger = logging.getLogger(__name__)


def run_pipeline(
    trigger: str = "cli",
) -> tuple[PipelineRun, list[ContentVariant], list[DistributionRecord]]:
    """Orchestrate the full newsjacking pipeline.

    Returns the PipelineRun record, top-scoring content variants, and distribution records.
    """
    run = PipelineRun(trigger=trigger)
    logger.info("Pipeline run %s started (trigger: %s)", run.id[:8], trigger)
    pipeline_start = time.time()

    try:
        # --- Ingestion ---
        t0 = time.time()
        news_items = fetch_news()
        logger.info("Ingestion: fetched %d articles (%.1fs)", len(news_items), time.time() - t0)
        for i, item in enumerate(news_items, 1):
            tickers_str = ", ".join(item.tickers) if item.tickers else "none"
            logger.info("  Article %d/%d: \"%s\" [%s] (%s)", i, len(news_items), item.title, tickers_str, item.source)

        if not news_items:
            logger.warning("No news articles fetched, ending run early")
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            return run, [], []

        # --- Analysis ---
        t0 = time.time()
        analyses = analyze_news_batch(news_items)
        analysis_failures = len(news_items) - len(analyses)
        if analysis_failures > 0:
            run.stage_errors["analysis"] = analysis_failures
        logger.info("Analysis: processed %d/%d articles (%.1fs)", len(analyses), len(news_items), time.time() - t0)

        # Build news lookup for logging
        news_by_id = {item.id: item for item in news_items}

        if not analyses:
            logger.warning("No analyses produced, ending run early")
            run.news_count = len(news_items)
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            return run, [], []

        # --- Generation + Per-analysis Scoring ---
        t0 = time.time()
        total_generated = 0
        generation_failures = 0
        scoring_failures = 0
        top_variants: list[ContentVariant] = []
        for idx, analysis in enumerate(analyses, 1):
            news_item = news_by_id.get(analysis.news_item_id)
            title = news_item.title if news_item else "unknown"
            logger.info("--- Article %d/%d: \"%s\" ---", idx, len(analyses), title)
            logger.info("  Analysis: %s | topics=%s | signal=%s", analysis.sentiment, analysis.topics, analysis.signal)

            variants = generate_variants(analysis)
            total_generated += len(variants)
            # Track generation failures (expected 3 styles per analysis)
            expected_styles = 3
            if len(variants) < expected_styles:
                generation_failures += expected_styles - len(variants)
            for v in variants:
                text_preview = v.text[:80] + "..." if len(v.text) > 80 else v.text
                logger.info("  Variant [%s]: \"%s\"", v.style, text_preview)

            if not variants:
                continue
            try:
                scored = score_variants(variants)
                best = select_top_n(scored, 1)[0]
            except Exception:
                logger.warning("  Scoring failed, keeping first variant")
                scoring_failures += 1
                best = variants[0]
            top_variants.append(best)

            score_str = f"{best.score:.1f}" if best.score is not None else "N/A"
            scored_count = sum(1 for v in variants if v.score is not None)
            logger.info("  Scoring: %d/%d scored | Best: [%s] score=%s", scored_count, len(variants), best.style, score_str)

        top_score = max((v.score for v in top_variants if v.score is not None), default=0.0)
        logger.info(
            "Summary: %d variants from %d analyses, %d best picks, top score %.1f (%.1fs)",
            total_generated, len(analyses), len(top_variants), top_score, time.time() - t0,
        )

        # --- Distribution ---
        t0 = time.time()
        distribution_records: list[DistributionRecord] = []
        distribution_failures = 0
        for variant in top_variants:
            record = post_tweet(variant)
            distribution_records.append(record)
            if record.status == "posted":
                run.variants_posted += 1
            elif record.status == "failed":
                distribution_failures += 1
            score_str = f"{variant.score:.1f}" if variant.score is not None else "N/A"
            logger.info(
                "Distribution: variant %s [%s] score=%s → %s",
                variant.id[:8], variant.style, score_str, record.status,
            )
        if distribution_failures > 0:
            run.stage_errors["distribution"] = distribution_failures
        logger.info(
            "Distribution: %d/%d posted (%.1fs)",
            run.variants_posted, len(top_variants), time.time() - t0,
        )

        # --- Finalize ---
        if generation_failures > 0:
            run.stage_errors["generation"] = generation_failures
        if scoring_failures > 0:
            run.stage_errors["scoring"] = scoring_failures
        run.news_count = len(news_items)
        run.variants_generated = total_generated
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)

    except Exception as exc:
        logger.error("Pipeline run %s failed: %s", run.id[:8], exc, exc_info=True)
        run.status = "failed"
        run.error = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        return run, [], []

    total = time.time() - pipeline_start
    logger.info("Pipeline run %s completed (%.1fs)", run.id[:8], total)
    return run, top_variants, distribution_records
