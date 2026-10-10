#!/usr/bin/env python3
"""TradeShield Database Setup & Verification Tool
=================================================
Automates database provisioning, schema creation, and demo data seeding
for local development, GitHub CI/CD, and judge evaluation.

Usage:
    python backend/scripts/setup_database.py [--reset] [--sqlite]

Options:
    --reset     Drop all existing tables or recreate local SQLite file before seeding
    --verify    Run integrity checks on all seeded records
"""

import argparse
import asyncio
from pathlib import Path
import sys

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, text
from app.core.config import get_settings
from app.database import (
    ACTIVE_DATABASE_URL,
    AsyncSessionLocal,
    Base,
    DEFAULT_SQLITE_FILE,
    engine,
    init_db,
)
from app.database.models import (
    OrderRecord,
    PaymentTransaction,
    RiskEventRecord,
    StrategyRecord,
    Subscription,
    SubscriptionPlan,
    TradeFillRecord,
    User,
)
from scripts.seed_demo_data import seed_demo_data


async def verify_database_health() -> dict[str, int]:
    """Inspect and report record counts across all core tables."""
    counts = {}
    async with AsyncSessionLocal() as session:
        for model, label in [
            (User, "Users"),
            (SubscriptionPlan, "Subscription Plans"),
            (StrategyRecord, "Strategies"),
            (Subscription, "User Subscriptions"),
            (PaymentTransaction, "Payment Transactions"),
            (OrderRecord, "Orders"),
            (TradeFillRecord, "Trade Fills"),
            (RiskEventRecord, "Risk Events"),
        ]:
            res = await session.execute(select(model))
            counts[label] = len(res.scalars().all())
    return counts


async def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="TradeShield Database Provisioning CLI")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset and recreate database schema from scratch",
    )
    args = parser.parse_args()

    settings = get_settings()

    print("=" * 72)
    print(" TRADESHIELD 021 ALGO PLATFORM - DATABASE PROVISIONING SUITE")
    print("=" * 72)
    print(f"[*] Configured Database URL : {settings.database_url}")
    print(f"[*] Active Engine           : {ACTIVE_DATABASE_URL}")
    print(f"[*] Broker Mode             : {settings.broker_mode.upper()}")
    print("-" * 72)

    if args.reset:
        print("[!] Reset flag detected: Recreating database tables...")
        if "sqlite" in ACTIVE_DATABASE_URL and DEFAULT_SQLITE_FILE.exists():
            print(f"[*] Refreshing SQLite database at: {DEFAULT_SQLITE_FILE}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            print("[+] Successfully cleared existing tables.")

    # 1. Initialize schema
    print("[*] Creating table schema and applying idempotent migrations...")
    await init_db()
    print("[+] Database schema successfully verified and up-to-date.")

    # 2. Seed judge evaluation data
    print("[*] Seeding demo users, strategies, subscriptions, and telemetry...")
    await seed_demo_data()

    # 3. Verify counts
    print("\n" + "-" * 72)
    print(" DATABASE INTEGRITY AUDIT")
    print("-" * 72)
    counts = await verify_database_health()
    for table_name, count in counts.items():
        status = "[PASS]" if count > 0 else "[EMPTY]"
        print(f"  * {table_name:<26} : {count:>4} records  {status}")

    print("\n" + "=" * 72)
    print(" READY FOR JUDGE EVALUATION & LIVE DEMONSTRATION")
    print("=" * 72)
    print("  * Lead Trader Login   : demo@trademint.in     / demo1234  (All 5 Strategies)")
    print("  * Judge Evaluator     : judge@trademint.in    / judge1234 (All 5 Strategies)")
    print("  * Quant Analyst       : priya.sharma@trademint.in / priya1234 (3 Strategies)")
    print("  * Risk Manager        : arjun.verma@trademint.in  / arjun1234 (0 Strategies)")
    print("  * Active Database     : backend/tradeshield.db")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
