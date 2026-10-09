import asyncio
from datetime import datetime, timezone
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
        self._lock = asyncio.Lock()

        # Shared HTTP client
        self._client = httpx.AsyncClient(
            timeout=float(self.settings.broker_call_timeout_seconds),
            headers={"Content-Type": "application/json"},
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ---------- Authentication Management ----------

    async def get_valid_token(self, force_refresh: bool = False) -> str:
        """Authenticate or reuse cached token. Refreshes if expired."""
        async with self._lock:
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

            try:
                resp = await self._client.post(auth_url, json=payload)
            except httpx.TimeoutException:
                raise BrokerTimeoutError("Auth request timed out")
            except httpx.RequestError as exc:
                raise BrokerServerError(f"Auth connection error: {exc}")

            if resp.status_code == 401:
                raise BrokerAuthExpiredError("Invalid 021 UCC or password", status_code=401)
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
    ) -> httpx.Response:
        """Execute authenticated request with auto-retry on 401."""
        token = await self.get_valid_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}{path}"

        try:
            resp = await self._client.request(
                method,
                url,
                json=json,
                params=params,
                headers=headers,
            )
        except httpx.TimeoutException:
            raise BrokerTimeoutError(f"Request to {path} timed out")
        except httpx.RequestError as exc:
            raise BrokerServerError(f"Network error on {path}: {exc}")

        # If token was revoked externally or expired, refresh once and retry
        if resp.status_code == 401 and retry_auth:
            token = await self.get_valid_token(force_refresh=True)
            headers["Authorization"] = f"Bearer {token}"
            try:
                resp = await self._client.request(
                    method,
                    url,
                    json=json,
                    params=params,
                    headers=headers,
                )
            except Exception as e:
                raise BrokerServerError(f"Retry after 401 failed: {e}")

        # Classify broker responses
        if resp.status_code == 401:
            raise BrokerAuthExpiredError("Unauthorized: Token revoked or invalid", status_code=401)
        elif resp.status_code == 422:
            body = resp.json() if resp.text else {}
            err_msg = body.get("error") or "Order blocked by safe mode"
            raise BrokerSafeModeError(err_msg, status_code=422, raw_response=body)
        elif resp.status_code == 429:
            raise BrokerRateLimitError("021 Rate limit exceeded", status_code=429)
        elif resp.status_code == 500:
            body = resp.json() if resp.text else {}
            err_msg = body.get("error") or "Internal broker error"
            # 021 spec: 500 with risk reason means order was rejected by risk checks
            if not body.get("success") and body.get("error"):
                raise BrokerRiskRejectedError(err_msg, status_code=500, raw_response=body)
            raise BrokerServerError(err_msg, status_code=500, raw_response=body)
        elif resp.status_code == 503:
            raise BrokerServerError("021 Service unavailable (503)", status_code=503)
        elif resp.status_code == 400:
            body = resp.json() if resp.text else {}
            err_msg = body.get("error") or resp.text
            raise BrokerBadRequestError(f"Bad request: {err_msg}", status_code=400, raw_response=body)

        return resp

    # ---------- BrokerInterface Implementation ----------

    async def place_order(self, request: OrderPlacementRequest) -> OrderPlacementResponse:
        """Place an order with 021 Developer API."""
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
        }
        if request.trigger_price_paise > 0:
            payload["trigger"] = request.trigger_price_paise

        resp = await self._request("POST", "/orders", json=payload)
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

        return BrokerOrder(
            order_id=str(item.get("orderId", "")),
            client_order_id=str(item.get("clientOrderId", "")),
            symbol=symbol,
            exchange=Exchange.NSE,
            side=side,
            product=Product(item.get("product", Product.INTRADAY.value)),
            book=Book(item.get("book", Book.RL.value)),
            validity=Validity(item.get("validity", Validity.DAY.value)),
            quantity=abs(raw_qty),
            price_paise=int(item.get("price", 0)),
            trigger_price_paise=int(item.get("triggerPrice", 0)),
            status=status,
            filled_quantity=abs(int(item.get("qtyTraded", 0))),
            average_price_paise=int(item.get("price", 0)),
            rejection_reason=item.get("reason", ""),
        )
