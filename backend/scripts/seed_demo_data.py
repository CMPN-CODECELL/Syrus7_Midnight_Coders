import asyncio
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

# Add backend root to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.core.security import hash_password
from app.database import AsyncSessionLocal, init_db
from app.database.models import (
    OrderRecord,
    RiskEventRecord,
    StrategyRecord,
    Subscription,
    TradeFillRecord,
    User,
)
from app.database.repositories import (
    OrderRepository,
    PaymentRepository,
    StrategyRepository,
    SubscriptionRepository,
    UserRepository,
)


async def seed_demo_data():
    print("=" * 60)
    print(" SEEDING DEMO & JUDGE EVALUATION DATA FOR TRADESHIELD")
    print("=" * 60)

    # Initialize DB (PostgreSQL or SQLite fallback)
    await init_db()

    async with AsyncSessionLocal() as session:
        # 0. Seed Default Subscription Plans
        plans = await SubscriptionRepository.seed_plans(session)
        print(f"[PLANS] Seeded {len(plans)} subscription tier catalog options.")

        # 1. Seed Demo Users
        users_data = [
            {
                "id": "u_1",
                "name": "Sahil Mehta (Lead Trader)",
                "email": "demo@trademint.in",
                "password": "demo1234",
                "role": "admin",
                "ucc": "HACK342",
                "tier": "ENTERPRISE",
                "balance": 25000000,  # ₹250,000.00
            },
            {
                "id": "u_judge",
                "name": "Hackathon Judge Evaluator",
                "email": "judge@trademint.in",
                "password": "judge1234",
                "role": "admin",
                "ucc": "HACK342",
                "tier": "PRO",
                "balance": 50000000,  # ₹500,000.00
            },
            {
                "id": "u_priya",
                "name": "Priya Sharma (Quant Analyst)",
                "email": "priya.sharma@trademint.in",
                "password": "priya1234",
                "role": "user",
                "ucc": "HACK342",
                "tier": "PRO",
                "balance": 10000000,  # ₹100,000.00
            },
            {
                "id": "u_arjun",
                "name": "Arjun Verma (Risk Manager)",
                "email": "arjun.verma@trademint.in",
                "password": "arjun1234",
                "role": "user",
                "ucc": "HACK342",
                "tier": "FREE",
                "balance": 5000000,  # ₹50,000.00
            },
            {
                "id": "u_karthik",
                "name": "Karthik R (HFT Algo Trader)",
                "email": "karthik@trademint.in",
                "password": "karthik1234",
                "role": "user",
                "ucc": "HACK342",
                "tier": "PRO",
                "balance": 15000000,  # ₹150,000.00
            },
        ]

        created_users = []
        for u_info in users_data:
            res = await session.execute(
                select(User).where((User.id == u_info["id"]) | (User.email == u_info["email"]))
            )
            user = res.scalar_one_or_none()
            if not user:
                user = User(
                    id=u_info["id"],
                    name=u_info["name"],
                    email=u_info["email"],
                    password_hash=hash_password(u_info["password"]),
                    role=u_info["role"],
                    is_active=True,
                    api_ucc=u_info["ucc"],
                    subscription_tier=u_info["tier"],
                    account_balance_paise=u_info["balance"],
                    notifications_enabled=True,
                    theme="light",
                )
                session.add(user)
            else:
                user.name = u_info["name"]
                user.email = u_info["email"]
                user.password_hash = hash_password(u_info["password"])
                user.is_active = True
                user.subscription_tier = u_info["tier"]
                user.account_balance_paise = u_info["balance"]
            created_users.append(user.id if user else u_info["id"])

        await session.commit()

        print(f"[USERS] Seeded {len(users_data)} judge-ready user accounts.")

        # 2. Seed Strategies
        strats_data = [
            {
                "id": "strat_time",
                "name": "Strategy 1: TimeBased (09:15 Entry, 15:15 Exit)",
                "description": "Enters a 1-share long position at 09:15 AM market open and automatically squares off at 15:15 PM.",
                "symbol": "RELIANCE",
                "timeframe": "1m",
                "status": "RUNNING",
                "type": "TimeBased",
                "price": 0,
            },
            {
                "id": "strat_breakout",
                "name": "Strategy 2: 1% Breakout (+5% Target / -5% SL)",
                "description": "Enters long if price rises 1% above day's open. Sets a profit target at +5% and a stop-loss at -5%.",
                "symbol": "INFY",
                "timeframe": "1m",
                "status": "RUNNING",
                "type": "Breakout",
                "price": 49900,  # ₹499/mo premium
            },
            {
                "id": "strat_ma",
                "name": "Strategy 3: MA Crossover on 1m Candles",
                "description": "Computes 5-SMA and 20-SMA on 1-minute aggregated candles. Buys on golden cross, sells on death cross.",
                "symbol": "TCS",
                "timeframe": "1m",
                "status": "RUNNING",
                "type": "MovingAverageCross",
                "price": 99900,  # ₹999/mo premium
            },
            {
                "id": "strat_vwap",
                "name": "Strategy 4: VWAP Mean Reversion",
                "description": "Monitors volume-weighted average price. Buys on 1.5 standard deviation dip, exits at mean.",
                "symbol": "HDFCBANK",
                "timeframe": "5m",
                "status": "RUNNING",
                "type": "TimeBased",
                "price": 0,
            },
            {
                "id": "strat_rsi",
                "name": "Strategy 5: RSI Momentum Breakout",
                "description": "Triggers long entries when 14-period RSI crosses above 60 with rising volume confirmation.",
                "symbol": "RELIANCE",
                "timeframe": "5m",
                "status": "RUNNING",
                "type": "Breakout",
                "price": 149900,  # ₹1,499/mo premium
            },
        ]

        for s_info in strats_data:
            await StrategyRepository.upsert_strategy(
                db=session,
                strategy_id=s_info["id"],
                name=s_info["name"],
                symbol=s_info["symbol"],
                description=s_info["description"],
                timeframe=s_info["timeframe"],
                status=s_info["status"],
                strategy_type=s_info["type"],
                price_paise=s_info["price"],
            )

        await session.commit()
        print(f"[STRATEGIES] Seeded {len(strats_data)} active trading strategies.")

        # 3. Seed Subscriptions & Payment Records
        # Explicit subscription mapping per user requirement:
        # - User 1 (u_1, demo@trademint.in): ALL 5 subscriptions
        # - User 2 (u_priya, priya.sharma@trademint.in): 3 subscriptions
        # - User 3 (u_arjun, arjun.verma@trademint.in): 0 subscriptions
        user_sub_mapping = {
            "u_1": [s["id"] for s in strats_data],  # All 5 strategies
            "u_judge": [s["id"] for s in strats_data],  # All 5 strategies
            "u_priya": ["strat_time", "strat_breakout", "strat_ma"],  # 3 strategies
            "u_arjun": [],  # 0 strategies (no subscriptions)
            "u_karthik": ["strat_time"],  # 1 strategy
        }

        sub_count = 0
        now = datetime.now(timezone.utc)
        for uid, allowed_strat_ids in user_sub_mapping.items():
            for s_info in strats_data:
                sid = s_info["id"]
                res = await session.execute(
                    select(Subscription).where(
                        Subscription.user_id == uid,
                        Subscription.strategy_id == sid,
                    )
                )
                existing = res.scalar_one_or_none()

                if sid in allowed_strat_ids:
                    if not existing:
                        sub = await SubscriptionRepository.create_or_renew_subscription(
                            db=session,
                            user_id=uid,
                            strategy_id=sid,
                            plan_tier="PRO" if uid in ["u_1", "u_judge"] else "FREE",
                            amount_paid_paise=s_info["price"],
                            duration_days=30,
                            payment_reference=f"REF_SEED_{uid}_{sid}",
                        )
                        sub_count += 1
                        if s_info["price"] > 0:
                            await PaymentRepository.create_transaction(
                                db=session,
                                user_id=uid,
                                subscription_id=sub.id,
                                amount_paise=s_info["price"],
                                payment_method="WALLET",
                                transaction_type="SUBSCRIPTION_PURCHASE",
                                status="SUCCESS",
                                remarks=f"Subscription purchase for {s_info['name']}",
                            )
                    else:
                        existing.is_active = True
                        existing.status = "ACTIVE"
                        sub_count += 1
                else:
                    if existing:
                        existing.is_active = False
                        existing.status = "CANCELLED"

        await session.commit()
        print(f"[SUBSCRIPTIONS] Created {sub_count} user-strategy subscriptions (User 1: All 5, User 2: 3, User 3: 0).")

        # 4. Seed Historical Orders and Fills for Judge Dashboard
        orders_data = [
            {
                "id": "ord_001",
                "client_order_id": "cli_001",
                "strategy_id": "strat_time",
                "symbol": "RELIANCE",
                "side": "BUY",
                "quantity": 2,
                "filled_quantity": 2,
                "price_paise": 142400,
                "status": "FILLED",
                "time_offset_min": 120,
            },
            {
                "id": "ord_002",
                "client_order_id": "cli_002",
                "strategy_id": "strat_breakout",
                "symbol": "INFY",
                "side": "BUY",
                "quantity": 1,
                "filled_quantity": 1,
                "price_paise": 99200,
                "status": "FILLED",
                "time_offset_min": 90,
            },
            {
                "id": "ord_003",
                "client_order_id": "cli_003",
                "strategy_id": "strat_ma",
                "symbol": "TCS",
                "side": "BUY",
                "quantity": 1,
                "filled_quantity": 1,
                "price_paise": 208000,
                "status": "FILLED",
                "time_offset_min": 60,
            },
            {
                "id": "ord_004",
                "client_order_id": "cli_004",
                "strategy_id": "strat_vwap",
                "symbol": "HDFCBANK",
                "side": "BUY",
                "quantity": 5,
                "filled_quantity": 5,
                "price_paise": 164500,
                "status": "FILLED",
                "time_offset_min": 45,
            },
            {
                "id": "ord_005",
                "client_order_id": "cli_005",
                "strategy_id": "strat_time",
                "symbol": "RELIANCE",
                "side": "SELL",
                "quantity": 2,
                "filled_quantity": 2,
                "price_paise": 143500,
                "status": "FILLED",
                "time_offset_min": 15,
            },
            {
                "id": "ord_006",
                "client_order_id": "cli_006",
                "strategy_id": "strat_rsi",
                "symbol": "RELIANCE",
                "side": "BUY",
                "quantity": 1,
                "filled_quantity": 0,
                "price_paise": 142000,
                "status": "OPEN",
                "time_offset_min": 5,
            },
        ]

        for o_info in orders_data:
            ord_rec = await session.get(OrderRecord, o_info["id"])
            if not ord_rec:
                await OrderRepository.save_order(
                    db=session,
                    order_id=o_info["id"],
                    client_order_id=o_info["client_order_id"],
                    strategy_id=o_info["strategy_id"],
                    symbol=o_info["symbol"],
                    side=o_info["side"],
                    quantity=o_info["quantity"],
                    filled_quantity=o_info["filled_quantity"],
                    price_paise=o_info["price_paise"],
                    status=o_info["status"],
                    user_id="u_1",
                )

                if o_info["filled_quantity"] > 0:
                    await OrderRepository.save_fill(
                        db=session,
                        order_id=o_info["id"],
                        strategy_id=o_info["strategy_id"],
                        symbol=o_info["symbol"],
                        side=o_info["side"],
                        quantity=o_info["filled_quantity"],
                        price_paise=o_info["price_paise"],
                        user_id="u_1",
                    )

        await session.commit()
        print(f"[ORDERS & FILLS] Seeded realistic executed orders and P&L trade fills.")

        # 5. Seed Risk Events for L3 Risk Controls Presentation
        risk_events_data = [
            {
                "strategy_id": "strat_breakout",
                "symbol": "INFY",
                "side": "BUY",
                "quantity": 1,
                "price_paise": 99200,
                "passed": True,
                "reason": "PASS_ALL_CHECKS",
                "message": "Passed tick size, lot size, circuit limit, and max loss checks.",
                "severity": "INFO",
            },
            {
                "strategy_id": "strat_ma",
                "symbol": "TCS",
                "side": "BUY",
                "quantity": 1,
                "price_paise": 208000,
                "passed": True,
                "reason": "PASS_ALL_CHECKS",
                "message": "Order intent validated against 021 exchange controls.",
                "severity": "INFO",
            },
            {
                "strategy_id": "strat_breakout",
                "symbol": "INFY",
                "side": "SELL",
                "quantity": 1,
                "price_paise": 99154,
                "passed": False,
                "reason": "TICK_SIZE_INVALID",
                "message": "Price Rs. 991.54 is not a valid multiple of tick size Rs. 0.05.",
                "severity": "WARNING",
            },
            {
                "strategy_id": "ALL",
                "symbol": "ALL",
                "side": "CLOSE",
                "quantity": 2,
                "price_paise": 0,
                "passed": False,
                "reason": "KILL_SWITCH_ACTIVE",
                "message": "Level 3 Emergency Kill Switch activated by operator. SLA met in 3.08s.",
                "severity": "CRITICAL",
            },
        ]

        for re_info in risk_events_data:
            await OrderRepository.save_risk_event(
                db=session,
                strategy_id=re_info["strategy_id"],
                symbol=re_info["symbol"],
                side=re_info["side"],
                quantity=re_info["quantity"],
                passed=re_info["passed"],
                price_paise=re_info["price_paise"],
                reason=re_info["reason"],
                message=re_info["message"],
                severity=re_info["severity"],
                user_id="u_1",
            )

        await session.commit()
        print(f"[RISK EVENTS] Seeded Level 3 Risk Controls audit logs for presentation.")

    print("\n" + "=" * 60)
    print(" DEMO DATA SEEDING COMPLETE! PREPARED FOR JUDGE DEMONSTRATION.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
