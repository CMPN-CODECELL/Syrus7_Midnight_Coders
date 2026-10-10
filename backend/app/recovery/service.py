import asyncio
import logging
from datetime import datetime, time, timezone
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
    rehydrated_strategies: list[str] = Field(default_factory=list)
    rehydrated_fills_count: int = 0
    discrepancies_detected: list[str] = Field(default_factory=list)
    reconciled_successfully: bool = True
    actions_taken: list[str] = Field(default_factory=list)


class RecoveryService:
    """State Recovery & Reconciliation Service (L2, L3, L4, L6).

    Recovers platform state after crash, network outage, or mid-trade restart:
    1. **Position Re-Hydration** – Queries today's executed fills from the
       database and replays them into each strategy's in-memory ``positions``,
       ``fills``, ``realized_pnl_paise``, and ``total_charges_paise`` so that
       the strategy resumes with accurate state rather than starting flat.
    2. Fetches current real positions and orders from broker.
    3. Aligns strategy positions with broker account reality.
    4. Rebuilds in-flight / working orders in RiskEngine.
    5. Detects position drift or unmanaged orphaned positions.
    6. Checks if risk limits (daily loss) were breached during downtime.
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

    # ------------------------------------------------------------------
    # Position Re-Hydration from Database
    # ------------------------------------------------------------------

    async def _rehydrate_positions_from_db(self, report: ReconciliationReport) -> None:
        """Replay today's persisted fills into each strategy's in-memory state.

        This is the critical step that ensures a mid-trade server restart does
        **not** lose open positions or cumulative P&L.

        Algorithm:
          1. Open a fresh DB session and query all ``TradeFillRecord`` rows
             created today, ordered by timestamp ASC (chronological replay).
          2. Group the fills by ``strategy_id``.
          3. For each registered strategy, replay its fills through the
             strategy's ``on_fill()`` method, which correctly updates
             ``positions``, ``realized_pnl_paise``, and ``total_charges_paise``.
        """
        try:
            from app.database.session import AsyncSessionLocal
            from app.database.models.models import TradeFillRecord
            from sqlalchemy import select

            # Determine the start of today (00:00 UTC)
            now_utc = datetime.now(timezone.utc)
            today_start = datetime.combine(now_utc.date(), time.min, tzinfo=timezone.utc)

            async with AsyncSessionLocal() as session:
                stmt = (
                    select(TradeFillRecord)
                    .where(TradeFillRecord.timestamp >= today_start)
                    .order_by(TradeFillRecord.timestamp.asc())
                )
                result = await session.execute(stmt)
                fill_records = list(result.scalars().all())

            if not fill_records:
                logger.info("[RECOVERY] No fills found in DB for today – positions start flat.")
                return

            # Group fills by strategy_id for targeted replay
            fills_by_strategy: dict[str, list[TradeFillRecord]] = {}
            for fr in fill_records:
                fills_by_strategy.setdefault(fr.strategy_id, []).append(fr)

            total_replayed = 0
            for strat in self.strategy_manager.list_strategies():
                strat_fills = fills_by_strategy.get(strat.strategy_id, [])
                if not strat_fills:
                    # No DB fills for this strategy – leave its current
                    # in-memory state untouched (it may have been populated
                    # through other channels before reconciliation).
                    continue

                # Reset the strategy's in-memory state before replay to avoid
                # double-counting if reconcile_state() is called more than once.
                # ONLY reset if we have DB fills to replay.
                strat.positions.clear()
                strat.fills.clear()
                strat.realized_pnl_paise = 0
                strat.unrealized_pnl_paise = 0
                strat.total_charges_paise = 0

                for fr in strat_fills:
                    side = Side.BUY if fr.side.upper() == "BUY" else Side.SELL
                    fill = TradeFill(
                        order_id=fr.order_id,
                        client_order_id=fr.order_id,  # Best available key
                        symbol=fr.symbol.upper(),
                        exchange=Exchange.NSE,
                        side=side,
                        quantity=fr.quantity,
                        price_paise=fr.price_paise,
                        brokerage_paise=fr.brokerage_paise or 0,
                        fee_paise=fr.fee_paise or 0,
                    )
                    strat.on_fill(fill)
                    total_replayed += 1

                report.rehydrated_strategies.append(strat.strategy_id)
                net_positions = {
                    sym: data["net_qty"]
                    for sym, data in strat.positions.items()
                    if data["net_qty"] != 0
                }
                logger.info(
                    f"[RECOVERY] Re-hydrated strategy {strat.strategy_id}: "
                    f"{len(strat_fills)} fills replayed, "
                    f"net positions = {net_positions}, "
                    f"realized P&L = ₹{strat.realized_pnl_paise / 100:.2f}"
                )
                report.actions_taken.append(
                    f"Re-hydrated {strat.strategy_id} with {len(strat_fills)} fills "
                    f"(net positions: {net_positions})"
                )

            report.rehydrated_fills_count = total_replayed
            logger.info(
                f"[RECOVERY] Position re-hydration complete: "
                f"{total_replayed} fills replayed across {len(report.rehydrated_strategies)} strategies."
            )

        except Exception as e:
            logger.error(f"[RECOVERY] Position re-hydration from DB failed: {e}")
            report.discrepancies_detected.append(
                f"DB position re-hydration error: {e}"
            )

    # ------------------------------------------------------------------
    # Full Reconciliation
    # ------------------------------------------------------------------

    async def reconcile_state(self) -> ReconciliationReport:
        """Execute full state reconciliation with broker."""
        report = ReconciliationReport()
        logger.info("[RECOVERY] Starting state reconciliation with broker...")

        # ── Phase 0: Re-hydrate strategy positions from DB fills ──
        await self._rehydrate_positions_from_db(report)

        # ── Phase 1: Fetch broker positions and orders ──
        try:
            broker_positions = await self.broker.get_positions()
            broker_orders = await self.broker.get_orders()
        except Exception as e:
            report.reconciled_successfully = False
            report.discrepancies_detected.append(f"Failed to query broker state: {e}")
            logger.error(f"[RECOVERY ERROR] Cannot query broker: {e}")
            return report

        report.broker_positions_count = len(broker_positions)

        # ── Phase 2: Rebuild Broker Position Lookup ──
        broker_pos_by_symbol: dict[str, int] = {}
        for p in broker_positions:
            broker_pos_by_symbol[p.symbol.upper()] = p.net_quantity

        # ── Phase 3: Sum up platform positions across all active strategies ──
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

        # ── Phase 4: Detect Position Drift / Discrepancies ──
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

        # ── Phase 5: Reconcile Open / Working Orders in Risk Engine ──
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

        # ── Phase 6: Re-evaluate Risk Engine constraints post-recovery ──
        for strat in self.strategy_manager.list_strategies():
            config = self.risk_engine.get_strategy_config(strat.strategy_id)
            if strat.net_pnl_paise <= -config.max_daily_loss_paise:
                strat.halt()
                report.actions_taken.append(
                    f"Halted strategy {strat.strategy_id} due to daily loss breach post-reconciliation."
                )

        report.reconciled_successfully = len(report.discrepancies_detected) == 0
        logger.info(
            f"[RECOVERY] Reconciliation complete. "
            f"Re-hydrated: {len(report.rehydrated_strategies)} strategies ({report.rehydrated_fills_count} fills). "
            f"Discrepancies: {len(report.discrepancies_detected)}, "
            f"Open orders re-registered: {report.open_orders_count}"
        )
        return report
