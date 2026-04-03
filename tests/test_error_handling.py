"""Tests for error handling: retries, graceful degradation, config validation, API errors."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.config import ConfigError, validate_config
from src.models.analysis import AnalysisResult
from src.models.news import NewsItem
from src.modules.analysis import analyze_news, analyze_news_batch
from src.modules.generation import generate_variants
from src.modules.ingestion import fetch_news
from src.modules.scoring import score_variants


# --- Fixtures ---


@pytest.fixture
def sample_news_item():
    return NewsItem(
        source="coingecko:test",
        title="Bitcoin breaks $100k",
        content="Bitcoin breaks $100k on ETF inflows.",
        published_at="2025-01-15T10:00:00Z",
        tickers=["BTC"],
    )


@pytest.fixture
def sample_analysis(sample_news_item):
    return AnalysisResult(
        news_item_id=sample_news_item.id,
        sentiment="bullish",
        topics=["BTC", "ETF"],
        summary="Bitcoin surges past $100k driven by ETF inflows.",
        signal="breakout potential",
    )


# --- Config validation ---


def test_validate_config_missing_api_key():
    """validate_config raises ConfigError when LLM_API_KEY is empty."""
    with patch("src.config.LLM_API_KEY", ""):
        with pytest.raises(ConfigError, match="LLM_API_KEY"):
            validate_config()


def test_validate_config_success():
    """validate_config succeeds when LLM_API_KEY is set."""
    with patch("src.config.LLM_API_KEY", "test-key-123"):
        validate_config()  # Should not raise


# --- Ingestion retry exhaustion ---


@patch("src.modules.ingestion._call_coingecko")
def test_fetch_news_returns_empty_on_failure(mock_call):
    """fetch_news returns empty list when API call fails after retries."""
    mock_call.side_effect = httpx.HTTPStatusError(
        "Server Error",
        request=MagicMock(),
        response=MagicMock(status_code=500),
    )
    result = fetch_news()
    assert result == []


# --- Analysis graceful degradation ---


@patch("src.modules.analysis._call_llm")
def test_analyze_news_batch_partial_failure(mock_llm, sample_news_item):
    """analyze_news_batch continues when individual items fail."""
    item2 = NewsItem(
        source="coingecko:test",
        title="Ethereum upgrade",
        content="Ethereum staking rewards increase.",
        published_at="2025-01-15T11:00:00Z",
        tickers=["ETH"],
    )

    # First call succeeds, second raises
    mock_llm.side_effect = [
        '{"sentiment": "bullish", "topics": ["BTC"], "summary": "test", "signal": "breakout"}',
        Exception("LLM error"),
    ]

    results = analyze_news_batch([sample_news_item, item2])
    assert len(results) == 1
    assert results[0].sentiment == "bullish"


@patch("src.modules.analysis._call_llm")
def test_analyze_news_batch_all_fail(mock_llm, sample_news_item):
    """analyze_news_batch returns empty list when all items fail."""
    mock_llm.side_effect = Exception("LLM error")
    results = analyze_news_batch([sample_news_item])
    assert results == []


# --- Generation graceful degradation ---


@patch("src.modules.generation._call_llm_with_temperature")
def test_generate_variants_partial_failure(mock_llm, sample_analysis):
    """generate_variants returns whatever variants succeed."""
    mock_llm.side_effect = [
        '{"text": "BTC to the moon!"}',
        Exception("LLM error"),
        '{"text": "Actually, BTC is overvalued."}',
    ]

    results = generate_variants(sample_analysis)
    assert len(results) == 2
    assert results[0].style == "analytical"
    assert results[1].style == "contrarian"


@patch("src.modules.generation._call_llm_with_temperature")
def test_generate_variants_all_fail(mock_llm, sample_analysis):
    """generate_variants returns empty list when all styles fail."""
    mock_llm.side_effect = Exception("LLM error")
    results = generate_variants(sample_analysis)
    assert results == []


# --- Scoring graceful degradation ---


def test_score_variants_empty_list():
    """score_variants handles empty input gracefully."""
    result = score_variants([])
    assert result == []


@patch("src.modules.scoring._call_llm")
def test_score_variants_returns_unscored_on_failure(mock_llm, sample_analysis):
    """score_variants returns variants unchanged when scoring fails."""
    from src.models.content import ContentVariant

    variants = [
        ContentVariant(
            analysis_id=sample_analysis.news_item_id,
            style="analytical",
            text="Test tweet",
            prompt_template="analytical",
        ),
    ]
    mock_llm.side_effect = Exception("LLM error")

    result = score_variants(variants)
    assert len(result) == 1
    assert result[0].score is None  # Unscored


# --- Pipeline partial-failure tracking ---


@patch("src.pipeline.score_variants")
@patch("src.pipeline.generate_variants")
@patch("src.pipeline.analyze_news_batch")
@patch("src.pipeline.fetch_news")
def test_pipeline_tracks_stage_errors(mock_fetch, mock_analyze, mock_generate, mock_score):
    """Pipeline records per-stage failure counts in stage_errors."""
    from src.models.content import ContentVariant
    from src.pipeline import run_pipeline

    news = [
        NewsItem(
            source="coingecko:test",
            title="BTC news",
            content="content",
            published_at="2025-01-15T10:00:00Z",
            tickers=["BTC"],
        ),
        NewsItem(
            source="coingecko:test",
            title="ETH news",
            content="content",
            published_at="2025-01-15T11:00:00Z",
            tickers=["ETH"],
        ),
    ]
    mock_fetch.return_value = news

    # Only 1 of 2 analyses succeeds
    analysis = AnalysisResult(
        news_item_id=news[0].id,
        sentiment="bullish",
        topics=["BTC"],
        summary="test",
        signal="breakout",
    )
    mock_analyze.return_value = [analysis]

    # Generate only 2 of 3 expected variants
    variants = [
        ContentVariant(
            analysis_id=analysis.news_item_id,
            style="analytical",
            text="Test tweet 1",
            prompt_template="analytical",
        ),
        ContentVariant(
            analysis_id=analysis.news_item_id,
            style="meme",
            text="Test tweet 2",
            prompt_template="meme",
        ),
    ]
    mock_generate.return_value = variants

    # Score succeeds
    for v in variants:
        v.score = 7.5
    mock_score.return_value = variants

    run, top = run_pipeline(trigger="cli")

    assert run.status == "completed"
    assert run.stage_errors.get("analysis") == 1  # 1 of 2 failed
    assert run.stage_errors.get("generation") == 1  # 1 of 3 styles missing


# --- API error handling ---


def test_api_exception_handler():
    """API returns structured JSON on unhandled exceptions."""
    from fastapi.testclient import TestClient
    from src.api.app import app

    client = TestClient(app, raise_server_exceptions=False)

    with patch("src.api.app.fetch_news", side_effect=RuntimeError("boom")):
        response = client.get("/news")
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
