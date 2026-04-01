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

- **News Ingestion** (`fetch_news`): Fetch crypto news from real APIs (CryptoPanic, CoinGecko, NewsAPI, CryptoCompare), filter and deduplicate
- **Analysis** (`analyze_news`): LLM-based sentiment/topic/signal extraction
- **Content Generation** (`generate_variants`): Multi-style output (analytical, meme, contrarian) with temperature control
- **Scoring** (`score_variants`, `select_top_n`): Weighted rubric — Hook Strength 30%, Clarity 25%, Engagement 25%, Relevance 20%
- **Distribution** (`post_tweet`): Post to Twitter, track outcomes in DistributionRecord

A single `run_pipeline()` function orchestrates all stages and is reused across three execution modes: CLI, FastAPI endpoints, and APScheduler.

## Data Models

Five Pydantic models define the data contracts: `NewsItem`, `AnalysisResult`, `ContentVariant`, `DistributionRecord`, `PipelineRun`. See `design-doc.md` for field-level details.

## API Endpoints (FastAPI)

- `GET /news` — latest ingested news
- `POST /run` — trigger full pipeline
- `POST /post` — post a specific variant
- `GET /runs` — list recent pipeline runs

## News Sources

Four real crypto news APIs power the ingestion layer:

- **CryptoPanic** — crypto news aggregator, requires free API key
- **CoinGecko** — no API key required for basic usage
- **NewsAPI.org** — general news with crypto filtering, requires free API key (100 req/day)
- **CryptoCompare** — crypto-specific with category filtering, requires free API key

## Error Handling Pattern

Graceful degradation: partial failures don't halt the pipeline. If analysis fails for one item, continue with others. If scoring fails, fall back to random ranking. If posting fails, save locally and record error status.

## Development Phases

1. Core Pipeline (MVP) — models, ingestion, analysis, generation, scoring, CLI
2. API Layer — FastAPI endpoints
3. Frontend — Streamlit dashboard
4. Distribution — Twitter integration
5. Automation — APScheduler
6. Refinement — prompt tuning, real engagement calibration, SQLite
