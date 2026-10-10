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
    const res = await fetchApi<{ connected: boolean; environment: string }>("/broker/connect", {
      method: "POST",
      body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret, environment: env }),
    });
    ls()?.setItem("tm_connected", env || "simulated");
    ls()?.setItem("tm_ucc", apiKey || "HACK342");
    return res ? { connected: res.connected, env: res.environment } : { connected: true, env: env || "simulated" };
  },
  isConnected() {
    return Boolean(ls()?.getItem("tm_connected"));
  },
};

// ---------------- Account ----------------
export const accountService = {
  async getAccountSummary(): Promise<Account> {
    const live = await fetchApi<Account>("/account/summary");
    return live || {
      accountValue: 1000000,
      availableBalance: 1000000,
      todayPnl: 0,
      riskStatus: "SAFE",
    };
  },
  async getPnlHistory(): Promise<PnLPoint[]> {
    const live = await fetchApi<PnLPoint[]>("/account/pnl-history");
    return live || [];
  },
};

// ---------------- Market data ----------------
const candleCache = new Map<string, Candle[]>();
export const marketDataService = {
  symbols: ["RELIANCE", "TCS", "INFY", "HDFCBANK", "TATAMOTORS", "NIFTY50"],
  async getInstruments(): Promise<any[]> {
    const live = await fetchApi<any[]>("/market/instruments");
    return live || [];
  },
  async getCandles(symbol: string, timeframe: Timeframe): Promise<Candle[]> {
    const key = `${symbol}:${timeframe}`;
    const live = await fetchApi<Candle[]>(`/market/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`);
    if (live && live.length > 0) {
      candleCache.set(key, live);
      return live;
    }
    return candleCache.get(key) || [];
  },
};

// ---------------- Strategies ----------------
export const strategyService = {
  async getStrategies(): Promise<Strategy[]> {
    const live = await fetchApi<Strategy[]>("/strategies");
    return live || [];
  },
  async getStrategy(id: string): Promise<Strategy> {
    const live = await fetchApi<Strategy[]>("/strategies");
    if (live) {
      const match = live.find((s) => s.id === id);
      if (match) return match;
    }
    throw new Error(`Strategy ${id} not found`);
  },
  async subscribe(id: string): Promise<Strategy> {
    const res = await fetchApi<Strategy>(`/strategies/${id}/subscribe`, { method: "POST", throwOnError: true });
    return res || (await strategyService.getStrategy(id));
  },
  async unsubscribe(id: string): Promise<Strategy> {
    const res = await fetchApi<Strategy>(`/strategies/${id}/unsubscribe`, { method: "POST", throwOnError: true });
    return res || (await strategyService.getStrategy(id));
  },
  async start(id: string): Promise<Strategy> {
    const res = await fetchApi<Strategy>(`/strategies/${id}/start`, { method: "POST", throwOnError: true });
    return res || (await strategyService.getStrategy(id));
  },
  async stop(id: string): Promise<Strategy> {
    const res = await fetchApi<Strategy>(`/strategies/${id}/stop`, { method: "POST", throwOnError: true });
    return res || (await strategyService.getStrategy(id));
  },
  async updateParameters(id: string, parameters: Record<string, any>, limits?: any): Promise<Strategy> {
    const updated = await fetchApi<Strategy>(`/strategies/${id}/parameters`, {
      method: "PUT",
      body: JSON.stringify({ parameters, limits }),
      throwOnError: true,
    });
    return updated || (await strategyService.getStrategy(id));
  },
  async squareOff(id: string): Promise<any> {
    return await fetchApi<any>(`/strategies/${id}/square-off`, {
      method: "POST",
      throwOnError: true,
    });
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
    return created!;
  },
  async delete(id: string): Promise<any> {
    return await fetchApi(`/strategies/${id}`, { method: "DELETE", throwOnError: true });
  },
};

// ---------------- Orders ----------------
export const orderService = {
  async getOrders(): Promise<Order[]> {
    const live = await fetchApi<Order[]>("/orders");
    return live || [];
  },
  async getOrder(id: string): Promise<Order | undefined> {
    const orders = await fetchApi<Order[]>("/orders");
    if (orders) {
      return orders.find((o) => o.id === id);
    }
    return undefined;
  },
  async placeOrder(payload: {
    strategyId: string;
    symbol: string;
    side: "BUY" | "SELL";
    orderType: "MARKET" | "LIMIT";
    quantity: number;
    price?: number | undefined;
  }) {
    return await fetchApi<{
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
  },
};

// ---------------- Positions ----------------
export const positionService = {
  async getPositions(): Promise<Position[]> {
    const live = await fetchApi<Position[]>("/positions");
    return live || [];
  },
};

// ---------------- Risk ----------------
export const riskService = {
  async getRiskStatus(): Promise<RiskStatus> {
    const live = await fetchApi<RiskStatus>("/risk/status");
    return live || {
      overall: "SAFE",
      limits: { maxDailyLoss: 500, maxPositionSize: 10, maxOrdersPerMinute: 5 },
      currentLoss: 0,
      currentMaxPosition: 0,
      currentOrdersPerMinute: 0,
    };
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
    return live || [];
  },
  async getKillSwitch(): Promise<KillSwitchStatus> {
    const live = await fetchApi<KillSwitchStatus>("/risk/kill-switch");
    return live || { active: false, scope: "NONE" };
  },
  async activateKillSwitch(options?: { scope?: string | undefined; reason?: string | undefined; targetId?: string | undefined; cooldownMinutes?: number | undefined }): Promise<KillSwitchStatus> {
    const live = await fetchApi<KillSwitchStatus>("/risk/kill-switch/activate", {
      method: "POST",
      body: JSON.stringify(options || { scope: "GLOBAL", reason: "Manual Emergency Halt" }),
      throwOnError: true,
    });
    return live || { active: true, scope: options?.scope || "GLOBAL" };
  },
  async resetKillSwitch(): Promise<KillSwitchStatus> {
    const live = await fetchApi<KillSwitchStatus>("/risk/kill-switch/reset", { method: "POST", throwOnError: true });
    return live || { active: false, scope: "NONE" };
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

export const subscriptionService = {
  async getPlans(): Promise<any[]> {
    const res = await fetchApi<any[]>("/subscriptions/plans");
    return res || [];
  },
  async buySubscription(payload: {
    plan_code?: string;
    strategy_id?: string;
    billing_cycle?: string;
    payment_method?: string;
  }): Promise<any> {
    return await fetchApi("/subscriptions/buy", {
      method: "POST",
      body: JSON.stringify(payload),
      throwOnError: true,
    });
  },
  async cancelSubscription(subscriptionId: number): Promise<any> {
    return await fetchApi("/subscriptions/cancel", {
      method: "POST",
      body: JSON.stringify({ subscription_id: subscriptionId }),
      throwOnError: true,
    });
  },
  async getTransactions(): Promise<any[]> {
    const res = await fetchApi<any[]>("/subscriptions/transactions");
    return res || [];
  },
  async topupWallet(amountInr: number, paymentMethod = "UPI"): Promise<any> {
    return await fetchApi("/user/wallet/topup", {
      method: "POST",
      body: JSON.stringify({ amount_inr: amountInr, payment_method: paymentMethod }),
      throwOnError: true,
    });
  },
};

export const userService = {
  async getUsers(search?: string, role?: string): Promise<any> {
    let url = "/users";
    const q: string[] = [];
    if (search) q.push(`search=${encodeURIComponent(search)}`);
    if (role) q.push(`role=${encodeURIComponent(role)}`);
    if (q.length > 0) url += `?${q.join("&")}`;
    const res = await fetchApi<any>(url);
    return res || { users: [], total: 0 };
  },
  async createUser(payload: {
    name: string;
    email: string;
    password: string;
    role?: string;
    initial_balance_inr?: number;
    subscription_tier?: string;
  }): Promise<User> {
    const res = await fetchApi<User>("/users", {
      method: "POST",
      body: JSON.stringify(payload),
      throwOnError: true,
    });
    return res!;
  },
  async updateUser(userId: string, payload: Record<string, any>): Promise<User> {
    const res = await fetchApi<User>(`/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
      throwOnError: true,
    });
    return res!;
  },
  async deleteUser(userId: string): Promise<any> {
    return await fetchApi(`/users/${userId}`, {
      method: "DELETE",
      throwOnError: true,
    });
  },
};

export const paymentService = {
  async createRazorpayOrder(amountInr: number, purpose = "Strategy Pass Subscription", strategyId?: string): Promise<any> {
    return await fetchApi("/payments/razorpay/create-order", {
      method: "POST",
      body: JSON.stringify({ amount_inr: amountInr, purpose, strategy_id: strategyId }),
      throwOnError: true,
    });
  },
  async verifyRazorpayPayment(payload: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
    amount_inr: number;
    purpose?: string;
    strategy_id?: string;
    billing_email?: string;
  }): Promise<any> {
    return await fetchApi("/payments/razorpay/verify-payment", {
      method: "POST",
      body: JSON.stringify(payload),
      throwOnError: true,
    });
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
  ...subscriptionService,
  ...userService,
  ...paymentService,
};



