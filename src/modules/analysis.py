import json
import logging

import litellm
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from src.config import LLM_API_KEY, LLM_MAX_TOKENS, LLM_MODEL, LLM_TEMPERATURE
from src.models.analysis import AnalysisResult
from src.models.news import NewsItem

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a crypto market analyst. Analyze the provided news article and return a JSON object with exactly these fields:

- "sentiment": one of "bullish", "bearish", or "neutral"
- "topics": a list of 2-5 short topic tags (e.g., "BTC", "ETF", "regulation", "DeFi", "staking")
- "summary": a 1-2 sentence summary of the news and its market implications
- "signal": a short trading signal phrase (e.g., "breakout potential", "sell pressure", "accumulation zone", "regulatory headwind")

Respond ONLY with valid JSON. No markdown, no explanation, no extra text."""


def _build_user_prompt(item: NewsItem) -> str:
    """Format a NewsItem into the user prompt for the LLM."""
    tickers = ", ".join(item.tickers) or "None identified"
    return (
        f"Title: {item.title}\n"
        f"Source: {item.source}\n"
        f"Published: {item.published_at.isoformat()}\n"
        f"Tickers: {tickers}\n"
        f"\nContent:\n{item.content}"
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call LLM via litellm with retry. Returns raw response content string."""
    response = litellm.completion(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _parse_llm_response(raw: str, news_item_id: str) -> AnalysisResult:
    """Parse JSON response into AnalysisResult. Raises on invalid structure."""
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)
    return AnalysisResult(
        news_item_id=news_item_id,
        sentiment=data["sentiment"],
        topics=data["topics"],
        summary=data["summary"],
        signal=data["signal"],
    )


def analyze_news(item: NewsItem) -> AnalysisResult:
    """Analyze a single news item via LLM. Raises on failure."""
    user_prompt = _build_user_prompt(item)
    raw_response = _call_llm(SYSTEM_PROMPT, user_prompt)
    return _parse_llm_response(raw_response, item.id)


def analyze_news_batch(items: list[NewsItem]) -> list[AnalysisResult]:
    """Analyze multiple news items with graceful degradation."""
    results: list[AnalysisResult] = []
    for item in items:
        try:
            result = analyze_news(item)
            results.append(result)
        except Exception:
            logger.warning("Analysis failed for news item: %s", item.title)
            continue
    logger.info("Analysis: processed %d/%d articles", len(results), len(items))
    return results
