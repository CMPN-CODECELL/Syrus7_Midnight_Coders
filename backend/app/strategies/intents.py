from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field, field_validator

from app.core.enums import Book, Exchange, Product, Side, Validity


class OrderIntent(BaseModel):
    """Represents a strategy's intent to place an order before risk validation."""

    intent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str
    symbol: str
    exchange: Exchange = Exchange.NSE
    side: Side
    quantity: int
    price_paise: int = 0  # 0 indicates market order in RL book
    trigger_price_paise: int = 0  # Used for stop-loss orders in SL book
    product: Product = Product.INTRADAY
    book: Book = Book.RL
    validity: Validity = Validity.DAY
    tag: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, v: str) -> str:
        symbol = v.strip().upper()
        if not symbol:
            raise ValueError("symbol must not be empty")
        return symbol

    @field_validator("quantity")
    @classmethod
    def _validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be strictly positive")
        return v

    @field_validator("price_paise", "trigger_price_paise")
    @classmethod
    def _validate_price(cls, v: int) -> int:
        if v < 0:
            raise ValueError("price must not be negative")
        return v
