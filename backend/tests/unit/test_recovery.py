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
