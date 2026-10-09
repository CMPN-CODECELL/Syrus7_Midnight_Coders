import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)   # slug, e.g. "breakout_1pct"
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    timeframe: Mapped[str | None] = mapped_column(String(5))        # "1m", "5m" or None
    status: Mapped[str] = mapped_column(String(20), default="STOPPED")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "strategy_id", name="uq_subscription"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.id"))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    subscribed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskLimit(Base):
    __tablename__ = "risk_limits"
    __table_args__ = (
        CheckConstraint("max_daily_loss_paise > 0", name="ck_risk_loss_positive"),
        CheckConstraint("max_position_size > 0", name="ck_risk_position_positive"),
        CheckConstraint("max_orders_per_minute > 0", name="ck_risk_rate_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.id"), unique=True)
    max_daily_loss_paise: Mapped[int] = mapped_column(BigInteger)
    max_position_size: Mapped[int] = mapped_column(Integer)          # absolute shares per instrument
    max_orders_per_minute: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )