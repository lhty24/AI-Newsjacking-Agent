"""Tests for dashboard API client helpers."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.dashboard import api_get, api_post


@pytest.fixture
def mock_response():
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    return resp


# --- api_get ---


@patch("src.dashboard.httpx.Client")
def test_api_get_success(mock_client_cls):
    """api_get returns parsed JSON on success."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"id": "run-1", "status": "completed"}]
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = api_get("/runs")
    assert result == [{"id": "run-1", "status": "completed"}]
    mock_client.get.assert_called_once()


@patch("src.dashboard.httpx.Client")
@patch("src.dashboard.st")
def test_api_get_error_returns_none(mock_st, mock_client_cls):
    """api_get returns None and shows error on failure."""
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = api_get("/runs")
    assert result is None
    mock_st.error.assert_called_once()


@patch("src.dashboard.httpx.Client")
def test_api_get_with_params(mock_client_cls):
    """api_get passes query params to httpx."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = []
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_cls.return_value = mock_client

    api_get("/variants", params={"run_id": "abc"})
    call_args = mock_client.get.call_args
    assert call_args.kwargs.get("params") == {"run_id": "abc"} or call_args[1].get("params") == {"run_id": "abc"}


# --- api_post ---


@patch("src.dashboard.httpx.Client")
def test_api_post_success(mock_client_cls):
    """api_post returns parsed JSON on success."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"run": {"id": "run-1"}, "top_variants": []}
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = api_post("/run")
    assert result == {"run": {"id": "run-1"}, "top_variants": []}


@patch("src.dashboard.httpx.Client")
def test_api_post_with_json_body(mock_client_cls):
    """api_post sends JSON body."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"variant_id": "v1", "status": "pending"}
    mock_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = api_post("/post", json={"variant_id": "v1"})
    assert result["status"] == "pending"
    call_args = mock_client.post.call_args
    assert call_args.kwargs.get("json") == {"variant_id": "v1"} or call_args[1].get("json") == {"variant_id": "v1"}


@patch("src.dashboard.httpx.Client")
@patch("src.dashboard.st")
def test_api_post_error_returns_none(mock_st, mock_client_cls):
    """api_post returns None and shows error on failure."""
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.ConnectError("Connection refused")
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = api_post("/run")
    assert result is None
    mock_st.error.assert_called_once()


@patch("src.dashboard.httpx.Client")
@patch("src.dashboard.st")
def test_api_get_http_error(mock_st, mock_client_cls):
    """api_get handles HTTP errors (4xx/5xx) gracefully."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found",
        request=MagicMock(),
        response=MagicMock(status_code=404),
    )

    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client_cls.return_value = mock_client

    result = api_get("/runs/nonexistent")
    assert result is None
    mock_st.error.assert_called_once()
