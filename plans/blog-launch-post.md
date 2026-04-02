# Plan: Blog Post for AI Newsjacking Agent Launch

## Context
~2000-word blog post announcing the AI Newsjacking Agent as the latest tool from Iliad AI. Targets both technical and non-technical audiences. Saved to `/blog/launch-post.md`, casual & conversational tone.

## Blog Structure (~2000 words)

### 1. Title & Hook
- Catchy title positioning the tool as an AI-powered crypto content engine
- Opening hook about the speed of crypto news and the challenge of staying relevant

### 2. Introduction / Summary (~200 words)
- What the tool does in one paragraph
- Why it exists — the newsjacking opportunity in crypto
- Position as Iliad AI's latest product

### 3. For Non-Technical Users (~500 words)
- Plain-language explanation: "think of it as a newsroom assistant that never sleeps"
- What it does step by step (fetch → analyze → write → pick the best → post)
- Who benefits: crypto marketers, community managers, founders, content creators
- What kind of content it produces (analytical, meme-style, contrarian takes)
- How someone would use it in practice

### 4. For Technical Users (~700 words)
- Architecture overview: 5-stage pipeline
- Tech stack: Python, LiteLLM, Pydantic, httpx, tenacity
- Key design decisions:
  - Direct prompting vs RAG (and why no RAG)
  - Per-style temperature control (0.3 / 0.7 / 0.9)
  - LLM-as-judge scoring with weighted rubric
  - Per-analysis relative comparison scoring
  - Graceful degradation at every stage
- Brief walkthrough of how a news article flows through the pipeline
- Code architecture: modular, single `run_pipeline()` reused across CLI/API/scheduler

### 5. What's Next / Roadmap (~300 words)
- Phase 2: REST API (FastAPI)
- Phase 3: Streamlit dashboard for monitoring
- Phase 4: Twitter/X auto-distribution
- Phase 5: Scheduled automation (APScheduler)
- Phase 6: Prompt tuning with real engagement data, SQLite persistence
- Open-ended: multi-platform distribution, historical signal tracking

### 6. Closing (~200 words)
- Call to action / what Iliad AI is building toward
- Invite readers to follow along

## Files to Create
- `/blog/launch-post.md` — the blog post

## Key Source Files to Reference
- `src/pipeline.py` — orchestrator
- `src/modules/ingestion.py` — news fetching
- `src/modules/analysis.py` — LLM analysis
- `src/modules/generation.py` — multi-style content generation
- `src/modules/scoring.py` — LLM-as-judge scoring
- `src/models/` — Pydantic data models
- `design-doc.md` — full technical spec

## Verification
- Read the final blog post for flow, tone consistency, and ~2000 word count
- Ensure both technical and non-technical sections are accessible to their audiences
- Verify all technical claims match the actual codebase
