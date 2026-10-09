from typing import Any
from app.core.enums import BrokerErrorKind


class BrokerError(Exception):
    """Base exception for all broker communication and execution failures."""

    def __init__(
        self,
        message: str,
        kind: BrokerErrorKind,
        status_code: int | None = None,
        raw_response: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.status_code = status_code
        self.raw_response = raw_response

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(kind={self.kind.value}, "
            f"status_code={self.status_code}, message={self.message!r})"
        )


class BrokerRiskRejectedError(BrokerError):
    """Raised when broker/exchange rejects the order due to risk checks (e.g., HTTP 500 with risk reason)."""

    def __init__(self, message: str, status_code: int | None = 500, raw_response: Any = None) -> None:
        super().__init__(
            message=message,
            kind=BrokerErrorKind.RISK_REJECTED,
            status_code=status_code,
            raw_response=raw_response,
        )


class BrokerServerError(BrokerError):
    """Raised on broker internal 500/503 errors without risk reasons (outcome ambiguous)."""

    def __init__(self, message: str, status_code: int | None = 500, raw_response: Any = None) -> None:
        super().__init__(
            message=message,
            kind=BrokerErrorKind.SERVER_ERROR,
            status_code=status_code,
            raw_response=raw_response,
        )


class BrokerTimeoutError(BrokerError):
    """Raised when a request to the broker times out without receiving a response."""

    def __init__(self, message: str = "Broker request timed out", raw_response: Any = None) -> None:
        super().__init__(
            message=message,
            kind=BrokerErrorKind.TIMEOUT,
            status_code=None,
            raw_response=raw_response,
        )


class BrokerRateLimitError(BrokerError):
    """Raised when the broker rate limit is hit (HTTP 429)."""

    def __init__(self, message: str, status_code: int | None = 429, raw_response: Any = None) -> None:
        super().__init__(
            message=message,
            kind=BrokerErrorKind.RATE_LIMITED,
            status_code=status_code,
            raw_response=raw_response,
        )


class BrokerSafeModeError(BrokerError):
    """Raised when safe mode or exchange simulator blocks an action (HTTP 422)."""

    def __init__(self, message: str, status_code: int | None = 422, raw_response: Any = None) -> None:
        super().__init__(
            message=message,
            kind=BrokerErrorKind.SAFE_MODE,
            status_code=status_code,
            raw_response=raw_response,
        )


class BrokerAuthExpiredError(BrokerError):
    """Raised when the session/token is expired or credentials invalid (HTTP 401)."""

    def __init__(self, message: str, status_code: int | None = 401, raw_response: Any = None) -> None:
        super().__init__(
            message=message,
            kind=BrokerErrorKind.AUTH_EXPIRED,
            status_code=status_code,
            raw_response=raw_response,
        )


class BrokerBadRequestError(BrokerError):
    """Raised when the request format or parameters are rejected (HTTP 400)."""

    def __init__(self, message: str, status_code: int | None = 400, raw_response: Any = None) -> None:
        super().__init__(
            message=message,
            kind=BrokerErrorKind.BAD_REQUEST,
            status_code=status_code,
            raw_response=raw_response,
        )
