import pytest

from app.broker.mock_021 import Mock021
from app.broker.models import BrokerOrder, BrokerPosition, OrderPlacementRequest, TradeFill
from app.core.enums import BrokerOrderStatus, Exchange, Side, StrategyStatus
from app.recovery.service import RecoveryService
from app.risk.engine import RiskEngine
from app.strategies.manager import StrategyManager
from app.strategies.time_based import TimeBasedStrategy


@pytest.mark.asyncio
async def test_recovery_service_detects_clean_state_alignment():
    broker = Mock021()
    broker.reset()
    risk_engine = RiskEngine()
    manager = StrategyManager()

    strat = TimeBasedStrategy(strategy_id="s_clean", symbol="RELIANCE")
    manager.register_strategy(strat)
    strat.start()

    # Buy 5 on broker
    await broker.place_order(OrderPlacementRequest(symbol="RELIANCE", side=Side.BUY, quantity=5, price_paise=290000))
    # Fill 5 on strategy
    strat.on_fill(TradeFill(order_id="o1", client_order_id="c1", symbol="RELIANCE", exchange=Exchange.NSE, side=Side.BUY, quantity=5, price_paise=290000))

    recovery = RecoveryService(strategy_manager=manager, risk_engine=risk_engine, broker=broker)
    report = await recovery.reconcile_state()

    assert report.reconciled_successfully is True
    assert len(report.discrepancies_detected) == 0
    assert report.broker_positions_count == 1
    assert report.strategy_positions_count == 1


@pytest.mark.asyncio
async def test_recovery_service_detects_position_drift():
    broker = Mock021()
    broker.reset()
    risk_engine = RiskEngine()
    manager = StrategyManager()

    strat = TimeBasedStrategy(strategy_id="s_drift", symbol="INFY")
    manager.register_strategy(strat)
    strat.start()

    # Broker has 10 shares, but strategy only knows about 5
    await broker.place_order(OrderPlacementRequest(symbol="INFY", side=Side.BUY, quantity=10, price_paise=150000))
    strat.on_fill(TradeFill(order_id="o1", client_order_id="c1", symbol="INFY", exchange=Exchange.NSE, side=Side.BUY, quantity=5, price_paise=150000))

    recovery = RecoveryService(strategy_manager=manager, risk_engine=risk_engine, broker=broker)
    report = await recovery.reconcile_state()

    assert report.reconciled_successfully is False
    assert len(report.discrepancies_detected) == 1
    assert "Position drift on INFY" in report.discrepancies_detected[0]


@pytest.mark.asyncio
async def test_recovery_service_rehydrates_strategy_positions_from_db():
    """Verify that RecoveryService re-hydrates in-memory positions and fills

    for registered strategies by replaying today's database trade fills on startup.
    """
    from datetime import datetime, timezone
    from app.database.session import init_db, AsyncSessionLocal
    from app.database.models.models import StrategyRecord, OrderRecord, TradeFillRecord

    await init_db()

    now = datetime.now(timezone.utc)
    strat_id = f"s_reh_{int(now.timestamp())}"
    ord1_id = f"o_reh_1_{int(now.timestamp())}"
    ord2_id = f"o_reh_2_{int(now.timestamp())}"

    async with AsyncSessionLocal() as session:
        strat_record = StrategyRecord(
            id=strat_id,
            name="Rehydration Test",
            symbol="RELIANCE",
            status="RUNNING",
        )
        session.add(strat_record)

        o1 = OrderRecord(
            id=ord1_id,
            client_order_id=ord1_id,
            strategy_id=strat_id,
            symbol="RELIANCE",
            side="BUY",
            quantity=10,
            price_paise=250000,
            status="EXECUTED",
            created_at=now,
        )
        o2 = OrderRecord(
            id=ord2_id,
            client_order_id=ord2_id,
            strategy_id=strat_id,
            symbol="RELIANCE",
            side="SELL",
            quantity=3,
            price_paise=260000,
            status="EXECUTED",
            created_at=now,
        )
        session.add(o1)
        session.add(o2)

        f1 = TradeFillRecord(
            order_id=ord1_id,
            strategy_id=strat_id,
            symbol="RELIANCE",
            side="BUY",
            quantity=10,
            price_paise=250000,
            timestamp=now,
        )
        f2 = TradeFillRecord(
            order_id=ord2_id,
            strategy_id=strat_id,
            symbol="RELIANCE",
            side="SELL",
            quantity=3,
            price_paise=260000,
            timestamp=now,
        )
        session.add(f1)
        session.add(f2)
        await session.commit()

    broker = Mock021()
    broker.reset()
    # Broker has 7 RELIANCE (matching net DB fills: 10 BUY - 3 SELL = 7)
    await broker.place_order(OrderPlacementRequest(symbol="RELIANCE", side=Side.BUY, quantity=7, price_paise=250000))

    risk_engine = RiskEngine()
    manager = StrategyManager()

    # Fresh strategy on platform reboot starts completely flat (0 positions)
    strat = TimeBasedStrategy(strategy_id=strat_id, symbol="RELIANCE")
    manager.register_strategy(strat)
    strat.start()

    assert strat.get_position("RELIANCE") == 0
    assert len(strat.fills) == 0

    recovery = RecoveryService(strategy_manager=manager, risk_engine=risk_engine, broker=broker)
    report = await recovery.reconcile_state()

    assert strat_id in report.rehydrated_strategies
    assert report.rehydrated_fills_count >= 2
    assert strat.get_position("RELIANCE") == 7
    assert len(strat.fills) == 2
    assert report.reconciled_successfully is True
    assert len(report.discrepancies_detected) == 0

