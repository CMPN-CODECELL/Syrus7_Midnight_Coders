from enum import Enum


# ---------- Trading vocabulary (names used in 021 requests) ----------

class Exchange(str, Enum):
    NSE = "NSE"
    NSEFO = "NSEFO"
    BSE = "BSE"
    BSEFO = "BSEFO"


# Names that appear in responses and in the instruments file
EXCHANGE_TO_INSTRUMENT_NAME = {
    Exchange.NSE: "NSECM",
    Exchange.NSEFO: "NSEFO",
    Exchange.BSE: "BSEEQ",
    Exchange.BSEFO: "BSEEQD",
}

# Numeric codes used by the websockets (3 and 6 are index data, not tradable)
EXCHANGE_WS_CODE = {
    Exchange.NSE: 1,
    Exchange.NSEFO: 2,
    Exchange.BSE: 4,
    Exchange.BSEFO: 5,
}


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Product(str, Enum):
    INTRADAY = "INTRADAY"
    CNC = "CNC"
    NRML = "NRML"


class Book(str, Enum):
    RL = "RL"   # regular limit (price 0 = market)
    SL = "SL"   # stop-loss, needs a trigger


class Validity(str, Enum):
    DAY = "Day"
    IOC = "IOC"


class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"


# ---------- Our own order lifecycle ----------

class OrderStatus(str, Enum):
    CREATED = "CREATED"                    # saved locally, not sent yet
    SUBMITTED = "SUBMITTED"                # broker accepted it
    UNKNOWN = "UNKNOWN"                    # send was ambiguous (timeout, 500, 503); reconcile
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in (OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED)


class RejectionSource(str, Enum):
    RISK = "RISK"        # our platform said no
    BROKER = "BROKER"    # 021 said no


# ---------- What the 021 API reports (kept apart from our own) ----------

class BrokerOrderStatus(str, Enum):
    RECEIVED = "Received"
    PLACED = "Placed"
    PENDING = "Pending"
    EXECUTED = "Executed"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"
    FROZEN = "Frozen"
    SENT_FOR_MODIFICATION = "SentForModification"
    SENT_FOR_CANCELLATION = "SentForCancellation"
    ACCEPTED_FOR_AMO = "AcceptedForAMO"


class BrokerErrorKind(str, Enum):
    """How a failed broker call should be treated. The adapter classifies it."""
    RISK_REJECTED = "RISK_REJECTED"    # HTTP 500 with a risk reason: order definitely not placed
    SERVER_ERROR = "SERVER_ERROR"      # HTTP 500 or 503 without a reason: outcome unknown
    TIMEOUT = "TIMEOUT"                # no answer: outcome unknown
    RATE_LIMITED = "RATE_LIMITED"      # slow down and retry
    SAFE_MODE = "SAFE_MODE"            # HTTP 422: blocked by the exchange simulator
    AUTH_EXPIRED = "AUTH_EXPIRED"      # HTTP 401: log in again
    BAD_REQUEST = "BAD_REQUEST"        # HTTP 400: our bug


# ---------- Strategies, risk, kill switch ----------

class StrategyStatus(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    HALTED = "HALTED"


class RiskReason(str, Enum):
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    MAX_POSITION_SIZE_EXCEEDED = "MAX_POSITION_SIZE_EXCEEDED"
    MAX_ORDERS_PER_MINUTE_EXCEEDED = "MAX_ORDERS_PER_MINUTE_EXCEEDED"
    MAX_DAILY_LOSS_EXCEEDED = "MAX_DAILY_LOSS_EXCEEDED"
    RISK_CONFIG_MISSING = "RISK_CONFIG_MISSING"
    SYSTEM_RECONCILING = "SYSTEM_RECONCILING"
    SYMBOL_HALTED = "SYMBOL_HALTED"
    RISK_INTERNAL_ERROR = "RISK_INTERNAL_ERROR"
    # Cheap checks we run before the broker does
    TICK_SIZE_INVALID = "TICK_SIZE_INVALID"
    LOT_SIZE_INVALID = "LOT_SIZE_INVALID"
    PRICE_OUTSIDE_CIRCUIT = "PRICE_OUTSIDE_CIRCUIT"
    FREEZE_QUANTITY_EXCEEDED = "FREEZE_QUANTITY_EXCEEDED"


class KillSwitchResult(str, Enum):
    VERIFIED = "VERIFIED"
    DEGRADED = "DEGRADED"


class Severity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"