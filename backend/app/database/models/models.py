from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(32), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    api_ucc: Mapped[str] = mapped_column(String(64), default="HACK342")
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    theme: Mapped[str] = mapped_column(String(16), default="light")
    reset_token_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reset_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )


class StrategyRecord(Base):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), default="1m")
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    max_daily_loss_paise: Mapped[int] = mapped_column(Integer, default=50000)
    max_position_size: Mapped[int] = mapped_column(Integer, default=10)
    max_orders_per_minute: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="strategy", cascade="all, delete-orphan"
    )
    orders: Mapped[list["OrderRecord"]] = relationship(
        "OrderRecord", back_populates="strategy", cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "strategy_id", name="uq_user_strategy"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(64), ForeignKey("strategies.id"), nullable=False)
    subscribed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    strategy: Mapped["StrategyRecord"] = relationship("StrategyRecord", back_populates="subscriptions")


class OrderRecord(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # broker order_id or client_order_id
    client_order_id: Mapped[str] = mapped_column(String(64), index=True)
    strategy_id: Mapped[str] = mapped_column(String(64), ForeignKey("strategies.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str] = mapped_column(String(16), default="NSE")
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    price_paise: Mapped[int] = mapped_column(Integer, default=0)
    product: Mapped[str] = mapped_column(String(16), default="INTRADAY")
    status: Mapped[str] = mapped_column(String(32), default="CREATED")
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    strategy: Mapped["StrategyRecord"] = relationship("StrategyRecord", back_populates="orders")
    fills: Mapped[list["TradeFillRecord"]] = relationship(
        "TradeFillRecord", back_populates="order", cascade="all, delete-orphan"
    )


class TradeFillRecord(Base):
    __tablename__ = "trade_fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), ForeignKey("orders.id"), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    brokerage_paise: Mapped[int] = mapped_column(Integer, default=2000)
    fee_paise: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    order: Mapped["OrderRecord"] = relationship("OrderRecord", back_populates="fills")


class RiskEventRecord(Base):
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_paise: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="INFO")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
