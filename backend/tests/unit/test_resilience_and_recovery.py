"""Master Test Suite: Platform Resilience, Fault-Tolerance & State Recovery.

Validates the 5 critical production hardening requirements:
1. Client-Side HTTP Rate Limiting & Backoff (429)
2. Automatic Retries on HTTP 500 & 503 Errors
3. Order Timeout "Query-Before-Retry" Loop
4. Idempotent Order Placement (Headers & Local Dedup Ledger)
5. Mid-Trade Server Restart: Position Re-Hydration from Database
"""

import asyncio
from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from app.broker.api_021 import Broker021
from app.broker.errors import BrokerRateLimitError, BrokerServerError, BrokerTimeoutError
from app.broker.mock_021 import Mock021
from app.broker.models import BrokerOrder, OrderPlacementRequest, TradeFill
from app.core.config import Settings
from app.core.enums import Book, BrokerOrderStatus, Exchange, Product, Side, Validity
from app.database.models.models import OrderRecord, StrategyRecord, TradeFillRecord
from app.database.session import AsyncSessionLocal, init_db
from app.execution.engine import ExecutionEngine
from app.market_data.instruments import InstrumentInfo
from app.recovery.service import RecoveryService
from app.risk.engine import RiskEngine
from app.strategies.intents import OrderIntent
from app.strategies.manager import StrategyManager
from app.strategies.time_based import TimeBasedStrategy


# ==============================================================================
# Condition 1: Client-Side HTTP Rate Limiting & Backoff (429)
# ==============================================================================
@pytest.mark.asyncio
async def test_condition_1_rate_limiting_and_429_backoff():
    """Requirement 1: Client-Side HTTP Rate Limiting & Backoff (429).

    Validates that:
    1. The client-side token bucket rate limiter intercepts and throttles calls.
    2. When the broker responds with HTTP 429, the client parses Retry-After,
       backs off, retries the request, and succeeds on the subsequent attempt.
    3. When 429 persists beyond max retries, BrokerRateLimitError is raised.
    """
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        # 1. Auth endpoint
        if request.url.path == "/api/v1/auth/token":
            return httpx.Response(
                200,
                json={"success": True, "data": {"accessToken": "tok_1", "expiresAt": "2030-01-01T00:00:00Z"}},
            )
        # 2. Orders endpoint: Return 429 with Retry-After header on first call, 200 on retry
        if request.url.path == "/api/v1/orders":
            if attempts == 2:  # First /orders call
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0.1"},
                    json={"success": False, "error": "Rate limit exceeded: 10 req/s"},
                )
            else:  # Second /orders call
                return httpx.Response(
                    200,
                    json={"success": True, "data": {"orderId": "ord_after_429", "status": "PLACED"}},
                )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test_021")
    settings = Settings(api_ucc="HACK_429", api_password="pass")
    broker = Broker021(settings=settings)
    broker.base_url = "http://test_021/api/v1"
    broker._client = client

    # Spy on the rate limiter to verify client-side throttle acquisition
    with patch.object(broker._rate_limiter, "acquire", wraps=broker._rate_limiter.acquire) as spy_limiter:
        resp = await broker._request(
            "POST",
            "/orders",
            json={"symbol": "TCS", "qty": 1},
            max_rate_limit_retries=2,
        )

    # Verifications:
    assert resp.status_code == 200
    assert resp.json()["data"]["orderId"] == "ord_after_429"
    # Token bucket was acquired on both attempts
    assert spy_limiter.call_count == 2
    # Total attempts = 1 auth + 2 order calls (initial 429 + successful retry)
    assert attempts == 3

    # Verification 1B: Persistent 429 exhausts retries and raises BrokerRateLimitError
    def persistent_429_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/token":
            return httpx.Response(200, json={"success": True, "data": {"accessToken": "tok_1", "expiresAt": "2030-01-01T00:00:00Z"}})
        return httpx.Response(429, headers={"Retry-After": "0.05"}, json={"success": False, "error": "Persistent 429"})

    broker._client = httpx.AsyncClient(transport=httpx.MockTransport(persistent_429_handler), base_url="http://test_021")
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(BrokerRateLimitError) as exc_info:
            await broker._request("POST", "/orders", json={"symbol": "TCS"}, max_rate_limit_retries=2)
    assert exc_info.value.status_code == 429


# ==============================================================================
# Condition 2: Automatic Retries on HTTP 500 & 503 Errors
# ==============================================================================
@pytest.mark.asyncio
async def test_condition_2_retries_on_http_500_and_503_errors():
    """Requirement 2: Automatic Retries on HTTP 500 & 503 Errors.

    Validates that:
    1. Broker021._request() catches 500 and 503 transient server errors.
    2. Performs exponential backoff retry loop without crashing.
    3. Successfully recovers and returns 200 once the server recovers.
    4. If the server remains down after max retries, raises BrokerServerError.
    """
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if request.url.path == "/api/v1/auth/token":
            return httpx.Response(200, json={"success": True, "data": {"accessToken": "tok_500", "expiresAt": "2030-01-01T00:00:00Z"}})
        if request.url.path == "/api/v1/orders":
            if attempts == 2:
                return httpx.Response(500, json={"success": False, "error": "Internal Server Error"})
            elif attempts == 3:
                return httpx.Response(503, json={"success": False, "error": "Service Unavailable"})
            else:
                return httpx.Response(200, json={"success": True, "data": {"orderId": "ord_500_recovered", "status": "PLACED"}})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test_021")
    settings = Settings(api_ucc="HACK_500", api_password="pass")
    broker = Broker021(settings=settings)
    broker.base_url = "http://test_021/api/v1"
    broker._client = client

    # Mock asyncio.sleep to verify exponential backoff is triggered without slowing down tests
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        resp = await broker._request(
            "POST",
            "/orders",
            json={"symbol": "INFY", "qty": 5},
            max_server_retries=3,
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["orderId"] == "ord_500_recovered"
    # Backoff sleep was called for the 500 and the 503 retries
    assert mock_sleep.call_count == 2
    assert attempts == 4  # 1 auth + attempt 0 (500) + attempt 1 (503) + attempt 2 (200)

    # Verification 2B: Persistent 500 raises BrokerServerError after retries exhausted
    def persistent_500_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/token":
            return httpx.Response(200, json={"success": True, "data": {"accessToken": "tok_1", "expiresAt": "2030-01-01T00:00:00Z"}})
        return httpx.Response(500, json={"success": False, "error": "Database Crash"})

    broker._client = httpx.AsyncClient(transport=httpx.MockTransport(persistent_500_handler), base_url="http://test_021")
    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(BrokerServerError) as exc_info:
            await broker._request("POST", "/orders", json={"symbol": "INFY"}, max_server_retries=2)
    assert exc_info.value.status_code == 500


# ==============================================================================
# Condition 3: Order Timeout "Query-Before-Retry" Loop
# ==============================================================================
@pytest.mark.asyncio
async def test_condition_3_order_timeout_query_before_retry_loop():
    """Requirement 3: Order Timeout 'Query-Before-Retry' Loop.

    Validates that:
    1. When place_order suffers a network timeout (httpx.TimeoutException / BrokerTimeoutError),
       the ExecutionEngine does NOT blindly declare failure or duplicate orders.
    2. PATH A (Order accepted by broker before timeout): ExecutionEngine queries
       broker.get_order(client_order_id) / get_orders(), detects that the broker
       actually executed the order, recovers the state, routes fills to strategy,
       and returns the recovered OrderPlacementResponse successfully.
    3. PATH B (Order absent from broker): If query confirms the order never reached
       the broker, ExecutionEngine safely releases in-flight risk reservations
       and raises BrokerTimeoutError.
    """
    # ── PATH A: Order reached broker before timeout ──
    class TimeoutAfterAcceptBroker(Mock021):
        """Simulates socket disconnect after broker successfully placed order."""

        async def place_order(self, request: OrderPlacementRequest):
            # 1. Place order internally at broker
            resp = await super().place_order(request)
            # 2. Simulate socket timeout on the HTTP response journey back to client
            raise BrokerTimeoutError("ReadTimeout: Connection reset by peer after order processing")

    broker_a = TimeoutAfterAcceptBroker()
    broker_a.reset()
    risk_engine_a = RiskEngine()
    manager_a = StrategyManager()

    strat_a = TimeBasedStrategy(strategy_id="s_qbr_recovery", symbol="RELIANCE", quantity=10)
    manager_a.register_strategy(strat_a)
    manager_a.start_all()

    exec_engine_a = ExecutionEngine(strategy_manager=manager_a, risk_engine=risk_engine_a, broker=broker_a)

    intent_a = OrderIntent(
        intent_id="intent_qbr_accepted_1",
        strategy_id="s_qbr_recovery",
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=10,
    )

    # Execute intent: should encounter timeout but RECOVER via Query-Before-Retry loop
    risk_res_a, order_res_a = await exec_engine_a.execute_intent(intent_a)

    assert risk_res_a.passed is True
    assert order_res_a is not None
    assert "Query-Before-Retry" in order_res_a.message
    # Strategy position received the recovered order's fill
    assert strat_a.get_position("RELIANCE") == 10
    # In-flight quantity properly released after recovery
    assert risk_engine_a.get_inflight_quantity("s_qbr_recovery", "RELIANCE") == 0

    # ── PATH B: Order never reached broker (confirmed absent) ──
    broker_b = Mock021()
    broker_b.reset()
    risk_engine_b = RiskEngine()
    manager_b = StrategyManager()

    strat_b = TimeBasedStrategy(strategy_id="s_qbr_absent", symbol="TCS", quantity=5)
    manager_b.register_strategy(strat_b)
    manager_b.start_all()

    exec_engine_b = ExecutionEngine(strategy_manager=manager_b, risk_engine=risk_engine_b, broker=broker_b)

    intent_b = OrderIntent(
        intent_id="intent_qbr_absent_2",
        strategy_id="s_qbr_absent",
        symbol="TCS",
        side=Side.BUY,
        quantity=5,
    )

    # Injected timeout BEFORE order creation
    broker_b.simulate_timeout("Connection timed out connecting to 021 gateway")

    with pytest.raises(BrokerTimeoutError):
        await exec_engine_b.execute_intent(intent_b)

    # Confirmed absent: in-flight reservation safely released
    assert risk_engine_b.get_inflight_quantity("s_qbr_absent", "TCS") == 0
    assert strat_b.get_position("TCS") == 0


# ==============================================================================
# Condition 4: Idempotent Order Placement (Headers & Platform Dedup Ledger)
# ==============================================================================
@pytest.mark.asyncio
async def test_condition_4_idempotent_order_placement_deduplication():
    """Requirement 4: Idempotent Order Placement.

    Validates that:
    1. Broker021.place_order transmits X-Idempotency-Key header and clientOrderId payload.
    2. Platform-level ExecutionEngine enforces a TTL-based deduplication ledger:
       Submitting an identical intent_id twice returns the cached result without
       creating a duplicate order at the broker or doubling strategy position.
    """
    # ── Layer 1: Broker HTTP Wire Protocol Verification ──
    captured_headers = {}
    captured_payload = {}

    def wire_handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers, captured_payload
        if request.url.path == "/api/v1/auth/token":
            return httpx.Response(200, json={"success": True, "data": {"accessToken": "tok_wire", "expiresAt": "2030-01-01T00:00:00Z"}})
        if request.url.path == "/api/v1/orders":
            captured_headers = dict(request.headers)
            captured_payload = json.loads(request.content)
            return httpx.Response(200, json={"success": True, "data": {"orderId": "ord_wire_ok", "status": "PLACED"}})
        return httpx.Response(404)

    wire_client = httpx.AsyncClient(transport=httpx.MockTransport(wire_handler), base_url="http://test_021")
    settings = Settings(api_ucc="HACK_IDEM", api_password="pass")
    broker_wire = Broker021(settings=settings)
    broker_wire.base_url = "http://test_021/api/v1"
    broker_wire._client = wire_client

    # Populate registry cache for INFY
    broker_wire.registry._by_symbol_exchange[("INFY", "NSE")] = InstrumentInfo(
        token=1594, exchange="NSE", symbol="INFY", instrument_type="EQ",
        tick_size_paise=5, lot_size=1, freeze_quantity=5000,
        lower_circuit_paise=0, upper_circuit_paise=0, isin="INE009A01021",
    )

    wire_req = OrderPlacementRequest(
        client_order_id="c_idem_unique_999",
        symbol="INFY",
        exchange=Exchange.NSE,
        side=Side.BUY,
        quantity=8,
        price_paise=150000,
        product=Product.INTRADAY,
        book=Book.RL,
        validity=Validity.DAY,
    )
    wire_resp = await broker_wire.place_order(wire_req)

    assert wire_resp.order_id == "ord_wire_ok"
    # HTTP Idempotency header must match client_order_id
    assert captured_headers.get("x-idempotency-key") == "c_idem_unique_999"
    # Payload clientOrderId must match client_order_id
    assert captured_payload.get("clientOrderId") == "c_idem_unique_999"

    # ── Layer 2: Platform ExecutionEngine Local Dedup Ledger Verification ──
    mock_broker = Mock021()
    mock_broker.reset()
    risk_engine = RiskEngine()
    manager = StrategyManager()

    strat = TimeBasedStrategy(strategy_id="s_idem_engine", symbol="INFY", quantity=8)
    manager.register_strategy(strat)
    manager.start_all()

    exec_engine = ExecutionEngine(strategy_manager=manager, risk_engine=risk_engine, broker=mock_broker)

    intent = OrderIntent(
        intent_id="intent_duplicate_guard_123",
        strategy_id="s_idem_engine",
        symbol="INFY",
        side=Side.BUY,
        quantity=8,
    )

    # First call: normal placement
    risk_1, order_1 = await exec_engine.execute_intent(intent)
    assert risk_1.passed is True
    assert order_1 is not None
    assert strat.get_position("INFY") == 8
    orders_count_1 = len(await mock_broker.get_orders())
    assert orders_count_1 == 1

    # Second call (immediate retry with SAME intent_id)
    risk_2, order_2 = await exec_engine.execute_intent(intent)
    assert risk_2.passed is True
    assert order_2 is not None
    assert order_2.order_id == order_1.order_id

    # CRITICAL: Broker was NOT called again; still only 1 order in broker
    orders_count_2 = len(await mock_broker.get_orders())
    assert orders_count_2 == 1
    # Strategy position remains exactly 8 (NOT doubled to 16)
    assert strat.get_position("INFY") == 8


# ==============================================================================
# Condition 5: Mid-Trade Server Restart: Position Re-Hydration
# ==============================================================================
@pytest.mark.asyncio
async def test_condition_5_mid_trade_server_restart_position_rehydration():
    """Requirement 5: Mid-Trade Server Restart: Position Re-Hydration.

    Validates that:
    1. During intraday trading, fills and orders are persisted in the database.
    2. On a complete server reboot, running strategies start with fresh in-memory
       state (positions = 0, fills = 0, P&L = 0).
    3. RecoveryService.reconcile_state() replays today's TradeFillRecord rows
       chronologically, rebuilding in-memory positions, fills, and realized P&L.
    4. Compares restored state against broker positions, confirming 0 discrepancies.
    """
    await init_db()

    now = datetime.now(timezone.utc)
    strat_id = f"s_midtrade_{int(now.timestamp())}"
    ord1_id = f"ord_buy_{int(now.timestamp())}"
    ord2_id = f"ord_sell_{int(now.timestamp())}"

    # 1. Simulate intraday DB persistence prior to server reboot:
    #    Fill 1: BUY 15 SBIN @ ₹700 (70,000 paise)
    #    Fill 2: SELL 5 SBIN @ ₹720 (72,000 paise) -> Profit = 5 * ₹20 = ₹100 (10,000 paise)
    #    Net Expected Position = 10 SBIN
    async with AsyncSessionLocal() as session:
        strat_record = StrategyRecord(
            id=strat_id,
            name="Mid-Trade Server Reboot Test",
            symbol="SBIN",
            status="RUNNING",
        )
        session.add(strat_record)

        o1 = OrderRecord(
            id=ord1_id,
            client_order_id=ord1_id,
            strategy_id=strat_id,
            symbol="SBIN",
            side="BUY",
            quantity=15,
            price_paise=70000,
            status="EXECUTED",
            created_at=now,
        )
        o2 = OrderRecord(
            id=ord2_id,
            client_order_id=ord2_id,
            strategy_id=strat_id,
            symbol="SBIN",
            side="SELL",
            quantity=5,
            price_paise=72000,
            status="EXECUTED",
            created_at=now,
        )
        session.add(o1)
        session.add(o2)

        f1 = TradeFillRecord(
            order_id=ord1_id,
            strategy_id=strat_id,
            symbol="SBIN",
            side="BUY",
            quantity=15,
            price_paise=70000,
            brokerage_paise=2000,
            fee_paise=500,
            timestamp=now,
        )
        f2 = TradeFillRecord(
            order_id=ord2_id,
            strategy_id=strat_id,
            symbol="SBIN",
            side="SELL",
            quantity=5,
            price_paise=72000,
            brokerage_paise=2000,
            fee_paise=500,
            timestamp=now,
        )
        session.add(f1)
        session.add(f2)
        await session.commit()

    # 2. Broker has real net position of 10 SBIN
    broker = Mock021()
    broker.reset()
    await broker.place_order(OrderPlacementRequest(symbol="SBIN", side=Side.BUY, quantity=10, price_paise=70000))

    risk_engine = RiskEngine()
    manager = StrategyManager()

    # 3. Simulate fresh server reboot: Strategy in-memory starts FLAT (0 positions)
    strat = TimeBasedStrategy(strategy_id=strat_id, symbol="SBIN")
    manager.register_strategy(strat)
    strat.start()

    assert strat.get_position("SBIN") == 0
    assert len(strat.fills) == 0
    assert strat.realized_pnl_paise == 0

    # 4. RecoveryService runs startup reconciliation
    recovery = RecoveryService(strategy_manager=manager, risk_engine=risk_engine, broker=broker)
    report = await recovery.reconcile_state()

    # 5. Verification of state recovery
    assert report.reconciled_successfully is True
    assert strat_id in report.rehydrated_strategies
    assert report.rehydrated_fills_count >= 2
    # In-memory positions restored from 0 to 10
    assert strat.get_position("SBIN") == 10
    # Both fills restored in-memory
    assert len(strat.fills) == 2
    # Realized P&L restored (5 * 2000 paise = 10,000 paise)
    assert strat.realized_pnl_paise == 10000
    # Perfect alignment with broker positions (0 drift)
    assert len(report.discrepancies_detected) == 0
