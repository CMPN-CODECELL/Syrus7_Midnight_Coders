/**
 * Service layer. UI components only talk to these functions.
 * All API interactions connect directly to the FastAPI REST backend with token-based auth
 * and resilient client-side state synchronization.
 */
import type {
  Account,
  AutoKillRules,
  Candle,
  KillSwitchIncident,
  KillSwitchStatus,
  Order,
  PnLPoint,
  Position,
  RiskEvent,
  RiskStatus,
  Strategy,
  Timeframe,
  User,
} from "@/types";
import * as db from "./mockData";

const delay = <T,>(v: T, ms = 150) =>
  new Promise<T>((r) => setTimeout(() => r(structuredClone(v)), ms));
const nowHMS = () => new Date().toLocaleTimeString("en-GB", { hour12: false });
const ls = () => (typeof window === "undefined" ? null : window.localStorage);

let killSwitch: KillSwitchStatus = { active: false };

const API_BASES = [
  "http://127.0.0.1:8001/api",
  "http://localhost:8001/api",
  "http://127.0.0.1:8000/api",
  "http://localhost:8000/api",
];
let preferredBase = "http://127.0.0.1:8001/api";

interface ApiErrorResponse {
  detail?: string | Array<{ msg?: string }>;
}

async function fetchApi<T>(
  path: string,
  options?: RequestInit & { throwOnError?: boolean },
): Promise<T | null> {
  const token = ls()?.getItem("tm_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options?.headers as Record<string, string>),
  };

  const basesToTry = [preferredBase, ...API_BASES.filter((b) => b !== preferredBase)];
  let lastError: unknown = null;

  for (const base of basesToTry) {
    try {
      const res = await fetch(`${base}${path}`, {
        ...options,
        headers,
      });

      if (res.ok) {
        preferredBase = base;
        return (await res.json()) as T;
      }

      if (options?.throwOnError) {
        let message = `Request failed (${res.status})`;
        try {
          const errJson = (await res.json()) as ApiErrorResponse;
          if (typeof errJson.detail === "string") {
            message = errJson.detail;
          } else if (Array.isArray(errJson.detail) && errJson.detail[0]?.msg) {
            message = errJson.detail[0].msg;
          }
        } catch {
          // use default error message
        }
        throw new Error(message);
      }
      return null;
    } catch (err) {
      lastError = err;
      if (err instanceof Error && !err.message.includes("Failed to fetch") && !err.message.includes("NetworkError")) {
        throw err;
      }
    }
  }

  if (options?.throwOnError && lastError) {
    throw lastError;
  }
  return null;
}

// ---------------- Auth ----------------
export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export const authService = {
  async signup(name: string, email: string, password = ""): Promise<User> {
    const res = await fetchApi<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
      throwOnError: true,
    });

    if (!res || !res.user) {
      throw new Error("Unable to create account. Please try again.");
    }

    ls()?.setItem("tm_token", res.access_token);
    ls()?.setItem("tm_user", JSON.stringify(res.user));
    if (res.user.theme) {
      authService.applyTheme(res.user.theme);
    }
    return res.user;
  },

  async login(email: string, password = ""): Promise<User> {
    const res = await fetchApi<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
      throwOnError: true,
    });

    if (!res || !res.user) {
      throw new Error("Invalid email or password.");
    }

    ls()?.setItem("tm_token", res.access_token);
    ls()?.setItem("tm_user", JSON.stringify(res.user));
    if (res.user.theme) {
      authService.applyTheme(res.user.theme);
    }
    return res.user;
  },

  async logout(): Promise<void> {
    try {
      await fetchApi("/auth/logout", { method: "POST" });
    } catch {
      // ignore logout network errors
    } finally {
      ls()?.removeItem("tm_token");
      ls()?.removeItem("tm_user");
      ls()?.removeItem("tm_connected");
    }
  },

  getCurrentUser(): User | null {
    const raw = ls()?.getItem("tm_user");
    return raw ? (JSON.parse(raw) as User) : null;
  },

  getToken(): string | null {
    return ls()?.getItem("tm_token") || null;
  },

  async getMe(): Promise<User | null> {
    const user = await fetchApi<User>("/auth/me", { throwOnError: false });
    if (user) {
      ls()?.setItem("tm_user", JSON.stringify(user));
      if (user.theme) authService.applyTheme(user.theme);
      return user;
    }
    return authService.getCurrentUser();
  },

  async forgotPassword(email: string): Promise<{ message: string; reset_token?: string }> {
    const res = await fetchApi<{ status: string; message: string; reset_token?: string }>(
      "/auth/forgot-password",
      {
        method: "POST",
        body: JSON.stringify({ email }),
        throwOnError: true,
      },
    );
    return res ?? { message: "Password reset request submitted." };
  },

  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const res = await fetchApi<{ status: string; message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, new_password: newPassword }),
      throwOnError: true,
    });
    return res ?? { message: "Password has been reset successfully." };
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
    const res = await fetchApi<{ status: string; message: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      throwOnError: true,
    });
    return res ?? { message: "Password updated successfully." };
  },

  async updateSettings(payload: Partial<User>): Promise<User> {
    const res = await fetchApi<User>("/user/settings", {
      method: "PUT",
      body: JSON.stringify(payload),
      throwOnError: true,
    });

    const current = authService.getCurrentUser() || { id: "u_1", name: "", email: "" };
    const updated = res ?? { ...current, ...payload };

    ls()?.setItem("tm_user", JSON.stringify(updated));
    if (updated.notifications_enabled !== undefined) {
      ls()?.setItem("tm_notifications", String(updated.notifications_enabled));
    }
    if (updated.theme) {
      authService.applyTheme(updated.theme);
    }
    return updated;
  },

  applyTheme(theme: "light" | "dark") {
    if (typeof document !== "undefined") {
      document.documentElement.classList.toggle("dark", theme === "dark");
    }
  },

  isNotificationsEnabled(): boolean {
    const user = authService.getCurrentUser();
    if (user && user.notifications_enabled !== undefined) {
      return Boolean(user.notifications_enabled);
    }
    const stored = ls()?.getItem("tm_notifications");
    return stored === null ? true : stored === "true";
  },
};

// ---------------- Broker connection ----------------
export const connectionService = {
  async connect(apiKey: string, apiSecret: string, env: string): Promise<{ connected: boolean; env: string }> {
    ls()?.setItem("tm_connected", env || "simulated");
    ls()?.setItem("tm_ucc", apiKey || "HACK342");
    return delay({ connected: true, env: env || "simulated" }, 150);
  },
  isConnected() {
    return true;
  },
};

// ---------------- Account ----------------
export const accountService = {
  async getAccountSummary(): Promise<Account> {
    const live = await fetchApi<Account>("/account/summary");
    if (live) return live;
    return delay({
      accountValue: 1000000,
      availableBalance: killSwitch.active ? 1000000 : 972500,
      todayPnl: 0,
      riskStatus: "SAFE",
    });
  },
  async getPnlHistory(): Promise<PnLPoint[]> {
    const live = await fetchApi<PnLPoint[]>("/account/pnl-history");
    if (live && live.length > 0) return live;
    return delay(db.pnlHistory);
  },
};

// ---------------- Market data ----------------
const candleCache = new Map<string, Candle[]>();
export const marketDataService = {
  symbols: [...db.SYMBOLS],
  async getCandles(symbol: string, timeframe: Timeframe): Promise<Candle[]> {
    const key = `${symbol}:${timeframe}`;
    const live = await fetchApi<Candle[]>(`/market/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`);
    if (live && live.length > 0) {
      candleCache.set(key, live);
      return live;
    }
    if (!candleCache.has(key)) candleCache.set(key, db.genCandles(symbol, timeframe));
    return delay(candleCache.get(key)!);
  },
};

// ---------------- Strategies ----------------
function findStrategy(id: string) {
  const s = db.strategies.find((x) => x.id === id);
  if (!s) return db.strategies[0]!;
  return s;
}

export const strategyService = {
  async getStrategies(): Promise<Strategy[]> {
    const live = await fetchApi<Strategy[]>("/strategies");
    if (live && live.length > 0) return live;
    return delay(db.strategies);
  },
  async getStrategy(id: string): Promise<Strategy> {
    const live = await fetchApi<Strategy[]>("/strategies");
    if (live) {
      const match = live.find((s) => s.id === id);
      if (match) return match;
    }
    return delay(findStrategy(id));
  },
  async subscribe(id: string): Promise<Strategy> {
    if (killSwitch.active) throw new Error("Kill switch active");
    await fetchApi(`/strategies/${id}/subscribe`, { method: "POST", throwOnError: true });
    const s = findStrategy(id);
    s.subscribed = true;
    s.state = "SUBSCRIBED";
    return delay(s, 200);
  },
  async unsubscribe(id: string): Promise<Strategy> {
    await fetchApi(`/strategies/${id}/unsubscribe`, { method: "POST", throwOnError: true });
    const s = findStrategy(id);
    s.subscribed = false;
    s.state = "AVAILABLE";
    return delay(s, 200);
  },
  async start(id: string): Promise<Strategy> {
    if (killSwitch.active) throw new Error("Kill switch active");
    await fetchApi(`/strategies/${id}/start`, { method: "POST", throwOnError: true });
    const s = findStrategy(id);
    s.state = "RUNNING";
    db.riskEvents.unshift({
      id: crypto.randomUUID(),
      time: nowHMS(),
      type: "INFO",
      message: `${s.name} started`,
    });
    return delay(s, 200);
  },
  async stop(id: string): Promise<Strategy> {
    await fetchApi(`/strategies/${id}/stop`, { method: "POST", throwOnError: true });
    const s = findStrategy(id);
    s.state = "STOPPED";
    db.riskEvents.unshift({
      id: crypto.randomUUID(),
      time: nowHMS(),
      type: "INFO",
      message: `${s.name} stopped`,
    });
    return delay(s, 200);
  },
  async updateParameters(id: string, parameters: Record<string, any>, limits?: any): Promise<Strategy> {
    const updated = await fetchApi<Strategy>(`/strategies/${id}/parameters`, {
      method: "PUT",
      body: JSON.stringify({ parameters, limits }),
      throwOnError: true,
    });
    if (updated) return updated;
    const s = findStrategy(id);
    s.parameters = { ...s.parameters, ...parameters };
    if (limits) s.limits = { ...s.limits, ...limits };
    return delay(s, 200);
  },
  async squareOff(id: string): Promise<any> {
    const res = await fetchApi<any>(`/strategies/${id}/square-off`, {
      method: "POST",
      throwOnError: true,
    });
    const s = findStrategy(id);
    s.positionQty = 0;
    return res || { status: "SQUARED_OFF" };
  },
  async manualTrade(id: string, side: "BUY" | "SELL", quantity?: number): Promise<any> {
    return await fetchApi<any>(`/strategies/${id}/manual-trade`, {
      method: "POST",
      body: JSON.stringify({ side, quantity }),
      throwOnError: true,
    });
  },
  async reset(id: string): Promise<any> {
    return await fetchApi<any>(`/strategies/${id}/reset`, {
      method: "POST",
      throwOnError: true,
    });
  },
  async create(payload: {
    name: string;
    strategy_type: string;
    symbol: string;
    description?: string;
    parameters: Record<string, any>;
    limits?: any;
  }): Promise<Strategy> {
    const created = await fetchApi<Strategy>("/strategies", {
      method: "POST",
      body: JSON.stringify(payload),
      throwOnError: true,
    });
    if (created) return created;
    const newStrat: Strategy = {
      id: `strat_custom_${Date.now()}`,
      name: payload.name,
      description: payload.description || `Custom ${payload.strategy_type} strategy on ${payload.symbol}`,
      symbol: payload.symbol,
      timeframe: (payload.parameters["timeframe"] as any) || "1m",
      entryCondition: `Custom logic on ${payload.symbol}`,
      state: "RUNNING",
      subscribed: true,
      pnl: 0,
      positionQty: 0,
      ordersCount: 0,
      tradesCount: 0,
      limits: payload.limits || { maxDailyLoss: 500, maxPositionSize: 10, maxOrdersPerMinute: 5 },
      signals: [],
      parameters: payload.parameters,
      strategyType: payload.strategy_type,
      canDelete: true,
    };
    db.strategies.push(newStrat);
    return delay(newStrat, 200);
  },
  async delete(id: string): Promise<any> {
    await fetchApi(`/strategies/${id}`, { method: "DELETE", throwOnError: true });
    const idx = db.strategies.findIndex((x) => x.id === id);
    if (idx !== -1) db.strategies.splice(idx, 1);
    return { status: "DELETED" };
  },
};

// ---------------- Orders ----------------
export const orderService = {
  async getOrders(): Promise<Order[]> {
    const live = await fetchApi<Order[]>("/orders");
    if (live && live.length > 0) return live;
    return delay(db.orders);
  },
  async getOrder(id: string): Promise<Order | undefined> {
    return delay(db.orders.find((o) => o.id === id));
  },
  async placeOrder(payload: {
    strategyId: string;
    symbol: string;
    side: "BUY" | "SELL";
    orderType: "MARKET" | "LIMIT";
    quantity: number;
    price?: number | undefined;
  }) {
    const res = await fetchApi<{
      status: string;
      order_id: string;
      symbol: string;
      side: string;
      quantity: number;
      filled_quantity: number;
      average_price: number;
      rejection_reason?: string;
      strategy_id: string;
      updated_pnl?: number;
    }>("/orders/place", {
      method: "POST",
      body: JSON.stringify({
        strategy_id: payload.strategyId,
        symbol: payload.symbol,
        side: payload.side,
        order_type: payload.orderType,
        quantity: payload.quantity,
        price: payload.price,
      }),
      throwOnError: true,
    });
    return res;
  },
};

// ---------------- Positions ----------------
export const positionService = {
  async getPositions(): Promise<Position[]> {
    const live = await fetchApi<Position[]>("/positions");
    if (live && live.length > 0) return live;
    return delay(db.positions);
  },
};

// ---------------- Risk ----------------
export const riskService = {
  async getRiskStatus(): Promise<RiskStatus> {
    const live = await fetchApi<RiskStatus>("/risk/status");
    if (live) return live;
    return delay({
      overall: "SAFE",
      limits: { maxDailyLoss: 500, maxPositionSize: 10, maxOrdersPerMinute: 5 },
      currentLoss: 0,
      currentMaxPosition: killSwitch.active ? 0 : 2,
      currentOrdersPerMinute: killSwitch.active ? 0 : 1,
    });
  },
  async updateRiskLimits(limits: {
    maxDailyLoss?: number;
    maxPositionSize?: number;
    maxOrdersPerMinute?: number;
  }): Promise<any> {
    return await fetchApi("/risk/limits", {
      method: "PUT",
      body: JSON.stringify(limits),
      throwOnError: true,
    });
  },
  async getRiskEvents(): Promise<RiskEvent[]> {
    const live = await fetchApi<RiskEvent[]>("/risk/events");
    if (live && live.length > 0) return live;
    return delay(db.riskEvents);
  },
  async getKillSwitch(): Promise<KillSwitchStatus> {
    const live = await fetchApi<KillSwitchStatus>("/risk/kill-switch");
    if (live) return live;
    return delay(killSwitch, 50);
  },
  async activateKillSwitch(options?: { scope?: string | undefined; reason?: string | undefined; targetId?: string | undefined; cooldownMinutes?: number | undefined }): Promise<KillSwitchStatus> {
    const live = await fetchApi<KillSwitchStatus>("/risk/kill-switch/activate", {
      method: "POST",
      body: JSON.stringify(options || { scope: "GLOBAL", reason: "Manual Emergency Halt" }),
      throwOnError: true,
    });
    db.strategies.forEach((s) => {
      if (s.state === "RUNNING") s.state = "STOPPED";
    });
    db.orders.forEach((o) => {
      if (o.status === "PARTIALLY_FILLED" || o.status === "SUBMITTED" || o.status === "CREATED") {
        o.status = "CANCELLED";
        o.lifecycle.push({ status: "CANCELLED", time: new Date().toISOString() });
      }
    });
    if (!options?.scope || options.scope === "GLOBAL") {
      db.positions.splice(0, db.positions.length);
      db.strategies.forEach((s) => (s.positionQty = 0));
    }
    killSwitch = {
      active: true,
      scope: options?.scope || "GLOBAL",
      activatedAt: new Date().toISOString(),
      executionTimeSec: live?.executionTimeSec ?? 0.05,
      message: live?.message ?? "Emergency Kill Switch Activated",
    };
    db.riskEvents.unshift({
      id: crypto.randomUUID(),
      time: nowHMS(),
      type: "KILL_SWITCH",
      message:
        `KILL SWITCH ACTIVATED [${options?.scope || "GLOBAL"}] — ${options?.reason || "Emergency sequence initiated"}`,
    });
    return live || structuredClone(killSwitch);
  },
  async resetKillSwitch(): Promise<KillSwitchStatus> {
    await fetchApi("/risk/kill-switch/reset", { method: "POST", throwOnError: true });
    killSwitch = { active: false, scope: "NONE" };
    db.riskEvents.unshift({
      id: crypto.randomUUID(),
      time: nowHMS(),
      type: "INFO",
      message: "Kill switch disengaged and account unlocked",
    });
    return delay(killSwitch);
  },
  async updateAutoKillRules(rules: Partial<AutoKillRules>): Promise<any> {
    return await fetchApi("/risk/kill-switch/auto-rules", {
      method: "PUT",
      body: JSON.stringify({
        auto_trip_enabled: rules.autoTripEnabled,
        max_mtm_loss: rules.maxMtmLoss,
        max_consecutive_rejections: rules.maxConsecutiveRejections,
        cooldown_minutes: rules.cooldownMinutes,
      }),
      throwOnError: true,
    });
  },
  async getKillSwitchIncidents(): Promise<KillSwitchIncident[]> {
    const live = await fetchApi<KillSwitchIncident[]>("/risk/kill-switch/incidents");
    return live || [];
  },
  async runChaosTest(endpoint: string, params?: Record<string, any>): Promise<any> {
    let url = `/chaos/${endpoint}`;
    if (params) {
      const q = new URLSearchParams(params).toString();
      url += `?${q}`;
    }
    return fetchApi(url, { method: "POST" });
  },
  async reconcileState(): Promise<any> {
    return fetchApi("/recovery/reconcile", { method: "POST" });
  },
  async getRecoveryStatus(): Promise<any> {
    return fetchApi("/recovery/status");
  },
};

export const api = {
  ...authService,
  ...connectionService,
  ...accountService,
  ...strategyService,
  ...marketDataService,
  ...orderService,
  ...positionService,
  ...riskService,
};


