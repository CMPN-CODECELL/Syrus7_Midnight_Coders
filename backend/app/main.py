from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes import router
from app.core.config import get_settings
from app.core.security import hash_password
from app.database import AsyncSessionLocal, init_db
from app.database.models import StrategyRecord, Subscription, User

settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and fallback
    await init_db()

    # Seed rich judge & demo data
    try:
        from scripts.seed_demo_data import seed_demo_data
        await seed_demo_data()
    except Exception as e:
        print(f"[MAIN] Demo seed warning: {e}")

    # Level 2/3: Automatic State Recovery & Reconciliation on startup/restart
    try:
        from app.api.routes import recovery_service
        reconcile_report = await recovery_service.reconcile_state()
        print(
            f"[RECOVERY] Startup state reconciliation completed: "
            f"{reconcile_report.broker_positions_count} broker pos, "
            f"{reconcile_report.open_orders_count} working orders."
        )
    except Exception as e:
        print(f"[RECOVERY] Startup reconciliation warning: {e}")


    feed_instance = None
    try:
        from app.api.routes import broker, manager
        from app.broker.api_021 import Broker021
        from app.market_data.feed_021 import MarketFeed021

        if isinstance(broker, Broker021):
            feed_instance = MarketFeed021(broker=broker, on_tick=manager.route_tick)
            feed_instance.subscribe_symbols(["RELIANCE", "TCS", "INFY", "HDFCBANK"])
            await feed_instance.start()
            print("[MAIN] 021 Live Market Feed initialized and started.")
    except Exception as e:
        print(f"[MAIN] 021 Live Feed notice: {e}")

    yield

    if feed_instance:
        await feed_instance.stop()


app = FastAPI(
    title="TradeShield - 021 Algo Trading Platform",
    description="Algorithmic trading platform built on 021 Developer APIs with platform-enforced Risk Controls",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)

# Enable CORS for all local and external origins
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "name": "TradeShield 021 Algo Platform API",
        "status": "running",
        "docs": "http://localhost:8001/docs",
        "health": "http://localhost:8001/health",
        "frontend_app": "http://localhost:8081",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "broker_mode": settings.broker_mode,
        "ucc": settings.api_ucc,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)

