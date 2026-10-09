from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import SessionLocal, check_connection, create_tables, engine, get_session
from app.database.seed import seed_defaults


@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_connection()          # fail fast with a clear message
    await create_tables()             # code first: tables come from the models
    async with SessionLocal() as session:
        await seed_defaults(session)
    # later: startup reconciliation runs here, before any strategy starts
    yield
    await engine.dispose()


app = FastAPI(title="TradeShield", lifespan=lifespan)


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}