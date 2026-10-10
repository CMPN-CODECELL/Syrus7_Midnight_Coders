from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.models import Subscription, SubscriptionPlan


class SubscriptionRepository:
    DEFAULT_PLANS = [
        {
            "id": "plan_free",
            "name": "Free Starter Plan",
            "code": "FREE",
            "description": "Essential trading features with paper trading, 3 active strategies, and standard risk limits.",
            "price_paise": 0,
            "billing_cycle": "monthly",
            "features_json": '["3 Active Strategies", "Standard Risk Engine Controls", "Paper Trading Mode", "5-Min Market Data"]',
        },
        {
            "id": "plan_pro",
            "name": "Pro Trader Pass",
            "code": "PRO",
            "description": "Professional tier with unlimited strategy subscriptions, 0ms broker execution priority, and advanced risk controls.",
            "price_paise": 299900,  # ₹2,999 / month
            "billing_cycle": "monthly",
            "features_json": '["Unlimited Strategy Subscriptions", "Sub-Millisecond Execution Engine", "Custom Parameters & Guardrails", "Level 3 Emergency Recovery", "Live WebSocket Feeds"]',
        },
        {
            "id": "plan_enterprise",
            "name": "HFT Institutional Pass",
            "code": "ENTERPRISE",
            "description": "Institutional grade infrastructure with custom strategy deployment, dedicated broker connection, and priority SLA.",
            "price_paise": 999900,  # ₹9,999 / month
            "billing_cycle": "monthly",
            "features_json": '["Dedicated 021 Broker Pipeline", "Custom Python Strategy Builder", "Dedicated SLA & Support", "Institutional Position Sizing", "Direct Database Access"]',
        },
    ]

    @classmethod
    async def seed_plans(cls, db: AsyncSession) -> list[SubscriptionPlan]:
        plans = []
        for p_data in cls.DEFAULT_PLANS:
            result = await db.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.code == p_data["code"])
            )
            plan = result.scalar_one_or_none()
            if not plan:
                plan = SubscriptionPlan(
                    id=p_data["id"],
                    name=p_data["name"],
                    code=p_data["code"],
                    description=p_data["description"],
                    price_paise=p_data["price_paise"],
                    billing_cycle=p_data["billing_cycle"],
                    features_json=p_data["features_json"],
                    is_active=True,
                )
                db.add(plan)
            plans.append(plan)
        await db.flush()
        return plans

    @staticmethod
    async def get_plans(db: AsyncSession) -> list[SubscriptionPlan]:
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_plan_by_code_or_id(db: AsyncSession, identifier: str) -> Optional[SubscriptionPlan]:
        result = await db.execute(
            select(SubscriptionPlan).where(
                (SubscriptionPlan.id == identifier) | (SubscriptionPlan.code == identifier)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_subscriptions(db: AsyncSession, user_id: str) -> list[Subscription]:
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.subscribed_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_active_user_subscription_for_strategy(
        db: AsyncSession, user_id: str, strategy_id: str
    ) -> Optional[Subscription]:
        result = await db.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.strategy_id == strategy_id,
                Subscription.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_or_renew_subscription(
        db: AsyncSession,
        user_id: str,
        strategy_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        plan_tier: str = "PRO",
        amount_paid_paise: int = 0,
        duration_days: int = 30,
        payment_reference: Optional[str] = None,
    ) -> Subscription:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=duration_days)
        target_strategy_id = strategy_id or plan_id or "ALL"

        if target_strategy_id:
            existing = await SubscriptionRepository.get_active_user_subscription_for_strategy(
                db, user_id, target_strategy_id
            )
            if existing:
                existing.is_active = True
                existing.status = "ACTIVE"
                existing.plan_tier = plan_tier
                existing.amount_paid_paise += amount_paid_paise
                existing.expires_at = (existing.expires_at or now) + timedelta(days=duration_days)
                existing.payment_reference = payment_reference or existing.payment_reference
                await db.flush()
                return existing

        sub = Subscription(
            user_id=user_id,
            strategy_id=target_strategy_id,
            plan_id=plan_id,
            plan_tier=plan_tier,
            amount_paid_paise=amount_paid_paise,
            status="ACTIVE",
            subscribed_at=now,
            expires_at=expires_at,
            auto_renew=True,
            payment_reference=payment_reference,
            is_active=True,
        )
        db.add(sub)
        await db.flush()
        return sub

    @staticmethod
    async def cancel_subscription(db: AsyncSession, user_id: str, subscription_id: int) -> Optional[Subscription]:
        result = await db.execute(
            select(Subscription).where(
                Subscription.id == subscription_id, Subscription.user_id == user_id
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.is_active = False
            sub.status = "CANCELLED"
            sub.auto_renew = False
            await db.flush()
        return sub
