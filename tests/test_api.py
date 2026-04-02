from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app, _runs, _variants
from src.models.content import ContentVariant
from src.models.news import NewsItem
from src.models.pipeline import PipelineRun


@pytest.fixture(autouse=True)
def clear_stores():
    """Reset in-memory stores between tests."""
    _runs.clear()
    _variants.clear()
    yield
    _runs.clear()
    _variants.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_news_items():
    return [
        NewsItem(
            source="coingecko:cointelegraph",
            title="Bitcoin breaks $100k",
            content="Bitcoin breaks $100k on ETF inflows.",
            published_at="2025-01-15T10:00:00Z",
            tickers=["BTC"],
        ),
        NewsItem(
            source="coingecko:decrypt",
            title="Ethereum upgrades staking",
            content="Ethereum staking rewards increase.",
            published_at="2025-01-15T11:00:00Z",
            tickers=["ETH"],
        ),
    ]


@pytest.fixture
def sample_variant():
    return ContentVariant(
        analysis_id="analysis-1",
        style="analytical",
        text="BTC breaks $100k — institutional ETF inflows accelerating.",
        prompt_template="analytical_v1",
        score=8.5,
    )


@pytest.fixture
def sample_run(sample_variant):
    run = PipelineRun(trigger="api", status="completed", news_count=1, variants_generated=3)
    return run, [sample_variant]


# --- GET /news ---


def test_get_news(client, sample_news_items):
    with patch("src.api.app.fetch_news", return_value=sample_news_items):
        resp = client.get("/news")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["title"] == "Bitcoin breaks $100k"


def test_get_news_empty(client):
    with patch("src.api.app.fetch_news", return_value=[]):
        resp = client.get("/news")
    assert resp.status_code == 200
    assert resp.json() == []


# --- POST /run ---


def test_post_run(client, sample_run):
    run, variants = sample_run
    with patch("src.api.app.run_pipeline", return_value=(run, variants)):
        resp = client.post("/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run"]["status"] == "completed"
    assert len(data["top_variants"]) == 1


def test_post_run_stores_results(client, sample_run):
    run, variants = sample_run
    with patch("src.api.app.run_pipeline", return_value=(run, variants)):
        client.post("/run")
    resp = client.get("/runs")
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == run.id


# --- GET /runs ---


def test_get_runs_empty(client):
    resp = client.get("/runs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_runs_limit(client, sample_variant):
    for i in range(3):
        run = PipelineRun(trigger="api", status="completed")
        _runs.append(run)
    resp = client.get("/runs", params={"limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# --- POST /post ---


def test_post_post_found(client, sample_variant):
    _variants.append(sample_variant)
    resp = client.post("/post", json={"variant_id": sample_variant.id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["variant_id"] == sample_variant.id
    assert data["status"] == "pending"


def test_post_post_not_found(client):
    resp = client.post("/post", json={"variant_id": "nonexistent-id"})
    assert resp.status_code == 404


# --- POST /post/batch ---


def test_post_batch_all_found(client, sample_variant):
    v2 = ContentVariant(
        analysis_id="analysis-2",
        style="meme",
        text="BTC 100K WE ARE SO BACK",
        prompt_template="meme_v1",
        score=7.0,
    )
    _variants.extend([sample_variant, v2])
    resp = client.post("/post/batch", json={"variant_ids": [sample_variant.id, v2.id]})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 2
    assert all(r["status"] == "pending" for r in results)


def test_post_batch_partial(client, sample_variant):
    _variants.append(sample_variant)
    resp = client.post("/post/batch", json={"variant_ids": [sample_variant.id, "bogus-id"]})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 2
    assert results[0]["status"] == "pending"
    assert results[1]["status"] == "failed"
    assert "not found" in results[1]["error"]


def test_post_batch_empty(client):
    resp = client.post("/post/batch", json={"variant_ids": []})
    assert resp.status_code == 200
    assert resp.json()["results"] == []
