import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import uuid

from app.broker.errors import (
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
    BrokerOrderStatus,
    Exchange,
    Product,
    Side,
)


class Mock021(BrokerInterface):
    """Mock implementation of the 021 broker adapter for testing and simulation.

    Supports:
    - Instant full fills (default)
    - Configurable order rejections (response or 500 exception)
    - Partial fills
    - Timeout simulations
    - 500/503 server error simulations
    - Realistic brokerage & statutory fee calculations
    - Real-time in-memory position and P&L tracking
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings: Settings = settings or get_settings()

        # In-memory stores
        self._orders: dict[str, BrokerOrder] = {}
        self._fills: dict[str, TradeFill] = {}
        # Key: (symbol, exchange, product)
        self._positions: dict[tuple[str, Exchange, Product], BrokerPosition] = {}

        # Default fallback prices in paise if market order (price_paise == 0)
        self._reference_prices: dict[str, int] = {
            "RELIANCE": 290000,  # ₹2900.00
            "TCS": 420000,       # ₹4200.00
            "INFY": 185000,      # ₹1850.00
        }
        self._default_market_price_paise: int = 100000  # ₹1000.00 default

        # Simulation behavior overrides
        self._next_error: BrokerError | None = None
        self._should_reject: bool = False
        self._rejection_reason: str = "Broker margin check failed"
        self._reject_with_exception: bool = False
        self._partial_fill_ratio: float | None = None

    # ---------- Simulation Control APIs (for tests and scenarios) ----------

    def set_reference_price(self, symbol: str, price_paise: int) -> None:
        """Set mock market reference price for a symbol in paise."""
        self._reference_prices[symbol.upper()] = price_paise

    def simulate_next_error(self, error: BrokerError) -> None:
        """Inject an error to be raised on the next broker call."""
        self._next_error = error

    def simulate_timeout(self, message: str = "Broker request timed out") -> None:
        """Inject a timeout on the next call."""
        self._next_error = BrokerTimeoutError(message=message)

    def simulate_server_error(self, status_code: int = 500, message: str = "Internal server error") -> None:
        """Inject an HTTP 500 or 503 server error on the next call."""
        self._next_error = BrokerServerError(message=message, status_code=status_code)

    def simulate_rate_limit(self, message: str = "Rate limit exceeded (429)") -> None:
        """Inject a 429 rate limit error on the next call."""
        self._next_error = BrokerRateLimitError(message=message)

    def simulate_safe_mode(self, message: str = "Exchange safe mode active") -> None:
        """Inject a 422 safe mode error on the next call."""
        self._next_error = BrokerSafeModeError(message=message)

    def set_rejection(
        self,
        enabled: bool = True,
        reason: str = "Broker margin check failed",
        raise_exception: bool = False,
    ) -> None:
        """Configure whether subsequent orders are rejected."""
        self._should_reject = enabled
        self._rejection_reason = reason
        self._reject_with_exception = raise_exception

    def set_partial_fill_ratio(self, ratio: float | None) -> None:
        """Configure partial fills (e.g., 0.5 fills 50% on placement). Set None to restore full fills."""
        if ratio is not None and not (0.0 < ratio < 1.0):
            raise ValueError("Partial fill ratio must be strictly between 0.0 and 1.0")
        self._partial_fill_ratio = ratio

    def reset(self) -> None:
        """Reset all in-memory orders, positions, and simulation controls."""
        self._orders.clear()
        self._fills.clear()
        self._positions.clear()
        self._next_error = None
        self._should_reject = False
        self._rejection_reason = "Broker margin check failed"
        self._reject_with_exception = False
        self._partial_fill_ratio = None

    # ---------- BrokerInterface Implementation ----------

    async def place_order(self, request: OrderPlacementRequest) -> OrderPlacementResponse:
        # 1. Check for simulated injected transient errors
        if self._next_error is not None:
            err = self._next_error
            self._next_error = None
            raise err

        # 2. Simulate latency if configured
        if self.settings.mock_fill_latency_ms > 0:
            await asyncio.sleep(self.settings.mock_fill_latency_ms / 1000.0)

        order_id = f"mock_ord_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # 3. Check for simulated rejection
        if self._should_reject:
            if self._reject_with_exception:
                raise BrokerRiskRejectedError(
                    message=self._rejection_reason,
                    status_code=500,
                    raw_response={"status": "error", "reason": self._rejection_reason},
                )

            # Rejection returned as standard order rejection response
            order = BrokerOrder(
                order_id=order_id,
                client_order_id=request.client_order_id,
                symbol=request.symbol,
                exchange=request.exchange,
                side=request.side,
                product=request.product,
                book=request.book,
                validity=request.validity,
                quantity=request.quantity,
                price_paise=request.price_paise,
                trigger_price_paise=request.trigger_price_paise,
                status=BrokerOrderStatus.REJECTED,
                rejection_reason=self._rejection_reason,
                created_at=now,
                updated_at=now,
            )
            self._orders[order_id] = order

            return OrderPlacementResponse(
                order_id=order_id,
                client_order_id=request.client_order_id,
                broker_status=BrokerOrderStatus.REJECTED,
                message=f"Order rejected: {self._rejection_reason}",
                rejection_reason=self._rejection_reason,
            )

        # 4. Resolve fill price (market order uses reference price)
        fill_price_paise = request.price_paise
        if fill_price_paise == 0:
            fill_price_paise = self._reference_prices.get(
                request.symbol.upper(), self._default_market_price_paise
            )

        # 5. Determine fill quantity (full or partial)
        if self._partial_fill_ratio is not None:
            filled_qty = max(1, int(request.quantity * self._partial_fill_ratio))
            status = BrokerOrderStatus.PENDING
        else:
            filled_qty = request.quantity
            status = BrokerOrderStatus.EXECUTED

        order = BrokerOrder(
            order_id=order_id,
            client_order_id=request.client_order_id,
            symbol=request.symbol,
            exchange=request.exchange,
            side=request.side,
            product=request.product,
            book=request.book,
            validity=request.validity,
            quantity=request.quantity,
            price_paise=request.price_paise,
            trigger_price_paise=request.trigger_price_paise,
            status=status,
            filled_quantity=filled_qty,
            average_price_paise=fill_price_paise,
            created_at=now,
            updated_at=now,
        )

        # 6. Create execution fill
        fill = self._execute_fill(order, filled_qty, fill_price_paise, now)
        order.fills.append(fill)
        self._orders[order_id] = order

        return OrderPlacementResponse(
            order_id=order_id,
            client_order_id=request.client_order_id,
            broker_status=status,
            message="Order executed" if status == BrokerOrderStatus.EXECUTED else "Order placed with partial fill",
        )

    async def cancel_order(self, request: OrderCancelRequest) -> OrderCancelResponse:
        if self._next_error is not None:
            err = self._next_error
            self._next_error = None
            raise err

        order = self._orders.get(request.order_id)
        if not order:
            return OrderCancelResponse(
                order_id=request.order_id,
                broker_status=BrokerOrderStatus.REJECTED,
                success=False,
                message="Order not found",
            )

        # Terminal orders cannot be cancelled
        if order.status in (BrokerOrderStatus.EXECUTED, BrokerOrderStatus.CANCELLED, BrokerOrderStatus.REJECTED):
            return OrderCancelResponse(
                order_id=order.order_id,
                broker_status=order.status,
                success=False,
                message=f"Order in state {order.status.value} cannot be cancelled",
            )

        order.status = BrokerOrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)

        return OrderCancelResponse(
            order_id=order.order_id,
            broker_status=BrokerOrderStatus.CANCELLED,
            success=True,
            message="Order cancelled successfully",
        )

    async def modify_order(self, request: OrderModifyRequest) -> OrderModifyResponse:
        if self._next_error is not None:
            err = self._next_error
            self._next_error = None
            raise err

        order = self._orders.get(request.order_id)
        if not order:
            return OrderModifyResponse(
                order_id=request.order_id,
                broker_status=BrokerOrderStatus.REJECTED,
                success=False,
                message="Order not found",
            )

        if order.status != BrokerOrderStatus.PENDING:
            return OrderModifyResponse(
                order_id=order.order_id,
                broker_status=order.status,
                success=False,
                message=f"Cannot modify order in state {order.status.value}",
            )

        if request.quantity is not None:
            if request.quantity < order.filled_quantity:
                return OrderModifyResponse(
                    order_id=order.order_id,
                    broker_status=order.status,
                    success=False,
                    message=f"New quantity ({request.quantity}) cannot be less than filled quantity ({order.filled_quantity})",
                )
            order.quantity = request.quantity

        if request.price_paise is not None:
            order.price_paise = request.price_paise

        if request.trigger_price_paise is not None:
            order.trigger_price_paise = request.trigger_price_paise

        order.updated_at = datetime.now(timezone.utc)

        return OrderModifyResponse(
            order_id=order.order_id,
            broker_status=BrokerOrderStatus.PENDING,
            success=True,
            message="Order modified successfully",
        )

    async def get_order(self, order_id: str) -> BrokerOrder | None:
        if self._next_error is not None:
            err = self._next_error
            self._next_error = None
            raise err
        return self._orders.get(order_id)

    async def get_orders(self) -> list[BrokerOrder]:
        if self._next_error is not None:
            err = self._next_error
            self._next_error = None
            raise err
        return list(self._orders.values())

    async def get_positions(self) -> list[BrokerPosition]:
        if self._next_error is not None:
            err = self._next_error
            self._next_error = None
            raise err
        return list(self._positions.values())

    async def cancel_all_orders(self) -> list[OrderCancelResponse]:
        """Cancel all pending / open orders."""
        if self._next_error is not None:
            err = self._next_error
            self._next_error = None
            raise err

        responses: list[OrderCancelResponse] = []
        for order in list(self._orders.values()):
            if order.status == BrokerOrderStatus.PENDING:
                resp = await self.cancel_order(OrderCancelRequest(order_id=order.order_id))
                responses.append(resp)
        return responses

    # ---------- Internal Helpers ----------

    def _execute_fill(
        self,
        order: BrokerOrder,
        qty: int,
        price_paise: int,
        timestamp: datetime,
    ) -> TradeFill:
        """Create fill record and update positions/realized P&L."""
        notional_paise = qty * price_paise

        # Brokerage from settings (in paise)
        brokerage = self.settings.brokerage_per_fill_paise

        # Statutory / exchange fee percent of notional
        fee = int(Decimal(str(notional_paise)) * self.settings.fee_percent_of_notional)

        fill = TradeFill(
            order_id=order.order_id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            exchange=order.exchange,
            side=order.side,
            quantity=qty,
            price_paise=price_paise,
            brokerage_paise=brokerage,
            fee_paise=fee,
            timestamp=timestamp,
        )
        self._fills[fill.fill_id] = fill

        # Update position
        pos_key = (order.symbol, order.exchange, order.product)
        if pos_key not in self._positions:
            self._positions[pos_key] = BrokerPosition(
                symbol=order.symbol,
                exchange=order.exchange,
                product=order.product,
            )
        pos = self._positions[pos_key]

        if order.side == Side.BUY:
            pos.buy_quantity += qty
            pos.buy_amount_paise += notional_paise
            pos.net_quantity += qty
        else:
            pos.sell_quantity += qty
            pos.sell_amount_paise += notional_paise
            pos.net_quantity -= qty

        # Calculate average price and realized P&L
        if pos.buy_quantity > 0 and pos.net_quantity > 0:
            pos.average_price_paise = pos.buy_amount_paise // pos.buy_quantity
        elif pos.sell_quantity > 0 and pos.net_quantity < 0:
            pos.average_price_paise = pos.sell_amount_paise // pos.sell_quantity
        else:
            pos.average_price_paise = 0

        # Realized P&L on closed round-trip quantity
        closed_qty = min(pos.buy_quantity, pos.sell_quantity)
        if closed_qty > 0:
            avg_buy = pos.buy_amount_paise // pos.buy_quantity if pos.buy_quantity else 0
            avg_sell = pos.sell_amount_paise // pos.sell_quantity if pos.sell_quantity else 0
            pos.realized_pnl_paise = closed_qty * (avg_sell - avg_buy)

        return fill
