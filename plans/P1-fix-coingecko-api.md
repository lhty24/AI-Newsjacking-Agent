# Fix: CoinGecko News API Breaking Changes

## Context
The CoinGecko `/api/v3/news` endpoint has changed its contract since the ingestion module was written. The API now returns HTTP 422 without a `page` parameter, and the response schema has changed. This causes `fetch_news()` to silently return an empty list.

## Root Cause
Three breaking changes in the CoinGecko API:

1. **`page` param now required** — request without `?page=1` returns `422 {"error":"Invalid page param!"}`
2. **Response field renames:**
   - `source_name` → `news_site`
   - `posted_at` → `created_at` (unix timestamp, not ISO string)
   - `title` used for content → `description` now available
3. **Removed fields:**
   - `related_coin_ids` — no longer present (ticker extraction from coin IDs won't work)
   - `type` — no longer present (guide filtering won't match anything)

## Current API response structure
```
GET /api/v3/news?page=1
{
  "data": [...],  // 20 items
  "count": 20,
  "page": 1
}

Each item:
{
  "id", "title", "description", "locale", "author",
  "url", "crawled_at", "created_at", "updated_at",
  "news_site", "thumb_2x"
}
```

## Fix Plan

**File:** `src/modules/ingestion.py`

### Change 1: Add `page=1` query param (line 84-87)
```python
response = client.get(
    COINGECKO_NEWS_URL,
    params={"page": 1},
    headers={"User-Agent": "AI-Newsjacking-Agent/1.0"},
)
```

### Change 2: Update field mappings in `fetch_news()` (lines 108-123)
```python
source_name = item.get("news_site", "unknown")  # was "source_name"
```

```python
content=item.get("description", item.get("title", "")),  # was just title
```

```python
published_at=item["created_at"],  # was "posted_at"
```

### Change 3: Unix timestamp — no code change needed
`published_at` is typed as `datetime` in `NewsItem`. Pydantic v2 auto-converts unix timestamps (int) to datetime. Verified: `T(dt=1775072848)` → `2026-04-01 19:47:28+00:00`.

### Change 4: Remove guide filter (line 102)
The `type` field no longer exists. Remove or make the filter a no-op:
```python
# Remove: news_items = [item for item in raw_items if item.get("type") != "guide"]
# Since type is gone, all items are news — just pass through
news_items = raw_items
```

### Change 5: Ticker extraction — rely on title-only (line 111-114)
`related_coin_ids` no longer exists. Pass empty list:
```python
tickers = _extract_tickers(
    item.get("title", ""),
    [],  # related_coin_ids no longer in API response
)
```

### Change 6: Update tests
**File:** `tests/test_ingestion.py`

Update `_make_raw_item` fixture (lines 18-35) to match new API schema:
- `posted_at` → `created_at` (use unix timestamp int, e.g. `1711533600`)
- `source_name` → `news_site`
- Remove `type` and `related_coin_ids` fields
- Add `description` field

Update `test_filters_guides` (line 134-141): remove this test since `type` field no longer exists.

Update `test_ticker_extraction` (line 144-152): remove `related_coin_ids` from mock, rely on title-only extraction. The test asserts `["BTC", "ETH"]` which still works because title is "ETH and BTC rally".

## Files to modify
- `src/modules/ingestion.py` — main fixes
- `src/models/news.py` — check/update `published_at` type handling
- `tests/test_ingestion.py` — update mocked responses

## Verification
1. `python -c "from src.modules.ingestion import fetch_news; items = fetch_news(); print(f'{len(items)} articles'); [print(f'  {i.title[:60]}... tickers={i.tickers}') for i in items[:3]]"`
2. `pytest tests/test_ingestion.py -v`
3. `pytest tests/ -v` (full suite still passes)
