from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
import pytest

from app.broker.models import TradeFill
from app.core.enums import Side, StrategyStatus, Timeframe
from app.market_data.candle import Candle, CandleAggregator, Tick
from app.strategies import (
    BreakoutStrategy,
    MovingAverageCrossStrategy,
    StrategyManager,
    TimeBasedStrategy,
)


def make_ist_time(hour: int, minute: int) -> datetime:
    tz = ZoneInfo("Asia/Kolkata")
    return datetime(2026, 10, 9, hour, minute, 0, tzinfo=tz).astimezone(timezone.utc)


def test_candle_aggregator_1m():
    agg = CandleAggregator(Timeframe.M1)

    t0 = datetime(2026, 10, 9, 9, 15, 10, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 9, 9, 15, 30, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 9, 9, 16, 5, tzinfo=timezone.utc)  # Crosses 1m boundary

    agg.process_tick(Tick(symbol="RELIANCE", ltp_paise=290000, volume=10, timestamp=t0))
    agg.process_tick(Tick(symbol="RELIANCE", ltp_paise=291000, volume=5, timestamp=t1))
    closed = agg.process_tick(Tick(symbol="RELIANCE", ltp_paise=289500, volume=20, timestamp=t2))

    assert closed is not None
    assert closed.symbol == "RELIANCE"
    assert closed.open_paise == 290000
    assert closed.high_paise == 291000
    assert closed.low_paise == 290000
    assert closed.close_paise == 291000
    assert closed.volume == 15
    assert closed.is_closed is True


def test_time_based_strategy_lifecycle():
    strat = TimeBasedStrategy(
        symbol="RELIANCE",
        quantity=10,
        entry_time=time(9, 15),
        exit_time=time(15, 15),
    )
    strat.start()

    # Tick before 9:15 AM IST (e.g. 9:10 AM)
    tick_pre = Tick(
        symbol="RELIANCE",
        ltp_paise=290000,
        timestamp=make_ist_time(9, 10),
    )
    assert len(strat.on_tick(tick_pre)) == 0

    # Tick at 9:15 AM IST -> Entry signal
    tick_entry = Tick(
        symbol="RELIANCE",
        ltp_paise=290000,
        timestamp=make_ist_time(9, 15),
    )
    intents = strat.on_tick(tick_entry)
    assert len(intents) == 1
    assert intents[0].side == Side.BUY
    assert intents[0].quantity == 10

    # Simulate entry fill
    fill = TradeFill(
        order_id="ord_1",
        client_order_id=intents[0].intent_id,
        symbol="RELIANCE",
        exchange=intents[0].exchange,
        side=Side.BUY,
        quantity=10,
        price_paise=290000,
    )
    strat.on_fill(fill)
    assert strat.get_position("RELIANCE") == 10

    # Tick at 3:15 PM IST (15:15) -> Exit squareoff signal
    tick_exit = Tick(
        symbol="RELIANCE",
        ltp_paise=295000,
        timestamp=make_ist_time(15, 15),
    )
    exit_intents = strat.on_tick(tick_exit)
    assert len(exit_intents) == 1
    assert exit_intents[0].side == Side.SELL
    assert exit_intents[0].quantity == 10


def test_breakout_strategy_target_and_stoploss():
    # Test Target Hit: Open = 1400.00 (140000 paise). +1% is 141400 paise.
    strat = BreakoutStrategy(
        symbol="INFY",
        quantity=1,
        open_price_paise=140000,
        tick_size_paise=5,
    )
    strat.start()

    # 1. Price below breakout threshold (140500 < 141400)
    tick_idle = Tick(symbol="INFY", ltp_paise=140500, timestamp=datetime.now(timezone.utc))
    assert len(strat.on_tick(tick_idle)) == 0

    # 2. Breakout triggered at +1% (141400 paise)
    tick_breakout = Tick(symbol="INFY", ltp_paise=141400, timestamp=datetime.now(timezone.utc))
    intents = strat.on_tick(tick_breakout)
    assert len(intents) == 1
    assert intents[0].side == Side.BUY
    assert intents[0].price_paise == 141400

    # 3. Fill arrives at 141400 paise
    # Target = 141400 * 1.05 = 148470. Stop-loss = 141400 * 0.95 = 134330
    fill = TradeFill(
        order_id="ord_bo_1",
        client_order_id=intents[0].intent_id,
        symbol="INFY",
        exchange=intents[0].exchange,
        side=Side.BUY,
        quantity=1,
        price_paise=141400,
    )
    strat.on_fill(fill)
    assert strat.target_price_paise == 148470
    assert strat.stop_loss_price_paise == 134330

    # 4. LTP hits Target (148470)
    tick_target = Tick(symbol="INFY", ltp_paise=148470, timestamp=datetime.now(timezone.utc))
    exit_intents = strat.on_tick(tick_target)
    assert len(exit_intents) == 1
    assert exit_intents[0].side == Side.SELL
    assert "target_hit" in exit_intents[0].tag


def test_moving_average_crossover_strategy():
    strat = MovingAverageCrossStrategy(
        symbol="TCS",
        quantity=5,
        timeframe=Timeframe.M1,
        fast_period=3,
        slow_period=5,
    )
    strat.start()

    base_time = datetime(2026, 10, 9, 9, 15, 0, tzinfo=timezone.utc)

    # Feed initial declining candles: Slow SMA will be higher than Fast SMA
    prices = [100000, 99000, 98000, 97000, 96000]
    for p in prices:
        c = Candle(
            symbol="TCS",
            timeframe=Timeframe.M1,
            open_paise=p,
            high_paise=p,
            low_paise=p,
            close_paise=p,
            start_time=base_time,
            is_closed=True,
        )
        assert len(strat.on_candle(c)) == 0

    # Now sharp upward spike -> Golden cross: Fast SMA crosses above Slow SMA
    spike_candle = Candle(
        symbol="TCS",
        timeframe=Timeframe.M1,
        open_paise=105000,
        high_paise=105000,
        low_paise=105000,
        close_paise=105000,
        start_time=base_time,
        is_closed=True,
    )
    intents = strat.on_candle(spike_candle)
    assert len(intents) == 1
    assert intents[0].side == Side.BUY
    assert intents[0].quantity == 5
    assert intents[0].tag == "ma_golden_cross_buy"


def test_strategy_manager_multi_strategy_isolation_l4():
    """Verify Level 4: Several strategies on one account each keeping isolated positions and P&L."""
    manager = StrategyManager()

    # User subscriptions (L1)
    strat1 = TimeBasedStrategy(strategy_id="strat_time", symbol="RELIANCE", quantity=10)
    strat2 = BreakoutStrategy(strategy_id="strat_breakout", symbol="RELIANCE", quantity=5, open_price_paise=290000)
    strat3 = MovingAverageCrossStrategy(strategy_id="strat_ma", symbol="TCS", quantity=2)

    manager.register_strategy(strat1)
    manager.register_strategy(strat2)
    manager.register_strategy(strat3)

    assert manager.subscribe(user_id="user_123", strategy_id="strat_time") is True
    assert manager.subscribe(user_id="user_123", strategy_id="strat_breakout") is True
    user_strats = manager.get_user_strategies("user_123")
    assert len(user_strats) == 2

    manager.start_all()

    # Simulate Strategy 1 going LONG 10 RELIANCE @ 290000
    fill_s1 = TradeFill(
        order_id="f1",
        client_order_id="c1",
        symbol="RELIANCE",
        exchange=strat1.exchange,
        side=Side.BUY,
        quantity=10,
        price_paise=290000,
        brokerage_paise=2000,
        fee_paise=870,
    )
    manager.route_fill("strat_time", fill_s1)

    # Simulate Strategy 2 going SHORT 5 RELIANCE @ 295000 on the same account
    fill_s2 = TradeFill(
        order_id="f2",
        client_order_id="c2",
        symbol="RELIANCE",
        exchange=strat2.exchange,
        side=Side.SELL,
        quantity=5,
        price_paise=295000,
        brokerage_paise=2000,
        fee_paise=442,
    )
    manager.route_fill("strat_breakout", fill_s2)

    # Check isolation: Strat 1 has net +10, Strat 2 has net -5
    assert strat1.get_position("RELIANCE") == 10
    assert strat2.get_position("RELIANCE") == -5

    # Check summary report
    summary = manager.get_strategy_performance()
    s1_perf = next(s for s in summary if s["strategy_id"] == "strat_time")
    s2_perf = next(s for s in summary if s["strategy_id"] == "strat_breakout")

    assert s1_perf["positions"]["RELIANCE"] == 10
    assert s2_perf["positions"]["RELIANCE"] == -5
