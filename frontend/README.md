# TradeMint Trading Terminal — Frontend

[![React](https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6.0-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![TanStack Router](https://img.shields.io/badge/TanStack_Router-1.0-FF4154?style=for-the-badge&logo=react&logoColor=white)](https://tanstack.com/router)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](../LICENSE)

Institutional algorithmic trading web terminal for the **TradeShield / TradeMint** platform. Built with React 18, Vite 6, TypeScript, TanStack Router, and Tailwind CSS. Features real-time market data streaming, dynamic strategy parameter tuning, multi-scope risk controls, SEBI Rule 15 contract notes, and automated email statement dispatching.

---

## 📸 Interface Preview

| Live Trading Dashboard | Risk Controls & Chaos Lab |
| :---: | :---: |
| ![TradeMint Terminal](../backend/trademint%20ss.png) | ![TradeMint Controls](../backend/trademint%20ss1.png) |

---

## 📑 Table of Contents
1. [Core Features & UI Modules](#-core-features--ui-modules)
2. [Interactive Modals & Dialogs](#-interactive-modals--dialogs)
3. [Component & Route Directory Structure](#-component--route-directory-structure)
4. [Technology Stack](#-technology-stack)
5. [Setup & Running Locally](#-setup--running-locally)
6. [Production Build & Deployment](#-production-build--deployment)
7. [Environment Configuration](#-environment-configuration)
8. [Services & Backend Integration](#-services--backend-integration)

---

## 🚀 Core Features & UI Modules

### 1. Executive Trading Dashboard (`/dashboard`)
- **Portfolio Telemetry**: Real-time display of Account Value, Available Margin, Gross P&L, Net P&L (after regulatory deductions), and Active Risk Status.
- **Top Action Bar**: Quick button for **"Email P&L"** statement dispatch with recipient selector.
- **Interactive Candlestick Chart**: Real-time 1m & 5m candlestick feed with volume bars powered by Recharts / D3.
- **Strategy Matrix**: Quick cards for `strat_time`, `strat_breakout`, and `strat_ma` with live state indicators.

### 2. Strategy Management Studio (`/strategies`, `/strategies/$id`)
- **Real-Time Strategy Matrix**: Monitor running status, isolated position, gross/net P&L, and trade count for each algorithm.
- **Live Parameter Customizer**: Modal sliders enabling live adjustment of Fast/Slow SMA periods, Breakout % thresholds, Take-Profit %, Stop-Loss %, and Trailing Stop % without restarting the backend.
- **Surgical Square-Off**: Flatten individual strategy positions instantly without affecting other running algorithms.
- **Discretionary Manual Orders**: Place manual buy/sell orders allocated directly to a strategy's isolated ledger.
- **Dynamic Strategy Deployment Wizard**: Deploy new custom algorithmic strategies on demand.

### 3. Order Book & Digital Contract Notes (`/orders`)
- **Lifecycle Tracking**: Real-time order state transition chips (`CREATED` $\rightarrow$ `PLACED` $\rightarrow$ `PARTIALLY_FILLED` $\rightarrow$ `EXECUTED`).
- **SEBI Rule 15 Digital Contract Notes**: Click the **"Contract Note"** button on any filled order to view an itemized breakdown of Brokerage, STT, Exchange Txn Fees, SEBI Turnover Fee, Stamp Duty, and 18% GST calculated using exact integer paise arithmetic.

### 4. Isolated Position Ledgers (`/positions`)
- **Multi-Strategy Exposure Matrix**: Displays individual strategy positions alongside net broker exposure.
- **Opposing Trades Support**: Transparently displays opposing trades (e.g., +5 Long on `RELIANCE` by Strategy A and -5 Short on `RELIANCE` by Strategy B) where internal ledgers maintain distinct P&L while the broker sits net flat.

### 5. Institutional Risk Center & Chaos Lab (`/risk-controls`)
- **Emergency Kill Switch**: Top-bar button opening the Multi-Scope Halt Modal with 4 institutional scopes (`GLOBAL`, `CANCEL_ONLY`, `STRATEGY`, `SYMBOL`), cause selection, and anti-revenge cooling-off lockouts.
- **Auto-Trip Rules Studio**: Configure pre-emptive drawdown limits and broker rejection thresholds.
- **Interactive Chaos Lab**: 1-click failure simulation tests for Partial Fills, Crash Recovery, Runaway Algo Throttling, and Broker 503 Outages.
- **Forensic Incident Audit Log**: Comprehensive, immutable post-mortem incident table with SLA compliance verification.

### 6. User Settings & Razorpay Subscriptions (`/settings`)
- **3-Tier Commercial Paywall**: Plan comparison cards for `Free / Paper`, `Standard Trio`, and `Institutional Pro`.
- **Razorpay Checkout Integration**: Dynamic client checkout flow with real-time payment handling and backend HMAC-SHA256 signature verification.

### 7. Broker Connection Portal (`/connect`)
- Connect and verify credentials for the 021 Trade Developer APIs (UCC: `HACK342`).

---

## 🪟 Interactive Modals & Dialogs

| Modal Component | File Location | Purpose |
| :--- | :--- | :--- |
| **`EmailStatementModal`** | `src/components/tm/EmailStatementModal.tsx` | Triggers live SEBI Rule 15 P&L statement dispatch via SMTP TLS, with real-time telemetry preview, recipient email input, and status badge. |
| **`ContractNoteModal`** | `src/components/tm/ContractNoteModal.tsx` | Renders official SEBI Rule 15 SCRA Digital Contract Note with itemized regulatory charges and paise precision. |
| **`KillSwitch`** | `src/components/tm/KillSwitch.tsx` | Institutional emergency halt modal supporting `GLOBAL`, `CANCEL_ONLY`, `STRATEGY`, and `SYMBOL` halts with cooldown timer. |
| **`StrategyCustomizerModal`** | `src/components/tm/StrategyCustomizerModal.tsx` | Interactive slider modal for tuning SMA periods, breakout thresholds, and risk limits on running algorithms. |
| **`PlaceOrderModal`** | `src/components/tm/PlaceOrderModal.tsx` | Discretionary manual order modal with auto-routing to strategy ledgers. |
| **`CreateStrategyModal`** | `src/components/tm/CreateStrategyModal.tsx` | Step-by-step wizard for deploying new algorithmic strategies. |
| **`ChaosLab`** | `src/components/tm/ChaosLab.tsx` | Interactive resilience test lab for triggering edge-case failures. |

---

## 📁 Component & Route Directory Structure

```
frontend/
├── package.json                    # Project dependencies & scripts
├── vite.config.ts                  # Vite 6 configuration & plugins
├── tsconfig.json                   # TypeScript configuration
├── src/
│   ├── components/tm/              # TradeMint Domain Components
│   │   ├── AuthShell.tsx           # Authentication card wrapper
│   │   ├── ChaosLab.tsx            # Chaos simulation control panel
│   │   ├── ContractNoteModal.tsx   # SEBI digital contract note viewer
│   │   ├── CreateStrategyModal.tsx # Deploy custom strategy modal
│   │   ├── EmailStatementModal.tsx # Automated Email P&L Statement modal
│   │   ├── KillSwitch.tsx          # Multi-scope emergency halt modal
│   │   ├── PlaceOrderModal.tsx     # Manual trade submission dialog
│   │   ├── StrategyControls.tsx    # Strategy card action buttons
│   │   └── StrategyCustomizerModal.tsx # Live parameter tuning sliders
│   ├── routes/                     # TanStack Router File-Based Pages
│   │   ├── __root.tsx              # Root HTML shell & query providers
│   │   ├── _app.tsx                # App layout shell with top navigation
│   │   ├── _app.dashboard.tsx      # Main executive trading dashboard
│   │   ├── _app.strategies.tsx     # Strategy studio & matrix
│   │   ├── _app.strategies._id.tsx # Single strategy telemetry & chart
│   │   ├── _app.orders.tsx         # Real-time order book & contract notes
│   │   ├── _app.positions.tsx      # Position ledgers & net exposures
│   │   ├── _app.markets.tsx        # Market watch & live ticker feed
│   │   ├── _app.risk-controls.tsx  # Risk firewall, kill switch, chaos lab
│   │   ├── _app.settings.tsx       # User profile & Razorpay subscriptions
│   │   ├── connect.tsx             # 021 Broker connection portal
│   │   ├── login.tsx               # User sign-in page
│   │   └── signup.tsx              # User registration page
│   ├── services/                   # API client layer (Axios / Fetch)
│   │   ├── index.ts                # Unified API services export
│   │   ├── api.ts                  # Axios base client with JWT interceptor
│   │   └── tradeshield.ts          # Endpoints for orders, strategies, risk, reports
│   └── types/                      # TypeScript domain models
│       ├── order.ts                # Order, Fill, Contract Note interfaces
│       ├── strategy.ts             # Strategy state & parameter interfaces
│       └── risk.ts                 # Kill switch, incident, & auto-rule types
```

---

## 🛠️ Technology Stack

- **Framework**: [React 18.3](https://react.dev)
- **Bundler & Dev Server**: [Vite 6.0](https://vitejs.dev)
- **Routing**: [TanStack Router / Start](https://tanstack.com/router)
- **Language**: [TypeScript 5.6](https://www.typescriptlang.org)
- **Styling**: [Tailwind CSS 3.4](https://tailwindcss.com)
- **Icons**: [Lucide React](https://lucide.dev)
- **Charts**: [Recharts](https://recharts.org) / D3
- **State & Caching**: [TanStack Query (React Query)](https://tanstack.com/query)

---

## 🚀 Setup & Running Locally

### 1. Prerequisites
- **Node.js**: Version `18.x` or `20.x`+ installed.
- **npm**: Version `9.x`+ installed.

### 2. Installation
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install
```

### 3. Launch Development Server
```bash
npm run dev
```

The web application will be accessible at:
- 🌐 [http://localhost:8081](http://localhost:8081) *(or port indicated by Vite)*

---

## 🏗️ Production Build & Deployment

To validate TypeScript compilation and generate the production distribution bundle:

```bash
npm run build
```

To preview the built production bundle locally:
```bash
npx vite preview
```

---

## ⚙️ Environment Configuration

Frontend environment variables can be configured via `.env` in the `frontend/` directory:

```ini
# Backend API Base URL
VITE_API_BASE_URL=http://localhost:8001
```

If left unset, the API client automatically defaults to `http://localhost:8001` with seamless fallback for local development.

---

## 📡 Services & Backend Integration

The frontend connects to the backend through authenticated REST APIs:

- **Auth**: Automatically injects JWT Bearer tokens stored in `localStorage`.
- **Real-Time Data**: Queries dashboard metrics and orders with automatic cache invalidation on trade actions.
- **Email P&L Statement**: Calls `POST /api/reports/email-statement` sending `recipient_email` and displays live delivery notification toasts.
- **SEBI Contract Notes**: Fetches itemized charges via `GET /api/orders/{id}/contract-note`.
- **Emergency Halt**: Dispatches halt requests to `POST /api/risk/kill-switch/activate` and verifies compliance within the $\le$ 10s SLA guarantee.
