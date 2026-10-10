import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from app.main import app
from app.database import init_db, AsyncSessionLocal
from app.database.models import User, Subscription
from app.core.security import hash_password
from app.database.repositories import SubscriptionRepository


@pytest.mark.asyncio
async def test_three_user_subscription_tiers():
    """Verify subscription isolation across 3 users:
    - User 1: All 5 subscriptions
    - User 2: Exactly 3 subscriptions
    - User 3: 0 subscriptions (can subscribe dynamically)
    """
    await init_db()

    async with AsyncSessionLocal() as db:
        users_config = [
            {"id": "u_test_all", "email": "test_all@trademint.in", "subs": ["strat_time", "strat_breakout", "strat_ma", "strat_momentum", "strat_mean_reversion"]},
            {"id": "u_test_three", "email": "test_three@trademint.in", "subs": ["strat_time", "strat_breakout", "strat_ma"]},
            {"id": "u_test_none", "email": "test_none@trademint.in", "subs": []},
        ]

        for u_cfg in users_config:
            u_res = await db.execute(select(User).where(User.email == u_cfg["email"]))
            user = u_res.scalar_one_or_none()
            if not user:
                user = User(
                    id=u_cfg["id"],
                    name=u_cfg["id"],
                    email=u_cfg["email"],
                    password_hash=hash_password("pass1234"),
                    role="user",
                    is_active=True,
                )
                db.add(user)
                await db.flush()

            for sid in ["strat_time", "strat_breakout", "strat_ma", "strat_momentum", "strat_mean_reversion"]:
                s_res = await db.execute(
                    select(Subscription).where(
                        Subscription.user_id == user.id,
                        Subscription.strategy_id == sid,
                    )
                )
                sub_row = s_res.scalar_one_or_none()
                if sid in u_cfg["subs"]:
                    if not sub_row:
                        db.add(Subscription(user_id=user.id, strategy_id=sid, is_active=True, status="ACTIVE"))
                    else:
                        sub_row.is_active = True
                        sub_row.status = "ACTIVE"
                else:
                    if sub_row:
                        sub_row.is_active = False
                        sub_row.status = "CANCELLED"

        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Login as User 1 (All Subscriptions)
        res1 = await ac.post("/api/auth/login", json={"email": "test_all@trademint.in", "password": "pass1234"})
        assert res1.status_code == 200, res1.text
        token1 = res1.json()["access_token"]

        strat_res1 = await ac.get("/api/strategies", headers={"Authorization": f"Bearer {token1}"})
        assert strat_res1.status_code == 200
        strats1 = strat_res1.json()
        subscribed1 = [s for s in strats1 if s.get("isSubscribed")]
        assert len(subscribed1) == len(strats1), f"User 1 expected all subscriptions, got {len(subscribed1)}/{len(strats1)}"

        # 2. Login as User 2 (3 Subscriptions)
        res2 = await ac.post("/api/auth/login", json={"email": "test_three@trademint.in", "password": "pass1234"})
        assert res2.status_code == 200, res2.text
        token2 = res2.json()["access_token"]

        strat_res2 = await ac.get("/api/strategies", headers={"Authorization": f"Bearer {token2}"})
        assert strat_res2.status_code == 200
        strats2 = strat_res2.json()
        subscribed2 = [s["id"] for s in strats2 if s.get("isSubscribed")]
        assert len(subscribed2) == 3, f"User 2 expected 3 subscriptions, got {len(subscribed2)} ({subscribed2})"
        assert set(subscribed2) == {"strat_time", "strat_breakout", "strat_ma"}

        # 3. Login as User 3 (0 Subscriptions)
        res3 = await ac.post("/api/auth/login", json={"email": "test_none@trademint.in", "password": "pass1234"})
        assert res3.status_code == 200, res3.text
        token3 = res3.json()["access_token"]

        strat_res3 = await ac.get("/api/strategies", headers={"Authorization": f"Bearer {token3}"})
        assert strat_res3.status_code == 200
        strats3 = strat_res3.json()
        subscribed3 = [s["id"] for s in strats3 if s.get("isSubscribed")]
        assert len(subscribed3) == 0, f"User 3 expected 0 subscriptions, got {len(subscribed3)} ({subscribed3})"

        # 4. User 3 subscribes dynamically to 'strat_time'
        sub_action = await ac.post("/api/strategies/strat_time/subscribe", headers={"Authorization": f"Bearer {token3}"})
        assert sub_action.status_code == 200, sub_action.text
        assert sub_action.json()["status"] == "SUBSCRIBED"

        # 5. Verify User 3 now has 1 subscription ('strat_time')
        strat_res3_after = await ac.get("/api/strategies", headers={"Authorization": f"Bearer {token3}"})
        assert strat_res3_after.status_code == 200
        strats3_after = strat_res3_after.json()
        subscribed3_after = [s["id"] for s in strats3_after if s.get("isSubscribed")]
        assert subscribed3_after == ["strat_time"]
