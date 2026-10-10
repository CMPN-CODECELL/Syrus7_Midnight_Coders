import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services.email_model import EmailService, calculate_regulatory_charges


def test_regulatory_charges_calculator():
    """Verify SEBI-compliant itemized charges arithmetic."""
    # 1. Buy 10 RELIANCE @ Rs. 2450 (245,000 paise)
    buy_charges = calculate_regulatory_charges(quantity=10, price_paise=245000, side="BUY")
    assert buy_charges["turnover_paise"] == 2450000  # Rs. 24,500.00
    assert buy_charges["brokerage_paise"] == 2000    # Rs. 20.00 flat
    assert buy_charges["stamp_duty_paise"] > 0       # Stamp duty on BUY
    assert buy_charges["stt_paise"] == 0             # No intraday STT on BUY

    # 2. Sell 10 RELIANCE @ Rs. 2480 (248,000 paise)
    sell_charges = calculate_regulatory_charges(quantity=10, price_paise=248000, side="SELL")
    assert sell_charges["stt_paise"] > 0             # STT applied on SELL
    assert sell_charges["stamp_duty_paise"] == 0     # No stamp duty on SELL
    assert sell_charges["total_charges_paise"] > 2000


def test_email_service_statement_generation():
    """Verify HTML rendering and P&L aggregation."""
    svc = EmailService()
    data = svc.build_pnl_statement_data(
        user_name="Evaluator Judge",
        user_email="judge@trademint.io",
        ucc="021-HACK342",
    )
    assert "metadata" in data
    assert "summary" in data
    assert "charges" in data
    assert data["metadata"]["ucc"] == "021-HACK342"

    html = svc.render_pnl_statement_html(data)
    assert "TradeMint" in html
    assert "021-HACK342" in html
    assert data["metadata"]["statementId"] in html


@pytest.mark.asyncio
async def test_email_api_endpoints():
    """Verify /api/email/pnl-statement and /api/email/smtp-status endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Check SMTP status
        smtp_res = await ac.get("/api/email/smtp-status")
        assert smtp_res.status_code == 200
        smtp_data = smtp_res.json()
        assert "smtpHost" in smtp_data
        assert "isConfigured" in smtp_data

        # 2. Dispatch P&L statement
        send_res = await ac.post(
            "/api/email/pnl-statement",
            json={"recipient_email": "test_judge@example.com"},
        )
        assert send_res.status_code == 200
        res_data = send_res.json()
        assert res_data["status"] in ("SUCCESS", "ERROR")
        assert "deliveryStatus" in res_data
        assert "statementId" in res_data

        # 3. Check email history
        hist_res = await ac.get("/api/email/history")
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert len(history) >= 1
        assert history[0]["statementId"] == res_data["statementId"]
