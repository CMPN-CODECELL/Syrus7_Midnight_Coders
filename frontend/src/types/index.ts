export type Side = "BUY" | "SELL";
export type OrderStatus =
  | "CREATED"
  | "SUBMITTED"
  | "PARTIALLY_FILLED"
  | "FILLED"
  | "REJECTED"
  | "CANCELLED";
export type Timeframe = "1m" | "5m" | "1D" | "1W" | "1M";
export type RiskLevel = "SAFE" | "WARNING" | "BREACHED";

export interface User {
  id: string;
  name: string;
  email: string;
  role?: string;
  api_ucc?: string;
  account_balance_paise?: number;
  account_balance_inr?: number;
  subscription_tier?: string;
  notifications_enabled?: boolean;
  theme?: "light" | "dark";
  created_at?: string;
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

export interface StrategyParameters {
  quantity?: number;
  fast_period?: number;
  slow_period?: number;
  timeframe?: string;
  breakout_pct?: number;
  target_pct?: number | null;
  stop_loss_pct?: number | null;
  direction?: string;
  trailing_stop_pct?: number | null;
  entry_time?: string;
  exit_time?: string;
  side?: string;
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
  parameters?: StrategyParameters;
  strategyType?: string;
  canDelete?: boolean;
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

export interface ItemizedCharges {
  brokerage: number;
  brokeragePaise: number;
  stt: number;
  sttPaise: number;
  exchangeTxnFee: number;
  exchangeTxnFeePaise: number;
  sebiTurnoverFee: number;
  sebiTurnoverFeePaise: number;
  stampDuty: number;
  stampDutyPaise: number;
  gst18: number;
  gst18Paise: number;
  totalCharges: number;
  totalChargesPaise: number;
}

export interface ContractNote {
  noteId: string;
  orderId: string;
  tradeDate: string;
  settlementDate: string;
  timestamp?: string;
  clearingHouse: string;
  sebiRegistration: string;
  memberCode: string;
  ucc: string;
  strategyId: string;
  strategyName: string;
  symbol: string;
  exchange: string;
  segment: string;
  side: Side;
  orderType: "MARKET" | "LIMIT";
  quantity: number;
  averagePrice: number;
  grossTurnover: number;
  grossTurnoverPaise: number;
  charges: ItemizedCharges;
  netObligation: number;
  netObligationPaise: number;
  chargesPercentage: number;
  status: string;
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
  charges?: ItemizedCharges | null;
  contractNote?: ContractNote | null;
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

export interface KillSwitchIncident {
  incidentId: string;
  timestamp: string;
  scope: "GLOBAL" | "CANCEL_ONLY" | "STRATEGY" | "SYMBOL" | string;
  source: string;
  reason: string;
  targetId?: string | null;
  result: string;
  ordersCancelled: number;
  positionsClosed: number;
  elapsedSeconds: number;
  slaMet: boolean;
  message: string;
}

export interface AutoKillRules {
  autoTripEnabled: boolean;
  maxMtmLoss: number;
  maxConsecutiveRejections: number;
  cooldownMinutes: number;
}

export interface KillSwitchStatus {
  active: boolean;
  scope?: "GLOBAL" | "CANCEL_ONLY" | "STRATEGY" | "SYMBOL" | "NONE" | string;
  activatedAt?: string;
  executionTimeSec?: number;
  ordersCancelled?: number;
  positionsClosed?: number;
  slaMet?: boolean;
  message?: string;
  cooldownUntil?: string | null;
  isCoolingDown?: boolean;
  lastIncident?: KillSwitchIncident | null;
  autoRules?: AutoKillRules;
  incidents?: KillSwitchIncident[];
}
