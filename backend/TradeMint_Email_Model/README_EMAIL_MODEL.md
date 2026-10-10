# TradeMint - Automated Email P&L Statement Engine

A completely self-contained implementation of the **TradeMint Daily Profit & Loss (P&L) Statement & Email Alert Engine**, compliant with SEBI SCRA Rule 15.

---

## 📁 File Structure & Integration
- **Standalone Model**: `email_model.py` — A 100% standalone Python script with zero third-party dependencies (uses only standard Python libraries: `smtplib`, `email`, `datetime`, `json`, `argparse`).
- **Core Integration**: Integrated directly into `backend/app/services/email_model.py` and bridged to the FastAPI backend via `backend/app/services/email_service.py`.
- **REST API Endpoint**: Exposed via `POST /api/reports/email-statement`.
- **UI Terminal Integration**: Interactive frontend modal at `frontend/src/components/tm/EmailStatementModal.tsx` accessible directly from the Top Navbar and Dashboard banner.

---

## ⚡ Quick Test (Command Line)

To test sending a real email statement immediately via CLI:

```bash
python email_model.py your_email@gmail.com
```

### With Custom Credentials:
```bash
python email_model.py recipient@gmail.com --user your_email@gmail.com --password your_16_digit_app_password
```

---

## 💻 Programmatic Usage

```python
from app.services.email_model import EmailService

# Initialize the service (loads credentials from environment or parameters)
service = EmailService(
    smtp_user="darshanmali44444@gmail.com",
    smtp_password="your_16_digit_app_password"  # Google App Password
)

# 1. Compile P&L and regulatory taxes (supports optional live account_data from dashboard)
statement_data = service.build_pnl_statement_data(
    user_name="Trader",
    user_email="client@example.com",
    ucc="021-HACK342"
)

# 2. Dispatch real email with modern HTML design
result = service.send_pnl_statement_email(
    recipient_email="client@example.com",
    statement_data=statement_data
)

print(result["deliveryStatus"])  # DELIVERED
```

---

## 📜 Regulatory Features (SEBI Rule 15 SCRA)
- **Itemized Charges**: Brokerage (₹20 flat per order), STT (0.025% on sell), Exchange Txn Charges, SEBI Turnover Fees, Stamp Duty, and 18% GST.
- **Integer Paise Arithmetic**: Eliminates float precision anomalies across accounting ledgers.
- **Dual Content**: Responsive dark-themed HTML table with clean plaintext fallback.
- **Zero Dependencies**: Requires only standard Python 3.11+ runtimes.
