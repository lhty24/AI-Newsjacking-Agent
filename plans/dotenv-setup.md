# Plan: Add .env file support

## Context
User wants to test Twitter/X posting. Rather than exporting env vars each session, we'll add `python-dotenv` so credentials load from a `.env` file automatically.

## Changes

### 1. Add `python-dotenv` to `requirements.txt`
- File: `requirements.txt`
- Add `python-dotenv>=1.0`

### 2. Add `load_dotenv()` to config
- File: `src/config.py`
- Import and call `load_dotenv()` at the top, before any `os.environ.get()` calls
- This ensures `.env` values are available when module-level variables are read

### 3. Create `.env` file with placeholder values
- File: `.env` (already in `.gitignore`)
- Include all env vars with empty/default values for the user to fill in

## Verification
1. `pip install -r requirements.txt`
2. Fill in `.env` with real credentials
3. `python -m src.cli` — should load config from `.env` and run pipeline
