import asyncio
import pytest

from app.broker.mock_021 import Mock021
from app.broker.models import OrderPlacementRequest, TradeFill
from app.core.enums import Book, Exchange, KillSwitchResult, Product, RiskReason, Side, StrategyStatus, Validity
from app.execution.engine import ExecutionEngine
from app.killswitch.service import KillSwitchService
from app.risk.engine import RiskEngine
from app.risk.models import RiskConfig
from app.strategies.base import BaseStrategy
from app.strategies.intents import OrderIntent
from app.strategies.manager import StrategyManager


class BuggyRunawayLoopStrategy(BaseStrategy):
    """Simulates a broken/buggy strategy that fires orders in a rapid loop on every tick."""

    def __init__(self, strategy_id: str, symbol: str) -> None:
        super().__init__(strategy_id=strategy_id, name="Buggy Runaway Strategy", symbols=[symbol])

    def on_tick(self, tick):
        # Emits orders uncontrollably
        return [
            OrderIntent(
                strategy_id=self.strategy_id,
                symbol=self.symbols[0],
                side=Side.BUY,
                quantity=1,
            )
        ]

    def on_candle(self, candle):
        return []


@pytest.mark.asyncio
async def test_runaway_strategy_contained_by_platform_risk_engine():
    """Verify a runaway strategy emitting 50 orders in a loop cannot breach risk limits."""
    risk_engine = RiskEngine()
    # Strategy allowed max 5 orders/minute, auto-halt after 3 consecutive breaches
    risk_engine.set_strategy_config(
        "strat_buggy",
        RiskConfig(
            max_orders_per_minute=5,
            max_runaway_breaches=3,
            max_position_size=10,
        ),
    )

    strat = BuggyRunawayLoopStrategy("strat_buggy", "INFY")
    strat.start()

    passed_count = 0
    rejected_count = 0

    # Simulate 50 order intents emitted in sub-second succession
    for i in range(50):
        intent = OrderIntent(
            intent_id=f"bug_{i}",
            strategy_id="strat_buggy",
            symbol="INFY",
            side=Side.BUY,
            quantity=1,
        )
        res = risk_engine.evaluate_intent(intent, strat)
        if res.passed:
            passed_count += 1
        else:
            rejected_count += 1

    # Exactly 5 orders pass the rate limit, the rest are blocked
    assert passed_count == 5
    assert rejected_count == 45
    # The runaway loop triggered auto-halt on the strategy
    assert strat.status == StrategyStatus.HALTED


@pytest.mark.asyncio
async def test_in_flight_position_risk_during_concurrent_orders():
    """Verify position limit is strictly protected even with asynchronous network latency."""
    broker = Mock021()
    broker.reset()
    risk_engine = RiskEngine()
    # Max position allowed is 5 shares
    risk_engine.set_strategy_config(
        "strat_concurrent",
        RiskConfig(max_position_size=5, max_order_quantity=5, max_orders_per_minute=50),
    )

    manager = StrategyManager()
    strat = BuggyRunawayLoopStrategy("strat_concurrent", "RELIANCE")
    manager.register_strategy(strat)
    strat.start()

    exec_engine = ExecutionEngine(strategy_manager=manager, risk_engine=risk_engine, broker=broker)

    # Order 1: BUY 3 shares
    intent1 = OrderIntent(intent_id="c_1", strategy_id="strat_concurrent", symbol="RELIANCE", side=Side.BUY, quantity=3)
    r1, _ = await exec_engine.execute_intent(intent1)
    assert r1.passed is True

    # Order 2: BUY 3 shares (sent before order 1 is confirmed filled)
    # Existing = 0, Inflight = 3 -> Projected = 6 > 5 -> REJECTED!
    intent2 = OrderIntent(intent_id="c_2", strategy_id="strat_concurrent", symbol="RELIANCE", side=Side.BUY, quantity=3)
    r2, _ = await exec_engine.execute_intent(intent2)
    assert r2.passed is False
    assert r2.reason == RiskReason.MAX_POSITION_SIZE_EXCEEDED

    # Order 3: BUY 2 shares (Existing 0 + Inflight 3 + Order 2 = 5 <= 5) -> APPROVED!
    intent3 = OrderIntent(intent_id="c_3", strategy_id="strat_concurrent", symbol="RELIANCE", side=Side.BUY, quantity=2)
    r3, _ = await exec_engine.execute_intent(intent3)
    assert r3.passed is True


@pytest.mark.asyncio
async def test_kill_switch_clears_inflight_and_halts_all_intents():
    """Activating kill switch blocks all queued intents and squares off broker positions."""
    broker = Mock021()
    broker.reset()
    risk_engine = RiskEngine()
    manager = StrategyManager()

    strat = BuggyRunawayLoopStrategy("strat_ks", "TCS")
    manager.register_strategy(strat)
    strat.start()

    # Create open position of 10 shares on broker
    await broker.place_order(
        OrderPlacementRequest(
            symbol="TCS",
            side=Side.BUY,
            quantity=10,
            price_paise=400000,
        )
    )

    kill_switch = KillSwitchService(risk_engine=risk_engine, strategy_manager=manager, broker=broker)
    report = await kill_switch.activate()

    assert report.result == KillSwitchResult.VERIFIED
    assert risk_engine.kill_switch_active is True
    assert strat.status == StrategyStatus.HALTED

    # Broker is completely flat
    broker_positions = await broker.get_positions()
    assert all(p.net_quantity == 0 for p in broker_positions)

    # Any new intent is unconditionally rejected
    intent = OrderIntent(strategy_id="strat_ks", symbol="TCS", side=Side.BUY, quantity=1)
    res = risk_engine.evaluate_intent(intent, strat)
    assert res.passed is False
    assert res.reason == RiskReason.KILL_SWITCH_ACTIVE
