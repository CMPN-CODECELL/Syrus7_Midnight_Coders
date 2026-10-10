import asyncio
import logging
import time
from typing import Optional

import httpx
from app.broker.errors import BrokerError, BrokerTimeoutError
from app.broker.interface import BrokerInterface
from app.broker.models import OrderPlacementRequest, OrderPlacementResponse, TradeFill
from app.core.enums import Book, BrokerOrderStatus, OrderStatus, Product, RiskReason, Severity, Side, Validity
from app.risk.engine import RiskEngine
from app.risk.models import RiskCheckResult
from app.strategies.intents import OrderIntent
from app.strategies.manager import StrategyManager

logger = logging.getLogger(__name__)


async def _async_db_persist(coro):
    try:
        await coro
    except Exception as e:
        logger.debug(f"[DB PERSIST ERROR] {e}")


def _fire_and_forget(coro):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_async_db_persist(coro))
    except RuntimeError:
        pass


async def _save_risk_record(
    strategy_id: str,
    symbol: str,
    side: str,
    quantity: int,
    price_paise: int,
    passed: bool,
    reason: str,
    message: str,
    severity: str,
):
    try:
        from app.database.session import AsyncSessionLocal
        from app.database.models import RiskEventRecord

        async with AsyncSessionLocal() as session:
            rec = RiskEventRecord(
                strategy_id=strategy_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price_paise=price_paise,
                passed=passed,
                reason=reason,
                message=message,
                severity=severity,
            )
            session.add(rec)
            await session.commit()
    except Exception as e:
        logger.debug(f"Risk event DB save error: {e}")


async def _save_order_record(
    order_id: str,
    client_order_id: str,
    strategy_id: str,
    symbol: str,
    exchange: str,
    side: str,
    quantity: int,
    price_paise: int,
    product: str,
    status: str,
    rejection_reason: Optional[str] = None,
):
    try:
        from app.database.session import AsyncSessionLocal
        from app.database.models import OrderRecord

        async with AsyncSessionLocal() as session:
            rec = OrderRecord(
                id=order_id,
                client_order_id=client_order_id,
                strategy_id=strategy_id,
                symbol=symbol,
                exchange=exchange,
                side=side,
                quantity=quantity,
                filled_quantity=0,
                price_paise=price_paise,
                product=product,
                status=status,
                rejection_reason=rejection_reason,
            )
            session.add(rec)
            await session.commit()
    except Exception as e:
        logger.debug(f"Order DB save error: {e}")


async def _save_fill_record(
    order_id: str,
    strategy_id: str,
    symbol: str,
    side: str,
    quantity: int,
    price_paise: int,
    brokerage_paise: int,
    fee_paise: int,
):
    try:
        from app.database.session import AsyncSessionLocal
        from app.database.models import TradeFillRecord, OrderRecord

        async with AsyncSessionLocal() as session:
            rec = TradeFillRecord(
                order_id=order_id,
                strategy_id=strategy_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price_paise=price_paise,
                brokerage_paise=brokerage_paise,
                fee_paise=fee_paise,
            )
            session.add(rec)
            ord_rec = await session.get(OrderRecord, order_id)
            if ord_rec:
                ord_rec.filled_quantity = (ord_rec.filled_quantity or 0) + quantity
                if ord_rec.filled_quantity >= ord_rec.quantity:
                    ord_rec.status = "EXECUTED"
                else:
                    ord_rec.status = "PARTIALLY_FILLED"
            await session.commit()
    except Exception as e:
        logger.debug(f"Fill DB save error: {e}")


class ExecutionEngine:
    """Execution Engine bridging Strategy Intents, Risk Gates, and Broker Orders (L2, L3, L4).

    Orchestrates:
    - Pre-trade risk evaluation through RiskEngine.
    - **Idempotent order placement**: a local dedup ledger keyed by
      ``client_order_id`` / ``intent_id`` ensures retrying a timed-out
      placement never creates a duplicate order.  Entries expire after
      ``IDEMPOTENCY_TTL_SECONDS`` (default 60 s).
    - In-flight (open/pending) order registration to protect position limits.
    - Broker order submission with error classification.
    - Order fill & partial fill routing back to strategies and risk counters.
    - In-flight release on cancellation, rejection, or fill completion.
    """

    IDEMPOTENCY_TTL_SECONDS: float = 60.0

    def __init__(
        self,
        strategy_manager: StrategyManager,
        risk_engine: RiskEngine,
        broker: BrokerInterface,
    ) -> None:
        self.strategy_manager = strategy_manager
        self.risk_engine = risk_engine
        self.broker = broker

        # Map order_id -> strategy_id and client_order_id -> strategy_id
        self._order_to_strategy: dict[str, str] = {}
        self._client_to_strategy: dict[str, str] = {}

        # ---- Idempotency Ledger ----
        # Prevents duplicate orders when a caller retries after a timeout.
        # Key: client_order_id / intent_id
        # Value: (timestamp, (RiskCheckResult, OrderPlacementResponse | None))
        self._idempotency_ledger: dict[
            str,
            tuple[float, tuple["RiskCheckResult", Optional[OrderPlacementResponse]]],
        ] = {}
        self._idempotency_lock = asyncio.Lock()

    def _purge_expired_idempotency_keys(self) -> None:
        """Remove stale entries from the dedup ledger (called while holding the lock)."""
        now = time.monotonic()
        expired = [
            k for k, (ts, _) in self._idempotency_ledger.items()
            if (now - ts) > self.IDEMPOTENCY_TTL_SECONDS
        ]
        for k in expired:
            del self._idempotency_ledger[k]

    async def execute_intent(
        self,
        intent: OrderIntent,
    ) -> tuple[RiskCheckResult, Optional[OrderPlacementResponse]]:
        """Process an order intent end-to-end: Dedup → Risk gate → in-flight tracking → Broker.

        **Idempotency guarantee**: if an identical ``intent_id`` (which becomes
        the ``client_order_id``) is submitted within ``IDEMPOTENCY_TTL_SECONDS``
        of a prior successful submission, the cached result is returned
        immediately without touching the broker again.
        """
        strat = self.strategy_manager.get_strategy(intent.strategy_id)
        if not strat:
            result = RiskCheckResult(
                passed=False,
                reason=RiskReason.SYMBOL_HALTED,
                message=f"Strategy {intent.strategy_id} is not registered",
                severity=Severity.ERROR,
            )
            return result, None

        # ---- Idempotency check ----
        dedup_key = intent.intent_id
        async with self._idempotency_lock:
            self._purge_expired_idempotency_keys()
            cached = self._idempotency_ledger.get(dedup_key)
            if cached is not None:
                logger.info(
                    f"[IDEMPOTENT] Duplicate intent {dedup_key} detected – "
                    f"returning cached response (age {time.monotonic() - cached[0]:.1f}s)"
                )
                return cached[1]

        # Step 1: Pre-trade platform risk check
        risk_result = self.risk_engine.evaluate_intent(intent, strat)
        if not risk_result.passed:
            logger.warning(
                f"[RISK REJECTED] Strategy {intent.strategy_id} {intent.side.value} {intent.quantity} "
                f"{intent.symbol}: {risk_result.reason} - {risk_result.message}"
            )
            _fire_and_forget(
                _save_risk_record(
                    strategy_id=intent.strategy_id,
                    symbol=intent.symbol,
                    side=intent.side.value,
                    quantity=intent.quantity,
                    price_paise=intent.price_paise,
                    passed=False,
                    reason=risk_result.reason.value if risk_result.reason else "UNKNOWN",
                    message=risk_result.message,
                    severity=risk_result.severity.value,
                )
            )
            return risk_result, None

        client_order_id = intent.intent_id or f"ord_{intent.strategy_id}_{int(asyncio.get_event_loop().time()*1000)}"

        # Step 2: Register in-flight order before network call to protect position limits
        self.risk_engine.register_inflight_order(
            strategy_id=intent.strategy_id,
            client_order_id=client_order_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            price_paise=intent.price_paise,
        )
        self._client_to_strategy[client_order_id] = intent.strategy_id

        # Step 3: Formulate broker placement request
        req = OrderPlacementRequest(
            client_order_id=client_order_id,
            symbol=intent.symbol,
            exchange=intent.exchange,
            side=intent.side,
            quantity=intent.quantity,
            price_paise=intent.price_paise,
            product=intent.product,
            book=intent.book,
            validity=intent.validity,
            tag=intent.tag,
        )

        # Step 4: Dispatch to broker
        try:
            resp = await self.broker.place_order(req)
            order_id = resp.order_id or client_order_id
            if resp.order_id:
                self._order_to_strategy[resp.order_id] = intent.strategy_id

            # Persist order to database
            _fire_and_forget(
                _save_order_record(
                    order_id=order_id,
                    client_order_id=client_order_id,
                    strategy_id=intent.strategy_id,
                    symbol=intent.symbol,
                    exchange=intent.exchange.value if hasattr(intent.exchange, "value") else str(intent.exchange),
                    side=intent.side.value,
                    quantity=intent.quantity,
                    price_paise=intent.price_paise,
                    product=intent.product.value if hasattr(intent.product, "value") else str(intent.product),
                    status=resp.broker_status.value.upper(),
                    rejection_reason=resp.message if resp.broker_status == BrokerOrderStatus.REJECTED else None,
                )
            )

            if resp.broker_status == BrokerOrderStatus.REJECTED:
                # Broker rejected: release in-flight immediately
                self.risk_engine.release_inflight_order(intent.strategy_id, client_order_id)
                logger.warning(f"[BROKER REJECTED] Order {client_order_id}: {resp.message}")
            else:
                # Query broker for execution status and fills (supports both Mock021 and Broker021)
                broker_order = None
                try:
                    if resp.order_id:
                        broker_order = await self.broker.get_order(resp.order_id)
                except Exception as bo_err:
                    logger.debug(f"Could not fetch broker order {resp.order_id}: {bo_err}")

                if broker_order and broker_order.fills:
                    for f in broker_order.fills:
                        self.handle_fill(f)
                    resp.broker_status = broker_order.status
                    resp.price_paise = broker_order.average_price_paise
                    resp.filled_quantity = broker_order.filled_quantity
                elif resp.broker_status == BrokerOrderStatus.EXECUTED or (broker_order and broker_order.status == BrokerOrderStatus.EXECUTED):
                    fill_price = (broker_order.average_price_paise if broker_order and broker_order.average_price_paise > 0 else intent.price_paise) or 100000
                    fill = TradeFill(
                        order_id=order_id,
                        client_order_id=client_order_id,
                        symbol=intent.symbol,
                        exchange=intent.exchange,
                        side=intent.side,
                        quantity=intent.quantity,
                        price_paise=fill_price,
                    )
                    self.handle_fill(fill)
                    resp.broker_status = BrokerOrderStatus.EXECUTED
                    resp.price_paise = fill_price
                    resp.filled_quantity = intent.quantity

                if resp.broker_status == BrokerOrderStatus.EXECUTED or getattr(resp.broker_status, "value", "").upper() in ("EXECUTED", "FILLED"):
                    self.risk_engine.release_inflight_order(intent.strategy_id, client_order_id)

            # Cache result in idempotency ledger (prevents duplicate on retry)
            async with self._idempotency_lock:
                self._idempotency_ledger[dedup_key] = (time.monotonic(), (risk_result, resp))
            return risk_result, resp



        except (BrokerTimeoutError, TimeoutError, httpx.TimeoutException) as timeout_exc:
            logger.warning(
                f"[ORDER TIMEOUT] Order placement timed out for client_order_id={client_order_id}. "
                f"Executing Query-Before-Retry verification at 021 broker..."
            )
            # Query-Before-Retry Loop: Verify whether the broker actually accepted the order
            queried_order = None
            try:
                # 1. Direct fetch by client_order_id
                queried_order = await self.broker.get_order(client_order_id)
            except Exception as q_err:
                logger.debug(f"[QUERY-BEFORE-RETRY] get_order({client_order_id}) direct fetch failed: {q_err}")

            if not queried_order:
                # 2. Fall back to scanning all broker orders for matching client_order_id or order_id
                try:
                    all_orders = await self.broker.get_orders()
                    for o in all_orders:
                        if getattr(o, "client_order_id", None) == client_order_id or getattr(o, "order_id", None) == client_order_id:
                            queried_order = o
                            break
                except Exception as q2_err:
                    logger.warning(f"[QUERY-BEFORE-RETRY] get_orders scan failed: {q2_err}")

            if queried_order and queried_order.order_id:
                logger.info(
                    f"[QUERY-BEFORE-RETRY RECOVERY SUCCESS] Order {client_order_id} (Broker ID: {queried_order.order_id}) "
                    f"was accepted by broker despite network timeout! Status: {queried_order.status}"
                )
                self._order_to_strategy[queried_order.order_id] = intent.strategy_id

                resp = OrderPlacementResponse(
                    order_id=queried_order.order_id,
                    client_order_id=client_order_id,
                    broker_status=queried_order.status,
                    message="Order recovered via Query-Before-Retry loop after network timeout.",
                    filled_quantity=queried_order.filled_quantity,
                    average_price_paise=queried_order.average_price_paise,
                )

                # Process any fills that occurred
                if queried_order.fills:
                    for f in queried_order.fills:
                        self.handle_fill(f)
                elif queried_order.status == BrokerOrderStatus.EXECUTED or getattr(queried_order.status, "value", "").upper() in ("EXECUTED", "FILLED"):
                    fill = TradeFill(
                        order_id=queried_order.order_id,
                        client_order_id=client_order_id,
                        symbol=intent.symbol,
                        exchange=intent.exchange,
                        side=intent.side,
                        quantity=intent.quantity,
                        price_paise=queried_order.average_price_paise or intent.price_paise,
                    )
                    self.handle_fill(fill)

                # Persist recovered order record to DB
                _fire_and_forget(
                    _save_order_record(
                        order_id=queried_order.order_id,
                        client_order_id=client_order_id,
                        strategy_id=intent.strategy_id,
                        symbol=intent.symbol,
                        exchange=intent.exchange.value if hasattr(intent.exchange, "value") else str(intent.exchange),
                        side=intent.side.value,
                        quantity=intent.quantity,
                        price_paise=intent.price_paise,
                        product=intent.product.value if hasattr(intent.product, "value") else str(intent.product),
                        status=queried_order.status.value.upper() if hasattr(queried_order.status, "value") else str(queried_order.status),
                    )
                )

                self.risk_engine.release_inflight_order(intent.strategy_id, client_order_id)
                # Cache recovered result in idempotency ledger
                async with self._idempotency_lock:
                    self._idempotency_ledger[dedup_key] = (time.monotonic(), (risk_result, resp))
                return risk_result, resp

            # If query confirms order is absent from broker, release in-flight and re-raise timeout exception
            self.risk_engine.release_inflight_order(intent.strategy_id, client_order_id)
            logger.error(
                f"[ORDER TIMEOUT CONFIRMED] Order {client_order_id} confirmed absent from 021 broker after query check."
            )
            raise timeout_exc

        except Exception as e:
            # On general exception / non-timeout broker failure: release in-flight to prevent ghost limits
            self.risk_engine.release_inflight_order(intent.strategy_id, client_order_id)
            logger.error(f"[EXECUTION ERROR] Order {client_order_id} failed: {e}")
            raise

    def handle_fill(self, fill: TradeFill) -> None:
        """Handle execution fill: update in-flight order, update strategy, check loss limit."""
        strategy_id = (
            self._order_to_strategy.get(fill.order_id)
            or self._client_to_strategy.get(fill.client_order_id or "")
        )

        if not strategy_id:
            # Fallback search across active strategies
            for s in self.strategy_manager.list_strategies():
                if fill.symbol in s.symbols:
                    strategy_id = s.strategy_id
                    break

        if not strategy_id:
            logger.warning(f"[EXECUTION] Unmatched fill {fill.order_id} for symbol {fill.symbol}")
            return

        # Release in-flight working quantity
        cid = fill.client_order_id
        strat_inflight = self.risk_engine._inflight_orders.get(strategy_id, {})
        if not cid or cid not in strat_inflight:
            if fill.order_id in strat_inflight:
                cid = fill.order_id
            else:
                for k, v in list(strat_inflight.items()):
                    if v.get("symbol") == fill.symbol:
                        cid = k
                        break

        if cid:
            self.risk_engine.release_inflight_order(
                strategy_id=strategy_id,
                client_order_id=cid,
                filled_qty=fill.quantity,
            )
        else:
            # If no specific key found, decrement any in-flight order for this symbol
            for k, v in list(strat_inflight.items()):
                if v.get("symbol") == fill.symbol:
                    self.risk_engine.release_inflight_order(strategy_id, k, fill.quantity)
                    break

        # Route fill to strategy (updates position, realized P&L, charges)
        self.strategy_manager.route_fill(strategy_id, fill)

        # Persist fill to database
        _fire_and_forget(
            _save_fill_record(
                order_id=fill.order_id,
                strategy_id=strategy_id,
                symbol=fill.symbol,
                side=fill.side.value,
                quantity=fill.quantity,
                price_paise=fill.price_paise,
                brokerage_paise=fill.brokerage_paise,
                fee_paise=fill.fee_paise,
            )
        )

        # Re-verify daily loss after fill accounting
        strat = self.strategy_manager.get_strategy(strategy_id)
        if strat:
            config = self.risk_engine.get_strategy_config(strategy_id)
            current_pnl = strat.net_pnl_paise
            if current_pnl <= -config.max_daily_loss_paise:
                strat.halt()
                logger.critical(
                    f"[AUTO-HALT] Strategy {strategy_id} breached daily loss limit after fill: "
                    f"Net P&L=Rs.{current_pnl/100:.2f} (Limit: Rs.{config.max_daily_loss_paise/100:.2f})"
                )

    def handle_order_cancelled_or_rejected(self, client_order_id: str, order_id: Optional[str] = None) -> None:
        """Release in-flight quantity when an order is cancelled or rejected."""
        strategy_id = (
            self._client_to_strategy.get(client_order_id)
            or (self._order_to_strategy.get(order_id) if order_id else None)
        )
        if strategy_id and client_order_id:
            self.risk_engine.release_inflight_order(strategy_id, client_order_id)
