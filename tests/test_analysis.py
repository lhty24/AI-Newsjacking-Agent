import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.models.analysis import AnalysisResult
from src.models.news import NewsItem
from src.modules.analysis import (
    _build_user_prompt,
    _parse_llm_response,
    analyze_news,
    analyze_news_batch,
)


# --- Fixtures ---


VALID_LLM_RESPONSE = json.dumps({
    "sentiment": "bullish",
    "topics": ["BTC", "ETF", "price"],
    "summary": "Bitcoin broke $100k driven by institutional ETF inflows.",
    "signal": "breakout potential",
})


@pytest.fixture
def sample_news_item():
    return NewsItem(
        source="coingecko:CoinDesk",
        title="Bitcoin hits $100k amid ETF inflows",
        content="Bitcoin surged past $100,000 for the first time as ETF inflows hit record levels.",
        url="https://example.com/btc-100k",
        published_at="2026-03-27T10:00:00Z",
        tickers=["BTC"],
    )


def _make_news_item(title="Test article", tickers=None):
    return NewsItem(
        source="coingecko:Test",
        title=title,
        content=f"Content for {title}",
        published_at="2026-03-27T10:00:00Z",
        tickers=tickers or [],
    )


# --- Parsing tests ---


class TestParseLlmResponse:
    def test_valid_response(self):
        result = _parse_llm_response(VALID_LLM_RESPONSE, "news-123")
        assert isinstance(result, AnalysisResult)
        assert result.news_item_id == "news-123"
        assert result.sentiment == "bullish"
        assert result.topics == ["BTC", "ETF", "price"]
        assert "ETF" in result.summary
        assert result.signal == "breakout potential"

    def test_malformed_json(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_llm_response("not valid json {", "news-123")

    def test_missing_field(self):
        incomplete = json.dumps({
            "sentiment": "bullish",
            "topics": ["BTC"],
            "summary": "A summary.",
            # missing "signal"
        })
        with pytest.raises(KeyError):
            _parse_llm_response(incomplete, "news-123")

    def test_invalid_sentiment(self):
        bad_sentiment = json.dumps({
            "sentiment": "positive",  # not in Literal
            "topics": ["BTC"],
            "summary": "A summary.",
            "signal": "breakout",
        })
        with pytest.raises(ValidationError):
            _parse_llm_response(bad_sentiment, "news-123")

    def test_markdown_code_fences_stripped(self):
        wrapped = f"```json\n{VALID_LLM_RESPONSE}\n```"
        result = _parse_llm_response(wrapped, "news-123")
        assert result.sentiment == "bullish"
        assert result.signal == "breakout potential"


# --- Prompt construction tests ---


class TestBuildUserPrompt:
    def test_includes_news_fields(self, sample_news_item):
        prompt = _build_user_prompt(sample_news_item)
        assert "Bitcoin hits $100k amid ETF inflows" in prompt
        assert "coingecko:CoinDesk" in prompt
        assert "BTC" in prompt
        assert "surged past $100,000" in prompt

    def test_no_tickers(self):
        item = _make_news_item(tickers=[])
        prompt = _build_user_prompt(item)
        assert "None identified" in prompt


# --- Single-item analysis tests ---


class TestAnalyzeNews:
    @patch("src.modules.analysis._call_llm")
    def test_success(self, mock_llm, sample_news_item):
        mock_llm.return_value = VALID_LLM_RESPONSE
        result = analyze_news(sample_news_item)

        assert isinstance(result, AnalysisResult)
        assert result.news_item_id == sample_news_item.id
        assert result.sentiment == "bullish"
        mock_llm.assert_called_once()

    @patch("src.modules.analysis._call_llm")
    def test_llm_failure_propagates(self, mock_llm, sample_news_item):
        mock_llm.side_effect = RuntimeError("LLM unavailable")
        with pytest.raises(RuntimeError, match="LLM unavailable"):
            analyze_news(sample_news_item)


# --- Batch analysis tests ---


class TestAnalyzeNewsBatch:
    @patch("src.modules.analysis._call_llm")
    def test_all_succeed(self, mock_llm):
        mock_llm.return_value = VALID_LLM_RESPONSE
        items = [_make_news_item(f"Article {i}") for i in range(3)]
        results = analyze_news_batch(items)
        assert len(results) == 3
        assert all(isinstance(r, AnalysisResult) for r in results)

    @patch("src.modules.analysis._call_llm")
    def test_partial_failure(self, mock_llm):
        mock_llm.side_effect = [
            VALID_LLM_RESPONSE,
            RuntimeError("fail"),
            VALID_LLM_RESPONSE,
        ]
        items = [_make_news_item(f"Article {i}") for i in range(3)]
        results = analyze_news_batch(items)
        assert len(results) == 2

    @patch("src.modules.analysis._call_llm")
    def test_all_fail(self, mock_llm):
        mock_llm.side_effect = RuntimeError("fail")
        items = [_make_news_item(f"Article {i}") for i in range(3)]
        results = analyze_news_batch(items)
        assert results == []

    @patch("src.modules.analysis._call_llm")
    def test_empty_input(self, mock_llm):
        results = analyze_news_batch([])
        assert results == []
        mock_llm.assert_not_called()
