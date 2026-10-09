import asyncio
from datetime import datetime, timedelta, timezone
import random
import sys
from pathlib import Path

# Add backend dir to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import delete
from app.core.security import hash_password
from app.database.models import (
    OrderRecord,
    RiskEventRecord,
    StrategyRecord,
    Subscription,
    TradeFillRecord,
    User,
)
from app.database.session import AsyncSessionLocal, init_db


async def seed_database():
    print("Initializing Database tables...")
    await init_db()

    async with AsyncSessionLocal() as session:
        print("Clearing existing data for a fresh, clean seed...")
        await session.execute(delete(TradeFillRecord))
        await session.execute(delete(OrderRecord))
        await session.execute(delete(RiskEventRecord))
        await session.execute(delete(Subscription))
        await session.execute(delete(StrategyRecord))
        await session.execute(delete(User))
        await session.commit()

        print("Seeding Users...")
        pwd_hash = hash_password("demo1234")
        admin_pwd_hash = hash_password("admin1234")

        user_demo = User(
            id="u_demo_01",
            name="Demo Trader",
            email="demo@trademint.in",
            password_hash=pwd_hash,
            role="trader",
            is_active=True,
            api_ucc="HACK342",
            notifications_enabled=True,
            theme="dark",
        )
        user_admin = User(
            id="u_admin_01",
            name="Risk Manager Admin",
            email="admin@trademint.in",
            password_hash=admin_pwd_hash,
            role="admin",
            is_active=True,
            api_ucc="HACK342",
            notifications_enabled=True,
            theme="dark",
        )
        user_rahul = User(
            id="u_rahul_02",
            name="Rahul Sharma",
            email="rahul.sharma@trademint.in",
            password_hash=pwd_hash,
            role="trader",
            is_active=True,
            api_ucc="HACK889",
            notifications_enabled=True,
            theme="light",
        )
        user_priya = User(
            id="u_priya_03",
            name="Priya Verma",
            email="priya.verma@trademint.in",
            password_hash=pwd_hash,
            role="trader",
            is_active=True,
            api_ucc="HACK912",
            notifications_enabled=True,
            theme="dark",
        )

        session.add_all([user_demo, user_admin, user_rahul, user_priya])
        await session.flush()

        print("Seeding Strategies...")
        strategies_data = [
            {
                "id": "strat_time",
                "name": "Strategy 1: TimeBased (09:15 Entry, 15:15 Exit)",
                "description": "Automated intraday time-bound entry & exit execution on bluechip equities",
                "symbol": "RELIANCE",
                "timeframe": "1m",
                "status": "RUNNING",
                "max_daily_loss_paise": 500000,
                "max_position_size": 25,
                "max_orders_per_minute": 5,
            },
            {
                "id": "strat_breakout",
                "name": "Strategy 2: 1% Day Open Breakout (+5% Target / -5% SL)",
                "description": "Volatility breakout engine targeting 1.0% impulse moves above session open",
                "symbol": "INFY",
                "timeframe": "1m",
                "status": "RUNNING",
                "max_daily_loss_paise": 350000,
                "max_position_size": 20,
                "max_orders_per_minute": 5,
            },
            {
                "id": "strat_ma",
                "name": "Strategy 3: MA Crossover on 1m Candles (Fast 5 / Slow 20)",
                "description": "Dual moving average golden/death cross scalper with trailing stop-loss protection",
                "symbol": "TCS",
                "timeframe": "1m",
                "status": "RUNNING",
                "max_daily_loss_paise": 400000,
                "max_position_size": 15,
                "max_orders_per_minute": 10,
            },
            {
                "id": "strat_momentum",
                "name": "Strategy 4: Alpha Momentum Scalper",
                "description": "High-frequency volume spike momentum strategy tracking banking sector leaders",
                "symbol": "HDFCBANK",
                "timeframe": "5m",
                "status": "RUNNING",
                "max_daily_loss_paise": 600000,
                "max_position_size": 30,
                "max_orders_per_minute": 8,
            },
            {
                "id": "strat_mean_reversion",
                "name": "Strategy 5: Intraday VWAP Mean Reversion",
                "description": "Mean reversion algorithm executing counter-trend trades on 2-sigma VWAP stretch",
                "symbol": "TATAMOTORS",
                "timeframe": "5m",
                "status": "RUNNING",
                "max_daily_loss_paise": 250000,
                "max_position_size": 50,
                "max_orders_per_minute": 5,
            },
            {
                "id": "strat_pairs",
                "name": "Strategy 6: Statistical Arbitrage Pairs",
                "description": "Co-integrated pairs arbitrage trading spread divergence across benchmark indices",
                "symbol": "NIFTY50",
                "timeframe": "1m",
                "status": "PAUSED",
                "max_daily_loss_paise": 500000,
                "max_position_size": 10,
                "max_orders_per_minute": 5,
            },
        ]

        strat_objs = []
        for s in strategies_data:
            obj = StrategyRecord(**s)
            session.add(obj)
            strat_objs.append(obj)
        await session.flush()

        print("Seeding Subscriptions...")
        subscriptions = []
        for u in [user_demo, user_admin, user_rahul, user_priya]:
            for st in strat_objs:
                subscriptions.append(
                    Subscription(user_id=u.id, strategy_id=st.id, is_active=True)
                )
        session.add_all(subscriptions)
        await session.flush()

        print("Seeding Orders, Fills, & Risk Events...")
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=6)

        order_templates = [
            # RELIANCE Trades
            ("strat_time", "RELIANCE", "NSE", "BUY", 10, 284500, "EXECUTED", None),
            ("strat_time", "RELIANCE", "NSE", "SELL", 5, 286200, "EXECUTED", None),
            ("strat_time", "RELIANCE", "NSE", "BUY", 8, 285000, "EXECUTED", None),
            ("strat_time", "RELIANCE", "NSE", "BUY", 20, 285500, "REJECTED", "MAX_POSITION_SIZE_EXCEEDED (Platform Limit: 15 units)"),
            
            # INFY Trades
            ("strat_breakout", "INFY", "NSE", "BUY", 15, 142800, "EXECUTED", None),
            ("strat_breakout", "INFY", "NSE", "SELL", 15, 149950, "EXECUTED", None),
            ("strat_breakout", "INFY", "NSE", "BUY", 12, 145000, "PARTIALLY_FILLED", None),
            ("strat_breakout", "INFY", "NSE", "BUY", 25, 145200, "REJECTED", "RATE_LIMIT_EXCEEDED (Max 5 orders/min breached)"),
            
            # TCS Trades
            ("strat_ma", "TCS", "NSE", "BUY", 5, 352000, "EXECUTED", None),
            ("strat_ma", "TCS", "NSE", "SELL", 5, 355500, "EXECUTED", None),
            ("strat_ma", "TCS", "NSE", "BUY", 8, 353000, "EXECUTED", None),
            ("strat_ma", "TCS", "NSE", "SELL", 4, 354200, "EXECUTED", None),

            # HDFCBANK Trades
            ("strat_momentum", "HDFCBANK", "NSE", "BUY", 20, 164500, "EXECUTED", None),
            ("strat_momentum", "HDFCBANK", "NSE", "SELL", 10, 166800, "EXECUTED", None),
            ("strat_momentum", "HDFCBANK", "NSE", "BUY", 15, 165200, "PLACED", None),
            ("strat_momentum", "HDFCBANK", "NSE", "BUY", 50, 165000, "REJECTED", "MAX_DAILY_LOSS_LIMIT (Risk Gate protection active)"),

            # TATAMOTORS Trades
            ("strat_mean_reversion", "TATAMOTORS", "NSE", "BUY", 30, 98000, "EXECUTED", None),
            ("strat_mean_reversion", "TATAMOTORS", "NSE", "SELL", 30, 99400, "EXECUTED", None),
            ("strat_mean_reversion", "TATAMOTORS", "NSE", "BUY", 25, 98200, "EXECUTED", None),
            ("strat_mean_reversion", "TATAMOTORS", "NSE", "SELL", 25, 97800, "CANCELLED", "Soft Halt Cancelled Pending Order"),

            # NIFTY50 Trades
            ("strat_pairs", "NIFTY50", "NSE", "BUY", 5, 2245000, "EXECUTED", None),
            ("strat_pairs", "NIFTY50", "NSE", "SELL", 5, 2258000, "EXECUTED", None),
        ]

        order_count = 100
        for i, (s_id, sym, ex, side, qty, price_p, stat, rej) in enumerate(order_templates):
            ord_id = f"ORD-{order_count + i}"
            c_ord_id = f"cid_{s_id}_{i+1}"
            t_offset = timedelta(minutes=i * 12 + random.randint(1, 5))
            created_dt = start_time + t_offset

            filled_q = qty if stat == "EXECUTED" else (qty // 2 if stat == "PARTIALLY_FILLED" else 0)

            ord_rec = OrderRecord(
                id=ord_id,
                client_order_id=c_ord_id,
                strategy_id=s_id,
                symbol=sym,
                exchange=ex,
                side=side,
                quantity=qty,
                filled_quantity=filled_q,
                price_paise=price_p,
                product="INTRADAY",
                status=stat,
                rejection_reason=rej,
                created_at=created_dt,
            )
            session.add(ord_rec)

            # Create Fills for executed/partially filled orders
            if filled_q > 0:
                turnover = filled_q * price_p
                brokerage = 2000  # ₹20.00
                stt = int(turnover * 0.00025) if side == "SELL" else 0
                exchange_fee = max(1, int(turnover * 0.0000297))
                sebi_fee = max(1, int(turnover * 0.000001))
                stamp_duty = int(turnover * 0.00015) if side == "BUY" else 0
                total_fee = brokerage + stt + exchange_fee + sebi_fee + stamp_duty

                fill = TradeFillRecord(
                    order_id=ord_id,
                    strategy_id=s_id,
                    symbol=sym,
                    side=side,
                    quantity=filled_q,
                    price_paise=price_p,
                    brokerage_paise=brokerage,
                    fee_paise=total_fee,
                    timestamp=created_dt + timedelta(seconds=1),
                )
                session.add(fill)

            # Create realistic Risk Event Records
            if stat == "REJECTED":
                risk_event = RiskEventRecord(
                    strategy_id=s_id,
                    symbol=sym,
                    side=side,
                    quantity=qty,
                    price_paise=price_p,
                    passed=False,
                    reason="RISK_GATE_BLOCK",
                    message=rej or "Risk gate policy violation",
                    severity="CRITICAL",
                    timestamp=created_dt,
                )
            else:
                risk_event = RiskEventRecord(
                    strategy_id=s_id,
                    symbol=sym,
                    side=side,
                    quantity=qty,
                    price_paise=price_p,
                    passed=True,
                    reason="CHECKS_PASSED",
                    message=f"Order approved: {side} {qty} {sym} @ ₹{price_p/100:.2f}",
                    severity="INFO",
                    timestamp=created_dt,
                )
            session.add(risk_event)

        # Add additional standalone risk events for rich audit history
        extra_risk_events = [
            ("strat_time", "RELIANCE", "BUY", 10, 284500, True, "SAFE", "Max Daily Loss Check Passed (Loss: ₹0.00 / Limit: ₹5,000.00)", "INFO"),
            ("strat_breakout", "INFY", "BUY", 15, 142800, True, "SAFE", "Rolling Rate Limiter Passed (2/5 orders in window)", "INFO"),
            ("strat_ma", "TCS", "SELL", 5, 355500, True, "SAFE", "Position Limit Check Passed (Net: 4 / Limit: 15)", "INFO"),
            ("strat_breakout", "INFY", "BUY", 30, 145000, False, "MAX_QTY_EXCEEDED", "Order quantity 30 exceeds strategy max limit 20", "WARNING"),
            ("strat_momentum", "HDFCBANK", "BUY", 25, 165000, False, "RATE_LIMITER", "Throttled: 6th order submitted within 60-second rolling window", "CRITICAL"),
            ("strat_time", "RELIANCE", "SELL", 10, 286000, True, "PROFIT_TAKEN", "Take Profit Signal Triggered (+0.52% gain)", "INFO"),
        ]

        for s_id, sym, side, qty, p_p, passed, reas, msg, sev in extra_risk_events:
            session.add(
                RiskEventRecord(
                    strategy_id=s_id,
                    symbol=sym,
                    side=side,
                    quantity=qty,
                    price_paise=p_p,
                    passed=passed,
                    reason=reas,
                    message=msg,
                    severity=sev,
                    timestamp=now - timedelta(minutes=random.randint(10, 180)),
                )
            )

        await session.commit()
        print("Database successfully seeded with comprehensive demo data!")


if __name__ == "__main__":
    asyncio.run(seed_database())
