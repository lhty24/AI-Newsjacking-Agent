import json
from unittest.mock import patch

import pytest

from src.models.analysis import AnalysisResult
from src.models.content import ContentVariant
from src.modules.generation import (
    STYLE_PROMPTS,
    STYLE_TEMPERATURES,
    _build_generation_prompt,
    _parse_tweet_response,
    generate_variants,
)


# --- Fixtures ---


VALID_LLM_RESPONSE = json.dumps({"text": "Bitcoin just broke $100k. ETF inflows are accelerating. This is just the beginning."})


@pytest.fixture
def sample_analysis():
    return AnalysisResult(
        news_item_id="news-123",
        sentiment="bullish",
        topics=["BTC", "ETF", "price"],
        summary="Bitcoin broke $100k driven by institutional ETF inflows.",
        signal="breakout potential",
    )


def _make_response(text="A generated tweet."):
    return json.dumps({"text": text})


# --- Parsing tests ---


class TestParseTweetResponse:
    def test_valid_json(self):
        text = _parse_tweet_response(VALID_LLM_RESPONSE)
        assert "Bitcoin" in text
        assert "$100k" in text

    def test_malformed_json(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_tweet_response("not json {")

    def test_missing_text_field(self):
        with pytest.raises(KeyError):
            _parse_tweet_response(json.dumps({"tweet": "wrong field"}))

    def test_markdown_code_fences_stripped(self):
        wrapped = f"```json\n{VALID_LLM_RESPONSE}\n```"
        text = _parse_tweet_response(wrapped)
        assert "Bitcoin" in text


# --- Prompt construction tests ---


class TestBuildGenerationPrompt:
    def test_includes_analysis_fields(self, sample_analysis):
        prompt = _build_generation_prompt(sample_analysis)
        assert "bullish" in prompt
        assert "BTC" in prompt
        assert "breakout potential" in prompt
        assert "ETF inflows" in prompt

    def test_empty_topics(self):
        analysis = AnalysisResult(
            news_item_id="news-456",
            sentiment="neutral",
            topics=[],
            summary="No major news.",
            signal="sideways",
        )
        prompt = _build_generation_prompt(analysis)
        assert "general crypto" in prompt


# --- Style config tests ---


class TestStyleConfig:
    def test_all_styles_have_prompts(self):
        for style in ["analytical", "meme", "contrarian"]:
            assert style in STYLE_PROMPTS

    def test_all_styles_have_temperatures(self):
        for style in ["analytical", "meme", "contrarian"]:
            assert style in STYLE_TEMPERATURES

    def test_temperature_ordering(self):
        assert STYLE_TEMPERATURES["analytical"] < STYLE_TEMPERATURES["contrarian"]
        assert STYLE_TEMPERATURES["contrarian"] < STYLE_TEMPERATURES["meme"]


# --- Single variant generation (via generate_variants with one style) ---


class TestGenerateVariants:
    @patch("src.modules.generation._call_llm_with_temperature")
    def test_single_style(self, mock_llm, sample_analysis):
        mock_llm.return_value = _make_response("Analytical tweet here.")
        results = generate_variants(sample_analysis, styles=["analytical"])

        assert len(results) == 1
        variant = results[0]
        assert isinstance(variant, ContentVariant)
        assert variant.style == "analytical"
        assert variant.analysis_id == "news-123"
        assert variant.text == "Analytical tweet here."
        assert variant.prompt_template == "analytical"

    @patch("src.modules.generation._call_llm_with_temperature")
    def test_default_all_styles(self, mock_llm, sample_analysis):
        mock_llm.return_value = _make_response("A tweet.")
        results = generate_variants(sample_analysis)

        assert len(results) == 3
        styles = {v.style for v in results}
        assert styles == {"analytical", "meme", "contrarian"}

    @patch("src.modules.generation._call_llm_with_temperature")
    def test_partial_failure(self, mock_llm, sample_analysis):
        mock_llm.side_effect = [
            _make_response("Good tweet."),
            RuntimeError("LLM fail"),
            _make_response("Another tweet."),
        ]
        results = generate_variants(sample_analysis)
        assert len(results) == 2

    @patch("src.modules.generation._call_llm_with_temperature")
    def test_all_fail(self, mock_llm, sample_analysis):
        mock_llm.side_effect = RuntimeError("fail")
        results = generate_variants(sample_analysis)
        assert results == []

    @patch("src.modules.generation._call_llm_with_temperature")
    def test_temperature_passed_correctly(self, mock_llm, sample_analysis):
        mock_llm.return_value = _make_response("Tweet.")
        generate_variants(sample_analysis, styles=["meme"])

        _, kwargs = mock_llm.call_args
        assert kwargs.get("temperature") is None  # passed as positional
        # Check positional: system_prompt, user_prompt, temperature
        args = mock_llm.call_args[0]
        assert args[2] == 0.9  # meme temperature
