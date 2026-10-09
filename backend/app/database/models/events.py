import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[str | None] = mapped_column(ForeignKey("strategies.id"))   # null = platform-wide
    event_type: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(String(60))
    details: Mapped[dict | None] = mapped_column(JSONB)       # intent, position, limits at decision time
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KillSwitchState(Base):
    """Single row, id always 1. Survives restarts."""

    __tablename__ = "kill_switch_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_by: Mapped[str | None] = mapped_column(String(100))
    last_run_duration_ms: Mapped[int | None] = mapped_column(Integer)
    last_run_result: Mapped[str | None] = mapped_column(String(20))     # VERIFIED / DEGRADED


class SystemEvent(Base):
    __tablename__ = "system_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())