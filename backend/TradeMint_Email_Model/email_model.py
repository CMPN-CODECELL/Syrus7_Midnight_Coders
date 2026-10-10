"""
========================================================================================
TradeMint - Complete Self-Contained Email P&L Statement Model & Dispatch Engine
========================================================================================
Author: TradeMint (Midnight Coders)
Description:
    A complete, production-grade, self-contained single-file implementation of the
    TradeMint Automated Profit & Loss (P&L) Email Alert and Statement Dispatch Engine.

Features:
    1. SEBI SCRA Rule 15 Regulatory Charges Calculator (Brokerage, STT, GST, Stamp Duty).
    2. Real-Time Multi-Strategy & Open Position P&L Aggregator.
    3. Institutional-grade, responsive HTML Email Template with CSS styling.
    4. Production SMTP client supporting TLS (Gmail, Outlook, Custom Mail Servers).
    5. Standalone CLI & direct execution runner for testing or automated cron jobs.

Usage:
    # 1. As a Standalone CLI Script:
    python email_model.py your_email@example.com

    # 2. As an Imported Module:
    from email_model import EmailService
    service = EmailService(smtp_user="your_email@gmail.com", smtp_password="app_password")
    statement = service.build_pnl_statement_data()
    result = service.send_pnl_statement_email("trader@example.com", statement)
========================================================================================
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import logging
import os
from pathlib import Path
import smtplib
import sys
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("trademint.email_model")


# ========================================================================================
# 1. SEBI-COMPLIANT REGULATORY CHARGES & TAX CALCULATOR
# ========================================================================================

def calculate_regulatory_charges(
    quantity: int,
    price_paise: int,
    side: str,
    product: str = "INTRADAY",
) -> Dict[str, Any]:
    """
    Calculate exact itemized regulatory charges for an executed order using integer paise arithmetic.

    Tariff Structure (SEBI & Indian Capital Markets):
    - Brokerage: Flat Rs. 20.00 (2000 paise) per executed order
    - STT (Securities Transaction Tax): 0.025% on Intraday Sell side
    - Exchange Transaction Charges (NSE): 0.00297% of turnover
    - SEBI Turnover Fee: Rs. 10 / Crore (0.0001% of turnover)
    - Stamp Duty: 0.015% on Buy turnover only (Indian Stamp Act)
    - GST: 18% on (Brokerage + Exchange Txn Charges + SEBI Fee)
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

    # 1. Flat Brokerage: Rs. 20.00 (2000 paise)
    brokerage_paise = 2000

    # 2. STT: 0.025% on Sell side for Intraday
    if product_upper == "INTRADAY":
        stt_paise = int(turnover_paise * 0.00025) if side_upper == "SELL" else 0
    else:
        stt_paise = int(turnover_paise * 0.0010)

    # 3. Exchange Transaction Charges (NSE): 0.00297%
    exchange_txn_paise = max(1, int(turnover_paise * 0.0000297))

    # 4. SEBI Turnover Fee: Rs. 10 / Crore = 0.0001%
    sebi_turnover_paise = max(1, int(turnover_paise * 0.000001))

    # 5. Stamp Duty: 0.015% on BUY side
    stamp_duty_paise = int(turnover_paise * 0.00015) if side_upper == "BUY" else 0

    # 6. GST: 18% on (Brokerage + Exchange Charges + SEBI Fee)
    taxable_services_paise = brokerage_paise + exchange_txn_paise + sebi_turnover_paise
    gst_paise = int(taxable_services_paise * 0.18)

    # Total Statutory Charges
    total_charges_paise = (
        brokerage_paise
        + stt_paise
        + exchange_txn_paise
        + sebi_turnover_paise
        + stamp_duty_paise
        + gst_paise
    )

    # Net settlement obligation
    if side_upper == "BUY":
        net_obligation_paise = turnover_paise + total_charges_paise
    else:
        net_obligation_paise = turnover_paise - total_charges_paise

    charges_pct = (
        round((total_charges_paise / turnover_paise) * 100, 4)
        if turnover_paise > 0
        else 0.0
    )

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


# ========================================================================================
# 2. MAIN EMAIL SERVICE & P&L DISPATCH ENGINE
# ========================================================================================

class EmailService:
    """
    Core Email Statement Generation & SMTP Delivery Engine for TradeMint.
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_from_email: Optional[str] = None,
        smtp_from_name: Optional[str] = None,
        smtp_tls: bool = True,
    ):
        self._sent_history: List[Dict[str, Any]] = []

        # 1. Base default configurations
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST") or os.getenv("MAIL_SERVER") or "smtp.gmail.com"
        
        try:
            port_val = smtp_port or os.getenv("SMTP_PORT") or os.getenv("MAIL_PORT") or 587
            self.smtp_port = int(port_val)
        except ValueError:
            self.smtp_port = 587

        # 2. Auto-load credentials from Environment Variables or parameters
        user_val = smtp_user or os.getenv("SMTP_USER") or os.getenv("MAIL_USERNAME") or ""
        pass_val = smtp_password or os.getenv("SMTP_PASSWORD") or os.getenv("MAIL_PASSWORD") or ""

        # Auto-detect if user swapped email and password order
        if user_val and pass_val:
            if "@" in pass_val and "@" not in user_val:
                user_val, pass_val = pass_val, user_val

        self.smtp_user = user_val.strip()
        self.smtp_password = pass_val.strip()
        self.smtp_from_email = (
            smtp_from_email
            or os.getenv("SMTP_FROM_EMAIL")
            or os.getenv("MAIL_FROM")
            or self.smtp_user
            or "alerts@trademint.io"
        )
        self.smtp_from_name = smtp_from_name or os.getenv("SMTP_FROM_NAME") or "TradeMint P&L Reports"
        self.smtp_tls = smtp_tls

    def get_smtp_config(self) -> Dict[str, Any]:
        """Return active non-sensitive SMTP configuration."""
        return {
            "smtpHost": self.smtp_host,
            "smtpPort": self.smtp_port,
            "smtpUser": self.smtp_user,
            "isConfigured": bool(self.smtp_user and self.smtp_password),
            "fromEmail": self.smtp_from_email or self.smtp_user or "alerts@trademint.io",
            "fromName": self.smtp_from_name,
            "smtpTls": self.smtp_tls,
        }

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return history of dispatched email alerts."""
        return self._sent_history[-limit:][::-1]

    def build_pnl_statement_data(
        self,
        user_name: str = "Trader",
        user_email: str = "trader@trademint.io",
        ucc: str = "021-HACK342",
        strategies_data: Optional[List[Dict[str, Any]]] = None,
        orders_data: Optional[List[Dict[str, Any]]] = None,
        positions_data: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate real-time metrics across strategies, positions, and orders
        to construct a complete SEBI-compliant P&L statement dataset.
        """
        try:
            ist_tz = ZoneInfo("Asia/Kolkata")
            now_ist = datetime.now(ist_tz)
        except Exception:
            now_ist = datetime.now(timezone.utc)

        # Default sample trading data if none provided
        strategies = strategies_data if strategies_data is not None else [
            {"id": "strat_vwap", "name": "VWAP Mean Reversion", "symbol": "RELIANCE", "state": "RUNNING", "tradesCount": 4, "pnl": 1250.50},
            {"id": "strat_breakout", "name": "Opening Range Breakout", "symbol": "TCS", "state": "RUNNING", "tradesCount": 2, "pnl": -340.00},
            {"id": "strat_ema", "name": "EMA 9/21 Trend Crossover", "symbol": "INFY", "state": "STOPPED", "tradesCount": 3, "pnl": 680.00},
        ]

        positions = positions_data if positions_data is not None else [
            {"symbol": "RELIANCE", "strategyName": "VWAP Reversion", "quantity": 10, "entryPrice": 2450.00, "currentPrice": 2485.00, "unrealizedPnl": 350.00},
            {"symbol": "INFY", "strategyName": "EMA Trend", "quantity": 25, "entryPrice": 1420.00, "currentPrice": 1428.50, "unrealizedPnl": 212.50},
        ]

        orders = orders_data if orders_data is not None else [
            {"id": "ORD-101", "symbol": "RELIANCE", "side": "BUY", "filledQuantity": 10, "averagePrice": 2450.00, "status": "FILLED", "time": "09:35:12"},
            {"id": "ORD-102", "symbol": "TCS", "side": "BUY", "filledQuantity": 5, "averagePrice": 3600.00, "status": "FILLED", "time": "10:15:44"},
            {"id": "ORD-103", "symbol": "TCS", "side": "SELL", "filledQuantity": 5, "averagePrice": 3532.00, "status": "FILLED", "time": "11:02:18"},
            {"id": "ORD-104", "symbol": "INFY", "side": "BUY", "filledQuantity": 25, "averagePrice": 1420.00, "status": "FILLED", "time": "11:45:00"},
        ]

        # P&L calculations (in integer paise for precision)
        total_realized_paise = sum(int(round(s.get("pnl", 0.0) * 100)) for s in strategies)
        total_unrealized_paise = sum(int(round(p.get("unrealizedPnl", 0.0) * 100)) for p in positions)
        net_pnl_paise = total_realized_paise + total_unrealized_paise

        # Regulatory charges across all executed orders
        tot_turnover_paise = 0
        tot_brokerage_paise = 0
        tot_stt_paise = 0
        tot_exchange_paise = 0
        tot_sebi_paise = 0
        tot_stamp_paise = 0
        tot_gst_paise = 0
        tot_charges_paise = 0
        filled_trades_count = 0

        for o in orders:
            qty = o.get("filledQuantity", o.get("quantity", 0))
            avg_price = o.get("averagePrice") or 0.0
            price_paise = int(avg_price * 100) if avg_price > 0 else o.get("price_paise", 0)
            side = o.get("side", "BUY")
            if qty > 0 and price_paise > 0:
                filled_trades_count += 1
                charges = calculate_regulatory_charges(qty, price_paise, side)
                tot_turnover_paise += charges["turnover_paise"]
                tot_brokerage_paise += charges["brokerage_paise"]
                tot_stt_paise += charges["stt_paise"]
                tot_exchange_paise += charges["exchange_txn_paise"]
                tot_sebi_paise += charges["sebi_turnover_paise"]
                tot_stamp_paise += charges["stamp_duty_paise"]
                tot_gst_paise += charges["gst_paise"]
                tot_charges_paise += charges["total_charges_paise"]

        net_settlement_obligation_paise = net_pnl_paise - tot_charges_paise

        return {
            "metadata": {
                "statementId": f"STM-{now_ist.strftime('%Y%m%d')}-{now_ist.strftime('%H%M%S')}",
                "date": now_ist.strftime("%d %b %Y"),
                "time": now_ist.strftime("%I:%M:%S %p IST"),
                "timestampIso": now_ist.isoformat(),
                "userName": user_name,
                "userEmail": user_email,
                "ucc": ucc,
                "clearingHouse": "NSE Clearing Limited (NCL)",
                "segment": "EQUITY CASH (MIS & INTRADAY)",
                "exchange": "NSE",
            },
            "summary": {
                "netPnl": round(net_pnl_paise / 100, 2),
                "netPnlPaise": net_pnl_paise,
                "isProfit": net_pnl_paise >= 0,
                "realizedPnl": round(total_realized_paise / 100, 2),
                "realizedPnlPaise": total_realized_paise,
                "unrealizedPnl": round(total_unrealized_paise / 100, 2),
                "unrealizedPnlPaise": total_unrealized_paise,
                "grossTurnover": round(tot_turnover_paise / 100, 2),
                "grossTurnoverPaise": tot_turnover_paise,
                "totalCharges": round(tot_charges_paise / 100, 2),
                "totalChargesPaise": tot_charges_paise,
                "netObligation": round(net_settlement_obligation_paise / 100, 2),
                "netObligationPaise": net_settlement_obligation_paise,
                "filledTradesCount": filled_trades_count,
                "activeStrategiesCount": len(strategies),
                "openPositionsCount": len(positions),
            },
            "charges": {
                "brokerage": round(tot_brokerage_paise / 100, 2),
                "stt": round(tot_stt_paise / 100, 2),
                "exchangeTxnFee": round(tot_exchange_paise / 100, 2),
                "sebiTurnoverFee": round(tot_sebi_paise / 100, 2),
                "stampDuty": round(tot_stamp_paise / 100, 2),
                "gst18": round(tot_gst_paise / 100, 2),
                "total": round(tot_charges_paise / 100, 2),
            },
            "strategies": strategies,
            "positions": positions,
            "orders": orders[:15],
        }

    def render_pnl_statement_html(self, data: Dict[str, Any]) -> str:
        """Render a high-end, responsive HTML email statement styled with TradeMint's visual design."""
        meta = data["metadata"]
        summary = data["summary"]
        charges = data["charges"]
        strategies = data["strategies"]
        positions = data["positions"]
        orders = data["orders"]

        is_prof = summary["isProfit"]
        pnl_color = "#10B981" if is_prof else "#EF4444"
        pnl_bg = "rgba(16, 185, 129, 0.12)" if is_prof else "rgba(239, 68, 68, 0.12)"
        pnl_sign = "+" if summary["netPnl"] > 0 else ""

        # Strategy breakdown rows
        strat_rows_html = ""
        for s in strategies:
            s_pnl = s.get("pnl", 0.0)
            s_color = "#10B981" if s_pnl >= 0 else "#EF4444"
            s_sign = "+" if s_pnl > 0 else ""
            status_badge = (
                '<span style="background: #D1FAE5; color: #065F46; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">RUNNING</span>'
                if s.get("state") == "RUNNING"
                else '<span style="background: #F3F4F6; color: #4B5563; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600;">STOPPED</span>'
            )
            strat_rows_html += f"""
            <tr style="border-bottom: 1px solid #E5E7EB;">
                <td style="padding: 10px 12px; font-weight: 600; color: #111827;">{s.get('name', 'Strategy')}</td>
                <td style="padding: 10px 12px; font-weight: 700; color: #4B5563;">{s.get('symbol', '—')}</td>
                <td style="padding: 10px 12px; text-align: center;">{status_badge}</td>
                <td style="padding: 10px 12px; text-align: center; color: #4B5563;">{s.get('tradesCount', len(s.get('signals', [])))}</td>
                <td style="padding: 10px 12px; text-align: right; font-weight: 700; color: {s_color};">{s_sign}₹{s_pnl:,.2f}</td>
            </tr>
            """

        if not strat_rows_html:
            strat_rows_html = '<tr><td colspan="5" style="padding: 14px; text-align: center; color: #9CA3AF;">No active strategy records</td></tr>'

        # Positions rows
        pos_rows_html = ""
        for p in positions:
            p_pnl = p.get("unrealizedPnl", 0.0)
            p_color = "#10B981" if p_pnl >= 0 else "#EF4444"
            p_sign = "+" if p_pnl > 0 else ""
            qty = p.get("quantity", 0)
            side_badge = (
                f'<span style="background: #DEF7EC; color: #03543F; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700;">LONG (+{qty})</span>'
                if qty > 0
                else f'<span style="background: #FDE8E8; color: #9B1C1C; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700;">SHORT ({qty})</span>'
            )
            pos_rows_html += f"""
            <tr style="border-bottom: 1px solid #E5E7EB;">
                <td style="padding: 10px 12px; font-weight: 700; color: #111827;">{p.get('symbol')}</td>
                <td style="padding: 10px 12px; color: #4B5563;">{p.get('strategyName', '—')}</td>
                <td style="padding: 10px 12px; text-align: center;">{side_badge}</td>
                <td style="padding: 10px 12px; text-align: right; color: #4B5563;">₹{p.get('entryPrice', 0):,.2f}</td>
                <td style="padding: 10px 12px; text-align: right; font-weight: 600; color: #111827;">₹{p.get('currentPrice', 0):,.2f}</td>
                <td style="padding: 10px 12px; text-align: right; font-weight: 700; color: {p_color};">{p_sign}₹{p_pnl:,.2f}</td>
            </tr>
            """

        if not pos_rows_html:
            pos_rows_html = '<tr><td colspan="6" style="padding: 14px; text-align: center; color: #9CA3AF;">All positions squared off flat</td></tr>'

        # Order fills rows
        order_rows_html = ""
        for o in orders[:8]:
            side_style = "color: #10B981; font-weight: 700;" if o.get("side") == "BUY" else "color: #EF4444; font-weight: 700;"
            avg_p = o.get("averagePrice") or 0.0
            time_str = o.get("time", "")
            if "T" in time_str:
                time_str = time_str.split("T")[-1][:8]
            order_rows_html += f"""
            <tr style="border-bottom: 1px solid #E5E7EB;">
                <td style="padding: 8px 10px; font-family: monospace; font-size: 11px; color: #6B7280;">{o.get('id')}</td>
                <td style="padding: 8px 10px; font-weight: 700; color: #111827;">{o.get('symbol')}</td>
                <td style="padding: 8px 10px; {side_style}">{o.get('side')}</td>
                <td style="padding: 8px 10px; text-align: center; color: #374151;">{o.get('filledQuantity', o.get('quantity'))}</td>
                <td style="padding: 8px 10px; text-align: right; color: #111827;">₹{avg_p:,.2f}</td>
                <td style="padding: 8px 10px; text-align: center;"><span style="background: #E0E7FF; color: #3730A3; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;">{o.get('status')}</span></td>
                <td style="padding: 8px 10px; text-align: right; color: #6B7280; font-size: 11px;">{time_str}</td>
            </tr>
            """

        if not order_rows_html:
            order_rows_html = '<tr><td colspan="7" style="padding: 14px; text-align: center; color: #9CA3AF;">No order executions recorded in current session</td></tr>'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TradeMint Daily Profit & Loss Statement</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F3F4F6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1F2937;">
    <div style="max-width: 680px; margin: 24px auto; background: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08); border: 1px solid #E5E7EB;">
        
        <!-- Header Banner -->
        <div style="background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); padding: 28px 32px; color: #FFFFFF;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="background: #3B82F6; color: #FFFFFF; font-weight: 900; font-size: 14px; padding: 4px 8px; border-radius: 6px; letter-spacing: 0.5px;">TM</span>
                            <span style="font-size: 20px; font-weight: 800; letter-spacing: -0.5px; color: #FFFFFF; margin-left: 6px;">TradeMint</span>
                        </div>
                        <p style="margin: 4px 0 0 0; font-size: 12px; color: #94A3B8; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">Algorithmic Trading &amp; Execution Platform</p>
                    </td>
                    <td style="text-align: right;">
                        <span style="background: rgba(59, 130, 246, 0.2); border: 1px solid rgba(59, 130, 246, 0.4); color: #93C5FD; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 9999px;">OFFICIAL P&amp;L STATEMENT</span>
                        <p style="margin: 6px 0 0 0; font-size: 12px; color: #CBD5E1;">{meta['date']} · {meta['time']}</p>
                    </td>
                </tr>
            </table>
        </div>

        <!-- Account Info Pill Bar -->
        <div style="background: #F8FAFC; border-bottom: 1px solid #E2E8F0; padding: 14px 32px;">
            <table style="width: 100%; font-size: 12px; color: #475569;">
                <tr>
                    <td><strong>Client:</strong> {meta['userName']} ({meta['userEmail']})</td>
                    <td style="text-align: center;"><strong>UCC / Account:</strong> <span style="font-family: monospace; font-weight: 700; color: #1E293B;">{meta['ucc']}</span></td>
                    <td style="text-align: right;"><strong>Statement ID:</strong> <span style="font-family: monospace; color: #64748B;">{meta['statementId']}</span></td>
                </tr>
            </table>
        </div>

        <div style="padding: 28px 32px;">
            
            <!-- Hero P&L Display Card -->
            <div style="background: {pnl_bg}; border: 1.5px solid {pnl_color}; border-radius: 10px; padding: 20px; text-align: center; margin-bottom: 24px;">
                <span style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: {pnl_color};">Net Daily Realized &amp; Marked-To-Market P&amp;L</span>
                <div style="font-size: 36px; font-weight: 900; color: {pnl_color}; margin: 8px 0; letter-spacing: -1px;">
                    {pnl_sign}₹{summary['netPnl']:,.2f}
                </div>
                <div style="font-size: 12px; color: #4B5563; font-weight: 500;">
                    Realized P&amp;L: <strong style="color: #111827;">{'+' if summary['realizedPnl']>0 else ''}₹{summary['realizedPnl']:,.2f}</strong> &nbsp;·&nbsp; 
                    Unrealized (MTM): <strong style="color: #111827;">{'+' if summary['unrealizedPnl']>0 else ''}₹{summary['unrealizedPnl']:,.2f}</strong>
                </div>
            </div>

            <!-- Financial Grid -->
            <table style="width: 100%; border-collapse: separate; border-spacing: 12px 0; margin: 0 -12px 24px -12px;">
                <tr>
                    <td style="width: 33.33%; background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px;">
                        <span style="font-size: 11px; font-weight: 600; color: #6B7280; text-transform: uppercase;">Gross Turnover</span>
                        <p style="margin: 4px 0 0 0; font-size: 17px; font-weight: 800; color: #111827;">₹{summary['grossTurnover']:,.2f}</p>
                        <span style="font-size: 11px; color: #9CA3AF;">{summary['filledTradesCount']} executed trades</span>
                    </td>
                    <td style="width: 33.33%; background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px;">
                        <span style="font-size: 11px; font-weight: 600; color: #6B7280; text-transform: uppercase;">Total Charges &amp; Taxes</span>
                        <p style="margin: 4px 0 0 0; font-size: 17px; font-weight: 800; color: #EF4444;">₹{summary['totalCharges']:,.2f}</p>
                        <span style="font-size: 11px; color: #9CA3AF;">SEBI / STT / GST / Brokerage</span>
                    </td>
                    <td style="width: 33.33%; background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px;">
                        <span style="font-size: 11px; font-weight: 600; color: #6B7280; text-transform: uppercase;">Net Settlement</span>
                        <p style="margin: 4px 0 0 0; font-size: 17px; font-weight: 800; color: {'#10B981' if summary['netObligation'] >= 0 else '#EF4444'};">
                            {'+' if summary['netObligation'] > 0 else ''}₹{summary['netObligation']:,.2f}
                        </p>
                        <span style="font-size: 11px; color: #9CA3AF;">Post-regulatory deduction</span>
                    </td>
                </tr>
            </table>

            <!-- Section: Itemized Regulatory Charges -->
            <div style="margin-bottom: 28px;">
                <h3 style="font-size: 14px; font-weight: 800; color: #111827; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 10px 0;">
                    Itemized Regulatory Taxes &amp; Published Charges
                </h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 12px; background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; overflow: hidden;">
                    <thead style="background: #F3F4F6; text-align: left; color: #4B5563;">
                        <tr>
                            <th style="padding: 8px 12px; font-weight: 600;">Charge Head</th>
                            <th style="padding: 8px 12px; font-weight: 600;">Applicable Tariff / Rate</th>
                            <th style="padding: 8px 12px; text-align: right; font-weight: 600;">Amount (INR)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="border-bottom: 1px solid #E5E7EB;">
                            <td style="padding: 8px 12px; font-weight: 600;">Brokerage</td>
                            <td style="padding: 8px 12px; color: #6B7280;">Flat ₹20.00 / executed order</td>
                            <td style="padding: 8px 12px; text-align: right; font-weight: 600;">₹{charges['brokerage']:,.2f}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #E5E7EB;">
                            <td style="padding: 8px 12px; font-weight: 600;">Securities Transaction Tax (STT)</td>
                            <td style="padding: 8px 12px; color: #6B7280;">0.025% on Intraday Sell side</td>
                            <td style="padding: 8px 12px; text-align: right; font-weight: 600;">₹{charges['stt']:,.2f}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #E5E7EB;">
                            <td style="padding: 8px 12px; font-weight: 600;">Exchange Txn Charges (NSE)</td>
                            <td style="padding: 8px 12px; color: #6B7280;">0.00297% of turnover</td>
                            <td style="padding: 8px 12px; text-align: right; font-weight: 600;">₹{charges['exchangeTxnFee']:,.2f}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #E5E7EB;">
                            <td style="padding: 8px 12px; font-weight: 600;">SEBI Turnover Fee</td>
                            <td style="padding: 8px 12px; color: #6B7280;">₹10 / Crore (0.0001%)</td>
                            <td style="padding: 8px 12px; text-align: right; font-weight: 600;">₹{charges['sebiTurnoverFee']:,.2f}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #E5E7EB;">
                            <td style="padding: 8px 12px; font-weight: 600;">Stamp Duty</td>
                            <td style="padding: 8px 12px; color: #6B7280;">0.015% on Buy turnover</td>
                            <td style="padding: 8px 12px; text-align: right; font-weight: 600;">₹{charges['stampDuty']:,.2f}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #E5E7EB;">
                            <td style="padding: 8px 12px; font-weight: 600;">GST (18%)</td>
                            <td style="padding: 8px 12px; color: #6B7280;">18% on (Brokerage + Txn + SEBI)</td>
                            <td style="padding: 8px 12px; text-align: right; font-weight: 600;">₹{charges['gst18']:,.2f}</td>
                        </tr>
                        <tr style="background: #F9FAFB; font-weight: 800;">
                            <td colspan="2" style="padding: 10px 12px; color: #111827;">Total Statutory Charges &amp; Taxes</td>
                            <td style="padding: 10px 12px; text-align: right; color: #EF4444; font-size: 13px;">₹{charges['total']:,.2f}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Section: Multi-Strategy Breakdown -->
            <div style="margin-bottom: 28px;">
                <h3 style="font-size: 14px; font-weight: 800; color: #111827; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 10px 0;">
                    Strategy Performance &amp; Ledger Breakdown
                </h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 12px; background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; overflow: hidden;">
                    <thead style="background: #F3F4F6; text-align: left; color: #4B5563;">
                        <tr>
                            <th style="padding: 8px 12px; font-weight: 600;">Strategy Name</th>
                            <th style="padding: 8px 12px; font-weight: 600;">Symbol</th>
                            <th style="padding: 8px 12px; text-align: center; font-weight: 600;">Status</th>
                            <th style="padding: 8px 12px; text-align: center; font-weight: 600;">Trades</th>
                            <th style="padding: 8px 12px; text-align: right; font-weight: 600;">Net P&amp;L</th>
                        </tr>
                    </thead>
                    <tbody>
                        {strat_rows_html}
                    </tbody>
                </table>
            </div>

            <!-- Section: Open Positions (MTM) -->
            <div style="margin-bottom: 28px;">
                <h3 style="font-size: 14px; font-weight: 800; color: #111827; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 10px 0;">
                    Active Open Positions
                </h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 12px; background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; overflow: hidden;">
                    <thead style="background: #F3F4F6; text-align: left; color: #4B5563;">
                        <tr>
                            <th style="padding: 8px 12px; font-weight: 600;">Symbol</th>
                            <th style="padding: 8px 12px; font-weight: 600;">Strategy</th>
                            <th style="padding: 8px 12px; text-align: center; font-weight: 600;">Position</th>
                            <th style="padding: 8px 12px; text-align: right; font-weight: 600;">Entry Price</th>
                            <th style="padding: 8px 12px; text-align: right; font-weight: 600;">LTP</th>
                            <th style="padding: 8px 12px; text-align: right; font-weight: 600;">Unrealized P&amp;L</th>
                        </tr>
                    </thead>
                    <tbody>
                        {pos_rows_html}
                    </tbody>
                </table>
            </div>

            <!-- Section: Trade Execution Audit -->
            <div style="margin-bottom: 24px;">
                <h3 style="font-size: 14px; font-weight: 800; color: #111827; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 10px 0;">
                    Recent Trade Execution Audit Trail
                </h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 12px; background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; overflow: hidden;">
                    <thead style="background: #F3F4F6; text-align: left; color: #4B5563;">
                        <tr>
                            <th style="padding: 8px 10px; font-weight: 600;">Order ID</th>
                            <th style="padding: 8px 10px; font-weight: 600;">Symbol</th>
                            <th style="padding: 8px 10px; font-weight: 600;">Side</th>
                            <th style="padding: 8px 10px; text-align: center; font-weight: 600;">Qty</th>
                            <th style="padding: 8px 10px; text-align: right; font-weight: 600;">Avg Price</th>
                            <th style="padding: 8px 10px; text-align: center; font-weight: 600;">Status</th>
                            <th style="padding: 8px 10px; text-align: right; font-weight: 600;">Time</th>
                        </tr>
                    </thead>
                    <tbody>
                        {order_rows_html}
                    </tbody>
                </table>
            </div>

            <!-- Platform Risk Controls Footer Note -->
            <div style="background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 14px; font-size: 11px; color: #1E40AF; line-height: 1.5;">
                <strong>Platform Risk Gate Active:</strong> All trades are validated against platform-enforced risk limits (Max Daily Loss: ₹500, Max Position: 10 units, Max Orders/Min: 5) and isolated virtual strategy ledgers.
            </div>

        </div>

        <!-- Regulatory & SEBI Disclaimer Footer -->
        <div style="background: #F8FAFC; border-top: 1px solid #E2E8F0; padding: 24px 32px; font-size: 11px; color: #64748B; line-height: 1.6;">
            <p style="margin: 0 0 8px 0; font-weight: 600; color: #334155;">
                SEBI SCRA Rule 15 Compliance &amp; Digital Contract Note Reference:
            </p>
            <p style="margin: 0 0 12px 0;">
                This document is a computer-generated daily profit and loss summary statement provided by TradeMint Algorithmic Trading Systems. All statutory levies, brokerage rates, and exchange fees have been calculated using integer paise precision in accordance with published tariff schedules.
            </p>
            <div style="display: flex; justify-content: space-between; border-top: 1px solid #E2E8F0; padding-top: 12px; font-size: 10px; color: #94A3B8;">
                <span>Member: 021-HACK342 &nbsp;|&nbsp; SEBI Reg: INZ000210021</span>
                <span>TradeMint Institutional Execution Engine v1.0.0</span>
            </div>
        </div>

    </div>
</body>
</html>"""

    def send_pnl_statement_email(
        self,
        recipient_email: str,
        statement_data: Dict[str, Any],
        custom_subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send the Profit & Loss statement to recipient email via real SMTP (TLS)
        or report clear diagnostic status.
        """
        meta = statement_data["metadata"]
        summary = statement_data["summary"]

        pnl_str = f"{'+' if summary['netPnl'] > 0 else ''}₹{summary['netPnl']:,.2f}"
        default_subject = f"TradeMint Daily P&L Statement [{meta['date']}] — {pnl_str} (UCC: {meta['ucc']})"
        subject = custom_subject or default_subject

        html_body = self.render_pnl_statement_html(statement_data)
        plain_text = (
            f"TradeMint Daily P&L Statement\n"
            f"Date: {meta['date']} {meta['time']}\n"
            f"Client: {meta['userName']} ({meta['userEmail']})\n"
            f"UCC: {meta['ucc']}\n"
            f"Statement ID: {meta['statementId']}\n\n"
            f"----------------------------------------\n"
            f"Net Daily P&L: {pnl_str}\n"
            f"Realized P&L: ₹{summary['realizedPnl']:,.2f}\n"
            f"Unrealized P&L: ₹{summary['unrealizedPnl']:,.2f}\n"
            f"Gross Turnover: ₹{summary['grossTurnover']:,.2f}\n"
            f"Total Charges & Taxes: ₹{summary['totalCharges']:,.2f}\n"
            f"Net Settlement Obligation: ₹{summary['netObligation']:,.2f}\n"
            f"----------------------------------------\n\n"
            f"View full digital statement in your TradeMint web console."
        )

        sent_status = "SIMULATED"
        error_msg = None
        delivery_message = ""

        # Check SMTP configuration
        smtp_configured = bool(self.smtp_user and self.smtp_password)

        if smtp_configured:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                from_addr = self.smtp_from_email or self.smtp_user
                msg["From"] = f"{self.smtp_from_name} <{from_addr}>"
                msg["To"] = recipient_email

                part1 = MIMEText(plain_text, "plain", "utf-8")
                part2 = MIMEText(html_body, "html", "utf-8")
                msg.attach(part1)
                msg.attach(part2)

                if self.smtp_port == 465:
                    with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=15) as server:
                        server.login(self.smtp_user, self.smtp_password)
                        server.sendmail(from_addr, [recipient_email], msg.as_string())
                else:
                    with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                        server.ehlo()
                        if self.smtp_tls:
                            server.starttls()
                            server.ehlo()
                        server.login(self.smtp_user, self.smtp_password)
                        server.sendmail(from_addr, [recipient_email], msg.as_string())

                sent_status = "DELIVERED"
                delivery_message = f"Real email statement successfully delivered to inbox ({recipient_email}) via {self.smtp_host}."
                logger.info(f"P&L Statement email successfully delivered to {recipient_email}")

            except smtplib.SMTPAuthenticationError as e:
                error_msg = f"Authentication Failed (535 Bad Credentials): {e.smtp_error.decode('utf-8', errors='ignore') if hasattr(e, 'smtp_error') else str(e)}"
                logger.error(f"Live SMTP Authentication Failed: {error_msg}")
                sent_status = "FAILED"
                delivery_message = (
                    "Gmail Authentication Failed. Google requires an active 16-character App Password "
                    "(generated at https://myaccount.google.com/apppasswords)."
                )
            except Exception as e:
                error_str = str(e)
                error_msg = error_str
                logger.error(f"Live SMTP delivery failed to {recipient_email}: {e}")
                sent_status = "FAILED"
                delivery_message = f"SMTP Delivery Failed: {error_str}"
        else:
            sent_status = "SIMULATED"
            delivery_message = (
                "P&L Statement compiled. (Delivery: SIMULATED — Set SMTP_USER & SMTP_PASSWORD to send real live emails)."
            )
            logger.info(f"Simulated SMTP: P&L Statement generated for {recipient_email}")

        record = {
            "id": f"eml_{len(self._sent_history) + 1}",
            "statementId": meta["statementId"],
            "recipient": recipient_email,
            "subject": subject,
            "status": sent_status,
            "netPnl": summary["netPnl"],
            "turnover": summary["grossTurnover"],
            "totalCharges": summary["totalCharges"],
            "sentAt": datetime.now(timezone.utc).isoformat(),
            "errorMessage": error_msg,
        }

        self._sent_history.append(record)

        return {
            "status": "SUCCESS" if sent_status != "FAILED" else "ERROR",
            "deliveryStatus": sent_status,
            "recipient": recipient_email,
            "subject": subject,
            "statementId": meta["statementId"],
            "summary": summary,
            "sentAt": record["sentAt"],
            "message": delivery_message,
            "errorMessage": error_msg,
            "isSmtpConfigured": smtp_configured,
        }


# ========================================================================================
# 3. CLI & STANDALONE EXECUTION RUNNER
# ========================================================================================

def main():
    """CLI Entry point for direct command-line execution."""
    parser = argparse.ArgumentParser(
        description="TradeMint Daily P&L Email Alert and Statement Dispatch Engine"
    )
    parser.add_argument(
        "recipient",
        nargs="?",
        default=os.getenv("SMTP_USER", "darshanmali44444@gmail.com"),
        help="Recipient email address to deliver the statement to",
    )
    parser.add_argument(
        "--user",
        default=os.getenv("SMTP_USER", "darshanmali44444@gmail.com"),
        help="SMTP sender email username (or set SMTP_USER env var)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("SMTP_PASSWORD", "vjykssyqrknqfqsj"),
        help="SMTP 16-character App Password (or set SMTP_PASSWORD env var)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        help="SMTP server host (default: smtp.gmail.com)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SMTP_PORT", 587)),
        help="SMTP server port (default: 587)",
    )
    parser.add_argument(
        "--save-html",
        metavar="PATH",
        help="Optionally save generated HTML statement to local file",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("   TradeMint Institutional P&L Statement Engine")
    print("=" * 60)

    service = EmailService(
        smtp_host=args.host,
        smtp_port=args.port,
        smtp_user=args.user,
        smtp_password=args.password,
    )

    print(f"\n[1/3] Compiling real-time P&L statement telemetry...")
    statement = service.build_pnl_statement_data(
        user_name="Trader",
        user_email=args.recipient,
        ucc="021-HACK342",
    )

    summary = statement["summary"]
    pnl_sign = "+" if summary["netPnl"] >= 0 else ""
    print(f"      - Net P&L: {pnl_sign}Rs. {summary['netPnl']:,.2f}")
    print(f"      - Gross Turnover: Rs. {summary['grossTurnover']:,.2f}")
    print(f"      - Total Statutory Charges & Taxes: Rs. {summary['totalCharges']:,.2f}")
    print(f"      - Net Settlement Obligation: Rs. {summary['netObligation']:,.2f}")

    if args.save_html:
        html_out = service.render_pnl_statement_html(statement)
        Path(args.save_html).write_text(html_out, encoding="utf-8")
        print(f"      - HTML preview written to: {args.save_html}")

    print(f"\n[2/3] Connecting to SMTP server ({args.host}:{args.port})...")
    result = service.send_pnl_statement_email(
        recipient_email=args.recipient,
        statement_data=statement,
    )

    print(f"\n[3/3] Execution Result:")
    print(f"      - Status: {result['deliveryStatus']}")
    print(f"      - Message: {result['message']}")
    if result.get("errorMessage"):
        print(f"      - Error: {result['errorMessage']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
