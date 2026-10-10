# TradeShield Backend Engine — 021 Algo Trading Platform

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![AsyncIO](https://img.shields.io/badge/AsyncIO-Concurrency-blue?style=for-the-badge)](https://docs.python.org/3/library/asyncio.html)
[![Tests](https://img.shields.io/badge/Tests-80%20Passed%20(100%25)-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)]()
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](../LICENSE)

Institutional-grade, asynchronous backend engine powering the **TradeShield / TradeMint** algorithmic trading terminal. Built with Python 3, FastAPI, SQLAlchemy 2.0 (async), and an independent Level 3 Risk Gate enforcing regulatory risk rules directly against 021 Developer APIs.

---

## 📑 Table of Contents
1. [Backend Architecture (L1 — L4)](#-backend-architecture-l1--l4)
2. [Component Directory Map](#-component-directory-map)
3. [Broker Client & Network Resilience](#-broker-client--network-resilience)
4. [Level 3 Risk Firewall & Kill Switch](#-level-3-risk-firewall--kill-switch)
5. [SEBI Rule 15 Contract Notes & Integer Arithmetic](#-sebi-rule-15-contract-notes--integer-arithmetic)
6. [TradeMint Automated Email Statement Engine](#-trademint-automated-email-statement-engine)
7. [Razorpay 3-Tier Paywall & Subscription Engine](#-razorpay-3-tier-paywall--subscription-engine)
8. [Database Provisioning & Self-Healing Architecture](#-database-provisioning--self-healing-architecture)
9. [Configuration & Environment Variables](#-configuration--environment-variables)
10. [Setup & Execution Instructions](#-setup--execution-instructions)
11. [Automated Test Suite (80 Passing Tests)](#-automated-test-suite-80-passing-tests)
12. [CLI Scripts & Demo Runners](#-cli-scripts--demo-runners)
13. [REST API Endpoints Reference](#-rest-api-endpoints-reference)

---

## 🏛️ Backend Architecture (L1 — L4)

```
                            [ 021 Broker WebSocket / Feed ]
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LEVEL 1: MARKET DATA LAYER                         │
│  - Binary Decoder (`market_data/decoder.py`): Parses TC 1, 2, 3 packets     │
│  - Candle Aggregator (`market_data/candle_aggregator.py`): 1m & 5m OHLCV    │
│  - Feed Handler (`market_data/feed_021.py`): Auto-reconnecting socket       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Real-time Candles & LTP
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       LEVEL 4: MULTI-STRATEGY ENGINE                        │
│  - Isolated Strategy Ledgers: `strat_time`, `strat_breakout`, `strat_ma`    │
│  - Dynamic Strategy Manager (`strategies/manager.py`)                       │
│  - Opposing Trades: +5 Long & -5 Short track separately; broker sits flat   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Raw Order Intent
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LEVEL 3: INDEPENDENT RISK FIREWALL                      │
│  - Risk Engine (`risk/engine.py`): Sits as a firewall before broker         │
│  - Pre-Trade Gate: Max order size, Max daily loss, Price collars            │
│  - Token-Bucket Limiter (`core/rate_limiter.py`): 5 req/s (burst 10)        │
│  - Multi-Scope Kill Switch (`killswitch/service.py`): GLOBAL, CANCEL_ONLY,  │
│    STRATEGY, SYMBOL with anti-revenge cooling-off lockouts                  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Approved Orders Only
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LEVEL 2: EXECUTION & RECOVERY ENGINE                     │
│  - Order Lifecycle Machine (`execution/engine.py`): State transitions       │
│  - Query-Before-Retry (`broker/api_021.py`): Resilient 504 timeout recovery │
│  - Mid-Trade Reconciler (`recovery/service.py`): Detects position drift     │
│  - SEBI Contract Notes (`accounting/contract_note.py`): Integer paise math  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ REST / WS
                                       ▼
                              [ 021 Broker API ]
```

---

## 📁 Component Directory Map

```
backend/
├── app/
│   ├── accounting/
│   │   └── contract_note.py        # SEBI SCRA Rule 15 integer-paise tax calculator
│   ├── api/
│   │   ├── routes.py               # REST API endpoints (FastAPI router)
│   │   └── schemas.py              # Pydantic request & response schemas
│   ├── broker/
│   │   ├── api_021.py              # Live 021 API client with Query-Before-Retry
│   │   ├── mock_021.py             # Configurable mock broker for testing
│   │   └── models.py               # Broker order, position, & account schemas
│   ├── core/
│   │   ├── config.py               # Dynaconf / pydantic-settings environment parser
│   │   ├── enums.py                # OrderType, Side, OrderStatus, Scope enums
│   │   └── rate_limiter.py         # Token-Bucket rolling window rate limiter
│   ├── database/
│   │   ├── __init__.py             # Database engine, session maker, base model
│   │   ├── models/                 # SQLAlchemy ORM models (users, orders, logs)
│   │   └── repositories/           # Repositories for strategy, user, orders
│   ├── execution/
│   │   └── engine.py               # Order lifecycle machine & working order registry
│   ├── killswitch/
│   │   └── service.py              # 4-scope halt engine, auto-trip rules, audit logs
│   ├── market_data/
│   │   ├── candle_aggregator.py    # Tick-to-candle (1m & 5m OHLCV) aggregation
│   │   ├── decoder.py              # Binary 021 packet unpacker (struct)
│   │   ├── feed_021.py             # WebSocket feed subscriber
│   │   └── instruments.py          # Master symbol registry (RELIANCE, TCS, INFY)
│   ├── recovery/
│   │   └── service.py              # Mid-trade state reconciliation & drift detection
│   ├── risk/
│   │   └── engine.py               # Level 3 Risk Gate: daily loss, limits, rate throttle
│   ├── services/
│   │   ├── email_model.py          # Standalone SEBI email P&L statement generator
│   │   └── email_service.py        # Asynchronous email delivery bridge
│   └── strategies/
│       ├── base.py                 # Abstract strategy interface & ledger tracking
│       ├── breakout.py             # Strategy 2: 1% Day Open Breakout
│       ├── moving_average.py       # Strategy 3: Dual SMA Crossover (Fast/Slow)
│       ├── time_based.py           # Strategy 1: Time-Based Intraday Entry/Exit
│       └── manager.py              # Strategy orchestrator & isolated ledger tracker
├── scripts/
│   ├── demo_chaos_scenarios.py     # Terminal demonstration of 6 judge failure modes
│   ├── demo_strategies.py          # Terminal demonstration of strategy lifecycle
│   ├── run_live_trading.py         # Real-time WebSocket algorithmic trading runner
│   └── setup_database.py           # Database provisioning, seeding, & integrity test
├── tests/
│   ├── failure/                    # Edge case & chaos tests
│   ├── integration/                # API, Auth, Subscriptions, & Email integration tests
│   ├── judge/                      # Comprehensive judge evaluation suite
│   └── unit/                       # Unit tests for broker, decoder, engine, risk, strategies
├── requirements.txt                # Production & development dependencies
└── tradeshield.db                  # Auto-generated SQLite database (zero-config)
```

---

## 🔄 Broker Client & Network Resilience

Algorithmic execution against live broker APIs must survive unannounced socket drops and HTTP gateway timeouts:

1. **Query-Before-Retry Pattern (`api_021.py`)**:
   - When placing an order, if the HTTP request times out (HTTP 504) or throws a network exception, the engine **does NOT blindly resubmit**.
   - It triggers a secondary query via `GET /orders/{client_order_id}` or polls the broker order registry.
   - If the broker has recorded the order, the internal state links to it immediately as `PLACED`.
   - If the broker confirms the order was not received, only then is a clean retry executed with exponential backoff.
2. **Token-Bucket Rate Limiter (`core/rate_limiter.py`)**:
   - Enforces a sustained limit of 5 requests/sec with burst capacity of 10 tokens.
   - Requests exceeding capacity are delayed asynchronously via token replenishment calculations, eliminating HTTP 429 Too Many Requests errors.

---

## 🛡️ Level 3 Risk Firewall & Kill Switch

The Risk Gate operates completely independently from the strategy engine:

- **Pre-Trade Sanity Checks**:
  - Maximum single order quantity (e.g. 10 shares limit).
  - Maximum daily portfolio loss (e.g. ₹2,000.00 MTM loss cap).
  - Rate limiting (e.g. max 5 orders per 60-second window).
- **Institutional Multi-Scope Kill Switch**:
  - **`GLOBAL`**: Instantly cancels all open orders across all books and executes market liquidations to flatten the entire account within a 10s SLA.
  - **`CANCEL_ONLY`**: Flushes in-flight pending orders but leaves open positions intact to prevent panic market slippage.
  - **`STRATEGY`**: Quarantines an individual rogue strategy without disturbing healthy algorithms.
  - **`SYMBOL`**: Freezes trading on a single specific instrument.
- **Auto-Trip Rules**:
  - Pre-emptive auto-halt on cumulative drawdown breaches.
  - Tripwire on 3 consecutive broker rejections.
- **Cooling-Off Lockout**:
  - Automated lockout timer (5, 15, 30 mins) preventing revenge trading.
- **Immutable Forensic Audit**:
  - Structured audit trail recorded in database with Incident ID, trigger source, scope, reason, elapsed execution duration, and compliance SLA verification.

---

## 💰 SEBI Rule 15 Contract Notes & Integer Arithmetic

All monetary figures in TradeShield are calculated and stored in **integer paise** (1 INR = 100 paise) to prevent IEEE-754 floating point rounding drift:

```
Net Realized P&L = Gross Trade P&L - Total Statutory Charges
```

| Fee Component | Statutory Basis | Calculation Formula |
| :--- | :--- | :--- |
| **Brokerage** | Flat ₹20 per executed order | `2,000 paise` |
| **STT (Securities Transaction Tax)** | 0.025% on Intraday SELL turnover | `int(sell_turnover * 0.00025)` |
| **Exchange Txn Fee** | 0.00297% on total turnover (NSE Equity) | `max(1, int(turnover * 0.0000297))` |
| **SEBI Turnover Fee** | ₹10 per crore (0.0001% of turnover) | `max(1, int(turnover * 0.000001))` |
| **Stamp Duty** | 0.015% on BUY side turnover | `int(buy_turnover * 0.00015)` |
| **GST** | 18% on (Brokerage + Txn Fee + SEBI Fee) | `int((brokerage + exchange + sebi) * 0.18)` |

Contract notes are serialized according to SEBI SCRA Rule 15 with unique alphanumeric IDs (e.g., `CN-20261010-093015-TCS`) and accessible via `GET /api/orders/{id}/contract-note`.

---

## 📧 TradeMint Automated Email Statement Engine

The platform features an automated, standalone **Profit & Loss Statement & Regulatory Email Engine**:

- **Pure Standard Library**: `app/services/email_model.py` requires zero third-party packages, running natively on standard `smtplib`, `email`, `datetime`, and `json`.
- **Dual HTML & Plaintext Formatting**: Generates modern dark-themed HTML tables with responsive styling, color-coded P&L indicators, and statutory charge summaries, accompanied by plaintext fallbacks.
- **Direct Runtime Telemetry Parity**: Ingests exact account summary state (`netPnl`, `accountValue`, `availableBalance`, `riskStatus`), guaranteeing 100% telemetry alignment with the live dashboard.
- **Live TLS/STARTTLS Socket Handling**: Supports Port 587 (STARTTLS) and Port 465 (SSL), with automatic retry and socket reconnection logic.

### 📸 Email Statement Preview:
| TradeMint SEBI Rule 15 Email Statement (P&L & Portfolio Summary) | Itemized Regulatory Charges & Trade Ledger |
| :---: | :---: |
| ![TradeMint Email Statement](trademint%20ss.png) | ![TradeMint Regulatory Breakdown](trademint%20ss1.png) |

### Standalone CLI Execution:
```bash
python app/services/email_model.py trader@example.com
```

### Programmatic Usage:
```python
from app.services.email_model import EmailService

service = EmailService(smtp_user="darshanmali44444@gmail.com", smtp_password="app_password")
statement_data = service.build_pnl_statement_data(
    user_name="Trader",
    user_email="trader@example.com",
    ucc="021-HACK342"
)
result = service.send_pnl_statement_email("trader@example.com", statement_data)
print(result["deliveryStatus"])  # DELIVERED
```

---

## 💳 Razorpay 3-Tier Paywall & Subscription Engine

TradeShield integrates a multi-tier commercialization system backed by Razorpay:

| Tier Identifier | Test Account | Execution Access | Features |
| :--- | :--- | :--- | :--- |
| **`tier_pro`** | `u_test_all` | Unlimited Algos | All built-in & custom strategies, live broker execution, priority risk alerts |
| **`tier_standard`** | `u_test_three` | 3 Algos | Access restricted to `strat_time`, `strat_breakout`, `strat_ma` |
| **`tier_free`** | `u_test_none` | Paper Only | Read-only terminal & simulated paper trades. Live broker calls blocked |

- **HMAC-SHA256 Signature Verification**: Webhook payloads are verified against `RAZORPAY_KEY_SECRET` using `hmac.new(..., hashlib.sha256)`.
- **Pre-Execution Tier Interceptor**: Attempts to activate unauthorized strategies throw HTTP 403 Forbidden with upgrade guidance.

---

## 💾 Database Provisioning & Self-Healing Architecture

The platform supports plug-and-play persistence with automatic table initialization on startup:

### 1. Zero-Config Local SQLite (Default)
- Zero external dependencies required.
- Automatically creates `backend/tradeshield.db` on first boot.
- Auto-seeds default demo credentials (`demo@trademint.in` / `demo1234`), 3 strategies, and tier accounts (`u_test_all`, `u_test_three`, `u_test_none`).

### 2. Enterprise PostgreSQL (Docker)
- Start container: `docker compose up -d postgres` (listens on `localhost:5434`).
- Connection string in `.env`: `postgresql+asyncpg://tradeshield:tradeshield@localhost:5434/tradeshield`.

### 3. Hosted Cloud PostgreSQL (Neon / Supabase / Railway)
- Paste the connection string directly into `.env` with `?ssl=require`.

### 4. Database Seeder & Integrity Script
```bash
# Verify connection & seed database:
python scripts/setup_database.py

# Complete reset & re-seed:
python scripts/setup_database.py --reset
```

---

## ⚙️ Configuration & Environment Variables

Copy `.env.example` to `.env` in `backend/` and configure:

```ini
# Database (SQLite default or PostgreSQL)
DATABASE_URL=sqlite+aiosqlite:///backend/tradeshield.db

# Security & JWT Token Auth
JWT_SECRET=trade-shield-dev-secret-key-change-in-prod-2026

# 021 Broker Settings ("mock" for sandbox, "api021" for live broker)
BROKER_MODE=mock
BROKER_BASE_URL=https://devapi.021.trade/api/developer-api
API_UCC=HACK342
API_PASSWORD=Darshan@47

# Risk & Session Parameters
TRADING_DAY_TZ=Asia/Kolkata
SESSION_START=09:15
DAILY_LOSS_MODE=net
RATE_WINDOW_SECONDS=60
KILL_SWITCH_TIMEOUT_SECONDS=10
BROKER_CALL_TIMEOUT_SECONDS=3

# Statutory Charges (Integer Paise)
BROKERAGE_PER_FILL_PAISE=2000
FEE_PERCENT_OF_NOTIONAL=0.0003
MOCK_FILL_LATENCY_MS=0
SYMBOLS=RELIANCE,TCS,INFY

# Razorpay & Email Credentials
RAZORPAY_KEY_ID=rzp_test_SFd7WR1rAUaPUA
RAZORPAY_KEY_SECRET=AHqEU8tXJJ1sbjLzZgiGNNsz
MAIL_USERNAME=darshanmali44444@gmail.com
MAIL_PASSWORD=vjykssyqrknqfqsj
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

---

## 🚀 Setup & Execution Instructions

```bash
# 1. Navigate to backend directory
cd backend

# 2. Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch FastAPI Server on port 8001
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

- 📖 **Interactive Swagger UI**: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
- 🩺 **Health Check**: [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health)

---

## 🧪 Automated Test Suite (80 Passing Tests)

Run the complete test suite verifying 100% code pass rate:

```bash
python -m pytest
```

### Test Suite Structure:
- **`tests/failure/` (3 tests)**: Injects catastrophic runaway loops, oversize orders, and drawdown halts into Level 3 Risk Gate.
- **`tests/integration/` (15 tests)**:
  - `test_api_auth.py`: JWT login, registration, password hashing.
  - `test_api_features.py`: Orders, strategies, killswitch activation/reset, contract notes.
  - `test_database_and_subscriptions.py`: DB schema persistence, self-healing setup.
  - `test_email_model.py`: SEBI Rule 15 math, HTML generation, TLS email delivery.
  - `test_user_subscriptions.py`: 3-tier user access control gates.
- **`tests/judge/` (10 tests)**: Exhaustive evaluation suite covering multi-scope kill switch, partial fill recovery, rate limiter burst behavior, and contract note itemization.
- **`tests/unit/` (52 tests)**:
  - `test_broker_021_retries.py`: Query-Before-Retry loop on HTTP 504 and transient drops.
  - `test_candle_decoder.py`: Binary unpacker for TC 1, 2, 3 and 1m/5m aggregations.
  - `test_contract_note.py`: Integer paise math validation for STT, GST, SEBI fee.
  - `test_execution_engine.py`: In-flight order registry, partial fill tracking.
  - `test_mock_021.py`: Simulated broker behavior.
  - `test_rate_limiter.py`: Token bucket replenishment and burst throttling.
  - `test_recovery.py`: Mid-trade crash recovery and position drift detection.
  - `test_resilience_and_recovery.py`: Process crash recovery and state audit.
  - `test_risk_engine.py`: Pre-trade checks, daily loss caps, position limits.
  - `test_strategies.py`: Isolated strategy ledgers and opposing trades.

---

## 🛠️ CLI Scripts & Demo Runners

1. **Failure & Chaos Scenarios Demo**:
   ```bash
   python scripts/demo_chaos_scenarios.py
   ```
2. **Strategy Lifecycle Demo**:
   ```bash
   python scripts/demo_strategies.py
   ```
3. **Live 021 Broker Algo Trading Runner**:
   ```bash
   python -u scripts/run_live_trading.py
   ```
4. **Standalone Email P&L Statement Test**:
   ```bash
   python app/services/email_model.py your_email@gmail.com
   ```

---

## 📡 REST API Endpoints Reference

| Category | Method | Endpoint | Description |
| :--- | :--- | :--- | :--- |
| **Auth** | `POST` | `/api/auth/register` | Register new user account |
| **Auth** | `POST` | `/api/auth/login` | Authenticate and obtain JWT access token |
| **Strategies** | `GET` | `/api/strategies` | List all algorithmic strategies with isolated P&L |
| **Strategies** | `POST` | `/api/strategies/{id}/start` | Start an algorithmic strategy |
| **Strategies** | `POST` | `/api/strategies/{id}/stop` | Stop an algorithmic strategy |
| **Strategies** | `POST` | `/api/strategies/{id}/square-off` | Liquidate single strategy's position safely |
| **Strategies** | `PUT` | `/api/strategies/{id}/parameters` | Dynamically update strategy parameters & risk limits |
| **Strategies** | `POST` | `/api/strategies/{id}/manual-trade` | Place a manual order under strategy's isolated ledger |
| **Orders** | `GET` | `/api/orders` | Query order book with status filters |
| **Orders** | `POST` | `/api/orders` | Place a new order intent |
| **Orders** | `DELETE` | `/api/orders/{id}` | Cancel a working/open order |
| **Contract Notes** | `GET` | `/api/orders/{id}/contract-note` | Generate SEBI Rule 15 SCRA contract note |
| **Risk & Killswitch** | `GET` | `/api/risk/kill-switch` | Current kill switch state, scope, and auto-rules |
| **Risk & Killswitch** | `POST` | `/api/risk/kill-switch/activate` | Trigger multi-scope halt (`GLOBAL`, `CANCEL_ONLY`, etc.) |
| **Risk & Killswitch** | `POST` | `/api/risk/kill-switch/reset` | Disengage halt and unlock account |
| **Risk & Killswitch** | `GET` | `/api/risk/kill-switch/incidents` | Forensic incident audit log |
| **Risk & Killswitch** | `PUT` | `/api/risk/kill-switch/auto-rules` | Update pre-emptive auto-trip drawdown thresholds |
| **Reports** | `GET` | `/api/reports/charges-summary` | Aggregated statutory friction summary |
| **Reports** | `POST` | `/api/reports/email-statement` | Send SEBI Rule 15 P&L Statement via SMTP TLS |
| **Recovery** | `POST` | `/api/recovery/reconcile` | Audit broker vs internal ledgers and detect drift |
| **Subscriptions** | `GET` | `/api/subscriptions/current` | Get active user tier & privileges |
| **Subscriptions** | `POST` | `/api/subscriptions/checkout` | Create Razorpay payment checkout order |
| **Subscriptions** | `POST` | `/api/subscriptions/verify-webhook` | Verify Razorpay HMAC-SHA256 signature and update tier |
