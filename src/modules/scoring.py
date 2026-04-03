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
from src.models.content import ContentVariant

logger = logging.getLogger(__name__)

RUBRIC_WEIGHTS = {
    "hook_strength": 0.30,
    "clarity": 0.25,
    "engagement": 0.25,
    "relevance": 0.20,
}

_SYSTEM_PROMPT = (
    "You are an expert social media content evaluator specializing in crypto Twitter. "
    "Score each content variant on these criteria (1-10 scale):\n"
    "- hook_strength: Does the opening line grab attention?\n"
    "- clarity: Is the message clear and easy to understand?\n"
    "- engagement: Would this drive replies, retweets, or clicks?\n"
    "- relevance: Is the content timely and tied to the news event?\n\n"
    "Compare variants relative to each other. Be critical and differentiate scores.\n\n"
    'Return JSON with a single field "scores" containing an array of objects, '
    "one per variant in the same order as presented. Each object must have:\n"
    '- "variant_id": the variant ID\n'
    '- "hook_strength": integer 1-10\n'
    '- "clarity": integer 1-10\n'
    '- "engagement": integer 1-10\n'
    '- "relevance": integer 1-10\n\n'
    "Respond ONLY with valid JSON. No markdown, no explanation, no extra text."
)


def _build_user_prompt(variants: list[ContentVariant]) -> str:
    """Format variants into the user prompt for scoring."""
    lines = ["Score the following content variants:\n"]
    for i, v in enumerate(variants, 1):
        lines.append(f"--- Variant {i} (ID: {v.id}, Style: {v.style}) ---")
        lines.append(v.text)
        lines.append("")
    return "\n".join(lines)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call LLM via litellm with retry. Returns raw response string."""
    response = litellm.completion(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=LLM_TEMPERATURE,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _parse_scores(raw: str) -> dict[str, dict[str, float]]:
    """Parse LLM JSON response into {variant_id: {criterion: score}} mapping."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)
    scores_list = data["scores"]

    return {
        entry["variant_id"]: {
            criterion: float(entry[criterion]) for criterion in RUBRIC_WEIGHTS
        }
        for entry in scores_list
    }


def _compute_composite(breakdown: dict[str, float]) -> float:
    """Compute weighted composite score from a score breakdown."""
    return round(
        sum(breakdown[c] * w for c, w in RUBRIC_WEIGHTS.items()),
        2,
    )


def score_variants(variants: list[ContentVariant]) -> list[ContentVariant]:
    """Score content variants using the LLM as an evaluator.

    All variants are sent in a single prompt for relative comparison.
    Populates score and score_breakdown on each variant.
    On failure, returns variants unchanged (graceful degradation).
    """
    if not variants:
        return variants

    try:
        user_prompt = _build_user_prompt(variants)
        raw_response = _call_llm(_SYSTEM_PROMPT, user_prompt)
        scores_map = _parse_scores(raw_response)

        for variant in variants:
            breakdown = scores_map.get(variant.id)
            if breakdown:
                variant.score_breakdown = breakdown
                variant.score = _compute_composite(breakdown)
            else:
                logger.warning("No scores returned for variant %s", variant.id)

    except Exception:
        logger.warning("Scoring failed, returning variants unchanged", exc_info=True)

    scored = sum(1 for v in variants if v.score is not None)
    logger.info("Scoring: %d/%d variants scored", scored, len(variants))
    return variants


def select_top_n(variants: list[ContentVariant], n: int) -> list[ContentVariant]:
    """Select top-performing variants by composite score.

    Variants with score=None are sorted last.
    """
    sorted_variants = sorted(
        variants,
        key=lambda v: v.score if v.score is not None else -1,
        reverse=True,
    )
    return sorted_variants[:n]
