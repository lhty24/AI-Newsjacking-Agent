from unittest.mock import patch

import pytest

from src.models.analysis import AnalysisResult
from src.models.content import ContentVariant
from src.models.news import NewsItem
from src.pipeline import run_pipeline


# --- Fixtures ---


@pytest.fixture
def sample_news_items():
    return [
        NewsItem(
            source="coingecko:cointelegraph",
            title="Bitcoin breaks $100k",
            content="Bitcoin breaks $100k on ETF inflows.",
            published_at="2025-01-15T10:00:00Z",
            tickers=["BTC"],
        ),
        NewsItem(
            source="coingecko:decrypt",
            title="Ethereum upgrades staking",
            content="Ethereum staking rewards increase.",
            published_at="2025-01-15T11:00:00Z",
            tickers=["ETH"],
        ),
    ]


@pytest.fixture
def sample_analyses(sample_news_items):
    return [
        AnalysisResult(
            news_item_id=sample_news_items[0].id,
            sentiment="bullish",
            topics=["BTC", "ETF"],
            summary="Bitcoin broke $100k driven by ETF inflows.",
            signal="breakout potential",
        ),
        AnalysisResult(
            news_item_id=sample_news_items[1].id,
            sentiment="bullish",
            topics=["ETH", "staking"],
            summary="Ethereum staking rewards increase.",
            signal="accumulation zone",
        ),
    ]


@pytest.fixture
def sample_variants(sample_analyses):
    return [
        ContentVariant(
            analysis_id=sample_analyses[0].news_item_id,
            style="analytical",
            text="BTC just crossed $100k. ETF inflows are driving institutional adoption.",
            prompt_template="analytical",
            score=8.5,
            score_breakdown={"hook_strength": 9, "clarity": 8, "engagement": 8, "relevance": 9},
        ),
        ContentVariant(
            analysis_id=sample_analyses[0].news_item_id,
            style="meme",
            text="100k BTC club lets gooo 🚀🚀🚀",
            prompt_template="meme",
            score=7.2,
            score_breakdown={"hook_strength": 8, "clarity": 7, "engagement": 8, "relevance": 6},
        ),
        ContentVariant(
            analysis_id=sample_analyses[1].news_item_id,
            style="contrarian",
            text="Everyone's bullish on ETH staking. Time to ask: who's selling the news?",
            prompt_template="contrarian",
            score=6.8,
            score_breakdown={"hook_strength": 7, "clarity": 7, "engagement": 7, "relevance": 6},
        ),
    ]


# --- Tests ---


MODULE = "src.pipeline"


class TestRunPipelineHappyPath:
    @patch(f"{MODULE}.select_top_n")
    @patch(f"{MODULE}.score_variants")
    @patch(f"{MODULE}.generate_variants")
    @patch(f"{MODULE}.analyze_news_batch")
    @patch(f"{MODULE}.fetch_news")
    def test_full_pipeline(
        self, mock_fetch, mock_analyze, mock_generate, mock_score, mock_top,
        sample_news_items, sample_analyses, sample_variants,
    ):
        mock_fetch.return_value = sample_news_items
        mock_analyze.return_value = sample_analyses
        mock_generate.side_effect = [
            sample_variants[:2],  # 2 variants for first analysis
            sample_variants[2:],  # 1 variant for second analysis
        ]
        mock_score.side_effect = [
            sample_variants[:2],  # scored variants for first analysis
            sample_variants[2:],  # scored variants for second analysis
        ]
        mock_top.side_effect = [
            [sample_variants[0]],  # best from first analysis
            [sample_variants[2]],  # best from second analysis
        ]

        run, top = run_pipeline(trigger="cli")

        assert run.status == "completed"
        assert run.trigger == "cli"
        assert run.news_count == 2
        assert run.variants_generated == 3
        assert run.completed_at is not None
        assert run.error is None
        assert len(top) == 2  # one best per analysis

        mock_fetch.assert_called_once()
        mock_analyze.assert_called_once_with(sample_news_items)
        assert mock_generate.call_count == 2
        assert mock_score.call_count == 2  # once per analysis
        assert mock_top.call_count == 2  # once per analysis


class TestRunPipelineEarlyReturn:
    @patch(f"{MODULE}.analyze_news_batch")
    @patch(f"{MODULE}.fetch_news")
    def test_zero_news_returns_early(self, mock_fetch, mock_analyze):
        mock_fetch.return_value = []

        run, top = run_pipeline()

        assert run.status == "completed"
        assert run.news_count == 0
        assert top == []
        mock_analyze.assert_not_called()

    @patch(f"{MODULE}.generate_variants")
    @patch(f"{MODULE}.analyze_news_batch")
    @patch(f"{MODULE}.fetch_news")
    def test_zero_analyses_returns_early(
        self, mock_fetch, mock_analyze, mock_generate, sample_news_items,
    ):
        mock_fetch.return_value = sample_news_items
        mock_analyze.return_value = []

        run, top = run_pipeline()

        assert run.status == "completed"
        assert run.news_count == 2
        assert top == []
        mock_generate.assert_not_called()


class TestRunPipelineGracefulDegradation:
    @patch(f"{MODULE}.select_top_n")
    @patch(f"{MODULE}.score_variants")
    @patch(f"{MODULE}.generate_variants")
    @patch(f"{MODULE}.analyze_news_batch")
    @patch(f"{MODULE}.fetch_news")
    def test_scoring_failure_falls_back(
        self, mock_fetch, mock_analyze, mock_generate, mock_score, mock_top,
        sample_news_items, sample_analyses, sample_variants,
    ):
        mock_fetch.return_value = sample_news_items
        mock_analyze.return_value = sample_analyses
        mock_generate.side_effect = [sample_variants[:2], sample_variants[2:]]
        mock_score.side_effect = RuntimeError("LLM unavailable")

        run, top = run_pipeline()

        assert run.status == "completed"
        assert run.variants_generated == 3
        # Falls back to first variant per analysis
        assert len(top) == 2
        mock_top.assert_not_called()


class TestRunPipelineFailure:
    @patch(f"{MODULE}.fetch_news")
    def test_unhandled_error_sets_failed(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("Network down")

        run, top = run_pipeline()

        assert run.status == "failed"
        assert "Network down" in run.error
        assert run.completed_at is not None
        assert top == []
