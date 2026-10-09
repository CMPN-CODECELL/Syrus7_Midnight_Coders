# TradeShield — 021 Algo Trading Platform

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6.0-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tests](https://img.shields.io/badge/Tests-46%20Passed%20(100%25)-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)]()

> **Built for the 021 Trade Hackathon (Syrus 2026) — Team Midnight Coders**  
> An institutional-grade algorithmic trading platform built on the 021 Developer APIs where **risk limits strictly hold even when strategies malfunction, crash, or send rogue orders**.

---

## 📑 Table of Contents
1. [Key Features & Highlights](#-key-features--highlights)
2. [Architecture Levels (L1 — L4)](#-architecture-levels-l1--l4)
3. [Strategy Customization & User Control](#-strategy-customization--user-control)
4. [Real-Life Institutional Kill Switch](#-real-life-institutional-kill-switch)
5. [Statutory Charges & SEBI Contract Notes](#-statutory-charges--sebi-contract-notes)
6. [Judge Failure & Chaos Scenarios](#-judge-failure--chaos-scenarios)
7. [Installation & How to Use](#-installation--how-to-use)
   - [Prerequisites](#prerequisites)
   - [Step 1: Clone the Repository](#step-1-clone-the-repository)
   - [Step 2: Backend Setup](#step-2-backend-setup)
   - [Step 3: Frontend Setup](#step-3-frontend-setup)
   - [Step 4: Demo Credentials & UI Walkthrough](#step-4-demo-credentials--ui-walkthrough)
8. [Automated Verification & CLI Scripts](#-automated-verification--cli-scripts)
9. [API Endpoints Overview](#-api-endpoints-overview)
10. [Project Directory Structure](#-project-directory-structure)

---

## 🚀 Key Features & Highlights

- 🛡️ **Level 3 Independent Risk Gate**: Strategy code *never* speaks directly to the broker. Every order intent passes through an independent Risk Engine enforcing max daily loss, max position limits, and rolling rate limiters.
- 🎛️ **Free User Customization Studio**: Full UI control over strategy parameters—tweak SMA periods, breakout thresholds, take-profit %, stop-loss %, trailing stop %, trade directions (`LONG_ONLY`, `SHORT_ONLY`, `BOTH`), and manual trade placement.
- 🛑 **Real-Life Institutional Kill Switch**:
  - **4 Granular Halt Scopes**: `GLOBAL` (liquidate all), `CANCEL_ONLY` (soft halt: cancel pending orders but preserve open positions to avoid panic slippage), `STRATEGY` (quarantine single rogue strategy), and `SYMBOL` (freeze single instrument).
  - **Pre-emptive Auto-Trip Rules**: Auto-halts if cumulative portfolio MTM loss breaches the threshold or on consecutive broker rejections.
  - **Cooling-Off Lockout**: Anti-revenge trading timer (e.g., 5, 15, 30 min lockouts).
  - **Forensic Audit History**: Immutable post-mortem incident log with sub-10s SLA verification guarantee.
- 📜 **SEBI Rule 15 SCRA Digital Contract Notes**: Automated itemized breakdown of Brokerage, STT, Exchange Txn Fees, SEBI Turnover Fees, Stamp Duty, and 18% GST using exact integer paise arithmetic.
- 🔄 **L2 Mid-Trade State Recovery**: Auto-reconciles broker positions vs. internal strategy ledgers on server restart; detects position drift and orphaned orders.
- ⚡ **High-Speed Binary Tick Parser & Candle Aggregator**: Decodes raw 021 binary feed packets (TC 1, 2, 3 Full Mode) and aggregates tick-by-tick data into 1-minute and 5-minute OHLCV candles without volume leaks.

---

## 🏛️ Architecture Levels (L1 — L4)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (React + Vite)                           │
│  Live Trading Terminal │ Strategy Customizer │ Risk Controls │ Contract Notes│
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
│                                              │ - 5 Orders/Min Rate Limiter │ │
│                                              │ - Multi-Scope Kill Switch   │ │
│                                              └──────────────┬──────────────┘ │
│                                                             │ Approved Only  │
│                                              ┌──────────────▼──────────────┐ │
│                                              │   L2: Execution & Recovery  │ │
│                                              │ - Order Lifecycle Engine    │ │
│                                              │ - State Reconciler & Drift  │ │
│                                              │ - Contract Note Calculator  │ │
│                                              └──────────────┬──────────────┘ │
└─────────────────────────────────────────────────────────────┼────────────────┘
                                                              │ REST / WS
                                               ┌──────────────▼──────────────┐
                                               │   021 Broker (Live / Mock)  │
                                               │   UCC: HACK342              │
                                               └─────────────────────────────┘
```

- **Level 1 (Data Layer)**: Handles real-time binary market data feed, decodes ticks into depth bids/asks, and streams 1-minute and 5-minute candlesticks.
- **Level 2 (Execution & Recovery)**: Manages order states (`CREATED` $\rightarrow$ `PLACED` $\rightarrow$ `PARTIALLY_FILLED` $\rightarrow$ `EXECUTED`), handles partial fill math, and recovers mid-trade state on process crashes.
- **Level 3 (Risk Enforcement)**: Sits as a firewall between strategies and the broker. Strictly blocks unauthorized sizes, throttles rapid orders, and halts runaway algos.
- **Level 4 (Isolated Ledgers)**: Manages concurrent strategies on a single trading account. Supports opposing trades (e.g. +5 Long and -5 Short on `RELIANCE` simultaneously), maintaining distinct P&L ledgers while the broker account sits flat.

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

## 🧪 Judge Failure & Chaos Scenarios

The platform includes an automated **Resilience Test Suite** verifying that risk gates hold across extreme edge cases:

| Scenario | Level | Injected Failure | Expected Behavior | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Partial Fill** | **L2** | Broker fills 4 out of 10 units | Strategy updates position to +4; remaining 6 stays in working registry. No drift. | **PASS** |
| **Crash Recovery** | **L2/L3** | Server killed mid-trade | Startup reconciler audits broker vs strategy state; restores in-flight tracking. | **PASS** |
| **Runaway Strategy** | **L3** | Rogue algo fires 15 orders in 1 sec | First 5 approved; subsequent orders throttled; strategy auto-halted. | **PASS** |
| **Risk Gate Breach** | **L3** | Order placed for 25 units (> 10 limit) | Platform Risk Engine rejects order before broker call. | **PASS** |
| **Broker Outage** | **L2** | Broker returns HTTP 503 / Timeout | Gracefully handled; order marked REJECTED/FAILED; state integrity preserved. | **PASS** |
| **Opposing Trades** | **L4** | +5 Long & -5 Short on `RELIANCE` | Both strategies track independent positions & P&L; broker net position is 0. | **PASS** |

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

# Start the FastAPI server on port 8001
python -m uvicorn app.main:app --port 8001 --reload
```

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
   - Quick status cards for all active strategies.
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

---

## 🧪 Automated Verification & CLI Scripts

### 1. Run Complete Pytest Suite (46 Tests Passing)
```bash
cd backend
.venv\Scripts\python -m pytest
```
*Expected Output: `46 passed in ~6.5s`*

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
| `POST` | `/api/recovery/reconcile` | Audit broker positions vs internal state & detect drift |

---

## 📁 Project Directory Structure

```
Syrus7_Midnight_Coders/
├── README.md                           # Main Project Documentation
├── backend/
│   ├── app/
│   │   ├── accounting/
│   │   │   └── contract_note.py        # Statutory Charges & Contract Notes
│   │   ├── api/
│   │   │   ├── routes.py               # REST API Endpoints & Kill Switch
│   │   │   └── schemas.py              # Pydantic Request/Response Models
│   │   ├── broker/
│   │   │   ├── api_021.py              # Live 021 Developer API Client
│   │   │   └── mock_021.py             # Mock Broker for Testing & Chaos
│   │   ├── core/
│   │   │   ├── config.py               # Application Settings
│   │   │   └── enums.py                # Order, Side, Book, & Status Enums
│   │   ├── execution/
│   │   │   └── engine.py               # Order Lifecycle & In-flight Manager
│   │   ├── killswitch/
│   │   │   └── service.py              # Multi-Scope Kill Switch & Auto-Trip Rules
│   │   ├── market_data/
│   │   │   ├── feed_021.py             # 021 WebSocket Stream Handler
│   │   │   ├── candle_aggregator.py    # 1m/5m Tick-to-Candle Aggregator
│   │   │   └── decoder.py              # Binary Tick Packet Decoder
│   │   ├── recovery/
│   │   │   └── service.py              # Mid-trade Crash Recovery & State Reconciler
│   │   ├── risk/
│   │   │   └── engine.py               # Level 3 Independent Risk Gate
│   │   └── strategies/
│   │       ├── base.py                 # Abstract Strategy Class
│   │       ├── time_based.py           # Strategy 1: Time-Based Open/Close
│   │       ├── breakout.py             # Strategy 2: 1% Day Open Breakout
│   │       ├── moving_average.py       # Strategy 3: Dual SMA Crossover
│   │       └── manager.py              # Strategy Registry & Orchestrator
│   ├── scripts/
│   │   ├── demo_chaos_scenarios.py     # Chaos & Failure Demonstration
│   │   ├── demo_strategies.py          # Strategy Lifecycle Demo
│   │   └── run_live_trading.py         # Live Broker Algo Trading Runner
│   ├── tests/
│   │   ├── failure/                    # Judge Chaos Failure Tests
│   │   ├── integration/                # API & Auth Integration Tests
│   │   └── unit/                       # Risk, Recovery, Strategy, & Decoder Tests
│   ├── requirements.txt                # Python Dependencies
│   └── tradeshield.db                  # Local SQLite Database
├── frontend/
│   ├── src/
│   │   ├── components/tm/
│   │   │   ├── ChaosLab.tsx            # Interactive Resilience & Failure Lab
│   │   │   ├── ContractNoteModal.tsx   # SEBI Contract Note Modal
│   │   │   ├── CreateStrategyModal.tsx # Deploy Custom Strategy Wizard
│   │   │   ├── KillSwitch.tsx          # Multi-Scope Emergency Halt Modal
│   │   │   ├── StrategyControls.tsx    # Strategy Action Buttons
│   │   │   └── StrategyCustomizerModal.tsx # Live Parameters Slider Modal
│   │   ├── routes/
│   │   │   ├── _app.dashboard.tsx      # Main Trading Dashboard
│   │   │   ├── _app.strategies.tsx     # Strategy Management & Studio
│   │   │   ├── _app.orders.tsx         # Order Book & Contract Notes
│   │   │   ├── _app.positions.tsx      # Live Positions & P&L
│   │   │   └── _app.risk-controls.tsx  # Risk Policy Studio & Forensics
│   │   ├── services/                   # API Client Services
│   │   └── types/                      # TypeScript Interfaces
│   ├── package.json                    # Frontend Dependencies
│   └── vite.config.ts                  # Vite Configuration
```

---

## 👥 Authors & Credits

- **Team**: Midnight Coders
- **Hackathon**: Syrus Hackathon 2026
- **Broker API**: 021 Trade Developer APIs (UCC: `HACK342`)
- **License**: MIT
