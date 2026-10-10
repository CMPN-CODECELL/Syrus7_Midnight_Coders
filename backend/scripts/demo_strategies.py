import asyncio
from datetime import datetime, time, timezone
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.broker import Mock021, OrderPlacementRequest
from app.market_data.candle import Tick
from app.strategies import (
    BreakoutStrategy,
    MovingAverageCrossStrategy,
    StrategyManager,
    TimeBasedStrategy,
)


async def run_simulation():
    print("=" * 70)
    print(" TRADESHIELD STRATEGY SIMULATION DEMO (LEVELS 1 - 4)")
    print("=" * 70)

    # 1. Initialize broker & strategy manager
    broker = Mock021()
    manager = StrategyManager()

    # 2. Instantiate and register the 3 required strategies
    strat1 = TimeBasedStrategy(
        strategy_id="strat_time",
        name="TimeBased (09:15 Buy, 15:15 Exit)",
        symbol="RELIANCE",
        quantity=10,
        entry_time=time(9, 15),
        exit_time=time(15, 15),
    )
    strat2 = BreakoutStrategy(
        strategy_id="strat_breakout",
        name="1% Breakout (+5% Target / -5% SL)",
        symbol="INFY",
        quantity=5,
        open_price_paise=140000,  # Rs. 1400.00
    )
    strat3 = MovingAverageCrossStrategy(
        strategy_id="strat_ma",
        name="Dual MA Crossover (5-SMA & 20-SMA)",
        symbol="TCS",
        quantity=2,
        fast_period=3,
        slow_period=5,
    )

    manager.register_strategy(strat1)
    manager.register_strategy(strat2)
    manager.register_strategy(strat3)

    # Subscribe user to strategies (L1 requirement)
    user_id = "user_hackathon"
    manager.subscribe(user_id, strat1.strategy_id)
    manager.subscribe(user_id, strat2.strategy_id)
    manager.subscribe(user_id, strat3.strategy_id)
    print(f"[OK] User '{user_id}' subscribed to 3 strategies:")
    for s in manager.get_user_strategies(user_id):
        print(f"   * [{s.strategy_id}] {s.name} on {s.symbols[0]}")

    manager.start_all()
    print("\n[INFO] All strategies set to RUNNING.\n")

    tz = ZoneInfo("Asia/Kolkata")

    # Helper function to feed tick and process any emitted orders
    async def feed_tick(tick: Tick):
        intents = manager.route_tick(tick)
        for intent in intents:
            print(f"  [SIGNAL] [{intent.strategy_id}] Intent: {intent.side.value} {intent.quantity} {intent.symbol} (Tag: {intent.tag})")
            # Submit to broker
            req = OrderPlacementRequest(
                client_order_id=intent.intent_id,
                symbol=intent.symbol,
                exchange=intent.exchange,
                side=intent.side,
                quantity=intent.quantity,
                price_paise=intent.price_paise,
                product=intent.product,
                book=intent.book,
                validity=intent.validity,
            )
            res = await broker.place_order(req)
            print(f"     -> Broker Status: {res.broker_status.value} (Order ID: {res.order_id})")

            # Route fill back to strategy (L2, L4 isolated position tracking)
            order = await broker.get_order(res.order_id)
            if order and order.fills:
                for fill in order.fills:
                    manager.route_fill(intent.strategy_id, fill)
                    print(f"     -> Fill Executed: {fill.quantity} @ Rs. {fill.price_paise/100:.2f} | Brokerage: Rs. {fill.brokerage_paise/100:.2f}")

    # --- Scenario A: Strategy 1 Time-Based Entry at 09:15 IST ---
    print("\n--- [Scenario A] 09:15 AM IST Market Open ---")
    t_0915 = datetime(2026, 10, 9, 9, 15, 0, tzinfo=tz).astimezone(timezone.utc)
    await feed_tick(Tick(symbol="RELIANCE", ltp_paise=290000, timestamp=t_0915))

    # --- Scenario B: Strategy 2 Breakout at +1% ---
    print("\n--- [Scenario B] INFY reaches +1% breakout threshold (Rs. 1414.00) ---")
    t_breakout = datetime(2026, 10, 9, 10, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    await feed_tick(Tick(symbol="INFY", ltp_paise=141400, timestamp=t_breakout))

    # --- Scenario C: Strategy 2 Hits +5% Target ---
    print("\n--- [Scenario C] INFY surges to +5% target (Rs. 1484.70) ---")
    t_target = datetime(2026, 10, 9, 11, 30, 0, tzinfo=tz).astimezone(timezone.utc)
    await feed_tick(Tick(symbol="INFY", ltp_paise=148470, timestamp=t_target))

    # --- Scenario D: Strategy 1 Market Square-off at 15:15 IST ---
    print("\n--- [Scenario D] 03:15 PM IST (15:15) Intraday Auto-Squareoff ---")
    t_1515 = datetime(2026, 10, 9, 15, 15, 0, tzinfo=tz).astimezone(timezone.utc)
    await feed_tick(Tick(symbol="RELIANCE", ltp_paise=294000, timestamp=t_1515))

    # Print Live Dashboard / Performance Summary
    print("\n" + "=" * 70)
    print(" LIVE STRATEGY PERFORMANCE & POSITION DASHBOARD (L4)")
    print("=" * 70)
    for perf in manager.get_strategy_performance():
        print(f"Strategy: {perf['name']}")
        print(f"  * Status         : {perf['status']}")
        print(f"  * Open Positions : {perf['positions'] if perf['positions'] else 'FLAT (0)'}")
        print(f"  * Realized P&L   : Rs. {perf['realized_pnl_paise']/100:.2f}")
        print(f"  * Total Charges  : Rs. {perf['total_charges_paise']/100:.2f}")
        print(f"  * Net P&L        : Rs. {perf['net_pnl_paise']/100:.2f}")
        print(f"  * Total Fills    : {perf['total_fills']}")
        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(run_simulation())
