import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_quantity_positive"),
        CheckConstraint("filled_quantity >= 0 AND filled_quantity <= quantity", name="ck_order_filled_range"),
        Index("ix_orders_strategy_status", "strategy_id", "status"),
        Index("ix_orders_account_created", "account_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    intent_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)   # our own id; the API has no idempotency key
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))

    exchange: Mapped[str] = mapped_column(String(10))
    token: Mapped[int] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(30))
    side: Mapped[str] = mapped_column(String(4))                      # BUY / SELL
    quantity: Mapped[int] = mapped_column(Integer)                    # requested, always positive
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    product: Mapped[str] = mapped_column(String(10))
    book: Mapped[str] = mapped_column(String(2))                      # RL / SL
    validity: Mapped[str] = mapped_column(String(5))
    price_paise: Mapped[int] = mapped_column(BigInteger, default=0)   # 0 = market
    trigger_paise: Mapped[int | None] = mapped_column(BigInteger)

    status: Mapped[str] = mapped_column(String(20), default="CREATED")
    rejection_source: Mapped[str | None] = mapped_column(String(10))  # RISK / BROKER
    rejection_reason: Mapped[str | None] = mapped_column(String(60))  # reason code
    broker_error_text: Mapped[str | None] = mapped_column(Text)       # raw text from the broker
    is_system_close: Mapped[bool] = mapped_column(Boolean, default=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(100), unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OrderEvent(Base):
    """Audit trail: every status change of every order."""

    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Fill(Base):
    __tablename__ = "fills"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_fill_quantity_positive"),
        UniqueConstraint("order_id", "broker_trade_id", name="uq_fill_broker_trade"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.id"), index=True)  # copied for fast queries
    exchange: Mapped[str] = mapped_column(String(10))
    token: Mapped[int] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(30))
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int] = mapped_column(Integer)                    # this fill only
    price_paise: Mapped[int] = mapped_column(BigInteger)
    charges_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    broker_trade_id: Mapped[str] = mapped_column(String(100))         # dedupe key