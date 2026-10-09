import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import init_db
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    from sqlalchemy import delete
    from app.database.session import AsyncSessionLocal
    from app.database.models import User, Subscription
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(User).where(
                User.email.in_([
                    "integration@trademint.in",
                    "forgot@trademint.in",
                ]) | User.email.like("settings_test_%")
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_registration_and_login_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register a new user
        reg_payload = {
            "name": "Integration User",
            "email": "integration@trademint.in",
            "password": "StrongPassword123!",
            "api_ucc": "TEST_UCC",
        }
        res = await client.post("/api/auth/register", json=reg_payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert "access_token" in data
        assert data["user"]["email"] == "integration@trademint.in"
        assert data["user"]["name"] == "Integration User"
        token = data["access_token"]

        # 2. Reject duplicate registration
        res_dup = await client.post("/api/auth/register", json=reg_payload)
        assert res_dup.status_code == 400
        assert "already exists" in res_dup.json()["detail"]

        # 3. Reject weak password
        res_weak = await client.post(
            "/api/auth/register",
            json={"name": "Bad", "email": "bad@trademint.in", "password": "weak"},
        )
        assert res_weak.status_code == 422  # validation error from pydantic

        # 4. Login with correct credentials
        res_login = await client.post(
            "/api/auth/login",
            json={"email": "integration@trademint.in", "password": "StrongPassword123!"},
        )
        assert res_login.status_code == 200
        login_data = res_login.json()
        assert "access_token" in login_data
        assert login_data["user"]["email"] == "integration@trademint.in"

        # 5. Login with invalid password
        res_bad_pw = await client.post(
            "/api/auth/login",
            json={"email": "integration@trademint.in", "password": "WrongPassword123!"},
        )
        assert res_bad_pw.status_code == 401
        assert res_bad_pw.json()["detail"] == "Invalid email or password"

        # 6. Access protected /api/auth/me
        res_me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res_me.status_code == 200
        assert res_me.json()["email"] == "integration@trademint.in"

        # 7. Unauthenticated access fails
        res_no_auth = await client.get("/api/auth/me")
        assert res_no_auth.status_code == 401


@pytest.mark.asyncio
async def test_forgot_and_reset_password_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Request reset token for an email
        res_forgot = await client.post(
            "/api/auth/forgot-password",
            json={"email": "demo@trademint.in"},
        )
        assert res_forgot.status_code == 200
        reset_token = res_forgot.json().get("reset_token")
        assert reset_token is not None

        # Reset password using token
        res_reset = await client.post(
            "/api/auth/reset-password",
            json={"token": reset_token, "new_password": "NewBrandPassword88!"},
        )
        assert res_reset.status_code == 200

        # Login with newly reset password succeeds
        res_login = await client.post(
            "/api/auth/login",
            json={"email": "demo@trademint.in", "password": "NewBrandPassword88!"},
        )
        assert res_login.status_code == 200

        # Token cannot be reused
        res_reuse = await client.post(
            "/api/auth/reset-password",
            json={"token": reset_token, "new_password": "AnotherPassword99!"},
        )
        assert res_reuse.status_code == 400


@pytest.mark.asyncio
async def test_user_settings_persistence():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register user
        email = f"settings_test_{pytest.__version__.replace('.', '')}@trademint.in"
        res = await client.post(
            "/api/auth/register",
            json={"name": "Tester", "email": email, "password": "TestPassword123!"},
        )
        token = res.json()["access_token"]

        # Get settings
        res_get = await client.get(
            "/api/user/settings", headers={"Authorization": f"Bearer {token}"}
        )
        assert res_get.status_code == 200
        assert res_get.json()["notifications_enabled"] is True
        assert res_get.json()["theme"] == "light"

        # Update settings: turn notifications OFF, theme to dark, update name
        res_put = await client.put(
            "/api/user/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Updated Tester",
                "notifications_enabled": False,
                "theme": "dark",
            },
        )
        assert res_put.status_code == 200
        updated = res_put.json()
        assert updated["name"] == "Updated Tester"
        assert updated["notifications_enabled"] is False
        assert updated["theme"] == "dark"

        # Fetch again to verify persistence
        res_verify = await client.get(
            "/api/user/settings", headers={"Authorization": f"Bearer {token}"}
        )
        assert res_verify.json()["notifications_enabled"] is False
        assert res_verify.json()["theme"] == "dark"
