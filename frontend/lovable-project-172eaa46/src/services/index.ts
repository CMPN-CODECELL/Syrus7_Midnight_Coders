/**
 * Service layer. UI components only talk to these functions.
 * Each function is async so the mock implementation can later be swapped for
 * FastAPI REST calls (and WebSocket subscriptions) without touching the UI.
 */
import type {
  Account, Candle, KillSwitchStatus, Order, PnLPoint, Position, RiskEvent, RiskStatus,
  Strategy, Timeframe, User,
} from "@/types";
import * as db from "./mockData";

const delay = <T,>(v: T, ms = 150) => new Promise<T>((r) => setTimeout(() => r(structuredClone(v)), ms));
const nowHMS = () => new Date().toLocaleTimeString("en-GB", { hour12: false });
const ls = () => (typeof window === "undefined" ? null : window.localStorage);

let killSwitch: KillSwitchStatus = { active: false };

// ---------------- Auth ----------------
export const authService = {
  async signup(name: string, email: string, _password: string): Promise<User> {
    const user = { id: "u_1", name, email };
    ls()?.setItem("tm_user", JSON.stringify(user));
    return delay(user, 400);
  },
  async login(email: string, _password: string): Promise<User> {
    const existing = authService.getCurrentUser();
    const user = existing?.email === email ? existing : { id: "u_1", name: "Sahil Mehta", email };
    ls()?.setItem("tm_user", JSON.stringify(user));
    return delay(user, 400);
  },
  logout() {
    ls()?.removeItem("tm_user");
    ls()?.removeItem("tm_connected");
  },
  getCurrentUser(): User | null {
    const raw = ls()?.getItem("tm_user");
    return raw ? (JSON.parse(raw) as User) : null;
  },
};

// ---------------- Broker connection (021 Sandbox) ----------------
export const connectionService = {
  async connect(_apiKey: string, _apiSecret: string, env: string): Promise<{ connected: boolean; env: string }> {
    // Credentials are intentionally discarded in the mock.
    ls()?.setItem("tm_connected", env);
    return delay({ connected: true, env }, 900);
  },
  isConnected() {
    return !!ls()?.getItem("tm_connected");
  },
};

// ---------------- Account ----------------
export const accountService = {
  async getAccountSummary(): Promise<Account> {
    return delay({
      accountValue: 1000000,
      availableBalance: killSwitch.active ? 1000000 : 972500,
      todayPnl: 2450,
      riskStatus: "SAFE",
    });
  },
  async getPnlHistory(): Promise<PnLPoint[]> {
    return delay(db.pnlHistory);
  },
};

// ---------------- Market data ----------------
const candleCache = new Map<string, Candle[]>();
export const marketDataService = {
  symbols: [...db.SYMBOLS],
  async getCandles(symbol: string, timeframe: Timeframe): Promise<Candle[]> {
    const key = `${symbol}:${timeframe}`;
    if (!candleCache.has(key)) candleCache.set(key, db.genCandles(symbol, timeframe));
    return delay(candleCache.get(key)!);
  },
};

// ---------------- Strategies ----------------
function findStrategy(id: string) {
  const s = db.strategies.find((x) => x.id === id);
  if (!s) throw new Error("Strategy not found");
  return s;
}
export const strategyService = {
  async getStrategies(): Promise<Strategy[]> {
    return delay(db.strategies);
  },
  async getStrategy(id: string): Promise<Strategy> {
    return delay(findStrategy(id));
  },
  async subscribe(id: string): Promise<Strategy> {
    if (killSwitch.active) throw new Error("Kill switch active");
    const s = findStrategy(id);
    s.subscribed = true;
    s.state = "SUBSCRIBED";
    return delay(s, 400);
  },
  async start(id: string): Promise<Strategy> {
    if (killSwitch.active) throw new Error("Kill switch active");
    const s = findStrategy(id);
    s.state = "RUNNING";
    db.riskEvents.unshift({ id: crypto.randomUUID(), time: nowHMS(), type: "INFO", message: `${s.name} started` });
    return delay(s, 400);
  },
  async stop(id: string): Promise<Strategy> {
    const s = findStrategy(id);
    s.state = "STOPPED";
    db.riskEvents.unshift({ id: crypto.randomUUID(), time: nowHMS(), type: "INFO", message: `${s.name} stopped` });
    return delay(s, 400);
  },
};

// ---------------- Orders ----------------
export const orderService = {
  async getOrders(): Promise<Order[]> {
    return delay(db.orders);
  },
  async getOrder(id: string): Promise<Order | undefined> {
    return delay(db.orders.find((o) => o.id === id));
  },
};

// ---------------- Positions ----------------
export const positionService = {
  async getPositions(): Promise<Position[]> {
    return delay(db.positions);
  },
};

// ---------------- Risk ----------------
export const riskService = {
  async getRiskStatus(): Promise<RiskStatus> {
    return delay({
      overall: "SAFE",
      limits: { maxDailyLoss: 5000, maxPositionSize: 50, maxOrdersPerMinute: 10 },
      currentLoss: 1250,
      currentMaxPosition: killSwitch.active ? 0 : 20,
      currentOrdersPerMinute: killSwitch.active ? 0 : 4,
    });
  },
  async getRiskEvents(): Promise<RiskEvent[]> {
    return delay(db.riskEvents);
  },
  async getKillSwitch(): Promise<KillSwitchStatus> {
    return delay(killSwitch, 50);
  },
  async activateKillSwitch(): Promise<KillSwitchStatus> {
    await delay(null, 1200);
    db.strategies.forEach((s) => { if (s.state === "RUNNING") s.state = "STOPPED"; });
    db.orders.forEach((o) => {
      if (o.status === "PARTIALLY_FILLED" || o.status === "SUBMITTED" || o.status === "CREATED") {
        o.status = "CANCELLED";
        o.lifecycle.push({ status: "CANCELLED", time: new Date().toISOString() });
      }
    });
    db.positions.splice(0, db.positions.length);
    db.strategies.forEach((s) => (s.positionQty = 0));
    killSwitch = { active: true, activatedAt: new Date().toISOString(), executionTimeSec: 4.3 };
    db.riskEvents.unshift({ id: crypto.randomUUID(), time: nowHMS(), type: "KILL_SWITCH", message: "KILL SWITCH ACTIVATED — strategies stopped, orders cancelled, positions closed" });
    return structuredClone(killSwitch);
  },
  async resetKillSwitch(): Promise<KillSwitchStatus> {
    killSwitch = { active: false };
    db.riskEvents.unshift({ id: crypto.randomUUID(), time: nowHMS(), type: "INFO", message: "Kill switch reset (demo)" });
    return delay(killSwitch);
  },
};
