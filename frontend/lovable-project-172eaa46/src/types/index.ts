export type Side = "BUY" | "SELL";
export type OrderStatus =
  | "CREATED"
  | "SUBMITTED"
  | "PARTIALLY_FILLED"
  | "FILLED"
  | "REJECTED"
  | "CANCELLED";
export type Timeframe = "1m" | "5m";
export type RiskLevel = "SAFE" | "WARNING" | "BREACHED";

export interface User {
  id: string;
  name: string;
  email: string;
}

export interface Account {
  accountValue: number;
  availableBalance: number;
  todayPnl: number;
  riskStatus: RiskLevel;
}

export interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface RiskLimit {
  maxDailyLoss: number;
  maxPositionSize: number;
  maxOrdersPerMinute: number;
}

export type StrategyRunState = "AVAILABLE" | "SUBSCRIBED" | "RUNNING" | "STOPPED";

export interface Subscription {
  strategyId: string;
  subscribedAt: string;
  symbol: string;
  limits: RiskLimit;
}

export interface Signal {
  time: string;
  type: Side;
  price: number;
  note: string;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  symbol: string;
  timeframe: Timeframe;
  entryCondition: string;
  state: StrategyRunState;
  subscribed: boolean;
  pnl: number;
  positionQty: number;
  ordersCount: number;
  tradesCount: number;
  limits: RiskLimit;
  signals: Signal[];
}

export interface Fill {
  time: string;
  quantity: number;
  price: number;
}

export interface OrderEvent {
  status: OrderStatus;
  time: string;
}

export interface Order {
  id: string;
  strategyId: string;
  strategyName: string;
  symbol: string;
  side: Side;
  orderType: "MARKET" | "LIMIT";
  quantity: number;
  filledQuantity: number;
  averagePrice: number | null;
  status: OrderStatus;
  time: string;
  rejectionReason?: string;
  lifecycle: OrderEvent[];
  fills: Fill[];
}

export interface Position {
  id: string;
  strategyId: string;
  strategyName: string;
  symbol: string;
  quantity: number;
  entryPrice: number;
  currentPrice: number;
}

export interface PnLPoint {
  time: string;
  pnl: number;
}

export interface RiskStatus {
  overall: RiskLevel;
  limits: RiskLimit;
  currentLoss: number;
  currentMaxPosition: number;
  currentOrdersPerMinute: number;
}

export interface RiskEvent {
  id: string;
  time: string;
  type: "APPROVED" | "REJECTED" | "PARTIAL_FILL" | "KILL_SWITCH" | "INFO";
  message: string;
  reason?: string;
}

export interface KillSwitchStatus {
  active: boolean;
  activatedAt?: string;
  executionTimeSec?: number;
}
