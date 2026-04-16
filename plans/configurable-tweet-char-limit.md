# Plan: Configurable Tweet Character Limit

## Context

Currently, tweet generation is hardcoded to 280 characters (standard Twitter limit). X Premium subscribers can post up to 25,000 characters. This feature adds a dropdown in the sidebar Actions section to let users select the max character count for generated tweet variants, threading it through the full stack.

## Dropdown Options

`[280, 500, 1000, 2500, 5000, 10000, 25000]` — default: **280**

## Changes (8 files)

### 1. `src/config.py` — Add constant
- Add `ALLOWED_CHAR_LIMITS = [280, 500, 1000, 2500, 5000, 10000, 25000]`

### 2. `src/modules/generation.py` — Dynamic char limit in prompt
- Convert `_RESPONSE_INSTRUCTION` from static string to a function `_response_instruction(max_chars: int) -> str` that interpolates the limit
- Replace static `STYLE_PROMPTS` dict with a function `_build_style_prompt(style: str, max_chars: int) -> str`
- Add `max_chars: int = 280` param to `_generate_single()` and `generate_variants()`

### 3. `src/modules/distribution.py` — Dynamic warning threshold
- Add `max_chars: int = 280` param to `post_tweet()`
- Replace hardcoded `TWITTER_CHAR_LIMIT = 280` usage in the warning check with the param

### 4. `src/pipeline.py` — Thread `max_chars` through orchestrator
- Add `max_chars: int = 280` param to `run_pipeline()`
- Pass to `generate_variants(analysis, max_chars=max_chars)` (line 74)
- Pass to `post_tweet(variant, max_chars=max_chars)` (line 110)

### 5. `src/scheduler.py` — Add scheduler-level state (mirrors `max_articles` pattern)
- Add `_max_chars: int = 280` module-level variable
- Add `ALLOWED_CHAR_LIMITS` import from config
- Add `update_max_chars(max_chars: int)` function
- Include `"max_chars"` in `get_scheduler_status()` return dict

### 6. `src/api/app.py` — API layer
- Add `max_chars: int = 280` to `RunRequest` model
- Add `max_chars` param to `_execute_pipeline()`, forward to `run_pipeline()`
- Pass `body.max_chars` in `/run` endpoint
- Add `max_chars: int` to `SchedulerStatus` model
- Add `MaxCharsRequest` model + `POST /scheduler/max-chars` endpoint (mirrors `/scheduler/max-articles`)
- Update `_scheduler_pipeline_callback()` to read `max_chars` from scheduler status and pass it through
- Import `update_max_chars` from scheduler

### 7. `src/dashboard.py` — UI dropdown in Actions section
- Add `st.selectbox("Max chars per tweet", [280, 500, 1000, 2500, 5000, 10000, 25000], index=0)` between "Articles to process" and the Run button
- Include `max_chars` in the `/run` POST payload
- Add matching selectbox in Scheduler controls section, POSTing to `/scheduler/max-chars` on change

### 8. `src/cli.py` — CLI argument
- Add `--max-chars` argument with `choices=[280, 500, 1000, 2500, 5000, 10000, 25000]`, default 280
- Pass to `run_pipeline()`

## Implementation Order

1. `config.py` (no deps)
2. `generation.py` + `distribution.py` (parallel, no deps)
3. `pipeline.py` (depends on 2)
4. `scheduler.py` (no deps, parallel with 2-3)
5. `api/app.py` (depends on 3, 4)
6. `dashboard.py` + `cli.py` (depends on 5)

### 9. `src/models/pipeline.py` — Persist max_chars on PipelineRun
- Add `max_chars: int = 280` field to the model

### 10. `src/pipeline.py` — Store max_chars on run record
- Pass `max_chars` when creating `PipelineRun`

### 11. `src/dashboard.py` — Display max_chars in Pipeline Runs history
- Show `max_chars` in the run expander details

## Verification

1. **CLI**: `python -m src.cli --max-chars 1000` — check LLM prompt contains "max 1000 chars"
2. **API**: `curl -X POST localhost:8000/run -d '{"max_articles":1,"max_chars":1000}'` — verify generation uses limit
3. **Dashboard**: Run Streamlit, select different char limits, trigger pipeline, verify generated variants respect the selected limit
4. **Scheduler**: Set max chars via scheduler controls, trigger scheduled run, verify it uses the configured value
5. **Distribution warning**: Generate a variant exceeding the configured limit, verify warning fires at correct threshold
6. **Runs history**: Check Pipeline Runs page shows the max_chars value for each run
