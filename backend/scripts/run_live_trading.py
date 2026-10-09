import argparse
import asyncio
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
import sys
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.broker import Broker021, OrderPlacementRequest
from app.core.enums import Book, Exchange, Product, Side, Validity
from app.execution import ExecutionEngine
from app.killswitch import KillSwitchService
from app.market_data import MarketFeed021, Tick
from app.risk import RiskConfig, RiskEngine
from app.strategies import (
    BreakoutStrategy,
    MovingAverageCrossStrategy,
    StrategyManager,
    TimeBasedStrategy,
)
from app.strategies.intents import OrderIntent


async def main():
    parser = argparse.ArgumentParser(description="021 Live Algo Trading Platform with Level 3 Risk Controls")
    parser.add_argument(
        "--test-order",
        action="store_true",
        help="Place an immediate 1-share test order on 021 to verify live execution",
    )
    args = parser.parse_args()

    print("=" * 70)
    print(" 021 LIVE ALGO TRADING PLATFORM (LEVELS 1 - 4 WITH RISK CONTROLS)")
    print("=" * 70)

    # 1. Initialize real broker adapter and authenticate
    broker = Broker021()
    token = await broker.get_valid_token()
    print(f"[AUTH OK] Authenticated with 021 API as UCC: '{broker.settings.api_ucc}'")

    # 2. Initialize Risk Engine (L3)
    risk_engine = RiskEngine()
    # Configure per-strategy risk limits (e.g. max loss ₹500, max pos 10, max 5 orders/min)
    default_risk = RiskConfig(
        max_daily_loss_paise=50000,   # ₹500.00
        max_position_size=10,         # 10 units
        max_orders_per_minute=5,      # 5 orders per 60s
    )
    print(f"[RISK ENGINE] Platform Risk Controls Active:")
    print(f"   * Max Daily Loss Limit  : Rs. {default_risk.max_daily_loss_paise/100:.2f}")
    print(f"   * Max Position Size     : {default_risk.max_position_size} units")
    print(f"   * Rate Limit            : {default_risk.max_orders_per_minute} orders/min")
    print(f"   * Pre-Trade Sanity Checks: Tick sizes, lot sizes, circuit limits")

    # Fetch initial account state
    init_orders = await broker.get_orders()
    init_positions = await broker.get_positions()
    print(f"[ACCOUNT] Current Sandbox Orders: {len(init_orders)} | Open Positions: {len(init_positions)}")

    manager = StrategyManager()

    # 3. Register all 3 strategies (021-03 Problem Statement & README)
    strat1 = TimeBasedStrategy(
        strategy_id="strat_time",
        name="Strategy 1: TimeBased (09:15 Entry, 15:15 Exit)",
        symbol="RELIANCE",
        quantity=1,
        entry_time=time(9, 15),
        exit_time=time(15, 15),
    )
    strat2 = BreakoutStrategy(
        strategy_id="strat_breakout",
        name="Strategy 2: 1% Breakout (+5% Target / -5% SL)",
        symbol="INFY",
        quantity=1,
    )
    strat3 = MovingAverageCrossStrategy(
        strategy_id="strat_ma",
        name="Strategy 3: MA Crossover on 1m Candles",
        symbol="TCS",
        quantity=1,
        fast_period=5,
        slow_period=20,
    )

    manager.register_strategy(strat1)
    manager.register_strategy(strat2)
    manager.register_strategy(strat3)

    user_id = broker.settings.api_ucc
    manager.subscribe(user_id, strat1.strategy_id)
    manager.subscribe(user_id, strat2.strategy_id)
    manager.subscribe(user_id, strat3.strategy_id)

    # 4. Initialize Execution Engine and Kill Switch Service (L2, L3)
    exec_engine = ExecutionEngine(
        strategy_manager=manager,
        risk_engine=risk_engine,
        broker=broker,
    )

    kill_switch = KillSwitchService(
        risk_engine=risk_engine,
        strategy_manager=manager,
        broker=broker,
    )

    manager.start_all()
    print(f"\n[STRATEGIES] Running 3 concurrent strategies on account {user_id}:")
    for s in manager.list_strategies():
        print(f"   * [{s.strategy_id}] {s.name} on {s.symbols[0]}")

    # Test order placement if requested
    if args.test_order:
        print("\n[TEST ORDER] Evaluating 1-share INTRADAY BUY test order for RELIANCE through Risk Engine...")
        test_intent = OrderIntent(
            strategy_id="strat_time",
            symbol="RELIANCE",
            exchange=Exchange.NSE,
            side=Side.BUY,
            quantity=1,
            price_paise=0,  # Market order
            product=Product.INTRADAY,
            book=Book.RL,
            validity=Validity.DAY,
            tag="validation_test_order",
        )
        try:
            risk_res, order_res = await exec_engine.execute_intent(test_intent)
            if risk_res.passed and order_res:
                print(f"[TEST ORDER SUCCESS] Order ID: {order_res.order_id} ({order_res.broker_status.value}) - {order_res.message}")
                print(">> Check this order live on https://devcarbon.021.trade in your Orders tab!\n")
            else:
                print(f"[TEST ORDER BLOCKED BY RISK] {risk_res.reason.value}: {risk_res.message}\n")
        except Exception as e:
            print(f"[TEST ORDER ERROR] {e}\n")

    # 5. Connect live market feed with real-time visual logger
    tick_count = 0
    tz = ZoneInfo("Asia/Kolkata")

    async def handle_tick(tick: Tick):
        nonlocal tick_count
        tick_count += 1

        local_time_str = tick.timestamp.astimezone(tz).strftime("%H:%M:%S")
        exch_time_str = (
            tick.exchange_time.astimezone(tz).strftime("%H:%M:%S")
            if tick.exchange_time
            else local_time_str
        )

        # Visual indicator for live feed
        time_tag = f"{local_time_str} [Exch: {exch_time_str}]"
        if tick.open_paise > 0:
            diff_pct = ((tick.ltp_paise - tick.open_paise) / tick.open_paise) * 100.0
            print(
                f"[TICK #{tick_count:04d}] {time_tag} | {tick.symbol:<8} "
                f"LTP: Rs. {tick.ltp_paise/100:>8.2f} | Open: Rs. {tick.open_paise/100:>8.2f} "
                f"({diff_pct:+.2f}%)"
            )
        else:
            print(
                f"[TICK #{tick_count:04d}] {time_tag} | {tick.symbol:<8} "
                f"LTP: Rs. {tick.ltp_paise/100:>8.2f}"
            )

        # Route tick to strategy manager
        intents = manager.route_tick(tick)
        for intent in intents:
            print(f"\n{'*'*65}")
            print(f" [INTENT EMITTED] Strategy: [{intent.strategy_id}]")
            print(f" Action: {intent.side.value} {intent.quantity} {intent.symbol} (Tag: {intent.tag})")

            # Route through ExecutionEngine (Risk Engine check -> In-flight tracking -> Broker)
            try:
                risk_res, order_resp = await exec_engine.execute_intent(intent)
                if not risk_res.passed:
                    print(f" [RISK REJECTED] {risk_res.reason.value}: {risk_res.message}")
                elif order_resp:
                    print(f" [021 ORDER PLACED] Order ID: {order_resp.order_id} ({order_resp.broker_status.value})")
                    print(f" Response: {order_resp.message}")
            except Exception as e:
                print(f" [EXECUTION EXCEPTION] {e}")
            print(f"{'*'*65}\n")

    orig_candle_cb = manager._on_candle_closed
    def log_candle_closed(c):
        print(f"\n{'='*65}\n [CANDLE {c.timeframe.value.upper()} CLOSED] {c.symbol:<8} O:{c.open:.2f} H:{c.high:.2f} L:{c.low:.2f} C:{c.close:.2f} Vol:{c.volume}\n{'='*65}")
        orig_candle_cb(c)

    manager.aggregator_1m.on_candle_closed = log_candle_closed
    manager.aggregator_5m.on_candle_closed = log_candle_closed

    feed = MarketFeed021(broker=broker, on_tick=handle_tick, mode="full")
    feed.subscribe_symbols(["RELIANCE", "INFY", "TCS"])
    await feed.start()
    print("\n[FEED] Connected to 021 binary WebSocket stream (Full Mode with TC 3 & Candle Aggregation).")
    print("[FEED] Streaming live ticks for RELIANCE, INFY, TCS... (Press Ctrl+C to trigger Kill Switch)\n")

    try:
        while True:
            await asyncio.sleep(15)
            summary = manager.get_strategy_performance()
            metrics = risk_engine.get_risk_metrics()
            print("\n" + "-" * 70)
            print(
                f" [LIVE DASHBOARD] Ticks: {tick_count} | KillSwitch: {risk_engine.kill_switch_active} | "
                f"Risk: (Pass: {metrics['total_passed']}, Blocked: {metrics['total_rejected']}, Working: {metrics['active_inflight_orders_count']})"
            )
            for item in summary:
                print(
                    f" [{item['strategy_id']}] {item['name']}: "
                    f"Pos={item['positions'] if item['positions'] else 'FLAT'} | "
                    f"Net P&L=Rs. {item['net_pnl_paise']/100:.2f} | "
                    f"Fills={item['total_fills']}"
                )
            print("-" * 70 + "\n")
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n\n" + "!" * 65)
        print(" [EMERGENCY TRIGGER] Activating Level 3 Kill Switch...")
        print("!" * 65)
        report = await kill_switch.activate()
        print(f"\n[KILL SWITCH RESULT] Status: {report.result.value}")
        print(f"   * Elapsed Time     : {report.elapsed_seconds:.2f}s (SLA: 10s)")
        print(f"   * Orders Cancelled : {report.orders_cancelled_count}")
        print(f"   * Positions Closed : {report.positions_closed_count}")
        print(f"   * Within 10s SLA   : {report.completed_within_sla}")
        print(f"   * Summary          : {report.message}\n")
    finally:
        await feed.stop()
        await broker.close()
        print("Clean shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
