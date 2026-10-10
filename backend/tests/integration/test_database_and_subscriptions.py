import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.database import AsyncSessionLocal, init_db
from app.database.models import User
from app.database.repositories import (
    OrderRepository,
    PaymentRepository,
    StrategyRepository,
    SubscriptionRepository,
    UserRepository,
)
from app.main import app


@pytest.mark.asyncio
async def test_user_repository_crud():
    await init_db()
    unique_email = f"dbtest_{uuid.uuid4().hex[:8]}@trademint.in"
    async with AsyncSessionLocal() as db:
        # Create user
        user = await UserRepository.create_user(
            db=db,
            name="Database Integration Tester",
            email=unique_email,
            password="Password123!",
            role="user",
            account_balance_paise=20000000,  # ₹200,000.00
            subscription_tier="FREE",
        )
        await db.commit()
        assert user.id.startswith("u_")

        # Fetch user by email
        fetched = await UserRepository.get_by_email(db, unique_email)
        assert fetched is not None
        assert fetched.name == "Database Integration Tester"
        assert fetched.account_balance_paise == 20000000

        # Update balance
        new_bal = await UserRepository.update_balance(db, fetched, -5000000)  # Deduct ₹50,000
        await db.commit()
        assert new_bal == 15000000

        # List users
        users, total = await UserRepository.list_users(db, search="Database Integration")
        assert total >= 1
        assert any(u.email == unique_email for u in users)


@pytest.mark.asyncio
async def test_subscription_and_payment_repositories():
    await init_db()
    unique_email = f"subuser_{uuid.uuid4().hex[:8]}@trademint.in"
    async with AsyncSessionLocal() as db:
        plans = await SubscriptionRepository.seed_plans(db)
        await db.commit()
        assert len(plans) >= 3

        user = await UserRepository.create_user(
            db=db,
            name="Subscriber User",
            email=unique_email,
            password="SubPassword123!",
            role="user",
        )
        await db.commit()

        # Create subscription
        sub = await SubscriptionRepository.create_or_renew_subscription(
            db=db,
            user_id=user.id,
            strategy_id="strat_time",
            plan_tier="PRO",
            amount_paid_paise=299900,
            duration_days=30,
            payment_reference="REF_TEST_12345",
        )
        await db.commit()
        assert sub.is_active is True
        assert sub.plan_tier == "PRO"

        # Record payment transaction
        txn = await PaymentRepository.create_transaction(
            db=db,
            user_id=user.id,
            subscription_id=sub.id,
            amount_paise=299900,
            payment_method="WALLET",
            transaction_type="SUBSCRIPTION_PURCHASE",
            status="SUCCESS",
            remarks="Pro Plan Subscription",
        )
        await db.commit()
        assert txn.status == "SUCCESS"

        # Query user transactions
        txns = await PaymentRepository.get_user_transactions(db, user.id)
        assert len(txns) >= 1
        assert txns[0].amount_paise == 299900


@pytest.mark.asyncio
async def test_buy_subscription_api_flow():
    await init_db()
    unique_email = f"buyer_{uuid.uuid4().hex[:8]}@trademint.in"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register user with wallet balance
        reg_res = await ac.post(
            "/api/auth/register",
            json={
                "name": "Buyer Tester",
                "email": unique_email,
                "password": "Password123!",
                "api_ucc": "HACK342",
            },
        )
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check subscription plans catalog
        plans_res = await ac.get("/api/subscriptions/plans")
        assert plans_res.status_code == 200
        plans = plans_res.json()
        assert len(plans) >= 3

        # Buy Pro subscription
        buy_res = await ac.post(
            "/api/subscriptions/buy",
            json={
                "plan_code": "PRO",
                "billing_cycle": "monthly",
                "payment_method": "WALLET",
            },
            headers=headers,
        )
        assert buy_res.status_code == 200
        buy_data = buy_res.json()
        assert buy_data["status"] == "ACTIVE"
        assert buy_data["plan_tier"] == "PRO"
        assert buy_data["amount_paid_inr"] == 2999.0
        assert "Invoice Reference #" in buy_data["message"]

        # Check transaction history
        txns_res = await ac.get("/api/subscriptions/transactions", headers=headers)
        assert txns_res.status_code == 200
        txns = txns_res.json()
        assert len(txns) >= 1
        assert txns[0]["amount_inr"] == 2999.0

        # Top up wallet balance
        topup_res = await ac.post(
            "/api/user/wallet/topup",
            json={
                "amount_inr": 5000.0,
                "payment_method": "UPI",
            },
            headers=headers,
        )
        assert topup_res.status_code == 200
        assert topup_res.json()["status"] == "SUCCESS"
