import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from app.broker.api_021 import AsyncTokenBucket, Broker021
from app.broker.errors import BrokerRateLimitError


@pytest.mark.asyncio
async def test_token_bucket_acquire_immediate():
    """Verify bucket permits requests immediately when tokens are available."""
    bucket = AsyncTokenBucket(rate=10.0, capacity=5.0)
    start = time.monotonic()
    await bucket.acquire(1.0)
    await bucket.acquire(1.0)
    elapsed = time.monotonic() - start
    # Should take less than 50ms since tokens were in bucket
    assert elapsed < 0.05
    assert bucket.tokens <= 3.05


@pytest.mark.asyncio
async def test_token_bucket_throttle_pacing():
    """Verify bucket throttles when capacity is exhausted."""
    # 20 tokens per second -> 0.05s per token
    bucket = AsyncTokenBucket(rate=20.0, capacity=1.0)
    await bucket.acquire(1.0)  # Empties the bucket

    start = time.monotonic()
    await bucket.acquire(1.0)  # Must wait for refill
    elapsed = time.monotonic() - start

    assert elapsed >= 0.04  # Waited at least ~40-50ms


@pytest.mark.asyncio
async def test_broker_021_retries_on_429():
    """Verify Broker021._request retries on 429 and succeeds on next attempt."""
    broker = Broker021()
    broker.get_valid_token = AsyncMock(return_value="mock_jwt_token")

    # Mock 1st call = 429 with Retry-After 0.01, 2nd call = 200 OK
    resp_429 = httpx.Response(
        status_code=429,
        headers={"Retry-After": "0.01"},
        json={"error": "Too Many Requests"},
        request=httpx.Request("GET", "http://test/v1/orders"),
    )
    resp_200 = httpx.Response(
        status_code=200,
        json={"success": True, "data": []},
        request=httpx.Request("GET", "http://test/v1/orders"),
    )

    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_client.request = AsyncMock(side_effect=[resp_429, resp_200])
    broker._client = mock_client

    res = await broker._request("GET", "/orders", max_rate_limit_retries=2)
    assert res.status_code == 200
    assert mock_client.request.call_count == 2
    await broker.close()


@pytest.mark.asyncio
async def test_broker_021_exhausts_429_retries():
    """Verify Broker021._request raises BrokerRateLimitError when retries are exhausted."""
    broker = Broker021()
    broker.get_valid_token = AsyncMock(return_value="mock_jwt_token")

    resp_429 = httpx.Response(
        status_code=429,
        headers={"Retry-After": "0.01"},
        json={"error": "Rate limit exceeded"},
        request=httpx.Request("GET", "http://test/v1/orders"),
    )

    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_client.request = AsyncMock(return_value=resp_429)
    broker._client = mock_client

    with pytest.raises(BrokerRateLimitError) as exc_info:
        await broker._request("GET", "/orders", max_rate_limit_retries=2)

    assert exc_info.value.status_code == 429
    assert mock_client.request.call_count == 3  # 1 initial + 2 retries
    await broker.close()
