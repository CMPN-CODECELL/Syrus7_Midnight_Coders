import pytest

from app.broker.mock_021 import Mock021
from app.broker.models import TradeFill
from app.core.enums import Exchange, Side, StrategyStatus
from app.execution.engine import ExecutionEngine
from app.risk.engine import RiskEngine
from app.risk.models import RiskConfig
from app.strategies.intents import OrderIntent
from app.strategies.manager import StrategyManager
from app.strategies.time_based import TimeBasedStrategy


@pytest.mark.asyncio
async def test_execution_engine_places_order_and_routes_fills():
    broker = Mock021()
    broker.reset()
    risk_engine = RiskEngine()
    manager = StrategyManager()

    strat = TimeBasedStrategy(strategy_id="s_exec", symbol="RELIANCE", quantity=2)
    manager.register_strategy(strat)
    manager.start_all()

    exec_engine = ExecutionEngine(strategy_manager=manager, risk_engine=risk_engine, broker=broker)

    intent = OrderIntent(
        intent_id="intent_101",
        strategy_id="s_exec",
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=2,
    )

    risk_res, order_res = await exec_engine.execute_intent(intent)
    assert risk_res.passed is True
    assert order_res is not None
    assert order_res.order_id is not None

    # Broker fill simulation
    fill = TradeFill(
        order_id=order_res.order_id,
        client_order_id="intent_101",
        symbol="RELIANCE",
        exchange=Exchange.NSE,
        side=Side.BUY,
        quantity=2,
        price_paise=290000,
    )
    exec_engine.handle_fill(fill)

    # Strategy received the fill
    assert strat.get_position("RELIANCE") == 2
    assert len(strat.fills) == 1
    # In-flight order was cleared
    assert risk_engine.get_inflight_quantity("s_exec", "RELIANCE") == 0


@pytest.mark.asyncio
async def test_execution_engine_auto_halts_on_loss_breach_after_fill():
    broker = Mock021()
    broker.reset()
    risk_engine = RiskEngine()
    # Loss limit: ₹300 (30,000 paise)
    risk_engine.set_strategy_config("s_loss_exec", RiskConfig(max_daily_loss_paise=30000))

    manager = StrategyManager()
    strat = TimeBasedStrategy(strategy_id="s_loss_exec", symbol="TCS", quantity=5)
    manager.register_strategy(strat)
    manager.start_all()

    exec_engine = ExecutionEngine(strategy_manager=manager, risk_engine=risk_engine, broker=broker)

    # 1. Buy 5 TCS @ ₹4000
    buy_fill = TradeFill(
        order_id="b1",
        client_order_id="c_buy",
        symbol="TCS",
        exchange=Exchange.NSE,
        side=Side.BUY,
        quantity=5,
        price_paise=400000,
    )
    exec_engine.handle_fill(buy_fill)
    assert strat.status == StrategyStatus.RUNNING

    # 2. Sell 5 TCS @ ₹3900 (Loss = ₹100 * 5 = ₹500 = 50,000 paise loss > 30,000 paise)
    sell_fill = TradeFill(
        order_id="s1",
        client_order_id="c_sell",
        symbol="TCS",
        exchange=Exchange.NSE,
        side=Side.SELL,
        quantity=5,
        price_paise=390000,
    )
    exec_engine.handle_fill(sell_fill)

    # Strategy should now be automatically HALTED by RiskEngine via ExecutionEngine
    assert strat.status == StrategyStatus.HALTED
    assert strat.net_pnl_paise < -30000
