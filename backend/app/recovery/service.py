import asyncio
import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.broker.interface import BrokerInterface
from app.broker.models import BrokerOrder, BrokerPosition, TradeFill
from app.core.enums import BrokerOrderStatus, Exchange, Side, StrategyStatus
from app.risk.engine import RiskEngine
from app.strategies.manager import StrategyManager

logger = logging.getLogger(__name__)


class ReconciliationReport(BaseModel):
    """Audit report generated after reconciling state with broker."""

    broker_positions_count: int = 0
    strategy_positions_count: int = 0
    open_orders_count: int = 0
    filled_orders_count: int = 0
    discrepancies_detected: list[str] = Field(default_factory=list)
    reconciled_successfully: bool = True
    actions_taken: list[str] = Field(default_factory=list)


class RecoveryService:
    """State Recovery & Reconciliation Service (L2, L3, L4).

    Recovers platform state after crash, network outage, or mid-trade restart:
    1. Fetches current real positions and orders from broker.
    2. Aligns strategy positions with broker account reality.
    3. Rebuilds in-flight / working orders in RiskEngine.
    4. Detects position drift or unmanaged orphaned positions.
    5. Checks if risk limits (daily loss) were breached during downtime.
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

    async def reconcile_state(self) -> ReconciliationReport:
        """Execute full state reconciliation with broker."""
        report = ReconciliationReport()
        logger.info("[RECOVERY] Starting state reconciliation with broker...")

        # 1. Fetch broker positions and orders
        try:
            broker_positions = await self.broker.get_positions()
            broker_orders = await self.broker.get_orders()
        except Exception as e:
            report.reconciled_successfully = False
            report.discrepancies_detected.append(f"Failed to query broker state: {e}")
            logger.error(f"[RECOVERY ERROR] Cannot query broker: {e}")
            return report

        report.broker_positions_count = len(broker_positions)

        # 2. Rebuild Broker Position Lookup
        broker_pos_by_symbol: dict[str, int] = {}
        for p in broker_positions:
            broker_pos_by_symbol[p.symbol.upper()] = p.net_quantity

        # 3. Sum up platform positions across all active strategies
        strategy_pos_by_symbol: dict[str, int] = {}
        for strat in self.strategy_manager.list_strategies():
            for sym, pos_data in strat.positions.items():
                qty = pos_data.get("net_qty", 0)
                if qty != 0:
                    sym_upper = sym.upper()
                    strategy_pos_by_symbol[sym_upper] = (
                        strategy_pos_by_symbol.get(sym_upper, 0) + qty
                    )

        report.strategy_positions_count = len(strategy_pos_by_symbol)

        # 4. Detect Position Drift / Discrepancies
        all_symbols = set(broker_pos_by_symbol.keys()) | set(strategy_pos_by_symbol.keys())
        for sym in all_symbols:
            b_qty = broker_pos_by_symbol.get(sym, 0)
            s_qty = strategy_pos_by_symbol.get(sym, 0)
            if b_qty != s_qty:
                drift_msg = (
                    f"Position drift on {sym}: Broker net qty = {b_qty}, "
                    f"Platform strategy net qty = {s_qty} (Difference: {b_qty - s_qty})"
                )
                report.discrepancies_detected.append(drift_msg)
                logger.warning(f"[RECOVERY] {drift_msg}")

        # 5. Reconcile Open / Working Orders in Risk Engine
        self.risk_engine.clear_all_inflight()
        for ord in broker_orders:
            if ord.status in (BrokerOrderStatus.PLACED, BrokerOrderStatus.PENDING, BrokerOrderStatus.RECEIVED):
                report.open_orders_count += 1
                # Find matching strategy
                target_strat_id = None
                for s in self.strategy_manager.list_strategies():
                    if ord.symbol in s.symbols:
                        target_strat_id = s.strategy_id
                        break

                if target_strat_id:
                    self.risk_engine.register_inflight_order(
                        strategy_id=target_strat_id,
                        client_order_id=ord.client_order_id or ord.order_id,
                        symbol=ord.symbol,
                        side=ord.side,
                        quantity=ord.quantity - ord.filled_quantity,
                        price_paise=ord.price_paise,
                    )
                    report.actions_taken.append(
                        f"Re-registered in-flight order {ord.order_id} ({ord.symbol} {ord.side.value} "
                        f"{ord.quantity - ord.filled_quantity}) for strategy {target_strat_id}"
                    )
            elif ord.status == BrokerOrderStatus.EXECUTED:
                report.filled_orders_count += 1

        # 6. Re-evaluate Risk Engine constraints post-recovery
        for strat in self.strategy_manager.list_strategies():
            config = self.risk_engine.get_strategy_config(strat.strategy_id)
            if strat.net_pnl_paise <= -config.max_daily_loss_paise:
                strat.halt()
                report.actions_taken.append(
                    f"Halted strategy {strat.strategy_id} due to daily loss breach post-reconciliation."
                )

        report.reconciled_successfully = len(report.discrepancies_detected) == 0
        logger.info(
            f"[RECOVERY] Reconciliation complete. Discrepancies: {len(report.discrepancies_detected)}, "
            f"Open orders re-registered: {report.open_orders_count}"
        )
        return report
