from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field, field_validator

from app.core.enums import Book, BrokerOrderStatus, Exchange, Product, Side, Validity


class OrderPlacementRequest(BaseModel):
    """Payload to place an order through the broker adapter."""

    client_order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    exchange: Exchange = Exchange.NSE
    side: Side
    quantity: int
    price_paise: int = 0  # 0 for market order in RL book
    trigger_price_paise: int = 0
    product: Product = Product.INTRADAY
    book: Book = Book.RL
    validity: Validity = Validity.DAY
    tag: str = ""

    @field_validator("symbol")
    @classmethod
    def _validate_symbol(cls, v: str) -> str:
        s = v.strip().upper()
        if not s:
            raise ValueError("symbol cannot be empty")
        return s

    @field_validator("quantity")
    @classmethod
    def _validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v

    @field_validator("price_paise", "trigger_price_paise")
    @classmethod
    def _validate_price(cls, v: int) -> int:
        if v < 0:
            raise ValueError("price must not be negative")
        return v


class OrderPlacementResponse(BaseModel):
    """Acknowledgement returned immediately from broker on order placement."""

    order_id: str
    client_order_id: str
    broker_status: BrokerOrderStatus
    message: str = ""
    rejection_reason: str | None = None


class OrderCancelRequest(BaseModel):
    """Request to cancel an open order."""

    order_id: str
    client_order_id: str = ""


class OrderCancelResponse(BaseModel):
    """Result of order cancellation."""

    order_id: str
    broker_status: BrokerOrderStatus
    success: bool
    message: str = ""


class OrderModifyRequest(BaseModel):
    """Request to modify quantity or price of a pending order."""

    order_id: str
    quantity: int | None = None
    price_paise: int | None = None
    trigger_price_paise: int | None = None

    @field_validator("quantity")
    @classmethod
    def _check_qty(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("modified quantity must be > 0")
        return v

    @field_validator("price_paise", "trigger_price_paise")
    @classmethod
    def _check_price(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("price cannot be negative")
        return v


class OrderModifyResponse(BaseModel):
    """Result of order modification."""

    order_id: str
    broker_status: BrokerOrderStatus
    success: bool
    message: str = ""


class TradeFill(BaseModel):
    """Execution fill event representing a trade transaction."""

    fill_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    client_order_id: str
    symbol: str
    exchange: Exchange
    side: Side
    quantity: int
    price_paise: int
    brokerage_paise: int = 0
    fee_paise: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BrokerOrder(BaseModel):
    """Full state representation of an order at the broker."""

    order_id: str
    client_order_id: str
    symbol: str
    exchange: Exchange
    side: Side
    product: Product
    book: Book
    validity: Validity
    quantity: int
    price_paise: int
    trigger_price_paise: int = 0
    status: BrokerOrderStatus
    filled_quantity: int = 0
    average_price_paise: int = 0
    rejection_reason: str | None = None
    fills: list[TradeFill] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def remaining_quantity(self) -> int:
        return max(0, self.quantity - self.filled_quantity)


class BrokerPosition(BaseModel):
    """Position summary for a specific symbol/exchange/product."""

    symbol: str
    exchange: Exchange
    product: Product
    net_quantity: int = 0
    buy_quantity: int = 0
    sell_quantity: int = 0
    buy_amount_paise: int = 0
    sell_amount_paise: int = 0
    average_price_paise: int = 0
    realized_pnl_paise: int = 0
