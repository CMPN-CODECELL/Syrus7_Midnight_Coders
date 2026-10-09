import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class Position(Base):
    """One row per strategy, account and instrument. Not the account-wide position."""

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("strategy_id", "account_id", "exchange", "token", name="uq_position_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    exchange: Mapped[str] = mapped_column(String(10))
    token: Mapped[int] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[int] = mapped_column(Integer, default=0)         # signed: long +, short -
    average_price_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    realized_pnl_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    unrealized_pnl_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Trade(Base):
    """One round trip: flat, then non-flat, then flat again."""

    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.id"), index=True)
    exchange: Mapped[str] = mapped_column(String(10))
    token: Mapped[int] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(30))
    side: Mapped[str] = mapped_column(String(5))                      # LONG / SHORT
    quantity: Mapped[int] = mapped_column(Integer)                    # peak size traded
    entry_price_paise: Mapped[int] = mapped_column(BigInteger)
    exit_price_paise: Mapped[int | None] = mapped_column(BigInteger)
    gross_pnl_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    charges_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    net_pnl_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DailyPnl(Base):
    __tablename__ = "pnl"
    __table_args__ = (UniqueConstraint("strategy_id", "trading_date", name="uq_pnl_day"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.id"))
    trading_date: Mapped[date] = mapped_column(Date)
    realized_pnl_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    unrealized_pnl_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    charges_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    net_pnl_paise: Mapped[int] = mapped_column(BigInteger, default=0)