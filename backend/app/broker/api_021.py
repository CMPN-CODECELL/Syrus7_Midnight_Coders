import asyncio
from datetime import datetime, timezone
import logging
import random
import time
from typing import Any, Optional
import httpx

from app.broker.errors import (
    BrokerAuthExpiredError,
    BrokerBadRequestError,
    BrokerError,
    BrokerRateLimitError,
    BrokerRiskRejectedError,
    BrokerSafeModeError,
    BrokerServerError,
    BrokerTimeoutError,
)
from app.broker.interface import BrokerInterface
from app.broker.models import (
    BrokerOrder,
    BrokerPosition,
    OrderCancelRequest,
    OrderCancelResponse,
    OrderModifyRequest,
    OrderModifyResponse,
    OrderPlacementRequest,
    OrderPlacementResponse,
    TradeFill,
)
from app.core.config import Settings, get_settings
from app.core.enums import (
    Book,
    BrokerErrorKind,
    BrokerOrderStatus,
    Exchange,
    Product,
    Side,
    Validity,
)
from app.market_data.instruments import InstrumentRegistry, get_instrument_registry

logger = logging.getLogger(__name__)


class AsyncTokenBucket:
    """Proactive client-side rate limiter / token bucket throttle.

    Smooths out bursts and pre-emptively avoids HTTP 429 rate limit rejections
    from the 021 broker API gateway.
    """

    def __init__(self, rate: float = 10.0, capacity: float = 10.0) -> None:
        """
        :param rate: tokens added per second (e.g. 10 requests / sec)
        :param capacity: maximum burst bucket capacity
        """
        self.rate = float(rate)
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

    @property
    def lock(self) -> asyncio.Lock:
        try:
            cur_loop = asyncio.get_running_loop()
        except RuntimeError:
            cur_loop = None
        if not hasattr(self, "_active_lock") or getattr(self, "_active_lock_loop", None) != cur_loop:
            self._active_lock = asyncio.Lock()
            self._active_lock_loop = cur_loop
        return self._active_lock

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait asynchronously until sufficient tokens are available and deduct them."""
        async with self.lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_refill = now

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                needed = tokens - self.tokens
                wait_time = max(0.01, needed / self.rate)
                await asyncio.sleep(wait_time)


class Broker021(BrokerInterface):
    """Production adapter for 021 Developer REST APIs.

    Follows all rules from 021 Trade Hackathon - API Guide.pdf:
    - Signed quantity: positive = BUY, negative = SELL.
    - Token resolution via InstrumentRegistry.
    - Single-session token caching (re-login revokes old tokens).
    - Robust classification of 500 risk rejections, 429 rate limits, and 503 errors.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        registry: Optional[InstrumentRegistry] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.registry = registry or get_instrument_registry()
        self.base_url = self.settings.broker_base_url.rstrip("/")
        # Ensure /v1 in base_url
        if not self.base_url.endswith("/v1"):
            self.base_url = f"{self.base_url}/v1"

        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        # Proactive client-side rate throttle (10 requests/sec default capacity)
        self._rate_limiter = AsyncTokenBucket(rate=10.0, capacity=10.0)

        # Shared HTTP client (lazily initialized on the active event loop)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def lock(self) -> asyncio.Lock:
        try:
            cur_loop = asyncio.get_running_loop()
        except RuntimeError:
            cur_loop = None
        if not hasattr(self, "_active_lock") or getattr(self, "_active_lock_loop", None) != cur_loop:
            self._active_lock = asyncio.Lock()
            self._active_lock_loop = cur_loop
        return self._active_lock

    def _get_client(self) -> httpx.AsyncClient:
        """Return or lazily initialize httpx.AsyncClient tied to the active event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._client is not None and not getattr(self._client, "is_closed", False):
            client_loop = getattr(self, "_client_loop", None)
            if client_loop is None or client_loop == current_loop:
                return self._client

        self._client = httpx.AsyncClient(
            timeout=float(self.settings.broker_call_timeout_seconds),
            headers={"Content-Type": "application/json"},
        )
        self._client_loop = current_loop
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    # ---------- Authentication Management ----------

    async def get_valid_token(self, force_refresh: bool = False) -> str:
        """Authenticate or reuse cached token. Refreshes if expired."""
        async with self.lock:
            now = datetime.now(timezone.utc)
            if (
                not force_refresh
                and self._access_token
                and self._token_expires_at
                and now < self._token_expires_at
            ):
                return self._access_token

            auth_url = f"{self.base_url}/auth/token"
            payload = {
                "username": self.settings.api_ucc,
                "password": self.settings.api_password,
            }

            for auth_attempt in range(3):
                try:
                    resp = await self._get_client().post(auth_url, json=payload)
                except httpx.TimeoutException:
                    if auth_attempt < 2:
                        await asyncio.sleep(0.5 * (2 ** auth_attempt))
                        continue
                    raise BrokerTimeoutError("Auth request timed out")
                except httpx.RequestError as exc:
                    if auth_attempt < 2:
                        await asyncio.sleep(0.5 * (2 ** auth_attempt))
                        continue
                    raise BrokerServerError(f"Auth connection error: {exc}")

                if resp.status_code == 401:
                    raise BrokerAuthExpiredError("Invalid 021 UCC or password", status_code=401)
                elif resp.status_code in (500, 502, 503, 504):
                    if auth_attempt < 2:
                        await asyncio.sleep(0.5 * (2 ** auth_attempt))
                        continue
                    raise BrokerServerError(f"Auth failed with HTTP {resp.status_code}: {resp.text}", status_code=resp.status_code)
                elif resp.status_code != 200:
                    raise BrokerServerError(f"Auth failed with HTTP {resp.status_code}: {resp.text}", status_code=resp.status_code)

                body = resp.json()
                if not body.get("success") or not body.get("data"):
                    raise BrokerServerError(f"Auth rejected: {body.get('error')}")

                data = body["data"]
                self._access_token = data["accessToken"]
                # Parse expiry
                try:
                    exp_str = data["expiresAt"]
                    self._token_expires_at = datetime.fromisoformat(exp_str).astimezone(timezone.utc)
                except Exception:
                    # Default safety: valid for 1 hour
                    self._token_expires_at = datetime.now(timezone.utc)

                return self._access_token

    async def _request(
        self,
        method: str,
        path: str,
        json: Any = None,
        params: Any = None,
        retry_auth: bool = True,
        max_rate_limit_retries: int = 3,
        max_server_retries: int = 3,
        idempotency_key: Optional[str] = None,
    ) -> httpx.Response:
        """Execute authenticated request with client-side throttle, token refresh, and exponential backoff on 429, 500, and 503.

        If *idempotency_key* is supplied (typically the ``client_order_id``),
        every attempt of this request will include an ``X-Idempotency-Key``
        header so the broker can deduplicate retried POST requests.
        """
        url = f"{self.base_url}{path}"
        can_retry_auth = retry_auth
        total_attempts = max(max_rate_limit_retries, max_server_retries) + 1

        for attempt in range(total_attempts):
            # 1. Proactive client-side token bucket rate throttle
            await self._rate_limiter.acquire(1.0)

            # 2. Get active authentication session token
            token = await self.get_valid_token()
            headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
            if idempotency_key:
                headers["X-Idempotency-Key"] = idempotency_key

            try:
                resp = await self._get_client().request(
                    method,
                    url,
                    json=json,
                    params=params,
                    headers=headers,
                )
            except httpx.TimeoutException:
                if attempt < max_server_retries:
                    delay = min(4.0, (0.5 * (2 ** attempt)) + random.uniform(0.05, 0.2))
                    logger.warning(
                        f"[BROKER TIMEOUT] Request to {path} timed out. "
                        f"Retrying in {delay:.2f}s (retry {attempt + 1}/{max_server_retries})..."
                    )
                    await asyncio.sleep(delay)
                    continue
                raise BrokerTimeoutError(f"Request to {path} timed out after {max_server_retries} retries")
            except httpx.RequestError as exc:
                if attempt < max_server_retries:
                    delay = min(4.0, (0.5 * (2 ** attempt)) + random.uniform(0.05, 0.2))
                    logger.warning(
                        f"[BROKER NETWORK ERROR] Network error on {path}: {exc}. "
                        f"Retrying in {delay:.2f}s (retry {attempt + 1}/{max_server_retries})..."
                    )
                    await asyncio.sleep(delay)
                    continue
                raise BrokerServerError(f"Network error on {path}: {exc}")

            # 3. Handle 401 Unauthorized (refresh once and retry)
            if resp.status_code == 401 and can_retry_auth:
                logger.info(f"[BROKER 401] Token invalid on {method} {path}. Refreshing session...")
                await self.get_valid_token(force_refresh=True)
                can_retry_auth = False
                continue

            # 4. Handle 429 Rate Limit with exponential backoff & jitter
            if resp.status_code == 429:
                if attempt < max_rate_limit_retries:
                    retry_after_hdr = resp.headers.get("Retry-After")
                    if retry_after_hdr:
                        try:
                            delay = max(0.1, float(retry_after_hdr))
                        except ValueError:
                            delay = 0.5 * (2 ** attempt)
                    else:
                        delay = min(4.0, (0.5 * (2 ** attempt)) + random.uniform(0.05, 0.2))

                    logger.warning(
                        f"[BROKER 429 RATE LIMIT] Rate limited on {method} {path}. "
                        f"Backing off for {delay:.2f}s (retry {attempt + 1}/{max_rate_limit_retries})..."
                    )
                    await asyncio.sleep(delay)
                    continue

                body = resp.json() if resp.text else {}
                err_msg = body.get("error") or "021 Rate limit exceeded after retries"
                logger.error(f"[BROKER 429 RATE LIMIT] Retries exhausted ({max_rate_limit_retries}) on {method} {path}")
                raise BrokerRateLimitError(err_msg, status_code=429, raw_response=body)

            # 5. Handle HTTP 500, 502, 503, 504 with automatic retries and exponential backoff
            if resp.status_code in (500, 502, 503, 504):
                body = {}
                try:
                    body = resp.json() if resp.text else {}
                except Exception:
                    body = {"raw": resp.text}

                # 021 spec: If 500 contains a specific risk rejection payload, treat as risk rejection rather than retryable outage
                if resp.status_code == 500 and not body.get("success") and body.get("error") and ("risk" in str(body.get("error")).lower() or "margin" in str(body.get("error")).lower() or "limit" in str(body.get("error")).lower() or "rejected" in str(body.get("error")).lower()):
                    err_msg = body.get("error") or "Order rejected by 021 risk checks"
                    raise BrokerRiskRejectedError(err_msg, status_code=500, raw_response=body)

                if attempt < max_server_retries:
                    delay = min(4.0, (0.5 * (2 ** attempt)) + random.uniform(0.05, 0.2))
                    logger.warning(
                        f"[BROKER HTTP {resp.status_code}] Transient server error on {method} {path}. "
                        f"Retrying in {delay:.2f}s (retry {attempt + 1}/{max_server_retries})..."
                    )
                    await asyncio.sleep(delay)
                    continue

                err_msg = body.get("error") or f"021 Server error ({resp.status_code}) after {max_server_retries} retries"
                logger.error(f"[BROKER {resp.status_code}] Retries exhausted ({max_server_retries}) on {method} {path}")
                raise BrokerServerError(err_msg, status_code=resp.status_code, raw_response=body)

            # 6. Classify other broker responses
            if resp.status_code == 401:
                raise BrokerAuthExpiredError("Unauthorized: Token revoked or invalid", status_code=401)
            elif resp.status_code == 422:
                body = resp.json() if resp.text else {}
                err_msg = body.get("error") or "Order blocked by safe mode"
                raise BrokerSafeModeError(err_msg, status_code=422, raw_response=body)
            elif resp.status_code == 400:
                body = resp.json() if resp.text else {}
                err_msg = body.get("error") or resp.text
                raise BrokerBadRequestError(f"Bad request: {err_msg}", status_code=400, raw_response=body)

            return resp

        # Fallback if loop ends
        raise BrokerServerError(f"021 Request failed after {total_attempts} attempts", status_code=500)

    # ---------- BrokerInterface Implementation ----------

    async def place_order(self, request: OrderPlacementRequest) -> OrderPlacementResponse:
        """Place an order with 021 Developer API.

        Idempotent: sends the client_order_id as both an HTTP
        ``X-Idempotency-Key`` header **and** a ``clientOrderId`` JSON field.
        If the broker has already processed an order with the same key it
        returns the original acknowledgement instead of creating a duplicate.
        """
        # 1. Resolve Instrument token
        inst = self.registry.find_by_symbol(request.symbol, request.exchange)
        if not inst:
            raise BrokerBadRequestError(f"Unknown instrument symbol {request.symbol} on {request.exchange.value}")

        # 2. Compute signed quantity (positive = BUY, negative = SELL)
        qty = abs(request.quantity) if request.side == Side.BUY else -abs(request.quantity)

        price = request.price_paise
        if price > 0 and inst.tick_size_paise > 1:
            price = int(round(price / inst.tick_size_paise) * inst.tick_size_paise)

        payload = {
            "exchange": request.exchange.value,
            "token": inst.token,
            "qty": qty,
            "price": price,
            "book": request.book.value,
            "product": request.product.value,
            "validity": request.validity.value,
            # Embed the client-side dedup key in the payload so the broker
            # can correlate retries at the application layer.
            "clientOrderId": request.client_order_id,
        }
        if request.trigger_price_paise > 0:
            payload["trigger"] = request.trigger_price_paise

        try:
            resp = await self._request(
                "POST",
                "/orders",
                json=payload,
                idempotency_key=request.client_order_id,
            )
        except BrokerSafeModeError as bsm:
            # If rejected because market orders are not permitted (e.g., pre-open session or wide bid-ask spread),
            # fall back gracefully to a marketable limit order at instrument mid-circuit price.
            if payload["price"] == 0 and any(kw in str(bsm).lower() for kw in ("market order", "spread", "pre-open")):
                if inst and inst.lower_circuit_paise > 0 and inst.upper_circuit_paise > 0:
                    fallback_price = (inst.lower_circuit_paise + inst.upper_circuit_paise) // 2
                else:
                    fallback_price = request.trigger_price_paise or 100000
                if inst and inst.tick_size_paise > 1:
                    fallback_price = int(round(fallback_price / inst.tick_size_paise) * inst.tick_size_paise)

                logger.warning(
                    f"[BROKER SAFE MODE] Market order blocked ({bsm}). "
                    f"Retrying as marketable limit order with price {fallback_price} paise..."
                )
                payload["price"] = fallback_price
                resp = await self._request(
                    "POST",
                    "/orders",
                    json=payload,
                    idempotency_key=f"{request.client_order_id}-lim",
                )
            else:
                raise

        data = resp.json()

        if not data.get("success"):
            err_msg = data.get("error", "Order placement rejected")
            return OrderPlacementResponse(
                order_id="",
                client_order_id=request.client_order_id,
                broker_status=BrokerOrderStatus.REJECTED,
                message=err_msg,
                rejection_reason=err_msg,
            )

        resp_data = data.get("data", {})
        order_id = str(resp_data.get("orderId", ""))
        msg = resp_data.get("message", "Order placed successfully")

        return OrderPlacementResponse(
            order_id=order_id,
            client_order_id=request.client_order_id,
            broker_status=BrokerOrderStatus.PLACED,
            message=msg,
        )

    async def cancel_order(self, request: OrderCancelRequest) -> OrderCancelResponse:
        """Cancel an open order via DELETE /orders/{orderId}."""
        # Retrieve order details to get token, exchange, product
        order = await self.get_order(request.order_id)
        if not order:
            return OrderCancelResponse(
                order_id=request.order_id,
                broker_status=BrokerOrderStatus.REJECTED,
                success=False,
                message="Order not found",
            )

        inst = self.registry.find_by_symbol(order.symbol, order.exchange)
        token = inst.token if inst else 0

        payload = {
            "exchange": order.exchange.value,
            "token": token,
            "product": order.product.value,
        }

        resp = await self._request("DELETE", f"/orders/{request.order_id}", json=payload)
        data = resp.json()
        success = bool(data.get("success"))

        return OrderCancelResponse(
            order_id=request.order_id,
            broker_status=BrokerOrderStatus.CANCELLED if success else order.status,
            success=success,
            message=data.get("data", {}).get("message", ""),
        )

    async def modify_order(self, request: OrderModifyRequest) -> OrderModifyResponse:
        """Modify an order via PUT /orders/{orderId}."""
        order = await self.get_order(request.order_id)
        if not order:
            return OrderModifyResponse(
                order_id=request.order_id,
                broker_status=BrokerOrderStatus.REJECTED,
                success=False,
                message="Order not found",
            )

        inst = self.registry.find_by_symbol(order.symbol, order.exchange)
        token = inst.token if inst else 0

        qty = request.quantity if request.quantity is not None else order.quantity
        if order.side == Side.SELL:
            qty = -abs(qty)
        else:
            qty = abs(qty)

        price = request.price_paise if request.price_paise is not None else order.price_paise

        payload = {
            "exchange": order.exchange.value,
            "token": token,
            "qty": qty,
            "price": price,
            "book": order.book.value,
            "product": order.product.value,
            "validity": order.validity.value,
        }

        resp = await self._request("PUT", f"/orders/{request.order_id}", json=payload)
        data = resp.json()
        success = bool(data.get("success"))

        return OrderModifyResponse(
            order_id=request.order_id,
            broker_status=BrokerOrderStatus.PENDING if success else order.status,
            success=success,
            message=data.get("data", {}).get("message", ""),
        )

    async def get_order(self, order_id: str) -> Optional[BrokerOrder]:
        """Fetch status of a single order via GET /orders/{orderId}."""
        resp = await self._request("GET", f"/orders/{order_id}")
        data = resp.json()
        # 021 returns single order inside a 1-element list
        if isinstance(data, list) and data:
            return self._parse_broker_order(data[0])
        elif isinstance(data, dict) and data.get("data"):
            order_data = data["data"]
            if isinstance(order_data, list) and order_data:
                return self._parse_broker_order(order_data[0])
            return self._parse_broker_order(order_data)
        return None

    async def get_orders(self) -> list[BrokerOrder]:
        """Fetch all orders placed today via GET /orders."""
        resp = await self._request("GET", "/orders")
        data = resp.json()
        orders: list[BrokerOrder] = []
        order_list = data if isinstance(data, list) else data.get("data", [])
        for item in order_list:
            orders.append(self._parse_broker_order(item))
        return orders

    async def get_positions(self) -> list[BrokerPosition]:
        """Fetch portfolio positions via GET /portfolio/positions."""
        resp = await self._request("GET", "/portfolio/positions")
        data = resp.json()
        positions: list[BrokerPosition] = []
        pos_list = data if isinstance(data, list) else data.get("data", [])
        for item in pos_list:
            token = int(item.get("token", 0))
            inst = self.registry.find_by_token(token)
            symbol = inst.symbol if inst else str(token)

            exch_str = item.get("exchange", "NSECM")
            exch = Exchange.NSE
            if "FO" in exch_str:
                exch = Exchange.NSEFO
            elif "BSE" in exch_str:
                exch = Exchange.BSE

            net_qty = int(item.get("netQuantity", 0))
            net_price = int(item.get("netPrice", 0))
            buy_price = int(item.get("buyPrice", 0))
            sell_price = int(item.get("sellPrice", 0))

            pos = BrokerPosition(
                symbol=symbol,
                exchange=exch,
                product=Product(item.get("product", Product.INTRADAY.value)),
                net_quantity=net_qty,
                average_price_paise=net_price,
            )
            positions.append(pos)
        return positions

    async def cancel_all_orders(self) -> list[OrderCancelResponse]:
        """Emergency action (Kill Switch): cancel all pending/active orders."""
        orders = await self.get_orders()
        responses: list[OrderCancelResponse] = []
        for ord_info in orders:
            if ord_info.status in (BrokerOrderStatus.PENDING, BrokerOrderStatus.PLACED, BrokerOrderStatus.RECEIVED):
                res = await self.cancel_order(OrderCancelRequest(order_id=ord_info.order_id))
                responses.append(res)
        return responses

    def _parse_broker_order(self, item: dict[str, Any]) -> BrokerOrder:
        token = int(item.get("token", 0))
        inst = self.registry.find_by_token(token)
        symbol = inst.symbol if inst else str(token)

        raw_qty = int(item.get("qtyRemaining", 0)) + int(item.get("qtyTraded", 0))
        side = Side.BUY if raw_qty >= 0 else Side.SELL

        status_str = item.get("status", "Pending")
        status = BrokerOrderStatus.PENDING
        for s in BrokerOrderStatus:
            if s.value.lower() == status_str.lower():
                status = s
                break

        epoch = item.get("time") or item.get("lastActivity")
        order_time = (
            datetime.fromtimestamp(epoch, tz=timezone.utc)
            if (epoch and isinstance(epoch, (int, float)) and epoch > 1000000000)
            else datetime.now(timezone.utc)
        )

        filled_q = abs(int(item.get("qtyTraded", 0)))
        fills_list = []
        if filled_q > 0:
            from app.broker.models import TradeFill
            fills_list.append(
                TradeFill(
                    order_id=str(item.get("orderId", "")),
                    client_order_id=str(item.get("clientOrderId", "")),
                    symbol=symbol,
                    exchange=Exchange.NSE,
                    side=side,
                    quantity=filled_q,
                    price_paise=int(item.get("price", 0)),
                    timestamp=order_time,
                )
            )

        return BrokerOrder(
            order_id=str(item.get("orderId", "")),
            client_order_id=str(item.get("clientOrderId", "")),
            symbol=symbol,
            exchange=Exchange.NSE,
            side=side,
            product=Product(item.get("product", Product.INTRADAY.value)),
            book=Book(item.get("book", Book.RL.value)),
            validity=Validity(item.get("validity", Validity.DAY.value)),
            quantity=abs(raw_qty) if abs(raw_qty) > 0 else max(1, filled_q),
            price_paise=int(item.get("price", 0)),
            trigger_price_paise=int(item.get("triggerPrice", 0)),
            status=status,
            filled_quantity=filled_q,
            average_price_paise=int(item.get("price", 0)),
            rejection_reason=item.get("reason", ""),
            fills=fills_list,
            created_at=order_time,
            updated_at=order_time,
        )
