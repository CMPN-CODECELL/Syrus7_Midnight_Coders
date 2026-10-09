import pytest
from app.broker import (
    BrokerRiskRejectedError,
    BrokerServerError,
    BrokerTimeoutError,
    Mock021,
    OrderCancelRequest,
    OrderModifyRequest,
    OrderPlacementRequest,
)
from app.core.enums import BrokerOrderStatus, Exchange, Product, Side


@pytest.fixture
def mock_broker():
    broker = Mock021()
    broker.reset()
    return broker


@pytest.mark.asyncio
async def test_instant_full_fill_buy_limit(mock_broker: Mock021):
    req = OrderPlacementRequest(
        symbol="RELIANCE",
        exchange=Exchange.NSE,
        side=Side.BUY,
        quantity=10,
        price_paise=290000,  # ₹2900.00
        product=Product.INTRADAY,
    )
    res = await mock_broker.place_order(req)

    assert res.broker_status == BrokerOrderStatus.EXECUTED
    assert res.order_id.startswith("mock_ord_")
    assert res.client_order_id == req.client_order_id

    # Verify order state
    order = await mock_broker.get_order(res.order_id)
    assert order is not None
    assert order.status == BrokerOrderStatus.EXECUTED
    assert order.filled_quantity == 10
    assert order.remaining_quantity == 0
    assert len(order.fills) == 1

    fill = order.fills[0]
    assert fill.quantity == 10
    assert fill.price_paise == 290000
    assert fill.brokerage_paise == 2000  # ₹20 = 2000 paise
    # Notional = 10 * 290000 = 2,900,000 paise. Fee = 0.0003 * 2,900,000 = 870 paise
    assert fill.fee_paise == 870

    # Verify positions
    positions = await mock_broker.get_positions()
    assert len(positions) == 1
    pos = positions[0]
    assert pos.symbol == "RELIANCE"
    assert pos.net_quantity == 10
    assert pos.average_price_paise == 290000


@pytest.mark.asyncio
async def test_market_order_uses_reference_price(mock_broker: Mock021):
    req = OrderPlacementRequest(
        symbol="TCS",
        exchange=Exchange.NSE,
        side=Side.BUY,
        quantity=5,
        price_paise=0,  # Market order
    )
    res = await mock_broker.place_order(req)
    assert res.broker_status == BrokerOrderStatus.EXECUTED

    order = await mock_broker.get_order(res.order_id)
    assert order is not None
    assert order.average_price_paise == 420000  # Default TCS reference price


@pytest.mark.asyncio
async def test_rejection_response(mock_broker: Mock021):
    mock_broker.set_rejection(enabled=True, reason="Insufficient margin", raise_exception=False)

    req = OrderPlacementRequest(
        symbol="INFY",
        side=Side.BUY,
        quantity=50,
        price_paise=185000,
    )
    res = await mock_broker.place_order(req)

    assert res.broker_status == BrokerOrderStatus.REJECTED
    assert res.rejection_reason == "Insufficient margin"
    assert "rejected" in res.message.lower()

    order = await mock_broker.get_order(res.order_id)
    assert order is not None
    assert order.status == BrokerOrderStatus.REJECTED
    assert order.filled_quantity == 0


@pytest.mark.asyncio
async def test_rejection_with_500_exception(mock_broker: Mock021):
    mock_broker.set_rejection(enabled=True, reason="Risk check rejected", raise_exception=True)

    req = OrderPlacementRequest(
        symbol="INFY",
        side=Side.BUY,
        quantity=10,
        price_paise=185000,
    )
    with pytest.raises(BrokerRiskRejectedError) as exc_info:
        await mock_broker.place_order(req)

    assert exc_info.value.status_code == 500
    assert "Risk check rejected" in exc_info.value.message


@pytest.mark.asyncio
async def test_partial_fill(mock_broker: Mock021):
    mock_broker.set_partial_fill_ratio(0.4)  # 40% fill

    req = OrderPlacementRequest(
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=10,
        price_paise=290000,
    )
    res = await mock_broker.place_order(req)

    assert res.broker_status == BrokerOrderStatus.PENDING
    order = await mock_broker.get_order(res.order_id)
    assert order is not None
    assert order.status == BrokerOrderStatus.PENDING
    assert order.filled_quantity == 4
    assert order.remaining_quantity == 6


@pytest.mark.asyncio
async def test_timeout_simulation(mock_broker: Mock021):
    mock_broker.simulate_timeout("Connection to exchange dropped")

    req = OrderPlacementRequest(
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=1,
        price_paise=290000,
    )
    with pytest.raises(BrokerTimeoutError) as exc:
        await mock_broker.place_order(req)

    assert "Connection to exchange dropped" in str(exc.value)


@pytest.mark.asyncio
async def test_server_error_500_simulation(mock_broker: Mock021):
    mock_broker.simulate_server_error(status_code=500, message="OMS Internal Gateway Error")

    req = OrderPlacementRequest(
        symbol="RELIANCE",
        side=Side.BUY,
        quantity=1,
        price_paise=290000,
    )
    with pytest.raises(BrokerServerError) as exc:
        await mock_broker.place_order(req)

    assert exc.value.status_code == 500
    assert "OMS Internal Gateway Error" in str(exc.value)


@pytest.mark.asyncio
async def test_cancel_order(mock_broker: Mock021):
    # Partial fill leaves the order pending
    mock_broker.set_partial_fill_ratio(0.5)
    res = await mock_broker.place_order(
        OrderPlacementRequest(symbol="TCS", side=Side.BUY, quantity=10, price_paise=400000)
    )
    assert res.broker_status == BrokerOrderStatus.PENDING

    # Cancel remaining pending order
    cancel_res = await mock_broker.cancel_order(OrderCancelRequest(order_id=res.order_id))
    assert cancel_res.success is True
    assert cancel_res.broker_status == BrokerOrderStatus.CANCELLED

    order = await mock_broker.get_order(res.order_id)
    assert order.status == BrokerOrderStatus.CANCELLED

    # Cancelling again should fail
    cancel_again = await mock_broker.cancel_order(OrderCancelRequest(order_id=res.order_id))
    assert cancel_again.success is False


@pytest.mark.asyncio
async def test_modify_order(mock_broker: Mock021):
    mock_broker.set_partial_fill_ratio(0.3)
    res = await mock_broker.place_order(
        OrderPlacementRequest(symbol="INFY", side=Side.BUY, quantity=10, price_paise=180000)
    )

    # Modify price and quantity
    mod_res = await mock_broker.modify_order(
        OrderModifyRequest(order_id=res.order_id, quantity=15, price_paise=182000)
    )
    assert mod_res.success is True

    order = await mock_broker.get_order(res.order_id)
    assert order.quantity == 15
    assert order.price_paise == 182000


@pytest.mark.asyncio
async def test_round_trip_realized_pnl(mock_broker: Mock021):
    # Buy 10 @ 290000
    await mock_broker.place_order(
        OrderPlacementRequest(symbol="RELIANCE", side=Side.BUY, quantity=10, price_paise=290000)
    )
    # Sell 10 @ 295000 (profit: 5000 paise per share * 10 = 50,000 paise = ₹500)
    await mock_broker.place_order(
        OrderPlacementRequest(symbol="RELIANCE", side=Side.SELL, quantity=10, price_paise=295000)
    )

    positions = await mock_broker.get_positions()
    assert len(positions) == 1
    pos = positions[0]
    assert pos.net_quantity == 0
    assert pos.realized_pnl_paise == 50000
