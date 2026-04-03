# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered newsjacking agent for the crypto market. Ingests real-time news, analyzes sentiment via LLMs, generates multi-style content variants, scores them with an LLM-as-judge rubric, and distributes top picks to Twitter/X.

The full technical specification lives in `design-doc.md`.

## Tech Stack

- **Backend:** Python, FastAPI, APScheduler
- **AI/ML:** OpenAI / Claude / LiteLLM (direct prompting, no RAG)
- **Data:** Pydantic models (in-memory, optional JSON/SQLite persistence)
- **Frontend:** Streamlit
- **Distribution:** Twitter/X via Tweepy
- **Resilience:** tenacity for retry with backoff

## Architecture

The system is a modular pipeline with five stages:

```
News Ingestion → Analysis → Content Generation → LLM-as-Judge Scoring → Distribution
```

- **News Ingestion** (`fetch_news`): Fetch crypto news from CoinGecko News API, filter and deduplicate
- **Analysis** (`analyze_news`): LLM-based sentiment/topic/signal extraction
- **Content Generation** (`generate_variants`): Multi-style output (analytical, meme, contrarian) with temperature control
- **Scoring** (`score_variants`, `select_top_n`): Per-analysis scoring (3 variants scored together, best 1 kept per article). Weighted rubric — Hook Strength 30%, Clarity 25%, Engagement 25%, Relevance 20%
- **Distribution** (`post_tweet`): Post to Twitter, track outcomes in DistributionRecord

A single `run_pipeline()` function orchestrates all stages and is reused across three execution modes: CLI, FastAPI endpoints, and APScheduler.

## Data Models

Five Pydantic models define the data contracts: `NewsItem`, `AnalysisResult`, `ContentVariant`, `DistributionRecord`, `PipelineRun`. See `design-doc.md` for field-level details.

## API Endpoints (FastAPI)

- `GET /news` — latest ingested news
- `POST /run` — trigger full pipeline (runs in background, returns immediately)
- `GET /runs` — list recent pipeline runs
- `GET /runs/{run_id}` — get a specific run and its variants
- `GET /variants` — list variants (optional `run_id` filter)
- `POST /post` — post a specific variant
- `POST /post/batch` — post multiple variants at once

## News Source

The ingestion layer uses a single API:

- **CoinGecko News API** — crypto-native news, no API key required for basic usage, 10–30 req/min

## Environment Variables

- `LLM_MODEL` — LiteLLM model identifier (default: `gpt-4o-mini`)
- `LLM_API_KEY` — API key for the LLM provider (required at runtime)
- `LLM_TEMPERATURE` — LLM temperature (default: `0.3`)
- `LLM_MAX_TOKENS` — Max tokens per LLM response (default: `1024`)
- `API_BASE_URL` — FastAPI server URL for the Streamlit dashboard (default: `http://localhost:8000`)

## Error Handling Pattern

Graceful degradation: partial failures don't halt the pipeline. If analysis fails for one item, continue with others. If scoring fails, fall back to random ranking. If posting fails, save locally and record error status.

## Development Phases

1. Core Pipeline (MVP) — models, ingestion, analysis, generation, scoring, CLI
2. API Layer — FastAPI endpoints
3. Frontend — Streamlit dashboard
4. Distribution — Twitter integration
5. Automation — APScheduler
6. Refinement — prompt tuning, real engagement calibration, SQLite
