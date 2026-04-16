from unittest.mock import MagicMock, patch

import pytest
import tweepy

from src.config import ConfigError
from src.models.content import ContentVariant
from src.models.distribution import DistributionRecord


# --- Fixtures ---


@pytest.fixture
def sample_variant():
    return ContentVariant(
        analysis_id="analysis-123",
        style="analytical",
        text="Bitcoin breaks $100k as ETF inflows surge. Institutional adoption is accelerating.",
        prompt_template="test-template",
    )


@pytest.fixture
def long_variant():
    return ContentVariant(
        analysis_id="analysis-456",
        style="meme",
        text="x" * 300,
        prompt_template="test-template",
    )


def _mock_tweet_response(tweet_id="1234567890"):
    resp = MagicMock()
    resp.data = {"id": tweet_id}
    return resp


# --- Tests ---


@patch("src.modules.distribution.TWITTER_ENABLED", True)
@patch("src.modules.distribution._get_twitter_client")
def test_post_tweet_success(mock_get_client, sample_variant):
    mock_client = MagicMock()
    mock_client.create_tweet.return_value = _mock_tweet_response("9876543210")
    mock_get_client.return_value = mock_client

    from src.modules.distribution import post_tweet

    record = post_tweet(sample_variant)

    assert isinstance(record, DistributionRecord)
    assert record.status == "posted"
    assert record.platform_post_id == "9876543210"
    assert record.posted_at is not None
    assert record.variant_id == sample_variant.id
    assert record.error is None
    mock_client.create_tweet.assert_called_once_with(text=sample_variant.text)


@patch("src.modules.distribution.TWITTER_ENABLED", True)
@patch("src.modules.distribution._get_twitter_client")
def test_post_tweet_failure(mock_get_client, sample_variant):
    mock_client = MagicMock()
    mock_client.create_tweet.side_effect = tweepy.TweepyException("Auth failed")
    mock_get_client.return_value = mock_client

    from src.modules.distribution import post_tweet

    record = post_tweet(sample_variant)

    assert record.status == "failed"
    assert "Auth failed" in record.error
    assert record.platform_post_id is None
    assert record.posted_at is None


@patch("src.modules.distribution.TWITTER_ENABLED", False)
def test_post_tweet_disabled(sample_variant):
    from src.modules.distribution import post_tweet

    record = post_tweet(sample_variant)

    assert record.status == "pending"
    assert record.error == "Twitter disabled"
    assert record.variant_id == sample_variant.id


@patch("src.modules.distribution.TWITTER_ENABLED", True)
@patch("src.modules.distribution._get_twitter_client")
def test_post_tweet_character_limit_warning(mock_get_client, long_variant, caplog):
    mock_client = MagicMock()
    mock_client.create_tweet.return_value = _mock_tweet_response()
    mock_get_client.return_value = mock_client

    import logging

    from src.modules.distribution import post_tweet

    with caplog.at_level(logging.WARNING, logger="src.modules.distribution"):
        record = post_tweet(long_variant)

    assert record.status == "posted"
    assert "exceeds" in caplog.text and "char limit" in caplog.text
    mock_client.create_tweet.assert_called_once()


def test_validate_twitter_config_missing_keys(monkeypatch):
    monkeypatch.setenv("TWITTER_ENABLED", "true")
    monkeypatch.delenv("TWITTER_API_KEY", raising=False)
    monkeypatch.delenv("TWITTER_API_SECRET", raising=False)
    monkeypatch.delenv("TWITTER_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TWITTER_ACCESS_TOKEN_SECRET", raising=False)

    # Re-import to pick up env changes
    from src.config import validate_twitter_config

    # Need to patch the module-level TWITTER_ENABLED since it was read at import time
    with patch("src.config.TWITTER_ENABLED", True):
        with pytest.raises(ConfigError, match="missing credentials"):
            validate_twitter_config()
