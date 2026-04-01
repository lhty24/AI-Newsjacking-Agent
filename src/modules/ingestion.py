import logging
import re
import unicodedata

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models.news import NewsItem

logger = logging.getLogger(__name__)

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


def _extract_tickers(title: str, related_coin_ids: list[str]) -> list[str]:
    """Extract ticker symbols from coin IDs and title text."""
    tickers = set()

    for coin_id in related_coin_ids:
        ticker = COIN_ID_TO_TICKER.get(coin_id)
        if ticker:
            tickers.add(ticker)

    # Regex fallback: scan title for known ticker symbols as whole words
    title_upper = title.upper()
    for ticker in KNOWN_TICKERS:
        if re.search(rf"\b{ticker}\b", title_upper):
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


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def _call_coingecko() -> list[dict]:
    """Fetch raw news data from CoinGecko with retry."""
    with httpx.Client(timeout=httpx.Timeout(10, read=30)) as client:
        response = client.get(
            COINGECKO_NEWS_URL,
            headers={"User-Agent": "AI-Newsjacking-Agent/1.0"},
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else data.get("data", [])


def fetch_news() -> list[NewsItem]:
    """Fetch crypto news from CoinGecko and return as NewsItem list."""
    try:
        raw_items = _call_coingecko()
    except Exception:
        logger.warning("Failed to fetch news from CoinGecko after retries")
        return []

    # Filter to news only (exclude guides)
    news_items = [item for item in raw_items if item.get("type") != "guide"]

    # Deduplicate by title
    news_items = _deduplicate(news_items)

    results: list[NewsItem] = []
    for item in news_items:
        try:
            source_name = item.get("source_name", "unknown")
            tickers = _extract_tickers(
                item.get("title", ""),
                item.get("related_coin_ids", []),
            )
            news = NewsItem(
                source=f"coingecko:{source_name}",
                title=item["title"],
                content=item.get("title", ""),
                url=item.get("url"),
                published_at=item["posted_at"],
                tickers=tickers,
            )
            results.append(news)
        except Exception:
            logger.warning("Failed to parse news item: %s", item.get("title", "???"))
            continue

    logger.info("Ingestion: fetched %d articles", len(results))
    return results
