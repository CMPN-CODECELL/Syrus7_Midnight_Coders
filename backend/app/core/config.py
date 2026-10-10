from datetime import time
from decimal import Decimal
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), extra="ignore")

    # Infrastructure
    database_url: str = "postgresql+asyncpg://tradeshield:tradeshield@localhost:5434/tradeshield"
    jwt_secret: str = "change-me"
    broker_mode: Literal["mock", "api021"] = "mock"

    # 021 broker (only needed when broker_mode == "api021")
    broker_base_url: str = "https://devapi.021.trade/api/developer-api/v1"
    api_ucc: str = ""
    api_password: str = ""

    # Trading day (D16)
    trading_day_tz: str = "Asia/Kolkata"
    session_start: time = time(9, 15)

    # Risk policy (D5, D7)
    daily_loss_mode: Literal["net", "realized"] = "net"
    rate_window_seconds: int = 60

    # Kill switch and broker timeouts
    kill_switch_timeout_seconds: int = 10
    broker_call_timeout_seconds: int = 3

    # Charges (D12). Prices and P&L are integer paise (D1).
    brokerage_per_fill_paise: int = 2000
    fee_percent_of_notional: Decimal = Decimal("0.0003")

    # Mock broker and market
    mock_fill_latency_ms: int = 0
    symbols: str = "RELIANCE,TCS,INFY"

    # Razorpay Gateway & Email Notifications
    razorpay_key_id: str = "rzp_test_SFd7WR1rAUaPUA"
    razorpay_key_secret: str = "AHqEU8tXJJ1sbjLzZgiGNNsz"
    mail_username: str = "mqqbrwraxzbzxnqa"
    mail_password: str = "darshanmali44444@gmail.com"
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587

    @field_validator("trading_day_tz")
    @classmethod
    def _valid_timezone(cls, v: str) -> str:
        ZoneInfo(v)  # raises if the name is not a real timezone
        return v

    @field_validator(
        "rate_window_seconds",
        "kill_switch_timeout_seconds",
        "broker_call_timeout_seconds",
    )
    @classmethod
    def _positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be greater than 0")
        return v

    @field_validator("brokerage_per_fill_paise")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("must not be negative")
        return v

    @field_validator("jwt_secret")
    @classmethod
    def _secret_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("JWT_SECRET must not be empty")
        return v

    @field_validator("broker_base_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @model_validator(mode="after")
    def _real_broker_needs_credentials(self) -> "Settings":
        return self

    @property
    def symbol_list(self) -> list[str]:
        return [s.strip().upper() for s in self.symbols.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()