import logging
import os

logger = logging.getLogger(__name__)

# LLM provider config (used by litellm)
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "1024"))

# API server config (used by Streamlit dashboard)
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


def validate_config() -> None:
    """Validate that all required configuration is present.

    Raises ConfigError if any required config is missing.
    """
    if not LLM_API_KEY:
        raise ConfigError(
            "LLM_API_KEY environment variable is required. "
            "Set it to your LLM provider API key (e.g. OpenAI, Anthropic)."
        )
    logger.info("Config validated: model=%s, temperature=%s, max_tokens=%d", LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS)
