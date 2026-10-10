import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib
from typing import Optional

from app.core.config import get_settings
from app.services.email_model import EmailService, calculate_regulatory_charges

logger = logging.getLogger(__name__)

_email_service_instance: Optional[EmailService] = None


def get_email_service(force_refresh: bool = False) -> EmailService:
    """Get or initialize singleton EmailService instance using application settings."""
    global _email_service_instance
    settings = get_settings()

    mail_user = (settings.mail_username or "").strip()
    mail_pass = (settings.mail_password or "").strip()

    # Auto-swap if email and password were provided in inverted fields
    if "@" in mail_pass and "@" not in mail_user:
        mail_user, mail_pass = mail_pass, mail_user

    # Fallback to known working Google App Password if needed
    if mail_user == "darshanmali44444@gmail.com" and mail_pass in ("mqqbrwraxzbzxnqa", "", None):
        mail_pass = "vjykssyqrknqfqsj"

    if (
        _email_service_instance is None
        or force_refresh
        or _email_service_instance.smtp_user != mail_user
        or _email_service_instance.smtp_password != mail_pass
    ):
        _email_service_instance = EmailService(
            smtp_host=settings.smtp_server,
            smtp_port=settings.smtp_port,
            smtp_user=mail_user,
            smtp_password=mail_pass,
            smtp_from_email=mail_user or "darshanmali44444@gmail.com",
            smtp_from_name="TradeMint P&L Reports",
        )
    return _email_service_instance


def send_email_sync(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> bool:
    """Send an email using SMTP (Gmail TLS)."""
    settings = get_settings()
    username = (settings.mail_username or "").strip()
    password = (settings.mail_password or "").strip()
    smtp_server = settings.smtp_server
    smtp_port = settings.smtp_port

    if "@" in password and "@" not in username:
        username, password = password, username
    if username == "darshanmali44444@gmail.com" and password in ("mqqbrwraxzbzxnqa", "", None):
        password = "vjykssyqrknqfqsj"


    if not username or not password:
        logger.warning("[EMAIL] Mail credentials not set. Skipping email send.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"TradeShield Platform <{username}>"
        msg["To"] = to_email

        if text_content:
            msg.attach(MIMEText(text_content, "plain"))

        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(username, password)
            server.sendmail(username, [to_email], msg.as_string())

        logger.info(f"[EMAIL] Successfully sent email '{subject}' to {to_email}")
        return True
    except Exception as e:
        logger.error(f"[EMAIL ERROR] Failed to send email to {to_email}: {e}")
        return False


async def send_email_async(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
) -> bool:
    """Asynchronously send an email in background thread."""
    return await asyncio.to_thread(send_email_sync, to_email, subject, html_content, text_content)


async def send_pnl_statement_async(
    recipient_email: str,
    statement_data: dict,
    custom_subject: Optional[str] = None,
) -> dict:
    """Asynchronously dispatch P&L statement email via EmailService."""
    svc = get_email_service()
    return await asyncio.to_thread(svc.send_pnl_statement_email, recipient_email, statement_data, custom_subject)


def generate_payment_receipt_html(
    user_name: str,
    payment_id: str,
    order_id: str,
    amount_inr: float,
    purpose: str,
    reference_id: str,
) -> str:
    """Generate professional HTML email invoice for Razorpay transaction."""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; color: #1e293b; margin: 0; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); border: 1px solid #e2e8f0; }}
        .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 30px 25px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }}
        .header p {{ margin: 6px 0 0 0; font-size: 13px; color: #94a3b8; }}
        .content {{ padding: 30px 25px; }}
        .badge {{ display: inline-block; background: #dcfce7; color: #15803d; font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 9999px; margin-bottom: 20px; }}
        .details-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .details-table td {{ padding: 12px 0; border-bottom: 1px solid #f1f5f9; font-size: 14px; }}
        .details-table tr:last-child td {{ border-bottom: none; }}
        .label {{ color: #64748b; font-weight: 500; }}
        .value {{ font-weight: 600; text-align: right; color: #0f172a; }}
        .total-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin-top: 25px; text-align: center; }}
        .total-box div {{ font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }}
        .total-box span {{ font-size: 28px; font-weight: 800; color: #16a34a; display: block; margin-top: 4px; }}
        .footer {{ background: #f8fafc; padding: 20px 25px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TradeShield 021 Platform</h1>
            <p>Official Payment Receipt & Tax Invoice</p>
        </div>
        <div class="content">
            <div class="badge">✓ Payment Verified via Razorpay</div>
            <p>Hi <strong>{user_name}</strong>,</p>
            <p>Thank you for your payment! Your transaction has been successfully processed and credited to your TradeShield account.</p>

            <table class="details-table">
                <tr>
                    <td class="label">Purpose / Product</td>
                    <td class="value">{purpose}</td>
                </tr>
                <tr>
                    <td class="label">Razorpay Payment ID</td>
                    <td class="value"><code>{payment_id}</code></td>
                </tr>
                <tr>
                    <td class="label">Razorpay Order ID</td>
                    <td class="value"><code>{order_id}</code></td>
                </tr>
                <tr>
                    <td class="label">Reference Invoice #</td>
                    <td class="value"><code>{reference_id}</code></td>
                </tr>
                <tr>
                    <td class="label">Payment Gateway</td>
                    <td class="value">Razorpay (UPI / Card / NetBanking)</td>
                </tr>
            </table>

            <div class="total-box">
                <div>Amount Paid</div>
                <span>₹{amount_inr:.2f}</span>
            </div>
        </div>
        <div class="footer">
            <p>© 2026 TradeShield — Syrus Hackathon 021 Algo Trading Platform</p>
            <p>If you have any questions, contact support at <code>demo@trademint.in</code></p>
        </div>
    </div>
</body>
</html>
"""
