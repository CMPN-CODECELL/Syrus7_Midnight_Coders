from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from app.core.enums import RiskReason, Severity


class RiskConfig(BaseModel):
    """Risk constraints enforced per strategy by the platform (L3)."""

    max_daily_loss_paise: int = 50000       # ₹500.00 loss limit
    max_position_size: int = 10             # Maximum units in open position
    max_order_quantity: int = 10            # Maximum units per single order
    max_orders_per_minute: int = 5          # Maximum order rate per 60-second window
    max_runaway_breaches: int = 3           # Auto-halt strategy if rate limit breached 3 times
    include_inflight_orders: bool = True    # Include working/pending orders in position limits
    enforce_pre_trade_sanity: bool = True   # Check tick size, lot size, circuits


class AccountRiskConfig(BaseModel):
    """Global portfolio risk constraints across all strategies combined (L3)."""

    max_account_daily_loss_paise: int = 200000  # ₹2,000.00 total platform loss limit
    max_account_orders_per_minute: int = 30     # Total orders across all strategies per minute
    max_total_open_positions: int = 50          # Max total contracts held across all strategies
    auto_halt_on_account_breach: bool = True


class RiskCheckResult(BaseModel):
    """Outcome of risk gate evaluation on an order intent."""

    passed: bool
    reason: Optional[RiskReason] = None
    message: str = ""
    severity: Severity = Severity.INFO
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskAuditEntry(BaseModel):
    """Historical audit record of evaluated order intent."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    strategy_id: str
    symbol: str
    side: str
    quantity: int
    price_paise: int
    passed: bool
    reason: Optional[RiskReason] = None
    message: str = ""
    severity: Severity = Severity.INFO
