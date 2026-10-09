from collections.abc import AsyncGenerator
import logging
import socket
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger("tradeshield.database")
settings = get_settings()


def _is_postgres_reachable(db_url: str) -> bool:
    """Fast check whether PostgreSQL host:port is listening before initializing engine."""
    if not ("postgres" in db_url):
        return True
    try:
        clean_url = db_url.split("+", 1)[-1] if "+" in db_url else db_url
        parsed = urlparse(clean_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        with socket.create_connection((host, port), timeout=0.6):
            return True
    except Exception:
        return False


# Determine active database URL (graceful local fallback when Docker/Postgres is offline)
if _is_postgres_reachable(settings.database_url):
    ACTIVE_DATABASE_URL = settings.database_url
    engine = create_async_engine(
        ACTIVE_DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
else:
    ACTIVE_DATABASE_URL = "sqlite+aiosqlite:///./tradeshield.db"
    logger.info(
        "PostgreSQL host at %s unreachable. Initializing local SQLite database: %s",
        settings.database_url,
        ACTIVE_DATABASE_URL,
    )
    print(f"[DATABASE] PostgreSQL offline. Using local SQLite database ({ACTIVE_DATABASE_URL})")
    engine = create_async_engine(
        ACTIVE_DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables with automatic SQLite fallback if PostgreSQL is unreachable."""
    global engine, AsyncSessionLocal
    from sqlalchemy import text
    import app.database.models.models  # noqa: F401 - ensure models register with Base.metadata

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Successfully initialized database tables: %s", ACTIVE_DATABASE_URL)
    except Exception as exc:
        fallback_url = "sqlite+aiosqlite:///./tradeshield.db"
        logger.warning(
            "Primary database %s failed (%s). Falling back to SQLite: %s",
            ACTIVE_DATABASE_URL,
            exc,
            fallback_url,
        )
        print(f"[DATABASE] Primary DB failed ({exc}). Falling back to local SQLite ({fallback_url})")
        engine = create_async_engine(
            fallback_url,
            echo=False,
            future=True,
            connect_args={"check_same_thread": False},
        )
        AsyncSessionLocal.configure(bind=engine)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            print("[DATABASE] Local SQLite schema created successfully.")

    # Try applying safe migrations if on PostgreSQL
    if "postgres" in str(engine.url):
        try:
            async with engine.begin() as conn:
                migration_statements = [
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(256) DEFAULT '' NOT NULL;",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32) DEFAULT 'user' NOT NULL;",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE NOT NULL;",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN DEFAULT TRUE NOT NULL;",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS theme VARCHAR(16) DEFAULT 'light' NOT NULL;",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_hash VARCHAR(128);",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires_at TIMESTAMP WITH TIME ZONE;",
                ]
                for stmt in migration_statements:
                    try:
                        await conn.execute(text(stmt))
                    except Exception:
                        pass
        except Exception:
            pass
