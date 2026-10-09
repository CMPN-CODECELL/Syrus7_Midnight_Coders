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
  const rand = rng(symbol.length * 977 + (tf === "1m" ? 13 : tf === "5m" ? 71 : 142) + symbol.charCodeAt(0));
  let step = 60_000;
  let vol = 0.0012;

  if (tf === "5m") {
    step = 300_000;
    vol = 0.0026;
  } else if (tf === "1D") {
    step = 86_400_000;
    vol = 0.012;
  } else if (tf === "1W") {
    step = 604_800_000;
    vol = 0.028;
  } else if (tf === "1M") {
    step = 2_592_000_000;
    vol = 0.055;
  }

  const end = new Date();
  end.setSeconds(0, 0);
  let price = (BASE[symbol] ?? 1000) * (0.95 + rand() * 0.08);
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
      volume: Math.round((tf === "1m" ? 8000 : tf === "5m" ? 40000 : 250000) * (0.5 + rand())),
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
    id: "strat_time",
    name: "Strategy 1: TimeBased (09:15 Entry, 15:15 Exit)",
    description: "Enters a 1-share long position at 09:15 AM market open and automatically squares off at 15:15 PM.",
    symbol: "BTCUSDT",
    timeframe: "1m",
    entryCondition: "Enters INTRADAY BUY when time reaches 09:15 IST; exits at 15:15 IST.",
    state: "RUNNING",
    subscribed: true,
    pnl: 1450,
    positionQty: 1,
    ordersCount: 2,
    tradesCount: 2,
    limits: { maxDailyLoss: 500, maxPositionSize: 10, maxOrdersPerMinute: 5 },
    signals: [
      { time: "09:15:00", type: "BUY", price: 1183.5, note: "09:15 AM Market Open Entry trigger" },
      { time: "15:15:00", type: "SELL", price: 1198.0, note: "15:15 PM EOD Square-Off trigger" },
    ],
  },
  {
    id: "strat_breakout",
    name: "Strategy 2: 1% Breakout (+5% Target / -5% SL)",
    description: "Enters long if price rises 1% above day's open. Sets a profit target at +5% and a stop-loss at -5%.",
    symbol: "ETHUSDT",
    timeframe: "1m",
    entryCondition: "Triggers BUY if LTP >= Open * 1.01. Auto-exits at +5% Target or -5% Stop-loss.",
    state: "RUNNING",
    subscribed: true,
    pnl: 850,
    positionQty: 1,
    ordersCount: 2,
    tradesCount: 2,
    limits: { maxDailyLoss: 500, maxPositionSize: 10, maxOrdersPerMinute: 5 },
    signals: [
      { time: "10:04:12", type: "BUY", price: 992.45, note: "1% Breakout above day open" },
      { time: "11:22:15", type: "SELL", price: 1042.0, note: "+5% Target hit" },
    ],
  },
  {
    id: "strat_ma",
    name: "Strategy 3: MA Crossover on 1m Candles",
    description: "Computes 5-SMA and 20-SMA on 1-minute aggregated candles. Buys on golden cross, sells on death cross.",
    symbol: "SOLUSDT",
    timeframe: "1m",
    entryCondition: "Triggers BUY when 5-period SMA crosses above 20-period SMA on completed 1m candles.",
    state: "RUNNING",
    subscribed: true,
    pnl: 520,
    positionQty: 1,
    ordersCount: 3,
    tradesCount: 2,
    limits: { maxDailyLoss: 500, maxPositionSize: 10, maxOrdersPerMinute: 5 },
    signals: [
      { time: "12:56:04", type: "BUY", price: 3410.0, note: "5-SMA crossed above 20-SMA on 1m candle" },
      { time: "13:45:10", type: "SELL", price: 3422.5, note: "5-SMA crossed below 20-SMA on 1m candle" },
    ],
  },
];

const t = (hms: string) => `2026-10-08T${hms}+05:30`;

export const orders: Order[] = [
  {
    id: "ORD-001", strategyId: "strat_time", strategyName: "TimeBased Momentum", symbol: "RELIANCE", side: "BUY",
    orderType: "MARKET", quantity: 5, filledQuantity: 5, averagePrice: 1424.5, status: "FILLED", time: t("14:42:11"),
    lifecycle: [
      { status: "CREATED", time: t("14:42:10") }, { status: "SUBMITTED", time: t("14:42:10") },
      { status: "PARTIALLY_FILLED", time: t("14:42:11") }, { status: "FILLED", time: t("14:42:11") },
    ],
    fills: [{ time: t("14:42:11"), quantity: 3, price: 1424.4 }, { time: t("14:42:11"), quantity: 2, price: 1424.65 }],
  },
  {
    id: "ORD-002", strategyId: "strat_breakout", strategyName: "Breakout Strategy", symbol: "TCS", side: "BUY",
    orderType: "LIMIT", quantity: 10, filledQuantity: 4, averagePrice: 3410.0, status: "PARTIALLY_FILLED", time: t("14:38:02"),
    lifecycle: [
      { status: "CREATED", time: t("14:38:01") }, { status: "SUBMITTED", time: t("14:38:01") },
      { status: "PARTIALLY_FILLED", time: t("14:38:02") },
    ],
    fills: [{ time: t("14:38:02"), quantity: 4, price: 3410.0 }],
  },
  {
    id: "ORD-003", strategyId: "strat_time", strategyName: "TimeBased Momentum", symbol: "HDFCBANK", side: "BUY",
    orderType: "MARKET", quantity: 15, filledQuantity: 0, averagePrice: null, status: "REJECTED", time: t("14:35:47"),
    rejectionReason: "MAX_POSITION_SIZE_EXCEEDED (Platform limit: 10 units)",
    lifecycle: [
      { status: "CREATED", time: t("14:35:47") }, { status: "SUBMITTED", time: t("14:35:47") },
      { status: "REJECTED", time: t("14:35:47") },
    ],
    fills: [],
  },
  {
    id: "ORD-004", strategyId: "strat_ma", strategyName: "Moving Average Cross", symbol: "INFY", side: "SELL",
    orderType: "MARKET", quantity: 4, filledQuantity: 4, averagePrice: 1520.25, status: "FILLED", time: t("14:30:01"),
    lifecycle: [
      { status: "CREATED", time: t("14:30:00") }, { status: "SUBMITTED", time: t("14:30:00") },
      { status: "FILLED", time: t("14:30:01") },
    ],
    fills: [{ time: t("14:30:01"), quantity: 4, price: 1520.25 }],
  },
  {
    id: "ORD-005", strategyId: "strat_time", strategyName: "TimeBased Momentum", symbol: "RELIANCE", side: "SELL",
    orderType: "MARKET", quantity: 5, filledQuantity: 5, averagePrice: 1435.0, status: "FILLED", time: t("13:18:45"),
    lifecycle: [
      { status: "CREATED", time: t("13:18:44") }, { status: "SUBMITTED", time: t("13:18:44") },
      { status: "FILLED", time: t("13:18:45") },
    ],
    fills: [{ time: t("13:18:45"), quantity: 5, price: 1435.0 }],
  },
  {
    id: "ORD-006", strategyId: "strat_breakout", strategyName: "Breakout Strategy", symbol: "TCS", side: "BUY",
    orderType: "LIMIT", quantity: 8, filledQuantity: 0, averagePrice: null, status: "CANCELLED", time: t("12:44:20"),
    lifecycle: [
      { status: "CREATED", time: t("12:44:18") }, { status: "SUBMITTED", time: t("12:44:18") },
      { status: "CANCELLED", time: t("12:44:20") },
    ],
    fills: [],
  },
  {
    id: "ORD-007", strategyId: "strat_ma", strategyName: "Moving Average Cross", symbol: "INFY", side: "BUY",
    orderType: "MARKET", quantity: 4, filledQuantity: 4, averagePrice: 1515.0, status: "FILLED", time: t("12:10:01"),
    lifecycle: [
      { status: "CREATED", time: t("12:10:00") }, { status: "SUBMITTED", time: t("12:10:00") },
      { status: "FILLED", time: t("12:10:01") },
    ],
    fills: [{ time: t("12:10:01"), quantity: 4, price: 1515.0 }],
  },
  {
    id: "ORD-008", strategyId: "momentum", strategyName: "Momentum", symbol: "BTCUSDT", side: "BUY",
    orderType: "MARKET", quantity: 20, filledQuantity: 20, averagePrice: 1412.8, status: "FILLED", time: t("11:05:03"),
    lifecycle: [
      { status: "CREATED", time: t("11:05:02") }, { status: "SUBMITTED", time: t("11:05:02") },
      { status: "FILLED", time: t("11:05:03") },
    ],
    fills: [{ time: t("11:05:03"), quantity: 20, price: 1412.8 }],
  },
];

export const positions: Position[] = [
  { id: "P1", strategyId: "momentum", strategyName: "Momentum Strategy", symbol: "BTCUSDT", quantity: 20, entryPrice: 1420, currentPrice: 1425 },
  { id: "P2", strategyId: "mean-reversion", strategyName: "Mean Reversion Strategy", symbol: "BTCUSDT", quantity: -10, entryPrice: 1430, currentPrice: 1425 },
  { id: "P3", strategyId: "breakout", strategyName: "Breakout Strategy", symbol: "BTCUSDT", quantity: 30, entryPrice: 1420, currentPrice: 1425 },
  { id: "P4", strategyId: "breakout", strategyName: "Breakout Strategy", symbol: "SOLUSDT", quantity: 15, entryPrice: 3412, currentPrice: 3405.5 },
];

export const riskEvents: RiskEvent[] = [
  { id: "E1", time: "14:42:10", type: "APPROVED", message: "Order approved — ORD-001 BUY 20 BTCUSDT (Momentum)" },
  { id: "E2", time: "14:38:02", type: "PARTIAL_FILL", message: "Partial fill received — ORD-002 15/30 SOLUSDT (Breakout)" },
  { id: "E3", time: "14:38:01", type: "APPROVED", message: "Order approved — ORD-002 BUY 30 SOLUSDT (Breakout)" },
  { id: "E4", time: "14:35:47", type: "REJECTED", message: "Order rejected — ORD-003 SELL 20 ETHUSDT (Mean Reversion)", reason: "MAX_POSITION_SIZE_EXCEEDED" },
  { id: "E5", time: "14:30:00", type: "APPROVED", message: "Order approved — ORD-004 SELL 10 BTCUSDT (Mean Reversion)" },
  { id: "E6", time: "09:15:00", type: "INFO", message: "Risk engine started — limits loaded for 2 active strategies" },
];
