# Manual Testing Guide — Phase 1 (Core Pipeline MVP)

## Context

Phase 1 is complete with 83 automated unit tests (all mocked). No manual/live testing has been done yet. This guide walks through testing each layer with real services.

> **Note:** The CoinGecko API schema changed since initial development. The ingestion module has been updated to match the new API contract (see `plans/P1-fix-coingecko-api.md`).

---

## Prerequisites

```bash
cd /Users/daddy/Documents/iliad/ai/AI-Newsjacking-Agent
pip install -r requirements.txt
```

You'll need an LLM API key. The default model is `gpt-4o-mini` (OpenAI). You can also use Claude or any LiteLLM-supported provider.

---

## Step 1: Run Automated Tests (Sanity Check)

```bash
pytest tests/ -v
```

**Expected:** All 83 tests pass. This confirms nothing is broken before live testing.

---

## Step 2: Test News Ingestion (No API Key Needed)

Open a Python REPL from the project root:

```bash
python -c "
from src.modules.ingestion import fetch_news
items = fetch_news()
print(f'Fetched {len(items)} articles')
for item in items[:20]:
    print(f'  - [{item.source}] {item.title}')
    print(f'    Content: {item.content[:80]}...')
    print(f'    Tickers: {item.tickers}')
    print(f'    Published: {item.published_at}')
    print(f'    URL: {item.url}')
    print()
"
```

**Verify:**

- Returns a non-empty list (should be ~20 articles)
- Each item has `source` (e.g. `coingecko:Decrypt`), `title`, `url`, `content` (description)
- No duplicate titles
- Tickers are uppercase symbols (e.g. BTC, ETH, SOL) when present in title — many articles may have empty tickers since the API no longer provides `related_coin_ids`
- `published_at` and `fetched_at` are populated

---

## Step 3: Test LLM Analysis (Requires API Key)

```bash
export LLM_API_KEY="your-key-here"
# export LLM_MODEL="gpt-4o-mini"  # default, change if using another provider
```

```bash
python -c "
from src.modules.ingestion import fetch_news
from src.modules.analysis import analyze_news

items = fetch_news()
if items:
    result = analyze_news(items[0])
    print(f'Article: {items[0].title}')
    print(f'Sentiment: {result.sentiment}')
    print(f'Topics: {result.topics}')
    print(f'Summary: {result.summary}')
    print(f'Signal: {result.signal}')
else:
    print('No news fetched')
"
```

**Verify:**

- `sentiment` is one of: bullish, bearish, neutral
- `topics` is a list of 2-5 tags
- `summary` is 1-2 concise sentences
- `signal` is a short actionable phrase
- No errors/exceptions

---

## Step 4: Test Batch Analysis

```bash
python -c "
from src.modules.ingestion import fetch_news
from src.modules.analysis import analyze_news_batch

items = fetch_news()
analyses = analyze_news_batch(items[:3])
print(f'Analyzed {len(analyses)}/{min(3, len(items))} articles')
for a in analyses:
    print(f'  - {a.sentiment} | {a.topics[:2]} | {a.signal}')
"
```

**Verify:**

- Processes multiple articles (should get results for most/all)
- Graceful degradation: if one fails, others still return

---

## Step 5: Test Content Generation

```bash
python -c "
from src.modules.ingestion import fetch_news
from src.modules.analysis import analyze_news
from src.modules.generation import generate_variants

items = fetch_news()
if items:
    analysis = analyze_news(items[0])
    variants = generate_variants(analysis)
    print(f'Generated {len(variants)} variants:')
    for v in variants:
        print(f'\n  [{v.style}] (temp used in prompt)')
        print(f'  Text: {v.text}')
        print(f'  Length: {len(v.text)} chars')
"
```

**Verify:**

- 3 variants generated (analytical, meme, contrarian)
- Each has different tone/style
- Text is <= 280 characters (tweet-sized)
- Content is relevant to the news article

---

## Step 6: Test LLM-as-Judge Scoring

```bash
python -c "
from src.modules.ingestion import fetch_news
from src.modules.analysis import analyze_news
from src.modules.generation import generate_variants
from src.modules.scoring import score_variants, select_top_n

items = fetch_news()
if items:
    analysis = analyze_news(items[0])
    variants = generate_variants(analysis)
    scored = score_variants(variants)
    print(f'Scored {len(scored)} variants:')
    for v in scored:
        print(f'  [{v.style}] score={v.score:.1f}')
        print(f'    Breakdown: {v.score_breakdown}')
        print(f'    Text: {v.text[:80]}...')

    top = select_top_n(scored, 2)
    print(f'\nTop 2: {[v.style for v in top]}')
"
```

**Verify:**

- Each variant has a `score` (float 0-10)
- `score_breakdown` has 4 keys: hook_strength, clarity, engagement, relevance
- Composite score = weighted average (0.3, 0.25, 0.25, 0.2)
- `select_top_n` returns variants sorted by score descending

---

## Step 7: Test Full Pipeline via CLI (End-to-End)

This is the main integration test:

```bash
export LLM_API_KEY="your-key-here"
python -m src.cli
```

**Verify:**

- Logs show each stage with timing: Ingestion, Analysis, Generation, Scoring
- Output shows top 3 variants with scores and styles
- Exit code is 0 (`echo $?` after running)
- Total runtime is reasonable (30s-2min depending on article count and LLM speed)

**Sample expected output:**

```
[2026-04-01 ...] Pipeline run abcd1234 started (trigger: cli)
[2026-04-01 ...] Ingestion: fetched N articles (X.Xs)
[2026-04-01 ...] Analysis: processed M/N articles (X.Xs)
[2026-04-01 ...] Generation: created K variants from M analyses (X.Xs)
[2026-04-01 ...] Scoring: scored K variants, top score X.X (X.Xs)
[2026-04-01 ...] Pipeline run abcd1234 completed (X.Xs)

============================================================
Pipeline run abcd1234 — 3 top variant(s)
============================================================

[1] (analytical, score: 7.5)
<tweet text here>

[2] (meme, score: 6.8)
<tweet text here>

[3] (contrarian, score: 6.2)
<tweet text here>
```

---

## Step 8: Test Error Handling

### 8a. Missing API key

```bash
unset LLM_API_KEY
python -m src.cli
echo $?  # Should be 1
```

**Verify:** Logs error about missing LLM_API_KEY, exits with code 1.

### 8b. Invalid API key

```bash
export LLM_API_KEY="invalid-key"
python -m src.cli
```

**Verify:** Pipeline handles LLM errors gracefully (doesn't crash with unhandled exception).

### 8c. Network isolation (optional)

Disconnect from internet, then:

```bash
export LLM_API_KEY="your-key-here"
python -c "
from src.modules.ingestion import fetch_news
items = fetch_news()
print(f'Items: {len(items)}')  # Should be 0, not a crash
"
```

**Verify:** Returns empty list, no unhandled exceptions.

---

## Step 9: Test with Different LLM Providers (Optional)

### OpenAI (default)

```bash
export LLM_MODEL="gpt-4o-mini"
export LLM_API_KEY="sk-..."
python -m src.cli
```

### Claude via LiteLLM

```bash
export LLM_MODEL="anthropic/claude-haiku-4-5-20251001"
export LLM_API_KEY="sk-ant-..."
python -m src.cli
```

**Verify:** Pipeline works across providers via LiteLLM abstraction.

---

## Quick Summary

| Step | What                          | API Key? | Time    |
| ---- | ----------------------------- | -------- | ------- |
| 1    | `pytest tests/ -v` (83 tests) | No       | ~5s     |
| 2    | News ingestion                | No       | ~3s     |
| 3    | Single article analysis       | Yes      | ~5s     |
| 4    | Batch analysis                | Yes      | ~15s    |
| 5    | Content generation            | Yes      | ~10s    |
| 6    | Scoring                       | Yes      | ~10s    |
| 7    | Full pipeline (CLI)           | Yes      | ~1-2min |
| 8    | Error handling                | Mixed    | ~10s    |
| 9    | Alt providers (optional)      | Yes      | ~1-2min |
