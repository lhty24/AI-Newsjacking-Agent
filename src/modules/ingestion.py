import logging
import re
import unicodedata

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.models.news import NewsItem

logger = logging.getLogger(__name__)


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Check if an exception is a rate-limit (429) error."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return True
    return False

COINGECKO_NEWS_URL = "https://api.coingecko.com/api/v3/news"

# Top coins: CoinGecko coin ID → ticker symbol
COIN_ID_TO_TICKER = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "ripple": "XRP",
    "cardano": "ADA",
    "dogecoin": "DOGE",
    "polkadot": "DOT",
    "chainlink": "LINK",
    "avalanche-2": "AVAX",
    "polygon-ecosystem-token": "POL",
    "litecoin": "LTC",
    "uniswap": "UNI",
    "cosmos": "ATOM",
    "stellar": "XLM",
    "near": "NEAR",
    "arbitrum": "ARB",
    "optimism": "OP",
    "sui": "SUI",
    "aptos": "APT",
    "pepe": "PEPE",
}

# Ticker symbols to scan for in titles
KNOWN_TICKERS = set(COIN_ID_TO_TICKER.values())

# Full coin name → ticker (lowercase for case-insensitive matching)
COIN_NAME_TO_TICKER = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "ripple": "XRP",
    "cardano": "ADA",
    "dogecoin": "DOGE",
    "polkadot": "DOT",
    "chainlink": "LINK",
    "avalanche": "AVAX",
    "polygon": "POL",
    "litecoin": "LTC",
    "uniswap": "UNI",
    "cosmos": "ATOM",
    "stellar": "XLM",
    "near": "NEAR",
    "arbitrum": "ARB",
    "optimism": "OP",
    "sui": "SUI",
    "aptos": "APT",
    "pepe": "PEPE",
}


def _extract_tickers(title: str, related_coin_ids: list[str]) -> list[str]:
    """Extract ticker symbols from coin IDs, coin names, and title text."""
    tickers = set()

    for coin_id in related_coin_ids:
        ticker = COIN_ID_TO_TICKER.get(coin_id)
        if ticker:
            tickers.add(ticker)

    title_upper = title.upper()
    title_lower = title.lower()

    # Match ticker symbols as whole words (e.g. BTC, ETH)
    for ticker in KNOWN_TICKERS:
        if re.search(rf"\b{ticker}\b", title_upper):
            tickers.add(ticker)

    # Match full coin names as whole words (e.g. Bitcoin, Ethereum)
    for name, ticker in COIN_NAME_TO_TICKER.items():
        if re.search(rf"\b{name}\b", title_lower):
            tickers.add(ticker)

    return sorted(tickers)


def _normalize_title(title: str) -> str:
    """Normalize title for deduplication: lowercase, strip punctuation/whitespace."""
    title = unicodedata.normalize("NFKC", title).lower().strip()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title


def _deduplicate(items: list[dict]) -> list[dict]:
    """Remove duplicate items by normalized title."""
    seen: set[str] = set()
    unique = []
    for item in items:
        key = _normalize_title(item.get("title", ""))
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=30),
    retry=retry_if_exception(lambda e: True),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _call_coingecko() -> list[dict]:
    """Fetch raw news data from CoinGecko with retry."""
    with httpx.Client(timeout=httpx.Timeout(10, read=30)) as client:
        response = client.get(
            COINGECKO_NEWS_URL,
            params={"page": 1},
            headers={"User-Agent": "AI-Newsjacking-Agent/1.0"},
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else data.get("data", [])


def fetch_news(max_items: int = 10) -> list[NewsItem]:
    """Fetch crypto news from CoinGecko and return as NewsItem list."""
    try:
        raw_items = _call_coingecko()
    except Exception:
        logger.warning("Failed to fetch news from CoinGecko after retries")
        return []

    # Deduplicate by title and limit
    news_items = _deduplicate(raw_items)[:max_items]

    results: list[NewsItem] = []
    for item in news_items:
        try:
            source_name = item.get("news_site", "unknown")
            tickers = _extract_tickers(
                item.get("title", ""),
                item.get("related_coin_ids", []),
            )
            news = NewsItem(
                source=f"coingecko:{source_name}",
                title=item["title"],
                content=item.get("description", item.get("title", "")),
                url=item.get("url"),
                published_at=item["created_at"],
                tickers=tickers,
            )
            results.append(news)
        except Exception:
            logger.warning("Failed to parse news item: %s", item.get("title", "???"))
            continue

    logger.info("Ingestion: fetched %d articles", len(results))
    return results
