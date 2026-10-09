from abc import ABC, abstractmethod

from app.broker.models import (
    BrokerOrder,
    BrokerPosition,
    OrderCancelRequest,
    OrderCancelResponse,
    OrderModifyRequest,
    OrderModifyResponse,
    OrderPlacementRequest,
    OrderPlacementResponse,
)


class BrokerInterface(ABC):
    """Abstract interface defining the contract for all broker adapters (Mock, 021 API, etc.)."""

    @abstractmethod
    async def place_order(self, request: OrderPlacementRequest) -> OrderPlacementResponse:
        """Place a new order at the broker."""
        pass

    @abstractmethod
    async def cancel_order(self, request: OrderCancelRequest) -> OrderCancelResponse:
        """Cancel an open order."""
        pass

    @abstractmethod
    async def modify_order(self, request: OrderModifyRequest) -> OrderModifyResponse:
        """Modify price or quantity of a pending order."""
        pass

    @abstractmethod
    async def get_order(self, order_id: str) -> BrokerOrder | None:
        """Retrieve the current state of a single order by ID."""
        pass

    @abstractmethod
    async def get_orders(self) -> list[BrokerOrder]:
        """Fetch all orders placed in the current session."""
        pass

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Fetch current broker positions and realized P&L."""
        pass

    @abstractmethod
    async def cancel_all_orders(self) -> list[OrderCancelResponse]:
        """Emergency action: cancel all active/pending orders."""
        pass
