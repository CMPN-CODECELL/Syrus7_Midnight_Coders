from datetime import datetime, timezone
from typing import Any, Optional


def calculate_regulatory_charges(
    quantity: int,
    price_paise: int,
    side: str,
    product: str = "INTRADAY",
) -> dict[str, Any]:
    """Calculate exact itemized regulatory charges for an executed order using integer paise arithmetic.
    
    Published Charges Table:
    1. Brokerage: Flat Rs. 20.00 (2000 paise) per executed order
    2. STT (Securities Transaction Tax):
       - Intraday Equity: 0.025% on Sell side only
       - Delivery Equity: 0.10% on Buy and Sell
    3. Exchange Transaction Charges: 0.00297% of turnover (NSE)
    4. SEBI Turnover Fee: 0.0001% of turnover (Rs. 10 / Crore, min 1 paise)
    5. Stamp Duty: 0.015% on Buy turnover only (Indian Stamp Act)
    6. GST: 18% on (Brokerage + Exchange Txn Charges + SEBI Fee)
    """
    if quantity <= 0 or price_paise <= 0:
        return {
            "turnover_paise": 0,
            "brokerage_paise": 0,
            "stt_paise": 0,
            "exchange_txn_paise": 0,
            "sebi_turnover_paise": 0,
            "stamp_duty_paise": 0,
            "gst_paise": 0,
            "total_charges_paise": 0,
            "net_obligation_paise": 0,
            "charges_percentage": 0.0,
        }

    turnover_paise = quantity * price_paise
    side_upper = side.upper()
    product_upper = product.upper()

    # 1. Flat Brokerage: Rs. 20.00
    brokerage_paise = 2000

    # 2. STT
    if product_upper == "INTRADAY":
        stt_paise = int(turnover_paise * 0.00025) if side_upper == "SELL" else 0
    else:
        stt_paise = int(turnover_paise * 0.0010)

    # 3. Exchange Transaction Charges: 0.00297%
    exchange_txn_paise = max(1, int(turnover_paise * 0.0000297))

    # 4. SEBI Turnover Fee: Rs. 10 / Crore = 0.0001%
    sebi_turnover_paise = max(1, int(turnover_paise * 0.000001))

    # 5. Stamp Duty: 0.015% on BUY side
    stamp_duty_paise = int(turnover_paise * 0.00015) if side_upper == "BUY" else 0

    # 6. GST: 18% on (Brokerage + Exchange Charges + SEBI Fee)
    taxable_services_paise = brokerage_paise + exchange_txn_paise + sebi_turnover_paise
    gst_paise = int(taxable_services_paise * 0.18)

    # Total Charges
    total_charges_paise = (
        brokerage_paise
        + stt_paise
        + exchange_txn_paise
        + sebi_turnover_paise
        + stamp_duty_paise
        + gst_paise
    )

    # Net settlement obligation (Debit if BUY, Credit if SELL)
    if side_upper == "BUY":
        net_obligation_paise = turnover_paise + total_charges_paise
    else:
        net_obligation_paise = turnover_paise - total_charges_paise

    charges_pct = round((total_charges_paise / turnover_paise) * 100, 4) if turnover_paise > 0 else 0.0

    return {
        "turnover_paise": turnover_paise,
        "turnover_rupees": round(turnover_paise / 100, 2),
        "brokerage_paise": brokerage_paise,
        "brokerage_rupees": round(brokerage_paise / 100, 2),
        "stt_paise": stt_paise,
        "stt_rupees": round(stt_paise / 100, 2),
        "exchange_txn_paise": exchange_txn_paise,
        "exchange_txn_rupees": round(exchange_txn_paise / 100, 2),
        "sebi_turnover_paise": sebi_turnover_paise,
        "sebi_turnover_rupees": round(sebi_turnover_paise / 100, 2),
        "stamp_duty_paise": stamp_duty_paise,
        "stamp_duty_rupees": round(stamp_duty_paise / 100, 2),
        "gst_paise": gst_paise,
        "gst_rupees": round(gst_paise / 100, 2),
        "total_charges_paise": total_charges_paise,
        "total_charges_rupees": round(total_charges_paise / 100, 2),
        "net_obligation_paise": net_obligation_paise,
        "net_obligation_rupees": round(net_obligation_paise / 100, 2),
        "charges_percentage": charges_pct,
    }


def generate_contract_note(
    order_id: str,
    symbol: str,
    side: str,
    quantity: int,
    price_paise: int,
    strategy_id: str = "strat_time",
    strategy_name: str = "TimeBased Momentum",
    timestamp: Optional[datetime] = None,
    order_type: str = "MARKET",
) -> dict[str, Any]:
    """Generate a formal SEBI-compliant digital contract note payload for an executed order."""
    now = timestamp or datetime.now(timezone.utc)
    charges = calculate_regulatory_charges(quantity, price_paise, side)

    note_id = f"CN-{now.strftime('%Y%m%d')}-{order_id.replace('ord_', '').replace('ORD-', '')}"

    return {
        "noteId": note_id,
        "orderId": order_id,
        "tradeDate": now.strftime("%Y-%m-%d"),
        "settlementDate": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        "clearingHouse": "NSE Clearing Limited (NCL)",
        "sebiRegistration": "INZ000210021",
        "memberCode": "021-HACK342",
        "ucc": "021-ALGO-PRO",
        "strategyId": strategy_id,
        "strategyName": strategy_name,
        "symbol": symbol.upper(),
        "exchange": "NSE",
        "segment": "EQUITY CASH (MIS)",
        "side": side.upper(),
        "orderType": order_type.upper(),
        "quantity": quantity,
        "averagePrice": round(price_paise / 100, 2),
        "grossTurnover": charges["turnover_rupees"],
        "grossTurnoverPaise": charges["turnover_paise"],
        "charges": {
            "brokerage": charges["brokerage_rupees"],
            "brokeragePaise": charges["brokerage_paise"],
            "stt": charges["stt_rupees"],
            "sttPaise": charges["stt_paise"],
            "exchangeTxnFee": charges["exchange_txn_rupees"],
            "exchangeTxnFeePaise": charges["exchange_txn_paise"],
            "sebiTurnoverFee": charges["sebi_turnover_rupees"],
            "sebiTurnoverFeePaise": charges["sebi_turnover_paise"],
            "stampDuty": charges["stamp_duty_rupees"],
            "stampDutyPaise": charges["stamp_duty_paise"],
            "gst18": charges["gst_rupees"],
            "gst18Paise": charges["gst_paise"],
            "totalCharges": charges["total_charges_rupees"],
            "totalChargesPaise": charges["total_charges_paise"],
        },
        "netObligation": charges["net_obligation_rupees"],
        "netObligationPaise": charges["net_obligation_paise"],
        "chargesPercentage": charges["charges_percentage"],
        "status": "SETTLED",
    }
