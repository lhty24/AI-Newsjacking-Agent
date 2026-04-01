from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models import (
    AnalysisResult,
    ContentVariant,
    DistributionRecord,
    NewsItem,
    PipelineRun,
)


# --- Fixtures ---


@pytest.fixture
def sample_news_item():
    return NewsItem(
        source="coindesk",
        title="Bitcoin hits new high",
        content="Bitcoin surged past $100k today amid institutional buying.",
        published_at=datetime(2026, 3, 15, tzinfo=timezone.utc),
        tickers=["BTC"],
    )


@pytest.fixture
def sample_analysis(sample_news_item):
    return AnalysisResult(
        news_item_id=sample_news_item.id,
        sentiment="bullish",
        topics=["BTC", "ETF"],
        summary="Bitcoin surges on institutional demand.",
        signal="breakout potential",
    )


@pytest.fixture
def sample_variant(sample_analysis):
    return ContentVariant(
        analysis_id=sample_analysis.news_item_id,
        style="analytical",
        text="BTC just broke $100k. Institutional flows are accelerating.",
        prompt_template="analytical_v1",
    )


# --- NewsItem ---


class TestNewsItem:
    def test_create_with_required_fields(self, sample_news_item):
        assert sample_news_item.source == "coindesk"
        assert sample_news_item.title == "Bitcoin hits new high"
        assert sample_news_item.tickers == ["BTC"]

    def test_id_auto_generated(self, sample_news_item):
        assert sample_news_item.id is not None
        assert len(sample_news_item.id) == 36  # UUID format

    def test_fetched_at_auto_populated(self, sample_news_item):
        assert sample_news_item.fetched_at is not None
        assert sample_news_item.fetched_at.tzinfo is not None

    def test_url_optional(self, sample_news_item):
        assert sample_news_item.url is None

    def test_url_accepts_value(self):
        item = NewsItem(
            source="mock",
            title="Test",
            content="Test content",
            published_at=datetime.now(timezone.utc),
            tickers=["ETH"],
            url="https://example.com/article",
        )
        assert item.url == "https://example.com/article"

    def test_unique_ids(self):
        a = NewsItem(
            source="mock",
            title="A",
            content="A",
            published_at=datetime.now(timezone.utc),
            tickers=[],
        )
        b = NewsItem(
            source="mock",
            title="B",
            content="B",
            published_at=datetime.now(timezone.utc),
            tickers=[],
        )
        assert a.id != b.id

    def test_model_dump(self, sample_news_item):
        data = sample_news_item.model_dump()
        assert isinstance(data, dict)
        assert "id" in data
        assert "source" in data
        assert "tickers" in data

    def test_json_round_trip(self, sample_news_item):
        json_str = sample_news_item.model_dump_json()
        restored = NewsItem.model_validate_json(json_str)
        assert restored.id == sample_news_item.id
        assert restored.title == sample_news_item.title
        assert restored.tickers == sample_news_item.tickers


# --- AnalysisResult ---


class TestAnalysisResult:
    def test_create_bullish(self, sample_analysis):
        assert sample_analysis.sentiment == "bullish"
        assert sample_analysis.topics == ["BTC", "ETF"]

    def test_create_bearish(self):
        a = AnalysisResult(
            news_item_id="abc",
            sentiment="bearish",
            topics=["ETH"],
            summary="Ethereum drops.",
            signal="sell pressure",
        )
        assert a.sentiment == "bearish"

    def test_create_neutral(self):
        a = AnalysisResult(
            news_item_id="abc",
            sentiment="neutral",
            topics=[],
            summary="Nothing happened.",
            signal="flat",
        )
        assert a.sentiment == "neutral"

    def test_invalid_sentiment_rejected(self):
        with pytest.raises(ValidationError):
            AnalysisResult(
                news_item_id="abc",
                sentiment="invalid",
                topics=[],
                summary="Test",
                signal="test",
            )

    def test_analyzed_at_auto_populated(self, sample_analysis):
        assert sample_analysis.analyzed_at is not None
        assert sample_analysis.analyzed_at.tzinfo is not None

    def test_json_round_trip(self, sample_analysis):
        json_str = sample_analysis.model_dump_json()
        restored = AnalysisResult.model_validate_json(json_str)
        assert restored.sentiment == sample_analysis.sentiment
        assert restored.news_item_id == sample_analysis.news_item_id


# --- ContentVariant ---


class TestContentVariant:
    def test_create_with_defaults(self, sample_variant):
        assert sample_variant.style == "analytical"
        assert sample_variant.score is None
        assert sample_variant.score_breakdown is None

    def test_valid_styles(self):
        for style in ["analytical", "meme", "contrarian"]:
            v = ContentVariant(
                analysis_id="abc",
                style=style,
                text="Test",
                prompt_template="tpl",
            )
            assert v.style == style

    def test_invalid_style_rejected(self):
        with pytest.raises(ValidationError):
            ContentVariant(
                analysis_id="abc",
                style="unknown",
                text="Test",
                prompt_template="tpl",
            )

    def test_score_breakdown_accepts_dict(self):
        v = ContentVariant(
            analysis_id="abc",
            style="meme",
            text="To the moon!",
            prompt_template="meme_v1",
            score=8.2,
            score_breakdown={
                "hook_strength": 9,
                "clarity": 7,
                "engagement": 9,
                "relevance": 8,
            },
        )
        assert v.score == 8.2
        assert v.score_breakdown["hook_strength"] == 9

    def test_id_auto_generated(self, sample_variant):
        assert len(sample_variant.id) == 36

    def test_json_round_trip(self, sample_variant):
        json_str = sample_variant.model_dump_json()
        restored = ContentVariant.model_validate_json(json_str)
        assert restored.id == sample_variant.id
        assert restored.style == sample_variant.style


# --- DistributionRecord ---


class TestDistributionRecord:
    def test_create_with_defaults(self):
        r = DistributionRecord(variant_id="v1")
        assert r.status == "pending"
        assert r.platform == "twitter"
        assert r.platform_post_id is None
        assert r.posted_at is None
        assert r.error is None

    def test_create_posted(self):
        r = DistributionRecord(
            variant_id="v1",
            status="posted",
            platform_post_id="1234567890",
            posted_at=datetime.now(timezone.utc),
        )
        assert r.status == "posted"
        assert r.platform_post_id == "1234567890"

    def test_create_failed(self):
        r = DistributionRecord(
            variant_id="v1",
            status="failed",
            error="Rate limit exceeded",
        )
        assert r.status == "failed"
        assert r.error == "Rate limit exceeded"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            DistributionRecord(variant_id="v1", status="invalid")

    def test_id_auto_generated(self):
        r = DistributionRecord(variant_id="v1")
        assert len(r.id) == 36

    def test_json_round_trip(self):
        r = DistributionRecord(variant_id="v1", status="posted")
        json_str = r.model_dump_json()
        restored = DistributionRecord.model_validate_json(json_str)
        assert restored.variant_id == r.variant_id
        assert restored.status == r.status


# --- PipelineRun ---


class TestPipelineRun:
    def test_create_with_defaults(self):
        run = PipelineRun(trigger="cli")
        assert run.status == "running"
        assert run.news_count == 0
        assert run.variants_generated == 0
        assert run.variants_posted == 0
        assert run.completed_at is None
        assert run.error is None

    def test_valid_triggers(self):
        for trigger in ["cli", "api", "scheduler"]:
            run = PipelineRun(trigger=trigger)
            assert run.trigger == trigger

    def test_invalid_trigger_rejected(self):
        with pytest.raises(ValidationError):
            PipelineRun(trigger="webhook")

    def test_started_at_auto_populated(self):
        run = PipelineRun(trigger="cli")
        assert run.started_at is not None
        assert run.started_at.tzinfo is not None

    def test_id_auto_generated(self):
        run = PipelineRun(trigger="api")
        assert len(run.id) == 36

    def test_model_copy_update(self):
        run = PipelineRun(trigger="cli")
        completed = run.model_copy(
            update={
                "status": "completed",
                "completed_at": datetime.now(timezone.utc),
                "news_count": 5,
                "variants_generated": 15,
                "variants_posted": 3,
            }
        )
        assert completed.status == "completed"
        assert completed.news_count == 5
        assert completed.id == run.id  # same run

    def test_json_round_trip(self):
        run = PipelineRun(trigger="scheduler")
        json_str = run.model_dump_json()
        restored = PipelineRun.model_validate_json(json_str)
        assert restored.trigger == run.trigger
        assert restored.id == run.id
