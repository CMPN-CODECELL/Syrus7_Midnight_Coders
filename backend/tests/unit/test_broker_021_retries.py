import asyncio
from datetime import datetime, timezone
import pytest
import httpx
from app.broker.api_021 import Broker021
from app.broker.errors import BrokerServerError, BrokerRateLimitError
from app.core.config import Settings


@pytest.mark.asyncio
async def test_broker_021_retries_on_500_and_503_success():
    """Verify that Broker021 retries on 500 and 503 errors and succeeds when a subsequent attempt returns 200."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if request.url.path == "/api/v1/auth/token":
            return httpx.Response(200, json={"success": True, "data": {"accessToken": "fake_token_123", "expiresAt": "2030-01-01T00:00:00Z"}})
        
        if request.url.path == "/api/v1/orders":
            if attempts == 2:  # First order request -> 500
                return httpx.Response(500, json={"success": False, "error": "Internal Server Error"})
            elif attempts == 3:  # Second order request -> 503
                return httpx.Response(503, json={"success": False, "error": "Service Unavailable"})
            else:  # Third order request -> 200 Success
                return httpx.Response(200, json={"success": True, "data": {"orderId": "ord_retry_123", "status": "PENDING"}})
        
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://test_021")

    settings = Settings(api_ucc="HACK342", api_password="test_password")
    broker = Broker021(settings=settings)
    broker.base_url = "http://test_021/api/v1"
    broker._client = client

    resp = await broker._request("POST", "/orders", json={"symbol": "RELIANCE", "qty": 1}, max_server_retries=3)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["orderId"] == "ord_retry_123"
    assert attempts == 4  # 1 auth + 3 order attempts


@pytest.mark.asyncio
async def test_broker_021_retries_exhausted_raises_server_error():
    """Verify that Broker021 raises BrokerServerError after retries are exhausted on persistent 500/503."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if request.url.path == "/api/v1/auth/token":
            return httpx.Response(200, json={"success": True, "data": {"accessToken": "fake_token_123", "expiresAt": "2030-01-01T00:00:00Z"}})
        
        if request.url.path == "/api/v1/orders":
            return httpx.Response(503, json={"success": False, "error": "Persistent Outage"})
        
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://test_021")

    settings = Settings(api_ucc="HACK342", api_password="test_password")
    broker = Broker021(settings=settings)
    broker.base_url = "http://test_021/api/v1"
    broker._client = client

    with pytest.raises(BrokerServerError) as exc:
        await broker._request("POST", "/orders", json={"symbol": "RELIANCE", "qty": 1}, max_server_retries=2)

    assert exc.value.status_code == 503
    assert attempts == 4  # 1 auth + 3 order attempts (attempt 0, 1, 2)


@pytest.mark.asyncio
async def test_broker_021_sends_idempotency_header_and_payload():
    """Verify that Broker021.place_order includes X-Idempotency-Key header and clientOrderId in JSON payload."""
    import json
    captured_headers = {}
    captured_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers, captured_payload
        if request.url.path == "/api/v1/auth/token":
            return httpx.Response(200, json={"success": True, "data": {"accessToken": "fake_token_123", "expiresAt": "2030-01-01T00:00:00Z"}})

        if request.url.path == "/api/v1/orders":
            captured_headers = dict(request.headers)
            captured_payload = json.loads(request.content)
            return httpx.Response(200, json={"success": True, "data": {"orderId": "ord_idem_999", "status": "PLACED"}})

        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://test_021")

    settings = Settings(api_ucc="HACK342", api_password="test_password")
    broker = Broker021(settings=settings)
    broker.base_url = "http://test_021/api/v1"
    broker._client = client

    from app.market_data.instruments import InstrumentInfo
    from app.broker.models import OrderPlacementRequest
    from app.core.enums import Exchange, Side, Product, Book, Validity

    info = InstrumentInfo(
        token=2885,
        exchange="NSE",
        symbol="RELIANCE",
        instrument_type="EQ",
        tick_size_paise=5,
        lot_size=1,
        freeze_quantity=10000,
        lower_circuit_paise=0,
        upper_circuit_paise=0,
        isin="INE002A01018",
    )
    broker.registry._by_symbol_exchange[("RELIANCE", "NSE")] = info

    req = OrderPlacementRequest(
        client_order_id="client_idem_12345",
        symbol="RELIANCE",
        exchange=Exchange.NSE,
        side=Side.BUY,
        quantity=10,
        price_paise=250000,
        product=Product.INTRADAY,
        book=Book.RL,
        validity=Validity.DAY,
    )

    resp = await broker.place_order(req)
    assert resp.order_id == "ord_idem_999"
    assert captured_headers.get("x-idempotency-key") == "client_idem_12345"
    assert captured_payload.get("clientOrderId") == "client_idem_12345"

