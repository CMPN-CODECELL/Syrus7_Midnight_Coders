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
    account_balance_paise: Mapped[int] = mapped_column(BigInteger, default=10000000)  # Default ₹100,000.00
    subscription_tier: Mapped[str] = mapped_column(String(32), default="FREE")
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    theme: Mapped[str] = mapped_column(String(16), default="light")
    reset_token_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reset_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["PaymentTransaction"]] = relationship(
        "PaymentTransaction", back_populates="user", cascade="all, delete-orphan"
    )
    created_strategies: Mapped[list["StrategyRecord"]] = relationship(
        "StrategyRecord", back_populates="creator"
    )


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    price_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    billing_cycle: Mapped[str] = mapped_column(String(32), default="monthly")  # "monthly", "annual", "one_time"
    features_json: Mapped[str] = mapped_column(Text, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="plan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "strategy_id", name="uq_user_strategy"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False)
    strategy_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("strategies.id"), nullable=True)
    plan_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("subscription_plans.id"), nullable=True)
    plan_tier: Mapped[str] = mapped_column(String(32), default="PRO")
    amount_paid_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")  # "ACTIVE", "CANCELLED", "EXPIRED", "PENDING"
    subscribed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    strategy: Mapped[Optional["StrategyRecord"]] = relationship("StrategyRecord", back_populates="subscriptions")
    plan: Mapped[Optional["SubscriptionPlan"]] = relationship("SubscriptionPlan", back_populates="subscriptions")
    transactions: Mapped[list["PaymentTransaction"]] = relationship("PaymentTransaction", back_populates="subscription")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False)
    subscription_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    payment_method: Mapped[str] = mapped_column(String(32), default="WALLET")  # "UPI", "CREDIT_CARD", "NET_BANKING", "WALLET"
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS")  # "SUCCESS", "PENDING", "FAILED", "REFUNDED"
    transaction_type: Mapped[str] = mapped_column(String(32), default="SUBSCRIPTION_PURCHASE")  # "SUBSCRIPTION_PURCHASE", "WALLET_TOPUP", "PLAN_UPGRADE"
    reference_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    remarks: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship("User", back_populates="transactions")
    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="transactions")


class StrategyRecord(Base):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    creator_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), default="1m")
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    strategy_type: Mapped[str] = mapped_column(String(64), default="TimeBased")
    parameters_json: Mapped[str] = mapped_column(Text, default="{}")
    max_daily_loss_paise: Mapped[int] = mapped_column(Integer, default=50000)
    max_position_size: Mapped[int] = mapped_column(Integer, default=10)
    max_orders_per_minute: Mapped[int] = mapped_column(Integer, default=5)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    price_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    creator: Mapped[Optional["User"]] = relationship("User", back_populates="created_strategies")
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="strategy", cascade="all, delete-orphan"
    )
    orders: Mapped[list["OrderRecord"]] = relationship(
        "OrderRecord", back_populates="strategy", cascade="all, delete-orphan"
    )


class OrderRecord(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # broker order_id or client_order_id
    client_order_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)
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
    user_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)
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
    user_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)
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


class UserActionLog(Base):
    __tablename__ = "user_action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("users.id"), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    strategy_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    price_paise: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    user: Mapped[Optional["User"]] = relationship("User")


