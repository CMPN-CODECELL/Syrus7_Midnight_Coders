# TradeShield — 021 Algo Trading Platform

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6.0-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tests](https://img.shields.io/badge/Tests-80%20Passed%20(100%25)-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)]()

> **Built for the 021 Trade Hackathon (Syrus 2026) — Team Midnight Coders**  
> An institutional-grade algorithmic trading platform built on the 021 Developer APIs where **risk limits strictly hold even when strategies malfunction, crash, or send rogue orders**.

---

## 📸 Platform Preview

| Live Trading Terminal & Dashboard | Risk Management & Strategy Studio |
| :---: | :---: |
| ![TradeMint Terminal](backend/trademint%20ss.png) | ![TradeMint Controls](backend/trademint%20ss1.png) |

---

## 📑 Table of Contents
1. [Key Features & Highlights](#-key-features--highlights)
2. [Architecture Levels (L1 — L4)](#-architecture-levels-l1--l4)
3. [TradeMint Automated Email Statement Engine](#-trademint-automated-email-statement-engine)
4. [Razorpay 3-Tier Subscription Engine](#-razorpay-3-tier-subscription-engine)
5. [Broker Resilience & Query-Before-Retry](#-broker-resilience--query-before-retry)
6. [Strategy Customization & User Control](#-strategy-customization--user-control)
7. [Real-Life Institutional Kill Switch](#-real-life-institutional-kill-switch)
8. [Statutory Charges & SEBI Contract Notes](#-statutory-charges--sebi-contract-notes)
9. [Judge Failure & Chaos Scenarios (80 Passing Tests)](#-judge-failure--chaos-scenarios-80-passing-tests)
10. [Installation & How to Use](#-installation--how-to-use)
    - [Prerequisites](#prerequisites)
    - [Step 1: Clone the Repository](#step-1-clone-the-repository)
    - [Step 2: Backend Setup](#step-2-backend-setup)
    - [Step 3: Frontend Setup](#step-3-frontend-setup)
    - [Step 4: Demo Credentials & UI Walkthrough](#step-4-demo-credentials--ui-walkthrough)
11. [Automated Verification & CLI Scripts](#-automated-verification--cli-scripts)
12. [API Endpoints Overview](#-api-endpoints-overview)
13. [Project Directory Structure](#-project-directory-structure)

---

## 🚀 Key Features & Highlights

- 🛡️ **Level 3 Independent Risk Gate**: Strategy code *never* speaks directly to the broker. Every order intent passes through an independent Risk Engine enforcing max daily loss, max position limits, and rolling rate limiters.
- 📧 **TradeMint Automated Email Statement Engine**: Real-time dispatched P&L statements compliant with SEBI SCRA Rule 15. Zero external dependencies, pure standard library TLS engine with integer paise financial precision, dual HTML/plaintext formatting, and a 1-click UI modal.
- 💳 **Razorpay 3-Tier Subscription Paywall**: Integrated payment flow with 3 access tiers (`u_test_all`, `u_test_three`, `u_test_none`), dynamic HMAC-SHA256 signature verification, and granular strategy execution gating.
- 🔄 **Query-Before-Retry Broker Engine**: Handles broker network timeouts (HTTP 504 / connection drop) safely by querying broker order state (`GET /orders/{id}`) before re-submitting, completely preventing duplicate executions.
- 🎛️ **Free User Customization Studio**: Full UI control over strategy parameters—tweak SMA periods, breakout thresholds, take-profit %, stop-loss %, trailing stop %, trade directions (`LONG_ONLY`, `SHORT_ONLY`, `BOTH`), and manual trade placement.
- 🛑 **Real-Life Institutional Kill Switch**:
  - **4 Granular Halt Scopes**: `GLOBAL` (liquidate all), `CANCEL_ONLY` (soft halt: cancel pending orders but preserve open positions to avoid panic slippage), `STRATEGY` (quarantine single rogue strategy), and `SYMBOL` (freeze single instrument).
  - **Pre-emptive Auto-Trip Rules**: Auto-halts if cumulative portfolio MTM loss breaches the threshold or on consecutive broker rejections.
  - **Cooling-Off Lockout**: Anti-revenge trading timer (e.g., 5, 15, 30 min lockouts).
  - **Forensic Audit History**: Immutable post-mortem incident log with sub-10s SLA verification guarantee.
- 📜 **SEBI Rule 15 SCRA Digital Contract Notes**: Automated itemized breakdown of Brokerage, STT, Exchange Txn Fees, SEBI Turnover Fees, Stamp Duty, and 18% GST using exact integer paise arithmetic.
- 🔄 **L2 Mid-Trade State Recovery**: Auto-reconciles broker positions vs. internal strategy ledgers on server restart; detects position drift and orphaned orders.
- ⚡ **High-Speed Binary Tick Parser & Candle Aggregator**: Decodes raw 021 binary feed packets (TC 1, 2, 3 Full Mode) and aggregates tick-by-tick data into 1-minute and 5-minute OHLCV candles without volume leaks.
- 💾 **Self-Healing Zero-Config Database**: Instant boot with local SQLite (`tradeshield.db`) or enterprise PostgreSQL (via Docker or Cloud Neon/Supabase) without manual setup scripts.

---

## 🏛️ Architecture Levels (L1 — L4)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (React + Vite)                           │
│  Live Trading Terminal │ Strategy Customizer │ Risk Controls │ Email Reports │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ REST / WebSocket
┌──────────────────────────────────────▼───────────────────────────────────────┐
│                           BACKEND (FastAPI + AsyncIO)                        │
│                                                                              │
│  ┌────────────────────────┐                  ┌─────────────────────────────┐ │
│  │   L1: Market Data      │                  │   L4: Multi-Strategy Engine │ │
│  │ - Binary Tick Decoder  │ ──Candles/LTP──► │ - strat_time (RELIANCE)     │ │
│  │ - Candle Aggregator    │                  │ - strat_breakout (INFY)     │ │
│  │   (1m & 5m OHLCV)      │                  │ - strat_ma (TCS)            │ │
│  └────────────────────────┘                  │ - Custom User Strategies    │ │
│                                              └──────────────┬──────────────┘ │
│                                                             │ Order Intents  │
│                                              ┌──────────────▼──────────────┐ │
│                                              │   L3: Independent Risk Gate │ │
│                                              │ - Max Daily Loss Monitor    │ │
│                                              │ - Max Position Size Checks  │ │
│                                              │ - Token-Bucket Rate Limiter │ │
│                                              │ - Multi-Scope Kill Switch   │ │
│                                              └──────────────┬──────────────┘ │
│                                                             │ Approved Only  │
│                                              ┌──────────────▼──────────────┐ │
│                                              │   L2: Execution & Recovery  │ │
│                                              │ - Order Lifecycle Engine    │ │
│                                              │ - State Reconciler & Drift  │ │
│                                              │ - Query-Before-Retry Loop   │ │
│                                              │ - Contract Note Calculator  │ │
│                                              └──────────────┬──────────────┘ │
│                                                             │                │
│  ┌────────────────────────┐                  ┌──────────────▼──────────────┐ │
│  │  Services & Auxiliary  │                  │   021 Broker (Live / Mock)  │ │
│  │ - SEBI Email Engine    │                  │   UCC: HACK342              │ │
│  │ - Razorpay Paywall     │                  └─────────────────────────────┘ │
│  │ - SQLite / Postgres DB │                                                  │
│  └────────────────────────┘                                                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **Level 1 (Data Layer)**: Handles real-time binary market data feed, decodes ticks into depth bids/asks, and streams 1-minute and 5-minute candlesticks.
- **Level 2 (Execution & Recovery)**: Manages order states (`CREATED` $\rightarrow$ `PLACED` $\rightarrow$ `PARTIALLY_FILLED` $\rightarrow$ `EXECUTED`), handles partial fill math, recovers mid-trade state on process crashes, and implements Query-Before-Retry on network timeouts.
- **Level 3 (Risk Enforcement)**: Sits as a firewall between strategies and the broker. Strictly blocks unauthorized sizes, throttles rapid orders via token bucket, and halts runaway algos.
- **Level 4 (Isolated Ledgers)**: Manages concurrent strategies on a single trading account. Supports opposing trades (e.g. +5 Long and -5 Short on `RELIANCE` simultaneously), maintaining distinct P&L ledgers while the broker account sits flat.

---

## 📧 TradeMint Automated Email Statement Engine

TradeShield incorporates an automated **Profit & Loss Statement & Regulatory Email Engine** compliant with SEBI SCRA Rule 15:

- **100% Zero-Dependency Standalone Script**: `backend/app/services/email_model.py` runs with pure standard library modules (`smtplib`, `email`, `datetime`, `json`, `argparse`). Can be invoked standalone via CLI or through backend services.
- **Live TLS/STARTTLS Dispatch**: Robust socket connection handling supporting Port 587 (STARTTLS) and Port 465 (SSL), with fallback and connection re-establishment.
- **Real-Time UI Parity**: The email statement pulls exact runtime portfolio telemetry directly from `get_account_summary()` (`netPnl`, `accountValue`, `availableBalance`, `riskStatus`), guaranteeing 100% parity between the dashboard and dispatched statements.
- **Interactive Web Modal**: Traders can trigger statements on demand via the **"Email P&L"** button on the dashboard or navbar using `EmailStatementModal.tsx`, specifying recipient email or selecting quick presets.
- **Itemized Statutory Tax Computation**: Automatically itemizes Gross P&L, Brokerage (₹20/order), STT, Exchange Turnover Fees, SEBI Charges, Stamp Duty, and 18% GST down to integer paise precision.

### Standalone CLI Execution:
```bash
cd backend
python app/services/email_model.py recipient@example.com
```

### REST API Trigger:
```bash
curl -X POST http://localhost:8001/api/reports/email-statement \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"recipient_email": "trader@example.com"}'
```

---

## 💳 Razorpay 3-Tier Subscription Engine

The platform features a multi-tier subscription engine with Razorpay integration and server-side HMAC-SHA256 signature verification:

| User Tier | Test Account | Strategy Execution Privileges | Real-Time Broker Access |
| :--- | :--- | :--- | :--- |
| **Tier 1 (Pro Unlimited)** | `u_test_all` | Full execution access to **all algorithmic strategies** | ✅ Live 021 Broker execution |
| **Tier 2 (Standard Trio)** | `u_test_three` | Restricted to **3 designated strategies** (`strat_time`, `strat_breakout`, `strat_ma`) | ✅ Live 021 Broker execution |
| **Tier 3 (Observer / Free)** | `u_test_none` | Paper / Simulation access only. Live order placement blocked by paywall gate | ❌ Simulation only |

- **Security Verification**: Webhook callbacks require `X-Razorpay-Signature` validation via HMAC-SHA256 using `RAZORPAY_KEY_SECRET`.
- **Dynamic Tier Gating**: Strategy execution requests are intercepted and verified against the user's active subscription tier before reaching the Level 3 Risk Gate.

---

## 🔄 Broker Resilience & Query-Before-Retry

In high-frequency algorithmic trading, network timeouts (such as HTTP 504 Gateway Timeout or TCP socket disconnects) present a dangerous race condition: *Was the order received and executed by the broker before the connection dropped, or did it fail?*

TradeShield eliminates duplicate order execution risks through an institutional **Query-Before-Retry** cycle:

1. **Broker Timeout Interception**: When a broker order submission times out or returns HTTP 504, the engine catches the exception without blindly resending the order.
2. **Order Reconciliation Query**: The engine queries the broker's order state via `GET /orders/{order_id}` or checks the account order book.
3. **Smart State Resolution**:
   - If the order exists on the broker: The engine links the internal state to the broker order ID and transitions to `PLACED`/`EXECUTED`.
   - If the order does not exist: The engine retries submission with exponential backoff.
4. **Token-Bucket Rate Limiter**: Strictly enforces broker rate limits (5 requests/sec sustained, burst capacity of 10), preventing broker 429 HTTP errors and account throttling.

---

## ⚙️ Strategy Customization & User Control

The platform provides an interactive **Strategy Studio** where users can freely tailor strategy rules and risk budgets:

| Strategy | Base Target | User-Configurable Parameters |
| :--- | :--- | :--- |
| **Time-Based (`strat_time`)** | `RELIANCE` | Entry Time (`HH:MM`), Exit Time (`HH:MM`), Order Quantity, Tick-level Take Profit %, Tick-level Stop Loss % |
| **Breakout (`strat_breakout`)** | `INFY` | Breakout Threshold % (e.g. 0.5% – 3.0%), Direction Mode (`BOTH`, `LONG_ONLY`, `SHORT_ONLY`), Take Profit %, Stop Loss %, Trailing Stop % |
| **Moving Average (`strat_ma`)** | `TCS` | Fast SMA Period (2 – 20), Slow SMA Period (10 – 50), Candle Timeframe (`1m` / `5m`), Take Profit %, Stop Loss % |
| **Custom Strategies** | Any Symbol | Custom rules deployed dynamically via the **Create Strategy Wizard** |

### User Control Features:
- 🎚️ **Live Parameter Tuning Modal**: Adjust parameters in real-time with visual sliders without restarting the server.
- ⚡ **Manual Quick-Trade**: Execute discretionary manual orders assigned directly to a strategy's isolated ledger.
- 🔄 **One-Click Strategy Square-Off**: Immediately flatten an individual strategy's position without disturbing other running algorithms.
- 📡 **Live Signal Stream**: Real-time signal event log capturing entry triggers, MA crossover points, and exit reasons.

---

## 🛑 Real-Life Institutional Kill Switch

TradeShield's Kill Switch mirrors institutional HFT desk risk management:

### 1. Multi-Scope Halts
- **`GLOBAL` (Full Platform Lockdown)**: Cancels all open/working orders, liquidates all positions via Market/IOC orders, disables all algos, and verifies flat exposure within SLA.
- **`CANCEL_ONLY` (Soft Halt / In-flight Flush)**: Instantly cancels all resting working orders to stop further exposure, but **leaves active positions intact** to avoid unnecessary market slippage during panic volatility.
- **`STRATEGY` (Surgical Quarantine)**: Immediately stops and squares off a single malfunctioning strategy, freeing capital while leaving healthy strategies running.
- **`SYMBOL` (Instrument Freeze)**: Cancels working orders and liquidates positions strictly for a single scrip (e.g., `RELIANCE` during flash drops).

### 2. Pre-emptive Auto-Trip Rules (`AutoKillRules`)
- **Cumulative Drawdown Breach**: Auto-trips if portfolio unrealized MTM loss exceeds configured threshold (e.g. ₹2,500.00).
- **Consecutive Rejection Tripwire**: Auto-engages if the broker rejects 3 consecutive orders (preventing runaway submission loops).
- **Runtime Configuration**: Auto-trip rules can be updated on the fly from the **Risk Controls** tab.

### 3. Cooling-Off Lockout Timer
- Enforces an automated cooldown lockout (e.g., 5, 15, or 30 minutes) to eliminate **emotional revenge trading**. New orders are blocked until the timer expires or an operator explicitly disengages the switch.

### 4. Forensic Incident Audit Trail
- Every activation creates an immutable audit record containing Incident ID, UTC timestamp, trigger source (`MANUAL_USER`, `RISK_GATE`, `AUTO_TRIP`), scope, reason, elapsed execution time, and **$\le$ 10s SLA verification guarantee**.

---

## 💰 Statutory Charges & SEBI Contract Notes

All financial transactions use **integer paise arithmetic** (1 INR = 100 paise) to eliminate floating-point rounding errors:

$$\text{Net P\&L} = \text{Gross P\&L} - (\text{Brokerage} + \text{Statutory Charges})$$

| Charge Component | Statutory Rate / Base | Implementation in Code |
| :--- | :--- | :--- |
| **Brokerage** | Flat ₹20.00 (2,000 paise) per executed fill | `backend/app/accounting/contract_note.py` |
| **STT** | 0.025% on Intraday SELL turnover (0% on BUY) | `int(turnover_paise * 0.00025)` |
| **Exchange Txn Charges** | 0.00297% of trade turnover (NSE Equity) | `max(1, int(turnover_paise * 0.0000297))` |
| **SEBI Turnover Fee** | ₹10.00 / Crore (0.0001% of turnover) | `max(1, int(turnover_paise * 0.000001))` |
| **Stamp Duty** | 0.015% on BUY side turnover only | `int(turnover_paise * 0.00015)` |
| **GST** | 18.00% on (Brokerage + Txn Charges + SEBI Fee) | `int((brokerage + exchange + sebi) * 0.18)` |
| **Electronic Contract Notes** | SEBI Rule 15 SCRA Digital Contract Notes | Rendered via `ContractNoteModal.tsx` |

---

## 🧪 Judge Failure & Chaos Scenarios (80 Passing Tests)

The platform includes an automated **Resilience Test Suite** verifying that risk gates hold across extreme edge cases:

| Scenario | Level | Injected Failure | Expected Behavior | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Partial Fill** | **L2** | Broker fills 4 out of 10 units | Strategy updates position to +4; remaining 6 stays in working registry. No drift. | **PASS** |
| **Crash Recovery** | **L2/L3** | Server killed mid-trade | Startup reconciler audits broker vs strategy state; restores in-flight tracking. | **PASS** |
| **Runaway Strategy** | **L3** | Rogue algo fires 15 orders in 1 sec | First 5 approved; subsequent orders throttled; strategy auto-halted. | **PASS** |
| **Risk Gate Breach** | **L3** | Order placed for 25 units (> 10 limit) | Platform Risk Engine rejects order before broker call. | **PASS** |
| **Broker Outage** | **L2** | Broker returns HTTP 503 / Timeout | Gracefully handled; order marked REJECTED/FAILED; state integrity preserved. | **PASS** |
| **Opposing Trades** | **L4** | +5 Long & -5 Short on `RELIANCE` | Both strategies track independent positions & P&L; broker net position is 0. | **PASS** |
| **Broker Timeout 504** | **L2** | Broker Gateway Timeout during placement | Query-Before-Retry queries `/orders/{id}` to prevent duplicate order placement. | **PASS** |
| **Token-Bucket Throttle** | **L3** | High burst order transmission | Token bucket rate-limiter throttles requests at 5 req/sec (burst 10). | **PASS** |
| **Email P&L Model** | **Aux** | Live SMTP/TLS statement compilation | Validates exact integer-paise math, HTML formatting, and TLS socket delivery. | **PASS** |
| **Subscription Paywall** | **Aux** | Tiered access check (`u_test_all`/`none`) | Gated execution verified with webhook signature HMAC-SHA256 validation. | **PASS** |

---

## 🛠️ Installation & How to Use

### Prerequisites
- **Python**: Version `3.11`, `3.12`, or `3.14` installed.
- **Node.js**: Version `18.x` or `20.x`+ installed with `npm`.
- **Git**: Installed.

---

### Step 1: Clone the Repository
```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/<REPO_NAME>.git
cd Syrus7_Midnight_Coders
```

---

### Step 2: Backend Setup
Open a terminal in the root folder:

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Provision & Seed Database Manually with Integrity Audit:
python scripts/setup_database.py
# Note: Even if you skip this command, the server automatically self-initializes
# and seeds demo data on its first boot!

# Start the FastAPI server on port 8001
python -m uvicorn app.main:app --port 8001 --reload
```

> **💾 Database Provisioning Options (Self-Healing Architecture)**:
> 1. **Zero-Config SQLite (Default / Recommended for Clone & Viva)**:
>    - Requires **zero installations or Docker**.
>    - On boot, the app automatically creates `backend/tradeshield.db` and seeds demo accounts, strategies, and subscriptions.
> 2. **Local PostgreSQL via Docker**:
>    - Run `docker compose up -d postgres` (listening on `localhost:5434`).
>    - Point `DATABASE_URL=postgresql+asyncpg://tradeshield:tradeshield@localhost:5434/tradeshield` in `.env`.
> 3. **Free Hosted Cloud PostgreSQL (Neon / Supabase / Railway)**:
>    - Simply paste your hosted PostgreSQL URL in `.env` with `?ssl=require`.
> 4. **Reset Database Anytime**:
>    - Run `python backend/scripts/setup_database.py --reset` to clear and re-seed clean judge data.

The backend is now live:
- 📖 **Interactive Swagger UI**: [http://localhost:8001/docs](http://localhost:8001/docs)
- 🩺 **Health Check**: [http://localhost:8001/health](http://localhost:8001/health)

---

### Step 3: Frontend Setup
Open a **new separate terminal** in the root folder:

```bash
# Navigate to frontend directory
cd frontend

# Install npm dependencies
npm install

# Start Vite development server
npm run dev
```

The web terminal will start at:
- 🌐 **Web Application**: [http://localhost:8081](http://localhost:8081) *(or port indicated by Vite)*

---

### Step 4: Demo Credentials & UI Walkthrough

#### 🔑 Logging In
- Navigate to [http://localhost:8081/login](http://localhost:8081/login)
- **Email**: `demo@trademint.in`
- **Password**: `demo1234`
*(Or click "Sign Up" to register an account)*

#### 🖥️ Exploring the Platform
1. **Trading Dashboard (`/dashboard`)**:
   - Live portfolio value, gross vs. net P&L with friction deductions.
   - Interactive candlestick charts with volume bars.
   - Click the **"Email P&L"** button in the top action bar to open the Email Statement modal and send a live SEBI Rule 15 statement to your email.
2. **Strategy Management (`/strategies`)**:
   - View, start, stop, and pause strategies.
   - Click **"Customize Parameters"** on any card to launch the Strategy Customizer Modal.
   - Click **"Square Off"** to flatten an individual strategy on demand.
   - Click **"+ Deploy Strategy"** to create a custom algorithmic instance.
3. **Order Book & Positions (`/orders`, `/positions`)**:
   - Inspect order lifecycles (`SUBMITTED` $\rightarrow$ `EXECUTED`).
   - Click the **"Contract Note"** button on any filled order to view its official SEBI-compliant digital contract note with itemized statutory charges.
4. **Risk Controls & Kill Switch (`/risk-controls`)**:
   - **Emergency Kill Switch Button**: Click the top-bar button to open the Multi-Scope Halt Modal. Select from `GLOBAL`, `CANCEL_ONLY`, `STRATEGY`, or `SYMBOL`, choose a reason, and set a cooldown lockout timer.
   - **Auto-Trip Rules Studio**: Configure automated MTM drawdown limits and max broker rejection tripwires.
   - **Interactive Chaos & Resilience Lab**: Run live simulation scenarios (Partial Fill, Crash Recovery, Runaway Loop, Opposing Positions) with real-time telemetry.
   - **Forensic Incident Audit Log**: Review immutable history of all triggered halts.
5. **Settings & Subscriptions (`/settings`)**:
   - View profile, broker connection details, and 3-Tier subscription plans.

---

## 🧪 Automated Verification & CLI Scripts

### 1. Run Complete Pytest Suite (80 Tests Passing - 100%)
```bash
cd backend
.venv\Scripts\python -m pytest
```
*Expected Output: `80 passed in ~25s`*

### 2. Run the Chaos & Failure CLI Demo
Demonstrates all failure modes and recovery loops directly in your terminal:
```bash
cd backend
.venv\Scripts\python scripts/demo_chaos_scenarios.py
```

### 3. Run Strategy Demonstration Engine
```bash
cd backend
.venv\Scripts\python scripts/demo_strategies.py
```

### 4. Run Live 021 WebSocket Algo Trading
Connects to live 021 broker WebSocket feeds, ticks binary packets, builds candles, and executes strategies:
```bash
cd backend
.venv\Scripts\python -u scripts/run_live_trading.py
```

### 5. Run Standalone Email P&L Statement Engine
Dispatches a live statement via SMTP TLS:
```bash
cd backend
.venv\Scripts\python app/services/email_model.py your_email@gmail.com
```

---

## 📡 API Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Authenticate user & issue JWT token |
| `GET` | `/api/strategies` | List all strategies with state & isolated P&L |
| `PUT` | `/api/strategies/{id}/parameters` | Dynamically update strategy parameters & risk limits |
| `POST` | `/api/strategies/{id}/square-off` | Liquidate single strategy's position safely |
| `POST` | `/api/strategies/{id}/manual-trade` | Place a manual order under a strategy's isolated ledger |
| `GET` | `/api/risk/kill-switch` | Current kill switch status, active scope, and auto-rules |
| `POST` | `/api/risk/kill-switch/activate` | Trigger multi-scope halt (`GLOBAL`, `CANCEL_ONLY`, etc.) |
| `POST` | `/api/risk/kill-switch/reset` | Disengage kill switch and unlock account |
| `GET` | `/api/risk/kill-switch/incidents` | Forensic incident audit trail records |
| `PUT` | `/api/risk/kill-switch/auto-rules` | Update pre-emptive auto-trip drawdown thresholds |
| `GET` | `/api/orders/{id}/contract-note` | Generate SEBI Rule 15 SCRA contract note for an order |
| `GET` | `/api/reports/charges-summary` | Aggregated statutory charges & session friction |
| `POST` | `/api/reports/email-statement` | Dispatch live SEBI Rule 15 P&L Statement via SMTP TLS |
| `POST` | `/api/recovery/reconcile` | Audit broker positions vs internal state & detect drift |
| `POST` | `/api/subscriptions/checkout` | Create Razorpay checkout order for selected tier |
| `POST` | `/api/subscriptions/verify-webhook` | Validate Razorpay HMAC-SHA256 signature and activate tier |

---

## 📁 Project Directory Structure

```
Syrus7_Midnight_Coders/
├── README.md                           # Main Project Documentation
├── docker-compose.yml                  # Docker Compose for PostgreSQL
├── backend/
│   ├── README.md                       # Comprehensive Backend Architecture Guide
│   ├── requirements.txt                # Python Dependencies
│   ├── tradeshield.db                  # Local SQLite Database (auto-generated)
│   ├── app/
│   │   ├── accounting/
│   │   │   └── contract_note.py        # Statutory Charges & Contract Notes
│   │   ├── api/
│   │   │   ├── routes.py               # REST API Endpoints & Kill Switch
│   │   │   └── schemas.py              # Pydantic Request/Response Models
│   │   ├── broker/
│   │   │   ├── api_021.py              # Live 021 Broker Client with Query-Before-Retry
│   │   │   └── mock_021.py             # Mock Broker for Testing & Chaos
│   │   ├── core/
│   │   │   ├── config.py               # Application Settings & Env Parsers
│   │   │   ├── enums.py                # Order, Side, Book, & Status Enums
│   │   │   └── rate_limiter.py         # Token-Bucket Broker Rate Limiter
│   │   ├── database/                   # Database Sessions, Models, & Repositories
│   │   ├── execution/
│   │   │   └── engine.py               # Order Lifecycle & In-flight Manager
│   │   ├── killswitch/
│   │   │   └── service.py              # Multi-Scope Kill Switch & Auto-Trip Rules
│   │   ├── market_data/
│   │   │   ├── feed_021.py             # 021 WebSocket Stream Handler
│   │   │   ├── candle_aggregator.py    # 1m/5m Tick-to-Candle Aggregator
│   │   │   ├── decoder.py              # Binary Tick Packet Decoder
│   │   │   └── instruments.py          # Tradable Instruments Registry
│   │   ├── recovery/
│   │   │   └── service.py              # Mid-trade Crash Recovery & State Reconciler
│   │   ├── risk/
│   │   │   └── engine.py               # Level 3 Independent Risk Gate
│   │   ├── services/
│   │   │   ├── email_model.py          # Standalone SEBI Email P&L Statement Engine
│   │   │   └── email_service.py        # Backend Email Dispatcher Service
│   │   └── strategies/
│   │       ├── base.py                 # Abstract Strategy Class
│   │       ├── time_based.py           # Strategy 1: Time-Based Open/Close
│   │       ├── breakout.py             # Strategy 2: 1% Day Open Breakout
│   │       ├── moving_average.py       # Strategy 3: Dual SMA Crossover
│   │       └── manager.py              # Strategy Registry & Orchestrator
│   ├── scripts/
│   │   ├── setup_database.py           # Database Initializer & Seed Auditor
│   │   ├── demo_chaos_scenarios.py     # Chaos & Failure Demonstration
│   │   ├── demo_strategies.py          # Strategy Lifecycle Demo
│   │   └── run_live_trading.py         # Live Broker Algo Trading Runner
│   └── tests/
│       ├── failure/                    # Judge Chaos Failure Tests
│       ├── integration/                # API, Auth, Subscriptions & Email Tests
│       ├── judge/                      # Comprehensive Judge Evaluation Suite
│       └── unit/                       # Risk, Recovery, Strategy, Decoder & Broker Tests
├── frontend/
│   ├── README.md                       # Comprehensive Frontend Architecture Guide
│   ├── package.json                    # Frontend Dependencies
│   ├── vite.config.ts                  # Vite Configuration
│   └── src/
│       ├── components/tm/
│       │   ├── ChaosLab.tsx            # Interactive Resilience & Failure Lab
│       │   ├── ContractNoteModal.tsx   # SEBI Contract Note Modal
│       │   ├── CreateStrategyModal.tsx # Deploy Custom Strategy Wizard
│       │   ├── EmailStatementModal.tsx # Real-Time Email P&L Statement Modal
│       │   ├── KillSwitch.tsx          # Multi-Scope Emergency Halt Modal
│       │   ├── StrategyControls.tsx    # Strategy Action Buttons
│       │   └── StrategyCustomizerModal.tsx # Live Parameters Slider Modal
│       ├── routes/
│       │   ├── _app.dashboard.tsx      # Main Trading Dashboard
│       │   ├── _app.strategies.tsx     # Strategy Management & Studio
│       │   ├── _app.orders.tsx         # Order Book & Contract Notes
│       │   ├── _app.positions.tsx      # Live Positions & P&L
│       │   ├── _app.risk-controls.tsx  # Risk Policy Studio & Forensics
│       │   └── _app.settings.tsx       # User Settings & Subscriptions
│       ├── services/                   # API Client Services
│       └── types/                      # TypeScript Interfaces
```

---

## 👥 Authors & Credits

- **Team**: Midnight Coders
- **Hackathon**: Syrus Hackathon 2026
- **Broker API**: 021 Trade Developer APIs (UCC: `HACK342`)
- **License**: MIT
