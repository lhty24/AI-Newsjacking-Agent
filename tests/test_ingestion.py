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
    description="Bitcoin surges past $100k milestone.",
    url="https://example.com/article",
    created_at=1711533600,
    news_site="AMBCrypto",
    related_coin_ids=None,
):
    item = {
        "title": title,
        "description": description,
        "url": url,
        "created_at": created_at,
        "news_site": news_site,
        "author": "Test Author",
        "thumb_2x": "https://example.com/img.jpg",
    }
    if related_coin_ids is not None:
        item["related_coin_ids"] = related_coin_ids
    return item


@pytest.fixture
def sample_response():
    return [
        _make_raw_item(
            title="BTC hits $100k amid ETF inflows",
        ),
        _make_raw_item(
            title="Ethereum upgrade boosts staking rewards",
            url="https://example.com/eth",
        ),
        _make_raw_item(
            title="Solana DEX volume surges",
            url="https://example.com/sol",
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

    def test_from_coin_name_in_title(self):
        tickers = _extract_tickers("Bitcoin surges past $100k", [])
        assert tickers == ["BTC"]

    def test_from_coin_name_case_insensitive(self):
        tickers = _extract_tickers("Solana ecosystem faces hack", [])
        assert tickers == ["SOL"]

    def test_coin_name_and_ticker_dedup(self):
        tickers = _extract_tickers("Bitcoin BTC rallies", [])
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
        assert results[0].title == "BTC hits $100k amid ETF inflows"
        assert results[0].source == "coingecko:AMBCrypto"
        assert "BTC" in results[0].tickers

    @patch("src.modules.ingestion._call_coingecko")
    def test_ticker_extraction(self, mock_call):
        mock_call.return_value = [
            _make_raw_item(title="ETH and BTC rally"),
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
