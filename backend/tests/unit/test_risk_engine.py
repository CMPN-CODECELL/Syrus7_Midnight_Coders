import asyncio
from datetime import datetime, timedelta, timezone
import pytest

from app.broker import Mock021, OrderPlacementRequest
from app.broker.models import TradeFill
from app.core.enums import Book, Exchange, KillSwitchResult, Product, RiskReason, Side, StrategyStatus
from app.killswitch import KillSwitchService
from app.risk import RiskCheckResult, RiskConfig, RiskEngine
from app.strategies import BreakoutStrategy, StrategyManager, TimeBasedStrategy
from app.strategies.intents import OrderIntent


@pytest.fixture
def risk_engine():
    engine = RiskEngine()
    engine.kill_switch_active = False
    return engine


def test_kill_switch_blocks_orders(risk_engine: RiskEngine):
    strat = TimeBasedStrategy(strategy_id="s1", symbol="RELIANCE")
    strat.start()

    intent = OrderIntent(
        strategy_id="s1",
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=5,
    )

    # Allowed initially
    res1 = risk_engine.evaluate_intent(intent, strat)
    assert res1.passed is True

    # Lock down with kill switch
    risk_engine.kill_switch_active = True
    res2 = risk_engine.evaluate_intent(intent, strat)
    assert res2.passed is False
    assert res2.reason == RiskReason.KILL_SWITCH_ACTIVE


def test_max_position_size_limit(risk_engine: RiskEngine):
    strat = TimeBasedStrategy(strategy_id="s1", symbol="RELIANCE")
    strat.start()

    # Set limit of 10 shares
    risk_engine.set_strategy_config(
        "s1", RiskConfig(max_position_size=10, max_orders_per_minute=20)
    )

    # Buy 8 -> allowed
    intent1 = OrderIntent(strategy_id="s1", symbol="RELIANCE", side=Side.BUY, quantity=8)
    assert risk_engine.evaluate_intent(intent1, strat).passed is True

    # Simulate fill of 8
    strat.on_fill(TradeFill(order_id="o1", client_order_id="c1", symbol="RELIANCE", exchange=Exchange.NSE, side=Side.BUY, quantity=8, price_paise=290000))
    assert strat.get_position("RELIANCE") == 8

    # Buy 5 more -> 8 + 5 = 13 > 10 -> REJECT
    intent2 = OrderIntent(strategy_id="s1", symbol="RELIANCE", side=Side.BUY, quantity=5)
    res = risk_engine.evaluate_intent(intent2, strat)
    assert res.passed is False
    assert res.reason == RiskReason.MAX_POSITION_SIZE_EXCEEDED

    # Selling 3 is allowed -> 8 - 3 = 5 <= 10
    intent3 = OrderIntent(strategy_id="s1", symbol="RELIANCE", side=Side.SELL, quantity=3)
    assert risk_engine.evaluate_intent(intent3, strat).passed is True


def test_rate_limit_sliding_window(risk_engine: RiskEngine):
    strat = TimeBasedStrategy(strategy_id="s_rate", symbol="INFY")
    strat.start()

    # Allow max 3 orders per minute
    risk_engine.set_strategy_config(
        "s_rate", RiskConfig(max_orders_per_minute=3, max_position_size=100)
    )

    now = datetime(2026, 10, 9, 10, 0, 0, tzinfo=timezone.utc)
    intent = OrderIntent(strategy_id="s_rate", symbol="INFY", side=Side.BUY, quantity=1)

    assert risk_engine.evaluate_intent(intent, strat, current_time=now).passed is True
    assert risk_engine.evaluate_intent(intent, strat, current_time=now + timedelta(seconds=10)).passed is True
    assert risk_engine.evaluate_intent(intent, strat, current_time=now + timedelta(seconds=20)).passed is True

    # 4th order within 60s window -> REJECT
    res_rejected = risk_engine.evaluate_intent(intent, strat, current_time=now + timedelta(seconds=30))
    assert res_rejected.passed is False
    assert res_rejected.reason == RiskReason.MAX_ORDERS_PER_MINUTE_EXCEEDED

    # After 65 seconds, previous orders expired -> ALLOWED again
    res_allowed = risk_engine.evaluate_intent(intent, strat, current_time=now + timedelta(seconds=65))
    assert res_allowed.passed is True


def test_max_daily_loss_limit_and_auto_halt(risk_engine: RiskEngine):
    strat = BreakoutStrategy(strategy_id="s_loss", symbol="TCS", quantity=5)
    strat.start()

    # Limit ₹500 loss (50,000 paise)
    risk_engine.set_strategy_config("s_loss", RiskConfig(max_daily_loss_paise=50000))

    # Buy 10 @ ₹4000
    strat.on_fill(TradeFill(order_id="o1", client_order_id="c1", symbol="TCS", exchange=Exchange.NSE, side=Side.BUY, quantity=10, price_paise=400000))

    # Sell 10 @ ₹3940 (loss of ₹60/share * 10 = ₹600 = 60,000 paise loss > 50,000)
    strat.on_fill(TradeFill(order_id="o2", client_order_id="c2", symbol="TCS", exchange=Exchange.NSE, side=Side.SELL, quantity=10, price_paise=394000))
    assert strat.net_pnl_paise < -50000

    # Next intent should be blocked and strategy HALTED
    intent = OrderIntent(strategy_id="s_loss", symbol="TCS", side=Side.BUY, quantity=1)
    res = risk_engine.evaluate_intent(intent, strat)
    assert res.passed is False
    assert res.reason == RiskReason.MAX_DAILY_LOSS_EXCEEDED
    assert strat.status == StrategyStatus.HALTED


def test_circuit_limits_pre_trade_sanity(risk_engine: RiskEngine):
    strat = TimeBasedStrategy(strategy_id="s_sanity", symbol="RELIANCE")
    strat.start()

    # RELIANCE circuits from instruments.csv are roughly 108700 to 132840 paise (or similar)
    inst = risk_engine.registry.find_by_symbol("RELIANCE")
    assert inst is not None

    # Intent with price wildly below lower circuit (e.g. ₹10.00 = 1000 paise)
    bad_price_intent = OrderIntent(
        strategy_id="s_sanity",
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=1,
        price_paise=1000,
    )
    res = risk_engine.evaluate_intent(bad_price_intent, strat)
    assert res.passed is False
    assert res.reason == RiskReason.PRICE_OUTSIDE_CIRCUIT


@pytest.mark.asyncio
async def test_kill_switch_service_completes_within_10s():
    broker = Mock021()
    broker.reset()
    risk_engine = RiskEngine()
    manager = StrategyManager()

    strat = TimeBasedStrategy(strategy_id="strat_kill", symbol="RELIANCE", quantity=10)
    manager.register_strategy(strat)
    manager.start_all()

    # Create an open position on the broker (LONG 10 RELIANCE)
    await broker.place_order(
        OrderPlacementRequest(
            symbol="RELIANCE",
            side=Side.BUY,
            quantity=10,
            price_paise=290000,
        )
    )
    positions_before = await broker.get_positions()
    assert len(positions_before) == 1
    assert positions_before[0].net_quantity == 10

    # Execute emergency kill switch
    kill_switch = KillSwitchService(
        risk_engine=risk_engine,
        strategy_manager=manager,
        broker=broker,
        settings=risk_engine.settings,
    )

    report = await kill_switch.activate()

    # Check assertions
    assert report.result == KillSwitchResult.VERIFIED
    assert report.completed_within_sla is True
    assert report.elapsed_seconds < 10.0
    assert report.positions_closed_count >= 1

    # Platform state check
    assert risk_engine.kill_switch_active is True
    assert strat.status == StrategyStatus.HALTED

    # Check broker positions are now flat
    positions_after = await broker.get_positions()
    assert all(p.net_quantity == 0 for p in positions_after)


def test_inflight_order_prevents_position_overshoot(risk_engine: RiskEngine):
    """If an order is pending at broker, subsequent intents must account for in-flight quantity."""
    strat = TimeBasedStrategy(strategy_id="s_inflight", symbol="RELIANCE")
    strat.start()

    # Limit is 10 shares
    risk_engine.set_strategy_config(
        "s_inflight", RiskConfig(max_position_size=10, max_order_quantity=10, max_orders_per_minute=20)
    )

    # First intent: Buy 6 shares
    intent1 = OrderIntent(
        intent_id="c1",
        strategy_id="s_inflight",
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=6,
    )
    res1 = risk_engine.evaluate_intent(intent1, strat)
    assert res1.passed is True

    # Order 1 passes risk and is in-flight at broker
    risk_engine.register_inflight_order(
        strategy_id="s_inflight",
        client_order_id="c1",
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=6,
    )

    # While Order 1 is still in-flight, strategy emits second intent for 6 shares
    # Position in strategy is still 0, but in-flight is 6 -> 0 + 6 + 6 = 12 > 10!
    intent2 = OrderIntent(
        intent_id="c2",
        strategy_id="s_inflight",
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=6,
    )
    res2 = risk_engine.evaluate_intent(intent2, strat)
    assert res2.passed is False
    assert res2.reason == RiskReason.MAX_POSITION_SIZE_EXCEEDED
    assert "in-flight=6" in res2.message

    # Now simulate Order 1 filled partially (4 shares filled, 2 still in-flight)
    strat.on_fill(TradeFill(order_id="o1", client_order_id="c1", symbol="RELIANCE", exchange=Exchange.NSE, side=Side.BUY, quantity=4, price_paise=290000))
    risk_engine.release_inflight_order("s_inflight", "c1", filled_qty=4)
    assert risk_engine.get_inflight_quantity("s_inflight", "RELIANCE") == 2
    assert strat.get_position("RELIANCE") == 4

    # Intent for 4 shares: current 4 + inflight 2 + intent 4 = 10 <= 10 -> ALLOWED!
    intent3 = OrderIntent(intent_id="c3", strategy_id="s_inflight", symbol="RELIANCE", side=Side.BUY, quantity=4)
    res3 = risk_engine.evaluate_intent(intent3, strat)
    assert res3.passed is True


def test_runaway_strategy_loop_auto_halt(risk_engine: RiskEngine):
    """Buggy strategy in tight loop breaching rate limit repeatedly is auto-halted."""
    strat = TimeBasedStrategy(strategy_id="s_buggy", symbol="RELIANCE")
    strat.start()

    # Rate limit: 2 orders/min, auto-halt after 3 consecutive breaches
    risk_engine.set_strategy_config(
        "s_buggy",
        RiskConfig(max_orders_per_minute=2, max_runaway_breaches=3),
    )

    now = datetime(2026, 10, 9, 10, 0, 0, tzinfo=timezone.utc)
    intent = OrderIntent(strategy_id="s_buggy", symbol="RELIANCE", side=Side.BUY, quantity=1)

    # 1st order -> pass
    assert risk_engine.evaluate_intent(intent, strat, current_time=now).passed is True
    # 2nd order -> pass
    assert risk_engine.evaluate_intent(intent, strat, current_time=now).passed is True

    # 3rd order -> 1st rate limit breach
    r1 = risk_engine.evaluate_intent(intent, strat, current_time=now)
    assert r1.passed is False
    assert strat.status == StrategyStatus.RUNNING

    # 4th order -> 2nd rate limit breach
    r2 = risk_engine.evaluate_intent(intent, strat, current_time=now)
    assert r2.passed is False
    assert strat.status == StrategyStatus.RUNNING

    # 5th order -> 3rd rate limit breach -> AUTO-HALT TRIGGERED!
    r3 = risk_engine.evaluate_intent(intent, strat, current_time=now)
    assert r3.passed is False
    assert strat.status == StrategyStatus.HALTED
    assert "Runaway loop detected" in r3.message


def test_tick_size_and_parameter_validations(risk_engine: RiskEngine):
    strat = TimeBasedStrategy(strategy_id="s_params", symbol="RELIANCE")
    strat.start()

    # 1. Zero quantity constructed defensively
    bad_qty = OrderIntent.model_construct(
        strategy_id="s_params", symbol="RELIANCE", side=Side.BUY, quantity=0, price_paise=0
    )
    assert risk_engine.evaluate_intent(bad_qty, strat).passed is False

    # 2. Exceeds max single order size
    risk_engine.set_strategy_config("s_params", RiskConfig(max_order_quantity=5))
    too_large = OrderIntent(strategy_id="s_params", symbol="RELIANCE", side=Side.BUY, quantity=6)
    r_large = risk_engine.evaluate_intent(too_large, strat)
    assert r_large.passed is False
    assert r_large.reason == RiskReason.MAX_POSITION_SIZE_EXCEEDED

    # 3. Invalid tick size (e.g. 1183.47 -> 118347 paise is not multiple of 5 paise)
    bad_tick = OrderIntent(strategy_id="s_params", symbol="RELIANCE", side=Side.BUY, quantity=1, price_paise=118347)
    r_tick = risk_engine.evaluate_intent(bad_tick, strat)
    assert r_tick.passed is False
    assert r_tick.reason == RiskReason.TICK_SIZE_INVALID


def test_risk_audit_and_metrics(risk_engine: RiskEngine):
    strat = TimeBasedStrategy(strategy_id="s_audit", symbol="RELIANCE")
    strat.start()

    # Send 1 good intent
    good_intent = OrderIntent(strategy_id="s_audit", symbol="RELIANCE", side=Side.BUY, quantity=1)
    risk_engine.evaluate_intent(good_intent, strat)

    # Send 1 bad intent (violates tick size)
    bad_intent = OrderIntent(strategy_id="s_audit", symbol="RELIANCE", side=Side.BUY, quantity=1, price_paise=118347)
    risk_engine.evaluate_intent(bad_intent, strat)

    metrics = risk_engine.get_risk_metrics()
    assert metrics["total_evaluated"] >= 2
    assert metrics["total_passed"] >= 1
    assert metrics["total_rejected"] >= 1

    logs = risk_engine.get_audit_log(limit=10, strategy_id="s_audit")
    assert len(logs) == 2
    assert logs[0]["passed"] is True
    assert logs[1]["passed"] is False


@pytest.mark.asyncio
async def test_single_strategy_square_off():
    broker = Mock021()
    broker.reset()
    risk_engine = RiskEngine()
    manager = StrategyManager()

    strat1 = TimeBasedStrategy(strategy_id="s_kill_one", symbol="RELIANCE")
    strat2 = TimeBasedStrategy(strategy_id="s_survivor", symbol="INFY")
    manager.register_strategy(strat1)
    manager.register_strategy(strat2)
    manager.start_all()

    # Simulate position on strat1
    strat1.on_fill(TradeFill(order_id="o1", client_order_id="c1", symbol="RELIANCE", exchange=Exchange.NSE, side=Side.BUY, quantity=5, price_paise=290000))
    assert strat1.get_position("RELIANCE") == 5

    kill_switch = KillSwitchService(risk_engine=risk_engine, strategy_manager=manager, broker=broker)

    report = await kill_switch.square_off_strategy("s_kill_one")
    assert report.result == KillSwitchResult.VERIFIED
    assert report.positions_closed_count == 1

    # strat1 is halted
    assert strat1.status == StrategyStatus.HALTED
    # strat2 is still running untouched!
    assert strat2.status == StrategyStatus.RUNNING
    # Platform kill switch is not engaged
    assert risk_engine.kill_switch_active is False
