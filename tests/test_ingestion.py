from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.models.news import NewsItem
from src.modules.ingestion import (
    _deduplicate,
    _extract_tickers,
    _normalize_title,
    fetch_news,
)


# --- Fixtures ---


def _make_raw_item(
    title="Bitcoin hits $100k",
    url="https://example.com/article",
    posted_at="2026-03-27T10:00:00Z",
    source_name="AMBCrypto",
    item_type="news",
    related_coin_ids=None,
):
    return {
        "title": title,
        "url": url,
        "posted_at": posted_at,
        "source_name": source_name,
        "type": item_type,
        "related_coin_ids": related_coin_ids or [],
        "image": "https://example.com/img.jpg",
        "author": "Test Author",
    }


@pytest.fixture
def sample_response():
    return [
        _make_raw_item(
            title="Bitcoin hits $100k amid ETF inflows",
            related_coin_ids=["bitcoin"],
        ),
        _make_raw_item(
            title="Ethereum upgrade boosts staking rewards",
            url="https://example.com/eth",
            related_coin_ids=["ethereum"],
        ),
        _make_raw_item(
            title="Solana DEX volume surges",
            url="https://example.com/sol",
            related_coin_ids=["solana"],
        ),
    ]


def _mock_response(data, status_code=200):
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    if status_code >= 400:
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock
        )
    return mock


# --- Unit tests for helpers ---


class TestExtractTickers:
    def test_from_coin_ids(self):
        tickers = _extract_tickers("Some title", ["bitcoin", "ethereum"])
        assert tickers == ["BTC", "ETH"]

    def test_from_title_fallback(self):
        tickers = _extract_tickers("SOL price surges past $200", [])
        assert "SOL" in tickers

    def test_combined_dedup(self):
        tickers = _extract_tickers("BTC rallies hard", ["bitcoin"])
        assert tickers == ["BTC"]

    def test_unknown_coin_id_ignored(self):
        tickers = _extract_tickers("Title", ["unknown-coin-xyz"])
        assert tickers == []


class TestNormalizeTitle:
    def test_lowercases(self):
        assert _normalize_title("Bitcoin HITS $100K") == "bitcoin hits 100k"

    def test_strips_whitespace(self):
        assert _normalize_title("  spaced  out  ") == "spaced out"

    def test_strips_punctuation(self):
        assert _normalize_title("hello, world!") == "hello world"


class TestDeduplicate:
    def test_removes_duplicates(self):
        items = [
            {"title": "Bitcoin hits $100k"},
            {"title": "  Bitcoin hits $100k!  "},
        ]
        assert len(_deduplicate(items)) == 1

    def test_keeps_unique(self):
        items = [
            {"title": "Bitcoin hits $100k"},
            {"title": "Ethereum upgrade live"},
        ]
        assert len(_deduplicate(items)) == 2


# --- Integration tests for fetch_news ---


class TestFetchNews:
    @patch("src.modules.ingestion._call_coingecko")
    def test_success(self, mock_call, sample_response):
        mock_call.return_value = sample_response
        results = fetch_news()

        assert len(results) == 3
        assert all(isinstance(r, NewsItem) for r in results)
        assert results[0].title == "Bitcoin hits $100k amid ETF inflows"
        assert results[0].source == "coingecko:AMBCrypto"
        assert "BTC" in results[0].tickers

    @patch("src.modules.ingestion._call_coingecko")
    def test_filters_guides(self, mock_call):
        mock_call.return_value = [
            _make_raw_item(title="News article", item_type="news"),
            _make_raw_item(title="How to use Python", item_type="guide"),
        ]
        results = fetch_news()
        assert len(results) == 1
        assert results[0].title == "News article"

    @patch("src.modules.ingestion._call_coingecko")
    def test_ticker_extraction(self, mock_call):
        mock_call.return_value = [
            _make_raw_item(
                title="ETH and BTC rally",
                related_coin_ids=["bitcoin", "ethereum"],
            ),
        ]
        results = fetch_news()
        assert results[0].tickers == ["BTC", "ETH"]

    @patch("src.modules.ingestion._call_coingecko")
    def test_deduplication(self, mock_call):
        mock_call.return_value = [
            _make_raw_item(title="Bitcoin hits $100k"),
            _make_raw_item(title="  Bitcoin hits $100k!  "),
        ]
        results = fetch_news()
        assert len(results) == 1

    @patch("src.modules.ingestion._call_coingecko")
    def test_api_error_returns_empty(self, mock_call):
        mock_call.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        results = fetch_news()
        assert results == []

    @patch("src.modules.ingestion._call_coingecko")
    def test_empty_response(self, mock_call):
        mock_call.return_value = []
        results = fetch_news()
        assert results == []

    @patch("src.modules.ingestion._call_coingecko")
    def test_partial_parse_failure(self, mock_call):
        mock_call.return_value = [
            _make_raw_item(title="Good article"),
            {"bad": "item"},  # missing required fields
            _make_raw_item(title="Another good one"),
        ]
        results = fetch_news()
        assert len(results) == 2
