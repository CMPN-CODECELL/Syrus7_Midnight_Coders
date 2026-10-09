import pytest_asyncio
from app.database.session import engine


@pytest_asyncio.fixture(autouse=True)
async def cleanup_database_connections():
    """Ensure database connections and engines are properly disposed per test."""
    yield
    await engine.dispose()
