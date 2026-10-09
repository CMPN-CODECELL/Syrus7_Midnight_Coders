// Centralised mock data. Only services import this file — never UI components.
import type { Candle, Order, PnLPoint, Position, RiskEvent, Strategy, Timeframe } from "@/types";

export const SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK"] as const;
const BASE: Record<string, number> = { RELIANCE: 1424, TCS: 3410, INFY: 1520, HDFCBANK: 1645 };

function rng(seed: number) {
  return () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
}

export function genCandles(symbol: string, tf: Timeframe, count = 120): Candle[] {
  const rand = rng(symbol.length * 977 + (tf === "1m" ? 13 : 71) + symbol.charCodeAt(0));
  const step = tf === "1m" ? 60_000 : 300_000;
  const vol = tf === "1m" ? 0.0012 : 0.0026;
  const end = new Date();
  end.setSeconds(0, 0);
  let price = (BASE[symbol] ?? 1000) * (0.985 + rand() * 0.01);
  const out: Candle[] = [];
  for (let i = count - 1; i >= 0; i--) {
    const open = price;
    const drift = (rand() - 0.48) * vol * 2 * open;
    const close = open + drift;
    const high = Math.max(open, close) + rand() * vol * open;
    const low = Math.min(open, close) - rand() * vol * open;
    out.push({
      timestamp: new Date(end.getTime() - i * step).toISOString(),
      open: +open.toFixed(2),
      high: +high.toFixed(2),
      low: +low.toFixed(2),
      close: +close.toFixed(2),
      volume: Math.round((tf === "1m" ? 8000 : 40000) * (0.5 + rand())),
    });
    price = close;
  }
  return out;
}

export const pnlHistory: PnLPoint[] = (() => {
  const r = rng(42);
  let v = 0;
  const pts: PnLPoint[] = [];
  for (let h = 9; h <= 15; h++) {
    for (const m of [15, 30, 45, 0]) {
      if (h === 9 && m < 15) continue;
      const hh = m === 0 ? h + 1 : h;
      if (hh > 15 || (hh === 15 && m > 30)) continue;
      v += (r() - 0.42) * 400;
      pts.push({ time: `${String(hh).padStart(2, "0")}:${String(m).padStart(2, "0")}`, pnl: Math.round(v) });
    }
  }
  pts[pts.length - 1]!.pnl = 2450;
  return pts;
})();

const defaultLimits = { maxDailyLoss: 5000, maxPositionSize: 50, maxOrdersPerMinute: 10 };

export const strategies: Strategy[] = [
  {
    id: "momentum",
    name: "Momentum Strategy",
    description: "Follows short-term trend strength using moving-average crossovers on liquid large caps.",
    symbol: "RELIANCE",
    timeframe: "1m",
    entryCondition:
      "Generates a BUY signal when the short-term moving average crosses above the long-term moving average.",
    state: "RUNNING",
    subscribed: true,
    pnl: 1250,
    positionQty: 20,
    ordersCount: 6,
    tradesCount: 4,
    limits: { ...defaultLimits },
    signals: [
      { time: "14:42:10", type: "BUY", price: 1424.5, note: "SMA(9) crossed above SMA(21)" },
      { time: "13:18:44", type: "SELL", price: 1419.2, note: "SMA(9) crossed below SMA(21)" },
      { time: "11:05:02", type: "BUY", price: 1412.8, note: "SMA(9) crossed above SMA(21)" },
    ],
  },
  {
    id: "mean-reversion",
    name: "Mean Reversion Strategy",
    description: "Fades stretched moves back toward the rolling mean using Bollinger Band extremes.",
    symbol: "RELIANCE",
    timeframe: "5m",
    entryCondition:
      "Generates a SELL signal when price closes above the upper Bollinger Band (20, 2) and a BUY when it closes below the lower band.",
    state: "RUNNING",
    subscribed: true,
    pnl: -350,
    positionQty: -10,
    ordersCount: 4,
    tradesCount: 2,
    limits: { ...defaultLimits },
    signals: [
      { time: "14:30:00", type: "SELL", price: 1430.0, note: "Close above upper band" },
      { time: "12:10:00", type: "BUY", price: 1411.4, note: "Close below lower band" },
    ],
  },
  {
    id: "breakout",
    name: "Breakout Strategy",
    description: "Enters when price breaks the opening range with confirming volume.",
    symbol: "TCS",
    timeframe: "5m",
    entryCondition:
      "Generates a BUY signal when price closes above the first 30-minute high with volume at least 1.5x the 20-bar average.",
    state: "AVAILABLE",
    subscribed: false,
    pnl: 0,
    positionQty: 0,
    ordersCount: 0,
    tradesCount: 0,
    limits: { ...defaultLimits },
    signals: [{ time: "10:15:00", type: "BUY", price: 3398.0, note: "Opening range high broken" }],
  },
];

const t = (hms: string) => `2026-10-08T${hms}+05:30`;

export const orders: Order[] = [
  {
    id: "ORD-001", strategyId: "momentum", strategyName: "Momentum", symbol: "RELIANCE", side: "BUY",
    orderType: "MARKET", quantity: 20, filledQuantity: 20, averagePrice: 1424.5, status: "FILLED", time: t("14:42:11"),
    lifecycle: [
      { status: "CREATED", time: t("14:42:10") }, { status: "SUBMITTED", time: t("14:42:10") },
      { status: "PARTIALLY_FILLED", time: t("14:42:11") }, { status: "FILLED", time: t("14:42:11") },
    ],
    fills: [{ time: t("14:42:11"), quantity: 12, price: 1424.4 }, { time: t("14:42:11"), quantity: 8, price: 1424.65 }],
  },
  {
    id: "ORD-002", strategyId: "breakout", strategyName: "Breakout", symbol: "TCS", side: "BUY",
    orderType: "LIMIT", quantity: 30, filledQuantity: 15, averagePrice: 3412, status: "PARTIALLY_FILLED", time: t("14:38:02"),
    lifecycle: [
      { status: "CREATED", time: t("14:38:01") }, { status: "SUBMITTED", time: t("14:38:01") },
      { status: "PARTIALLY_FILLED", time: t("14:38:02") },
    ],
    fills: [{ time: t("14:38:02"), quantity: 15, price: 3412 }],
  },
  {
    id: "ORD-003", strategyId: "mean-reversion", strategyName: "Mean Reversion", symbol: "INFY", side: "SELL",
    orderType: "MARKET", quantity: 20, filledQuantity: 0, averagePrice: null, status: "REJECTED", time: t("14:35:47"),
    rejectionReason: "MAX_POSITION_SIZE_EXCEEDED",
    lifecycle: [
      { status: "CREATED", time: t("14:35:47") }, { status: "SUBMITTED", time: t("14:35:47") },
      { status: "REJECTED", time: t("14:35:47") },
    ],
    fills: [],
  },
  {
    id: "ORD-004", strategyId: "mean-reversion", strategyName: "Mean Reversion", symbol: "RELIANCE", side: "SELL",
    orderType: "MARKET", quantity: 10, filledQuantity: 10, averagePrice: 1430, status: "FILLED", time: t("14:30:01"),
    lifecycle: [
      { status: "CREATED", time: t("14:30:00") }, { status: "SUBMITTED", time: t("14:30:00") },
      { status: "FILLED", time: t("14:30:01") },
    ],
    fills: [{ time: t("14:30:01"), quantity: 10, price: 1430 }],
  },
  {
    id: "ORD-005", strategyId: "momentum", strategyName: "Momentum", symbol: "RELIANCE", side: "SELL",
    orderType: "MARKET", quantity: 20, filledQuantity: 20, averagePrice: 1419.2, status: "FILLED", time: t("13:18:45"),
    lifecycle: [
      { status: "CREATED", time: t("13:18:44") }, { status: "SUBMITTED", time: t("13:18:44") },
      { status: "FILLED", time: t("13:18:45") },
    ],
    fills: [{ time: t("13:18:45"), quantity: 20, price: 1419.2 }],
  },
  {
    id: "ORD-006", strategyId: "momentum", strategyName: "Momentum", symbol: "RELIANCE", side: "BUY",
    orderType: "LIMIT", quantity: 25, filledQuantity: 0, averagePrice: null, status: "CANCELLED", time: t("12:44:20"),
    lifecycle: [
      { status: "CREATED", time: t("12:44:18") }, { status: "SUBMITTED", time: t("12:44:18") },
      { status: "CANCELLED", time: t("12:44:20") },
    ],
    fills: [],
  },
  {
    id: "ORD-007", strategyId: "mean-reversion", strategyName: "Mean Reversion", symbol: "RELIANCE", side: "BUY",
    orderType: "MARKET", quantity: 10, filledQuantity: 10, averagePrice: 1411.4, status: "FILLED", time: t("12:10:01"),
    lifecycle: [
      { status: "CREATED", time: t("12:10:00") }, { status: "SUBMITTED", time: t("12:10:00") },
      { status: "FILLED", time: t("12:10:01") },
    ],
    fills: [{ time: t("12:10:01"), quantity: 10, price: 1411.4 }],
  },
  {
    id: "ORD-008", strategyId: "momentum", strategyName: "Momentum", symbol: "RELIANCE", side: "BUY",
    orderType: "MARKET", quantity: 20, filledQuantity: 20, averagePrice: 1412.8, status: "FILLED", time: t("11:05:03"),
    lifecycle: [
      { status: "CREATED", time: t("11:05:02") }, { status: "SUBMITTED", time: t("11:05:02") },
      { status: "FILLED", time: t("11:05:03") },
    ],
    fills: [{ time: t("11:05:03"), quantity: 20, price: 1412.8 }],
  },
];

export const positions: Position[] = [
  { id: "P1", strategyId: "momentum", strategyName: "Momentum Strategy", symbol: "RELIANCE", quantity: 20, entryPrice: 1420, currentPrice: 1425 },
  { id: "P2", strategyId: "mean-reversion", strategyName: "Mean Reversion Strategy", symbol: "RELIANCE", quantity: -10, entryPrice: 1430, currentPrice: 1425 },
  { id: "P3", strategyId: "breakout", strategyName: "Breakout Strategy", symbol: "RELIANCE", quantity: 30, entryPrice: 1420, currentPrice: 1425 },
  { id: "P4", strategyId: "breakout", strategyName: "Breakout Strategy", symbol: "TCS", quantity: 15, entryPrice: 3412, currentPrice: 3405.5 },
];

export const riskEvents: RiskEvent[] = [
  { id: "E1", time: "14:42:10", type: "APPROVED", message: "Order approved — ORD-001 BUY 20 RELIANCE (Momentum)" },
  { id: "E2", time: "14:38:02", type: "PARTIAL_FILL", message: "Partial fill received — ORD-002 15/30 TCS (Breakout)" },
  { id: "E3", time: "14:38:01", type: "APPROVED", message: "Order approved — ORD-002 BUY 30 TCS (Breakout)" },
  { id: "E4", time: "14:35:47", type: "REJECTED", message: "Order rejected — ORD-003 SELL 20 INFY (Mean Reversion)", reason: "MAX_POSITION_SIZE_EXCEEDED" },
  { id: "E5", time: "14:30:00", type: "APPROVED", message: "Order approved — ORD-004 SELL 10 RELIANCE (Mean Reversion)" },
  { id: "E6", time: "09:15:00", type: "INFO", message: "Risk engine started — limits loaded for 2 active strategies" },
];
