import json
import logging

import litellm
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from src.config import LLM_API_KEY, LLM_MAX_TOKENS, LLM_MODEL
from src.models.analysis import AnalysisResult
from src.models.content import ContentVariant

logger = logging.getLogger(__name__)

DEFAULT_STYLES = ["analytical", "meme", "contrarian"]

STYLE_TEMPERATURES = {
    "analytical": 0.3,
    "meme": 0.9,
    "contrarian": 0.7,
}

_STYLE_INSTRUCTION = {
    "analytical": (
        "You are a crypto market analyst writing a professional tweet. "
        "Be data-driven, clear, and authoritative."
    ),
    "meme": (
        "You are a crypto Twitter personality. "
        "Write a viral, funny tweet using crypto slang, emojis, and meme culture."
    ),
    "contrarian": (
        "You are a contrarian crypto analyst. "
        "Challenge the mainstream narrative. Be provocative but substantive."
    ),
}

_RESPONSE_INSTRUCTION = (
    '\n\nReturn JSON with a single field "text" containing the tweet (max 280 chars). '
    "Respond ONLY with valid JSON. No markdown, no explanation, no extra text."
)

STYLE_PROMPTS = {
    style: instruction + _RESPONSE_INSTRUCTION
    for style, instruction in _STYLE_INSTRUCTION.items()
}


def _build_generation_prompt(analysis: AnalysisResult) -> str:
    """Format an AnalysisResult into the user prompt for content generation."""
    topics = ", ".join(analysis.topics) or "general crypto"
    return (
        f"Sentiment: {analysis.sentiment}\n"
        f"Topics: {topics}\n"
        f"Signal: {analysis.signal}\n"
        f"\nSummary:\n{analysis.summary}"
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _call_llm_with_temperature(
    system_prompt: str, user_prompt: str, temperature: float
) -> str:
    """Call LLM via litellm with a specific temperature. Returns raw response string."""
    response = litellm.completion(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=LLM_MAX_TOKENS,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _parse_tweet_response(raw: str) -> str:
    """Extract tweet text from LLM JSON response."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)
    return data["text"]


def _generate_single(analysis: AnalysisResult, style: str) -> ContentVariant:
    """Generate a single content variant for a given style."""
    system_prompt = STYLE_PROMPTS[style]
    user_prompt = _build_generation_prompt(analysis)
    temperature = STYLE_TEMPERATURES[style]

    raw_response = _call_llm_with_temperature(system_prompt, user_prompt, temperature)
    text = _parse_tweet_response(raw_response)

    return ContentVariant(
        analysis_id=analysis.news_item_id,
        style=style,
        text=text,
        prompt_template=style,
    )


def generate_variants(
    analysis: AnalysisResult, styles: list[str] | None = None
) -> list[ContentVariant]:
    """Generate content variants for each style with graceful degradation."""
    if styles is None:
        styles = DEFAULT_STYLES

    results: list[ContentVariant] = []
    for style in styles:
        try:
            variant = _generate_single(analysis, style)
            results.append(variant)
        except Exception:
            logger.warning("Generation failed for style '%s'", style)
            continue

    logger.info("Generation: produced %d/%d variants", len(results), len(styles))
    return results
