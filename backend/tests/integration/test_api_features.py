import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import init_db
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_strategies_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get strategies
        res = await client.get("/api/strategies")
        assert res.status_code == 200
        strats = res.json()
        assert len(strats) >= 3

        strat_id = strats[0]["id"]

        # Stop strategy
        res_stop = await client.post(f"/api/strategies/{strat_id}/stop")
        assert res_stop.status_code == 200
        assert res_stop.json()["status"] == "STOPPED"

        # Start strategy
        res_start = await client.post(f"/api/strategies/{strat_id}/start")
        assert res_start.status_code == 200
        assert res_start.json()["status"] == "RUNNING"


@pytest.mark.asyncio
async def test_kill_switch_activation_and_reset():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check initial kill switch status
        res_status = await client.get("/api/risk/kill-switch")
        assert res_status.status_code == 200

        # Activate kill switch
        res_act = await client.post("/api/risk/kill-switch/activate")
        assert res_act.status_code == 200
        data = res_act.json()
        assert data["active"] is True
        assert data["slaMet"] is True

        # When kill switch is active, starting strategy must be blocked
        res_blocked = await client.post("/api/strategies/strat_time/start")
        assert res_blocked.status_code == 400
        assert "kill switch" in res_blocked.json()["detail"].lower()

        # Reset kill switch
        res_reset = await client.post("/api/risk/kill-switch/reset")
        assert res_reset.status_code == 200
        assert res_reset.json()["active"] is False

        # Soft halt (CANCEL_ONLY)
        res_soft = await client.post(
            "/api/risk/kill-switch/activate",
            json={"scope": "CANCEL_ONLY", "reason": "High Volatility Spike"},
        )
        assert res_soft.status_code == 200
        assert res_soft.json()["scope"] == "CANCEL_ONLY"

        # Check incidents endpoint
        res_inc = await client.get("/api/risk/kill-switch/incidents")
        assert res_inc.status_code == 200
        incidents = res_inc.json()
        assert len(incidents) >= 1
        assert incidents[0]["scope"] in ("CANCEL_ONLY", "GLOBAL")

        # Update auto-kill rules
        res_rules = await client.put(
            "/api/risk/kill-switch/auto-rules",
            json={"max_mtm_loss": 3000.0, "max_consecutive_rejections": 4},
        )
        assert res_rules.status_code == 200
        assert res_rules.json()["autoRules"]["maxMtmLoss"] == 3000.0
        assert res_rules.json()["autoRules"]["maxConsecutiveRejections"] == 4

        # Disengage
        await client.post("/api/risk/kill-switch/reset")


@pytest.mark.asyncio
async def test_account_summary_and_orders():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_acc = await client.get("/api/account/summary")
        assert res_acc.status_code == 200
        acc = res_acc.json()
        assert "accountValue" in acc
        assert "todayPnl" in acc

        res_orders = await client.get("/api/orders")
        assert res_orders.status_code == 200
        assert isinstance(res_orders.json(), list)

        res_pos = await client.get("/api/positions")
        assert res_pos.status_code == 200
        assert isinstance(res_pos.json(), list)


@pytest.mark.asyncio
async def test_strategy_customization_and_trade_controls():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Update strategy parameters
        res_update = await client.put(
            "/api/strategies/strat_ma/parameters",
            json={
                "parameters": {"fast_period": 7, "slow_period": 25, "quantity": 8},
                "limits": {"maxDailyLoss": 750.0, "maxPositionSize": 15, "maxOrdersPerMinute": 8},
            },
        )
        assert res_update.status_code == 200
        data = res_update.json()
        assert data["parameters"]["fast_period"] == 7
        assert data["parameters"]["slow_period"] == 25
        assert data["parameters"]["quantity"] == 8
        assert data["limits"]["maxDailyLoss"] == 750.0
        assert data["limits"]["maxPositionSize"] == 15

        # 2. Reset strategy cycle
        res_reset = await client.post("/api/strategies/strat_ma/reset")
        assert res_reset.status_code == 200
        assert res_reset.json()["status"] == "RESET"

        # 3. Manual user trade control
        res_manual = await client.post(
            "/api/strategies/strat_ma/manual-trade",
            json={"side": "BUY", "quantity": 2},
        )
        assert res_manual.status_code == 200
        manual_data = res_manual.json()
        assert manual_data["status"] == "EXECUTED"
        assert manual_data["quantity"] == 2

        # 4. Square off strategy
        res_sq = await client.post("/api/strategies/strat_ma/square-off")
        assert res_sq.status_code == 200
        sq_data = res_sq.json()
        assert sq_data["status"] in ("SQUARED_OFF", "ALREADY_FLAT")

        # 5. Create a brand new custom strategy
        res_create = await client.post(
            "/api/strategies",
            json={
                "name": "My Custom Scalper",
                "strategy_type": "Breakout",
                "symbol": "HDFCBANK",
                "parameters": {"quantity": 5, "breakout_pct": 1.5, "target_pct": 3.0, "stop_loss_pct": 1.5, "direction": "LONG_ONLY"},
                "limits": {"maxDailyLoss": 600.0, "maxPositionSize": 10},
            },
        )
        assert res_create.status_code == 200
        created = res_create.json()
        assert created["name"] == "My Custom Scalper"
        assert created["symbol"] == "HDFCBANK"
        assert created["canDelete"] is True
        strat_id = created["id"]

        # 6. Delete custom strategy
        res_del = await client.delete(f"/api/strategies/{strat_id}")
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "DELETED"
