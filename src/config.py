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

# Twitter/X config (used by distribution module)
TWITTER_ENABLED = os.environ.get("TWITTER_ENABLED", "false").lower() == "true"
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")


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
    validate_twitter_config()


def _mask(value: str) -> str:
    """Mask a credential string for safe logging."""
    if len(value) <= 6:
        return "***"
    return value[:3] + "..." + value[-3:]


def validate_twitter_config() -> None:
    """Validate Twitter credentials when Twitter is enabled.

    Raises ConfigError if TWITTER_ENABLED is true but credentials are missing.
    """
    if not TWITTER_ENABLED:
        logger.info("Twitter distribution is disabled")
        return

    missing = []
    for name in ("TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET"):
        if not os.environ.get(name, ""):
            missing.append(name)

    if missing:
        raise ConfigError(
            f"Twitter is enabled but missing credentials: {', '.join(missing)}. "
            "Set these environment variables or set TWITTER_ENABLED=false."
        )

    logger.info(
        "Twitter config validated: api_key=%s, access_token=%s",
        _mask(TWITTER_API_KEY),
        _mask(TWITTER_ACCESS_TOKEN),
    )
