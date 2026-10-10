from collections.abc import AsyncGenerator
import logging
from pathlib import Path
import socket
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger("tradeshield.database")
settings = get_settings()

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_SQLITE_FILE = BACKEND_DIR / "tradeshield.db"
DEFAULT_SQLITE_URL = f"sqlite+aiosqlite:///{DEFAULT_SQLITE_FILE.as_posix()}"


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
if settings.database_url.startswith("sqlite"):
    ACTIVE_DATABASE_URL = settings.database_url
    engine = create_async_engine(
        ACTIVE_DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )
elif _is_postgres_reachable(settings.database_url):
    ACTIVE_DATABASE_URL = settings.database_url
    engine = create_async_engine(
        ACTIVE_DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
else:
    ACTIVE_DATABASE_URL = DEFAULT_SQLITE_URL
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
        fallback_url = DEFAULT_SQLITE_URL
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

    # Apply idempotent table migrations for SQLite & Postgres
    async with engine.begin() as conn:
        migration_statements = [
            # User table migrations
            "ALTER TABLE users ADD COLUMN password_hash VARCHAR(256) DEFAULT '';",
            "ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'user';",
            "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE;",
            "ALTER TABLE users ADD COLUMN account_balance_paise BIGINT DEFAULT 10000000;",
            "ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(32) DEFAULT 'FREE';",
            "ALTER TABLE users ADD COLUMN notifications_enabled BOOLEAN DEFAULT TRUE;",
            "ALTER TABLE users ADD COLUMN theme VARCHAR(16) DEFAULT 'light';",
            "ALTER TABLE users ADD COLUMN reset_token_hash VARCHAR(128);",
            "ALTER TABLE users ADD COLUMN reset_token_expires_at TIMESTAMP WITH TIME ZONE;",
            "ALTER TABLE users ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE;",

            # Subscriptions table migrations
            "ALTER TABLE subscriptions ADD COLUMN plan_id VARCHAR(64);",
            "ALTER TABLE subscriptions ADD COLUMN plan_tier VARCHAR(32) DEFAULT 'PRO';",
            "ALTER TABLE subscriptions ADD COLUMN amount_paid_paise BIGINT DEFAULT 0;",
            "ALTER TABLE subscriptions ADD COLUMN status VARCHAR(32) DEFAULT 'ACTIVE';",
            "ALTER TABLE subscriptions ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE;",
            "ALTER TABLE subscriptions ADD COLUMN auto_renew BOOLEAN DEFAULT TRUE;",
            "ALTER TABLE subscriptions ADD COLUMN payment_reference VARCHAR(128);",

            # Strategies table migrations
            "ALTER TABLE strategies ADD COLUMN creator_id VARCHAR(64);",
            "ALTER TABLE strategies ADD COLUMN strategy_type VARCHAR(64) DEFAULT 'TimeBased';",
            "ALTER TABLE strategies ADD COLUMN parameters_json TEXT DEFAULT '{}';",
            "ALTER TABLE strategies ADD COLUMN is_public BOOLEAN DEFAULT TRUE;",
            "ALTER TABLE strategies ADD COLUMN price_paise BIGINT DEFAULT 0;",

            # Orders & Trade Fills & Risk Events user_id migrations
            "ALTER TABLE orders ADD COLUMN user_id VARCHAR(64);",
            "ALTER TABLE trade_fills ADD COLUMN user_id VARCHAR(64);",
            "ALTER TABLE risk_events ADD COLUMN user_id VARCHAR(64);",
        ]
        for stmt in migration_statements:
            try:
                await conn.execute(text(stmt))
            except Exception:
                # Column already exists or table alter ignored
                pass
