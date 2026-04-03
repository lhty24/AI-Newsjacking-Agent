import logging
from datetime import datetime, timezone

import tweepy
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.config import (
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_TOKEN_SECRET,
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ENABLED,
)
from src.models.content import ContentVariant
from src.models.distribution import DistributionRecord

logger = logging.getLogger(__name__)

TWITTER_CHAR_LIMIT = 280

_twitter_client: tweepy.Client | None = None


def _get_twitter_client() -> tweepy.Client:
    """Lazily initialize and cache a Tweepy v2 Client."""
    global _twitter_client
    if _twitter_client is None:
        _twitter_client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
        )
    return _twitter_client


def _is_retryable(exc: BaseException) -> bool:
    """Only retry on rate-limit (429) or server errors (5xx)."""
    if isinstance(exc, tweepy.TooManyRequests):
        return True
    if isinstance(exc, tweepy.TwitterServerError):
        return True
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=60),
    retry=retry_if_exception(_is_retryable),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _create_tweet(client: tweepy.Client, text: str) -> tweepy.Response:
    """Post a tweet with retry on transient errors."""
    return client.create_tweet(text=text)


def post_tweet(variant: ContentVariant) -> DistributionRecord:
    """Post a content variant to Twitter/X.

    Returns a DistributionRecord with the outcome. When Twitter is disabled,
    returns a record with status="pending" for dry-run usage.
    """
    if not TWITTER_ENABLED:
        logger.info("Twitter disabled, skipping post for variant %s", variant.id[:8])
        return DistributionRecord(
            variant_id=variant.id,
            status="pending",
            error="Twitter disabled",
        )

    if len(variant.text) > TWITTER_CHAR_LIMIT:
        logger.warning(
            "Variant %s text length (%d) exceeds Twitter %d-char limit",
            variant.id[:8],
            len(variant.text),
            TWITTER_CHAR_LIMIT,
        )

    try:
        client = _get_twitter_client()
        response = _create_tweet(client, variant.text)
        tweet_id = str(response.data["id"])
        logger.info("Posted variant %s as tweet %s", variant.id[:8], tweet_id)
        return DistributionRecord(
            variant_id=variant.id,
            platform_post_id=tweet_id,
            status="posted",
            posted_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        logger.error("Failed to post variant %s: %s", variant.id[:8], exc)
        return DistributionRecord(
            variant_id=variant.id,
            status="failed",
            error=str(exc),
        )
