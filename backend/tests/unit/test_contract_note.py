from app.accounting.contract_note import calculate_regulatory_charges, generate_contract_note


def test_calculate_regulatory_charges_buy():
    """Verify Level 2 Published Charges arithmetic for BUY order."""
    qty = 5
    price_paise = 142450  # Rs. 1424.50

    charges = calculate_regulatory_charges(qty, price_paise, side="BUY", product="INTRADAY")

    # Turnover = 5 * 142450 = 712250 paise (Rs. 7122.50)
    assert charges["turnover_paise"] == 712250
    assert charges["turnover_rupees"] == 7122.50

    # Brokerage: Flat Rs. 20.00 (2000 paise)
    assert charges["brokerage_paise"] == 2000
    assert charges["brokerage_rupees"] == 20.00

    # STT: 0 on intraday buy
    assert charges["stt_paise"] == 0

    # Exchange txn fee: 0.00297%
    assert charges["exchange_txn_paise"] == 21

    # SEBI turnover fee: 0.0001% (Rs. 10/Cr, min 1 paise)
    assert charges["sebi_turnover_paise"] == 1

    # Stamp duty: 0.015% on buy
    assert charges["stamp_duty_paise"] == 106

    # GST: 18% on (2000 + 21 + 1) = 363 paise
    assert charges["gst_paise"] == 363

    # Total charges: 2000 + 0 + 21 + 1 + 106 + 363 = 2491 paise (Rs. 24.91)
    assert charges["total_charges_paise"] == 2491
    assert charges["total_charges_rupees"] == 24.91

    # Net payable obligation = turnover + total charges
    assert charges["net_obligation_paise"] == 714741
    assert charges["net_obligation_rupees"] == 7147.41


def test_calculate_regulatory_charges_sell():
    """Verify Level 2 Published Charges arithmetic for SELL order."""
    qty = 4
    price_paise = 152025  # Rs. 1520.25

    charges = calculate_regulatory_charges(qty, price_paise, side="SELL", product="INTRADAY")

    # Turnover = 4 * 152025 = 608100 paise (Rs. 6081.00)
    assert charges["turnover_paise"] == 608100

    # Brokerage: Flat Rs. 20.00
    assert charges["brokerage_paise"] == 2000

    # STT: 0.025% on Intraday SELL = int(608100 * 0.00025) = 152 paise
    assert charges["stt_paise"] == 152
    assert charges["stt_rupees"] == 1.52

    # Stamp duty: 0 on sell
    assert charges["stamp_duty_paise"] == 0

    # Net receivable obligation = turnover - total charges
    assert charges["net_obligation_paise"] == charges["turnover_paise"] - charges["total_charges_paise"]


def test_generate_contract_note():
    """Verify SEBI-compliant digital contract note generation."""
    note = generate_contract_note(
        order_id="ORD-TEST-001",
        symbol="TCS",
        side="BUY",
        quantity=10,
        price_paise=341000,
        strategy_id="strat_breakout",
        strategy_name="Breakout Strategy",
    )

    assert note["orderId"] == "ORD-TEST-001"
    assert note["symbol"] == "TCS"
    assert note["quantity"] == 10
    assert note["clearingHouse"] == "NSE Clearing Limited (NCL)"
    assert note["sebiRegistration"] == "INZ000210021"
    assert note["memberCode"] == "021-HACK342"
    assert note["status"] == "SETTLED"
    assert note["charges"]["brokerage"] == 20.00
    assert note["charges"]["totalChargesPaise"] > 0
    assert note["grossTurnover"] == 34100.00
