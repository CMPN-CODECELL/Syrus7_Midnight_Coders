# 🤖 TradeShield — Complete Verbatim AI Prompting Record (`prompt.md`)

> **Event**: 021 Trade Hackathon (Syrus 2026)  
> **Team**: Midnight Coders  
> **Project**: TradeShield — Institutional Algo Trading & Risk Platform  
> **Repository**: `CMPN-CODECELL/Syrus7_Midnight_Coders`  
> **Documentation Version**: 2.0 (Full Verbatim Prompts Log)  

---

## 📑 Table of Contents

1. [Master Architecture & System Context Prompt](#1-master-architecture--system-context-prompt)
2. [Level 1: Market Data & Candle Aggregation Prompts](#2-level-1-market-data--candle-aggregation-prompts)
   - [Prompt 1.1: Binary Tick Feed Decoder (TC 1, 2, 3)](#prompt-11-binary-tick-feed-decoder-tc-1-2-3)
   - [Prompt 1.2: Zero-Volume-Leak Candle Aggregator (1m & 5m)](#prompt-12-zero-volume-leak-candle-aggregator-1m--5m)
   - [Prompt 1.3: Live 021 WebSocket Stream & Feed Handler](#prompt-13-live-021-websocket-stream--feed-handler)
3. [Level 2: Live Trading, Mid-Trade Recovery & SEBI Accounting Prompts](#3-level-2-live-trading-mid-trade-recovery--sebi-accounting-prompts)
   - [Prompt 2.1: 021 Broker REST API Client & Rate-Limit Resilient Handler](#prompt-21-021-broker-rest-api-client--rate-limit-resilient-handler)
   - [Prompt 2.2: Order Lifecycle State Machine & Partial Fill Engine](#prompt-22-order-lifecycle-state-machine--partial-fill-engine)
   - [Prompt 2.3: Mid-Trade Crash Recovery & Position Drift Reconciler](#prompt-23-mid-trade-crash-recovery--position-drift-reconciler)
   - [Prompt 2.4: SEBI Rule 15 SCRA Integer-Paise Contract Note Calculator](#prompt-24-sebi-rule-15-scra-integer-paise-contract-note-calculator)
4. [Level 3: Independent Risk Gate Firewall & Kill Switch Prompts](#4-level-3-independent-risk-gate-firewall--kill-switch-prompts)
   - [Prompt 3.1: Independent Pre-Trade Risk Firewall Engine](#prompt-31-independent-pre-trade-risk-firewall-engine)
   - [Prompt 3.2: Multi-Scope Institutional Emergency Kill Switch & SLA Engine](#prompt-32-multi-scope-institutional-emergency-kill-switch--sla-engine)
   - [Prompt 3.3: Risk Metrics Auditor & Auto-Trip Rules](#prompt-33-risk-metrics-auditor--auto-trip-rules)
5. [Level 4: Multi-Strategy Engine & Virtual Sub-Ledger Prompts](#5-level-4-multi-strategy-engine--virtual-sub-ledger-prompts)
   - [Prompt 4.1: Hedged Virtual Sub-Ledger Accounting Engine](#prompt-41-hedged-virtual-sub-ledger-accounting-engine)
   - [Prompt 4.2: Strategy Customization Studio & Parameter Engine](#prompt-42-strategy-customization-studio--parameter-engine)
6. [Chaos Testing & Judge Failure Verification Prompts](#6-chaos-testing--judge-failure-verification-prompts)
   - [Prompt 5.1: Judge Failure & Chaos Scenario Simulator](#prompt-51-judge-failure--chaos-scenario-simulator)
   - [Prompt 5.2: Automated Pytest Suite Generation (46 Unit & Integration Tests)](#prompt-52-automated-pytest-suite-generation-46-unit--integration-tests)
7. [Frontend Terminal & User Experience Prompts](#7-frontend-terminal--user-experience-prompts)
   - [Prompt 6.1: Real-Time Quantitative Trading Terminal UI](#prompt-61-real-time-quantitative-trading-terminal-ui)
   - [Prompt 6.2: Institutional Kill Switch Control Matrix & Modal UI](#prompt-62-institutional-kill-switch-control-matrix--modal-ui)
8. [AI Audit, Verification & Human-in-the-Loop Refinement Log](#8-ai-audit-verification--human-in-the-loop-refinement-log)

---

## 1. Master Architecture & System Context Prompt

```text
SYSTEM ROLE & CONTEXT:
You are a Principal Quantitative Infrastructure Engineer and Systems Architect building "TradeShield", an institutional-grade algorithmic trading platform for the 021 Developer APIs (021 Trade Hackathon - Syrus 2026).

CORE PROBLEM STATEMENT & PROBLEM INVARIANT:
"Build an algo trading platform on the 021 developer APIs where risk limits hold even when the strategy itself is buggy."
Strategies will crash, emit rogue order loops (50 orders/sec), calculate invalid position sizes, encounter server crashes mid-trade, or receive corrupted tick data. THE PLATFORM MUST ABSOLUTELY GUARANTEE THAT RISK LIMITS HOLD AND THE BROKER ACCOUNT REMAINS PROTECTED REGARDLESS OF BUGGY STRATEGY CODE.

ARCHITECTURAL BLUEPRINT (LEVEL 1 TO LEVEL 4):
1. Level 1 (Data Layer): Parse raw binary 021 WebSocket market feed (Transaction Codes 1, 2, 3) using struct unpacking (`>i`, `>q`, `>H`). Construct deterministic 1-minute and 5-minute OHLCV candles without volume leaks or timestamp drift.
2. Level 2 (Execution & Recovery): Build an order execution engine supporting CREATED -> PLACED -> PARTIALLY_FILLED -> EXECUTED states. Implement a server startup reconciliation service that connects to the broker, detects position drift vs internal DB, flags orphan orders, and reconciles state after crashes (`kill -9`). Calculate SEBI Rule 15 SCRA contract notes using exact integer paise math (Brokerage, STT, Exchange Txn Fee, SEBI Turnover Fee, Stamp Duty, 18% GST).
3. Level 3 (Independent Risk Gate Firewall): Strategy code must NEVER have direct access to broker API credentials. Every OrderIntent must pass through an independent Risk Gate enforcing:
   - Max Daily Loss drawdown limit
   - Max Position Size limit per symbol
   - Rolling sliding-window rate limiter (max 5 orders/minute)
   - Multi-Scope Emergency Kill Switch (GLOBAL, CANCEL_ONLY, STRATEGY, SYMBOL) with cooling-off lockouts and sub-10 second execution guarantee.
4. Level 4 (Multi-Strategy Virtual Sub-Ledgers): Run multiple concurrent strategies on a single broker account. Support opposing positions (e.g. Strategy A is LONG 100 TCS, Strategy B is SHORT 100 TCS) while keeping isolated P&L ledgers even when the broker net position sits at 0.

TECH STACK REQUIREMENTS:
- Backend: Python 3.11+, FastAPI, AsyncIO, SQLAlchemy (Async SQLite), Pydantic v2, Pytest.
- Frontend: React 18, Vite, TypeScript, TailwindCSS / Vanilla CSS styling with glassmorphism dark mode, Lucide icons.
- Verification: 100% test passing, automated CLI chaos scripts for judge evaluation.
```

---

## 2. Level 1: Market Data & Candle Aggregation Prompts

### Prompt 1.1: Binary Tick Feed Decoder (TC 1, 2, 3)

- **Target File**: [`backend/app/market_data/tick_decoder.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/market_data/tick_decoder.py)
- **Full Verbatim Prompt**:
```text
Create a high-performance Python binary stream decoder to unpack raw 021 WebSocket tick packets.

REQUIREMENTS:
1. Support 021 Transaction Codes (TC):
   - TC 1 (Index / Simple Tick): 4-byte header, 4-byte Token, 4-byte LTP, 8-byte Timestamp.
   - TC 2 (Compact Depth): 4-byte Token, 4-byte LTP, 4-byte LTV, Best Bid Price/Qty, Best Ask Price/Qty.
   - TC 3 (Full Mode Tick): Token, LTP, LTV, Total Volume Traded, Open, High, Low, Close, 5-level Bid/Ask Market Depth arrays (Price, Qty, Orders count).
2. Binary Unpacking: Use Python's `struct.unpack` with big-endian network byte order (`>i`, `>q`, `>H`).
3. Stream Handling: Implement `BinaryTickDecoder` class with a stateful buffer. Handlers must handle incomplete chunks, discard corrupted headers, and emit strongly-typed `TickData` Pydantic models.
4. Scale: Ensure unpacking takes < 0.05 milliseconds per packet.
5. Verification: Write unit tests in `tests/unit/test_candle_decoder.py` asserting exact field extraction from known raw byte hex arrays.
```

### Prompt 1.2: Zero-Volume-Leak Candle Aggregator (1m & 5m)

- **Target File**: [`backend/app/market_data/candle_aggregator.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/market_data/candle_aggregator.py)
- **Full Verbatim Prompt**:
```text
Implement an in-memory real-time Candlestick Aggregator that converts streaming TickData into 1-minute and 5-minute OHLCV candles.

REQUIREMENTS:
1. Minute Boundary Precision:
   - Ticks arriving at timestamp 09:15:59.999 must update the 09:15 candle.
   - The first tick at 09:16:00.000 must finalize and close the 09:15 candle, trigger event callbacks (`on_candle_close`), and initialize a new 09:16 candle with Open = LTP.
2. Zero Volume Leakage:
   - Total volume per candle must equal sum of tick volumes within that exact interval window. Cumulative volume reset must handle broker feed total volume counter resets cleanly.
3. Multi-Interval Support: Support simultaneous 1-minute and 5-minute candle aggregation per subscribed token.
4. Thread/Async Safety: Aggregator must be non-blocking under async task execution.
5. Unit Tests: Provide test cases in `tests/unit/test_candle_decoder.py` testing boundary ticks, missing ticks, and multi-token isolation.
```

### Prompt 1.3: Live 021 WebSocket Stream & Feed Handler

- **Target File**: [`backend/app/market_data/feed_handler.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/market_data/feed_handler.py)
- **Full Verbatim Prompt**:
```text
Build an AsyncIO WebSocket Feed Handler to manage connection lifecycle to the 021 Sandbox Market Data Feed.

REQUIREMENTS:
1. Connection Resilience: Auto-reconnect with exponential backoff (1s, 2s, 4s up to 30s max delay) on socket disconnects or network drops.
2. Subscription Management: Support dynamic subscription and unsubscription of instrument tokens.
3. Integration: Route raw incoming binary messages directly to `BinaryTickDecoder`, then pass decoded ticks to `CandleAggregator` and live strategy tick listeners.
4. Heartbeat: Send ping frames every 15 seconds to prevent server socket timeout.
```

---

## 3. Level 2: Live Trading, Mid-Trade Recovery & SEBI Accounting Prompts

### Prompt 2.1: 021 Broker REST API Client & Rate-Limit Resilient Handler

- **Target File**: [`backend/app/broker/client.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/broker/client.py)
- **Full Verbatim Prompt**:
```text
Design an async HTTP client (`O21BrokerClient`) using `httpx` to interface with the 021 Developer Sandbox REST API.

REQUIREMENTS:
1. Endpoints Implemented:
   - `place_order(symbol, qty, side, order_type, price)`
   - `cancel_order(order_id)`
   - `get_orders()`
   - `get_positions()`
   - `get_margins()`
2. Sandbox Error Handling: The 021 sandbox deliberately throws HTTP 500, 503, and 429 rate limit errors.
   - Implement automatic retry logic for HTTP 500/503 with jittered retry delays (up to 3 retries).
   - Raise custom exceptions: `BrokerRateLimitError`, `BrokerServerError`, `BrokerOrderRejected`.
3. Mode Switch: Support a `MOCK_MODE` toggle for offline unit testing without network dependency.
```

### Prompt 2.2: Order Lifecycle State Machine & Partial Fill Engine

- **Target File**: [`backend/app/execution/engine.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/execution/engine.py)
- **Full Verbatim Prompt**:
```text
Build the Level 2 Execution Engine state machine managing order states and partial fill math.

REQUIREMENTS:
1. State Flow: `CREATED` -> `RISK_APPROVED` -> `PLACED` -> `PARTIALLY_FILLED` -> `EXECUTED` (or `REJECTED` / `CANCELLED`).
2. Partial Fill Math:
   - When a partial fill callback arrives (e.g. 40 filled out of 100 ordered at ₹1,500), update `filled_quantity`, calculate weighted average fill price (`avg_fill_price`), and record remaining open quantity.
   - When remaining quantity is filled, transition status to `EXECUTED`.
3. Database Audit: Persist every state transition timestamp and payload to the SQLite orders table via async SQLAlchemy.
4. Unit Verification: Add unit tests in `tests/unit/test_execution_engine.py` covering split fills, immediate cancellations, and rejection handling.
```

### Prompt 2.3: Mid-Trade Crash Recovery & Position Drift Reconciler

- **Target File**: [`backend/app/recovery/reconciler.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/recovery/reconciler.py)
- **Full Verbatim Prompt**:
```text
Implement a state reconciliation service (`RecoveryReconciler`) triggered on backend startup after process crashes (`kill -9`).

REQUIREMENTS:
1. Audit Process:
   - Query 021 Broker REST API for live net positions and open orders.
   - Load local SQLite database records for open strategy orders and strategy position ledgers.
2. Drift Detection:
   - Compare broker net position per symbol vs total strategy net positions.
   - If a discrepancy exists (Position Drift), log a severity `CRITICAL` audit event.
   - Identify 'Orphaned Orders' (orders placed with broker but not confirmed in local DB) and issue cancellation requests.
3. State Alignment: Sync local DB strategy positions to reflect verified broker position truth and mark unconfirmed pending orders as `RECONCILED_CANCELLED`.
4. Tests: Include test cases in `tests/unit/test_recovery.py` simulating server crash midway through multi-order execution.
```

### Prompt 2.4: SEBI Rule 15 SCRA Integer-Paise Contract Note Calculator

- **Target File**: [`backend/app/accounting/contract_note.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/accounting/contract_note.py)
- **Full Verbatim Prompt**:
```text
Build an institutional SEBI Rule 15 SCRA Digital Contract Note Calculator using EXACT INTEGER PAISE ARITHMETIC (1 Rupee = 100 Paise) to eliminate floating-point rounding bugs.

REQUIREMENTS & FORMULAS (Equities Intraday):
1. Turnover = Quantity * Price_in_Paise
2. Brokerage: min(0.03% * Turnover, 2000 Paise [₹20]) per executed trade.
3. STT (Securities Transaction Tax): 0.025% on Sell Turnover for Delivery, 0.0125% for Intraday Sell side (rounded to nearest Rupee as per statutory rule).
4. Exchange Transaction Fee: 0.00345% of Turnover.
5. SEBI Turnover Fee: 0.0001% of Turnover (₹10 per Crore).
6. Stamp Duty: 0.003% of Buy Turnover only.
7. GST: 18% of (Brokerage + Exchange Txn Fee + SEBI Fee).
8. Net Payable / Receivable: Gross Trade Value +/- Total Statutory Charges.

Output strongly-typed itemized Pydantic models and verify using `tests/unit/test_contract_note.py`.
```

---

## 4. Level 3: Independent Risk Gate Firewall & Kill Switch Prompts

### Prompt 3.1: Independent Pre-Trade Risk Firewall Engine

- **Target File**: [`backend/app/risk/engine.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/risk/engine.py)
- **Full Verbatim Prompt**:
```text
Architect the Level 3 Independent Risk Gate Firewall (`RiskEngine`).

CORE GUARANTEE: Strategy code NEVER calls broker order placement directly. All order intents MUST pass through `RiskEngine.validate_order(order_intent)`.

VALIDATION RULES (PRE-TRADE SANITY CHECKS):
1. Max Position Limit Check: Reject order if resulting position size (current + new order qty) exceeds strategy or global symbol limit.
2. Max Daily Loss Check: Reject order if cumulative realized + unrealized MTM loss for the day exceeds max_daily_loss threshold (e.g., -₹10,000).
3. Order Rate Limiter: Implement a sliding 60-second window rate limiter. Maximum 5 orders allowed per 60s per strategy. Reject 6th order with `RATE_LIMIT_EXCEEDED`.
4. Kill Switch Status Check: If any Kill Switch halt scope is active for the strategy or symbol, instantly reject order with `KILL_SWITCH_ACTIVE`.
5. Price & Tick Sanity: Reject orders with price <= 0, qty <= 0, or non-compliant tick size.

OUTPUT: Return `RiskCheckResult(approved: bool, rejection_reason: Optional[str], metric_snapshot: dict)`. Log all rejections to `risk_audit_logs`.
```

### Prompt 3.2: Multi-Scope Institutional Emergency Kill Switch & SLA Engine

- **Target File**: [`backend/app/killswitch/service.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/killswitch/service.py)
- **Full Verbatim Prompt**:
```text
Implement an emergency Kill Switch service (`KillSwitchService`) with 4 distinct halt scopes and sub-10 second execution SLA.

SCOPES TO IMPLEMENT:
1. GLOBAL:
   - Instantly set global system halt flag.
   - Cancel all open pending orders across all strategies concurrently via `asyncio.gather()`.
   - Send market sell/buy order intents to square off all open positions across the entire account.
2. CANCEL_ONLY (Soft Halt):
   - Cancel all pending open orders to stop exposure growth, but DO NOT liquidate open positions (prevents panic market impact slippage).
3. STRATEGY: Quarantine a single rogue strategy ID. Cancel its open orders and square off its positions while leaving other strategies running safely.
4. SYMBOL: Freeze trading for a specific ticker (e.g. RELIANCE) across all strategies.

ADDITIONAL REQUIREMENTS:
- Anti-Revenge Trading Lockout: Support cooling-off lockout timers (5 min, 15 min, 30 min, or manual admin unlock).
- Execution SLA: Guarantee complete cancellation and square-off execution within 10 seconds (benchmark targeted < 0.5s).
- Audit: Record triggering user, scope, timestamp, affected orders count, and total execution time in `kill_switch_audits`.
```

### Prompt 3.3: Risk Metrics Auditor & Auto-Trip Rules

- **Target File**: [`backend/app/risk/engine.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/risk/engine.py)
- **Full Verbatim Prompt**:
```text
Add automatic pre-emptive trip rules to the Risk Engine.

AUTO-TRIP CONDITIONS:
1. Drawdown Breached Auto-Trip: If portfolio MTM loss drops below 100% of max daily loss, auto-trigger `GLOBAL` or `STRATEGY` kill switch without waiting for user action.
2. Consecutive Rejection Auto-Trip: If 3 consecutive orders from a strategy are rejected by the broker (e.g. insufficient margin or invalid price), auto-quarantine that strategy (`STRATEGY` halt scope).
3. Write automated unit tests in `tests/unit/test_risk_engine.py` validating auto-tripping under rapid loss injection.
```

---

## 5. Level 4: Multi-Strategy Engine & Virtual Sub-Ledger Prompts

### Prompt 4.1: Hedged Virtual Sub-Ledger Accounting Engine

- **Target File**: [`backend/app/portfolio/ledger.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/portfolio/ledger.py)
- **Full Verbatim Prompt**:
```text
Implement a Virtual Sub-Ledger system (`VirtualLedgerManager`) for Level 4 multi-strategy execution on a single account.

SCENARIO:
- Strategy #1 (Moving Average Crossover) goes LONG 100 shares of INFY at ₹1,400.
- Strategy #2 (Breakout Short) goes SHORT 100 shares of INFY at ₹1,410.
- Broker Account Net Position: 0 shares.

LEDGER REQUIREMENTS:
1. Virtual Position Decoupling:
   - Strategy #1 ledger tracks: Net Qty = +100, Avg Price = ₹1,400, Realized P&L, Unrealized P&L based on LTP.
   - Strategy #2 ledger tracks: Net Qty = -100, Avg Price = ₹1,410, Realized P&L, Unrealized P&L based on LTP.
2. Isolated Risk Limits: Max position limit for Strategy #1 is evaluated against its virtual +100 qty, NOT the broker net 0 qty.
3. Test Coverage: Write unit tests in `test_strategies.py` asserting concurrent long/short virtual P&L tracking.
```

### Prompt 4.2: Strategy Customization Studio & Parameter Engine

- **Target File**: [`backend/app/strategies/base.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/app/strategies/base.py)
- **Full Verbatim Prompt**:
```text
Build a modular Strategy Parameter Engine allowing users to customize and tune strategies via REST API / UI.

PARAMETERS SUPPORTED:
- Fast SMA Period (e.g. 5 to 50)
- Slow SMA Period (e.g. 20 to 200)
- Breakout Threshold % (e.g. 0.5% to 5.0%)
- Stop Loss % (e.g. 0.5% to 10.0%)
- Take Profit % (e.g. 1.0% to 20.0%)
- Trailing Stop Loss %
- Trade Direction Allowed: `LONG_ONLY`, `SHORT_ONLY`, `BOTH`
- Execution Quantity & Max Allocation ₹ Amount

Provide validation schemas preventing invalid parameters (e.g. Fast SMA >= Slow SMA).
```

---

## 6. Chaos Testing & Judge Failure Verification Prompts

### Prompt 5.1: Judge Failure & Chaos Scenario Simulator

- **Target File**: [`backend/scripts/demo_chaos_scenarios.py`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/scripts/demo_chaos_scenarios.py)
- **Full Verbatim Prompt**:
```text
Write an interactive CLI Chaos Simulator script (`demo_chaos_scenarios.py`) for hackathon judges to verify platform resilience under failure conditions.

SCENARIOS TO SIMULATE & PRINT:
1. Scenario 1 (Sandbox HTTP 500/503 Failures): Inject 40% random HTTP server errors into 021 broker calls. Show automatic client retries succeeding without crashing the platform.
2. Scenario 2 (Runaway Strategy Spam Loop): Launch a buggy strategy emitting 50 order intents in 2 seconds. Show Level 3 Risk Gate throttling after 5 orders and auto-halting the runaway algo.
3. Scenario 3 (Mid-Trade Process Crash & Recovery): Execute active trades, issue process `kill -9` signal, restart service, and demonstrate `RecoveryReconciler` clearing position drift and orphan orders.
4. Scenario 4 (Global Kill Switch Sub-10s SLA): Trigger `GLOBAL` kill switch under 20 active open orders and print exact millisecond execution time (< 500ms).

Format console output with ANSI colors, step headers, and final PASS/FAIL summary table.
```

### Prompt 5.2: Automated Pytest Suite Generation (46 Unit & Integration Tests)

- **Target Directory**: [`backend/tests/`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/backend/tests)
- **Full Verbatim Prompt**:
```text
Create a comprehensive test suite across unit, integration, and failure directories targeting 100% pass rate.

TEST MODULES REQUIRED:
- `test_candle_decoder.py`: Binary unpacking of TC 1, 2, 3 and 1m/5m candle aggregator boundaries.
- `test_contract_note.py`: Integer paise statutory charge breakdown matching SEBI tax tables.
- `test_execution_engine.py`: Order lifecycle transitions and partial fill math.
- `test_recovery.py`: State reconciler position drift detection and orphan order cleanup.
- `test_risk_engine.py`: Max daily loss auto-halt, position limit block, rate limiter, and sub-10s kill switch SLA.
- `test_strategies.py`: L4 virtual sub-ledger isolation with opposing long/short positions.
```

---

## 7. Frontend Terminal & User Experience Prompts

### Prompt 6.1: Real-Time Quantitative Trading Terminal UI

- **Target File**: [`frontend/src/routes/_app.strategies.$id.tsx`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/frontend/src/routes/_app.strategies.$id.tsx)
- **Full Verbatim Prompt**:
```text
Design a dark-mode quantitative trading terminal interface in React 18 + Vite + TypeScript.

UI PANELS REQUIRED:
1. Strategy Header: Live status pill (RUNNING, HALTED, QUARANTINED), P&L badge (green/red), active capital allocation.
2. Customization Studio: Interactive sliders for Fast/Slow SMA, Stop Loss %, Take Profit %, and segmented buttons for Trade Direction (`LONG_ONLY`, `SHORT_ONLY`, `BOTH`).
3. Order Book & Execution Log: Live order table with side badges, fill status, and itemized SEBI tax breakdown drawer on click.
4. Risk Monitor Widget: Real-time gauge for Daily Loss limit utilization (e.g. ₹3,400 / ₹10,000 used) and order rate counter.
```

### Prompt 6.2: Institutional Kill Switch Control Matrix & Modal UI

- **Target File**: [`frontend/src/components/tm/StrategyCustomizerModal.tsx`](file:///c:/Users/karti/OneDrive/Desktop/codecell/Syrus7_Midnight_Coders/frontend/src/components/tm/StrategyCustomizerModal.tsx)
- **Full Verbatim Prompt**:
```text
Build a prominent emergency Kill Switch modal with multi-scope selector and double-confirmation safety.

FEATURES:
1. Scope Radios: `GLOBAL` (liquidate all), `CANCEL_ONLY` (cancel open orders only), `STRATEGY` (quarantine selected algo), `SYMBOL` (freeze ticker).
2. Lockout Duration Selector: 5 Min, 15 Min, 30 Min, or Manual Unlock.
3. Confirmation Step: Requires typing "HALT" or clicking red primary action button to prevent accidental clicks.
4. Sub-second feedback toast showing total orders cancelled and SLA execution time.
```

---

## 8. AI Audit, Verification & Human-in-the-Loop Refinement Log

| Iteration # | Target Module | Initial AI Output | Human Code Audit Finding | Refactored Verbatim Prompt / Solution |
| :--- | :--- | :--- | :--- | :--- |
| **Iter 1** | Contract Note | Standard Python float division (`0.0003 * turnover`) | Floating point precision errors ($\pm 0.02$ paise discrepancy) | Re-prompted: "Rewrite using integer arithmetic in paise (`Turnover_Paise * 3 // 10000`). Round statutory taxes according to SEBI rounding rules." |
| **Iter 2** | Kill Switch SLA | Sequential cancellation loop over open orders (`for o in orders: cancel(o)`) | Execution took 4.2 seconds under 30 active orders | Re-prompted: "Refactor cancellation execution using `asyncio.gather(*[cancel(o) for o in orders])` for concurrent dispatch." Execution reduced to 180ms. |
| **Iter 3** | Candle Aggregator | Ticks at `XX:XX:00.000` were placed into old minute candle | Caused minute boundary volume leak | Re-prompted: "Enforce strict timestamp comparison `tick.timestamp >= next_minute_boundary` to emit closed candle before appending tick to new candle." |
| **Iter 4** | Risk Gate | Strategy could bypass risk check by instantiating raw REST client | Violated core hackathon problem statement | Re-prompted: "Enforce strict dependency injection where broker client credentials are private to the Risk Gate and unavailable to Strategy classes." |

---

*TradeShield — Complete Verbatim AI Prompting Record generated for 021 Trade Hackathon (Syrus 2026).*
