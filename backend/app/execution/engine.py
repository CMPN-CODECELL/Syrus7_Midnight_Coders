import asyncio
import logging
from typing import Optional

from app.broker.errors import BrokerError
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
    - In-flight (open/pending) order registration to protect position limits.
    - Broker order submission with error classification.
    - Order fill & partial fill routing back to strategies and risk counters.
    - In-flight release on cancellation, rejection, or fill completion.
    """

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

    async def execute_intent(
        self,
        intent: OrderIntent,
    ) -> tuple[RiskCheckResult, Optional[OrderPlacementResponse]]:
        """Process an order intent end-to-end: Risk gate -> in-flight tracking -> Broker."""
        strat = self.strategy_manager.get_strategy(intent.strategy_id)
        if not strat:
            result = RiskCheckResult(
                passed=False,
                reason=RiskReason.SYMBOL_HALTED,
                message=f"Strategy {intent.strategy_id} is not registered",
                severity=Severity.ERROR,
            )
            return result, None

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

            return risk_result, resp



        except Exception as e:
            # On exception / broker failure: release in-flight to prevent ghost limits
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
        if fill.client_order_id:
            self.risk_engine.release_inflight_order(
                strategy_id=strategy_id,
                client_order_id=fill.client_order_id,
                filled_qty=fill.quantity,
            )

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
