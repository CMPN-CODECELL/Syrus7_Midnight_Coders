import { useState, useEffect } from "react";
import { Sliders, Shield, Zap, Check, AlertCircle } from "lucide-react";
import { Button, Modal } from "./ui";
import { useUpdateStrategyParameters } from "@/hooks/queries";
import type { Strategy } from "@/types";
import { inr } from "@/lib/format";

interface StrategyCustomizerModalProps {
  open: boolean;
  onClose: () => void;
  strategy: Strategy;
}

const STOCK_SYMBOLS = [
  "RELIANCE",
  "TCS",
  "INFY",
  "HDFCBANK",
  "ICICIBANK",
  "TATAMOTORS",
  "SBIN",
  "BHARTIARTL",
  "ITC",
  "KOTAKBANK",
  "LT",
  "AXISBANK",
  "WIPRO",
  "HCLTECH",
  "ASIANPAINT",
  "TITAN",
  "MARUTI",
  "SUNPHARMA",
  "BAJFINANCE",
  "ZOMATO",
  "PAYTM",
  "JIOFIN",
  "TATASTEEL",
  "NIFTY50",
  "BANKNIFTY",
  "FINNIFTY",
];

export function StrategyCustomizerModal({ open, onClose, strategy }: StrategyCustomizerModalProps) {
  const m = useUpdateStrategyParameters();
  const [successMsg, setSuccessMsg] = useState(false);

  // Symbol Selection State
  const [symbol, setSymbol] = useState(strategy.symbol || "RELIANCE");
  const [customSymbol, setCustomSymbol] = useState("");

  // General & Risk Limits
  const [quantity, setQuantity] = useState(strategy.positionQty || 1);
  const [maxDailyLoss, setMaxDailyLoss] = useState(strategy.limits.maxDailyLoss || 500);
  const [maxPositionSize, setMaxPositionSize] = useState(strategy.limits.maxPositionSize || 10);
  const [maxOrdersPerMinute, setMaxOrdersPerMinute] = useState(strategy.limits.maxOrdersPerMinute || 5);

  // Strategy Specifics
  const params: any = strategy.parameters || {};
  const isMa = strategy.id.includes("ma") || strategy.strategyType?.includes("MovingAverage");
  const isBreakout = strategy.id.includes("breakout") || strategy.strategyType?.includes("Breakout");
  const isTime = strategy.id.includes("time") || strategy.strategyType?.includes("TimeBased");

  // MA parameters
  const [fastPeriod, setFastPeriod] = useState<number>(params.fast_period || 5);
  const [slowPeriod, setSlowPeriod] = useState<number>(params.slow_period || 20);
  const [timeframe, setTimeframe] = useState<string>(params.timeframe || strategy.timeframe || "1m");

  // Breakout parameters
  const [breakoutPct, setBreakoutPct] = useState<number>(params.breakout_pct || 1.0);
  const [direction, setDirection] = useState<string>(params.direction || "BOTH");
  const [trailingStopPct, setTrailingStopPct] = useState<number | string>(params.trailing_stop_pct || "");

  // Common target & stop-loss
  const [targetPct, setTargetPct] = useState<number>(params.target_pct || (isBreakout ? 5.0 : 2.0));
  const [stopLossPct, setStopLossPct] = useState<number>(params.stop_loss_pct || (isBreakout ? 5.0 : 1.0));

  // Time-based
  const [entryTime, setEntryTime] = useState<string>(params.entry_time || "09:15");
  const [exitTime, setExitTime] = useState<string>(params.exit_time || "15:15");
  const [side, setSide] = useState<string>(params.side || "BUY");

  // Sync state whenever strategy changes
  useEffect(() => {
    if (!open) return;
    const p: any = strategy.parameters || {};
    setSymbol(strategy.symbol || "RELIANCE");
    setCustomSymbol("");
    setQuantity(p.quantity || 1);
    setMaxDailyLoss(strategy.limits.maxDailyLoss || 500);
    setMaxPositionSize(strategy.limits.maxPositionSize || 10);
    setMaxOrdersPerMinute(strategy.limits.maxOrdersPerMinute || 5);

    if (p.fast_period) setFastPeriod(p.fast_period);
    if (p.slow_period) setSlowPeriod(p.slow_period);
    if (p.breakout_pct) setBreakoutPct(p.breakout_pct);
    if (p.direction) setDirection(p.direction);
    if (p.trailing_stop_pct !== undefined) setTrailingStopPct(p.trailing_stop_pct || "");
    if (p.target_pct) setTargetPct(p.target_pct);
    if (p.stop_loss_pct) setStopLossPct(p.stop_loss_pct);
    if (p.entry_time) setEntryTime(p.entry_time);
    if (p.exit_time) setExitTime(p.exit_time);
    if (p.side) setSide(p.side);
    setSuccessMsg(false);
  }, [open, strategy]);

  const selectedSymbol = customSymbol.trim() ? customSymbol.trim().toUpperCase() : symbol;

  const handleSave = async () => {
    const newParams: any = {
      quantity: Number(quantity),
      symbol: selectedSymbol,
    };

    if (isMa) {
      newParams["fast_period"] = Number(fastPeriod);
      newParams["slow_period"] = Number(slowPeriod);
      newParams["take_profit_pct"] = Number(targetPct);
      newParams["stop_loss_pct"] = Number(stopLossPct);
      newParams["timeframe"] = timeframe;
      newParams["exit_time"] = exitTime;
    } else if (isBreakout) {
      newParams["breakout_pct"] = Number(breakoutPct);
      newParams["target_pct"] = Number(targetPct);
      newParams["stop_loss_pct"] = Number(stopLossPct);
      newParams["direction"] = direction;
      newParams["trailing_stop_pct"] = trailingStopPct !== "" ? Number(trailingStopPct) : null;
    } else if (isTime) {
      newParams["entry_time"] = entryTime;
      newParams["exit_time"] = exitTime;
      newParams["side"] = side;
      newParams["target_pct"] = targetPct ? Number(targetPct) : null;
      newParams["stop_loss_pct"] = stopLossPct ? Number(stopLossPct) : null;
    }

    const newLimits = {
      maxDailyLoss: Number(maxDailyLoss),
      maxPositionSize: Number(maxPositionSize),
      maxOrdersPerMinute: Number(maxOrdersPerMinute),
    };

    try {
      await m.mutateAsync({
        id: strategy.id,
        parameters: newParams,
        limits: newLimits,
      });
      setSuccessMsg(true);
      setTimeout(() => {
        setSuccessMsg(false);
        onClose();
      }, 900);
    } catch {
      // handled by mutation error
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Customize Strategy: ${strategy.name}`}
    >
      <div className="space-y-5 text-sm">
        {/* Trade Sizing & Stock Symbol */}
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center gap-2 font-semibold">
            <Zap className="h-4 w-4 text-primary" />
            <span>Order Sizing & Stock Symbol</span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-muted-foreground">Order Quantity (shares)</label>
              <input
                type="number"
                min={1}
                max={maxPositionSize}
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Instrument Symbol (Select or Type Any)</label>
              <div className="mt-1 flex gap-2">
                <select
                  value={STOCK_SYMBOLS.includes(symbol) ? symbol : "RELIANCE"}
                  onChange={(e) => {
                    setSymbol(e.target.value);
                    setCustomSymbol("");
                  }}
                  className="w-1/2 rounded-md border border-input bg-background px-2 py-1.5 text-xs font-medium"
                >
                  {STOCK_SYMBOLS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <input
                  type="text"
                  placeholder="Or custom stock"
                  value={customSymbol}
                  onChange={(e) => setCustomSymbol(e.target.value.toUpperCase())}
                  className="w-1/2 rounded-md border border-input bg-background px-2 py-1.5 text-xs font-medium uppercase"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Strategy Specific Indicator Parameters */}
        {isMa && (
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center gap-2 font-semibold">
              <Sliders className="h-4 w-4 text-primary" />
              <span>Moving Average Crossover Parameters</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-muted-foreground">Fast SMA Period ({fastPeriod})</label>
                <input
                  type="range"
                  min={2}
                  max={25}
                  value={fastPeriod}
                  onChange={(e) => setFastPeriod(Number(e.target.value))}
                  className="mt-2 w-full accent-primary"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Slow SMA Period ({slowPeriod})</label>
                <input
                  type="range"
                  min={10}
                  max={60}
                  value={slowPeriod}
                  onChange={(e) => setSlowPeriod(Number(e.target.value))}
                  className="mt-2 w-full accent-primary"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Candle Timeframe</label>
                <select
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                >
                  <option value="1m">1 Minute Candles</option>
                  <option value="5m">5 Minute Candles</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Intraday Exit Time</label>
                <input
                  type="time"
                  value={exitTime}
                  onChange={(e) => setExitTime(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                />
              </div>
            </div>
          </div>
        )}

        {isBreakout && (
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center gap-2 font-semibold">
              <Sliders className="h-4 w-4 text-primary" />
              <span>Breakout Trigger Thresholds</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-muted-foreground">Breakout Threshold: {breakoutPct}%</label>
                <input
                  type="range"
                  min={0.2}
                  max={3.0}
                  step={0.1}
                  value={breakoutPct}
                  onChange={(e) => setBreakoutPct(Number(e.target.value))}
                  className="mt-2 w-full accent-primary"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Trading Direction</label>
                <select
                  value={direction}
                  onChange={(e) => setDirection(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                >
                  <option value="BOTH">Both (Long & Short Breakouts)</option>
                  <option value="LONG_ONLY">Long Only (Buy on +1% Open)</option>
                  <option value="SHORT_ONLY">Short Only (Sell on -1% Open)</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Trailing Stop Loss (% optional)</label>
                <input
                  type="number"
                  step="0.5"
                  placeholder="e.g. 1.5% trailing"
                  value={trailingStopPct}
                  onChange={(e) => setTrailingStopPct(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                />
              </div>
            </div>
          </div>
        )}

        {isTime && (
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center gap-2 font-semibold">
              <Sliders className="h-4 w-4 text-primary" />
              <span>Time-based Execution Window</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-muted-foreground">Entry Time</label>
                <input
                  type="time"
                  value={entryTime}
                  onChange={(e) => setEntryTime(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Square-off Exit Time</label>
                <input
                  type="time"
                  value={exitTime}
                  onChange={(e) => setExitTime(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Trade Side</label>
                <select
                  value={side}
                  onChange={(e) => setSide(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                >
                  <option value="BUY">BUY (Long Entry)</option>
                  <option value="SELL">SELL (Short Entry)</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Target and Stop Loss */}
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center justify-between font-semibold">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-success" />
              <span>Profit Target & Stop Loss</span>
            </div>
            <span className="text-xs font-normal text-muted-foreground">Monitored tick-by-tick</span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-muted-foreground">Target / Take Profit (%): {targetPct}%</label>
              <input
                type="number"
                step="0.5"
                min={0.5}
                max={20}
                value={targetPct}
                onChange={(e) => setTargetPct(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Stop Loss (%): {stopLossPct}%</label>
              <input
                type="number"
                step="0.5"
                min={0.2}
                max={15}
                value={stopLossPct}
                onChange={(e) => setStopLossPct(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium"
              />
            </div>
          </div>
        </div>

        {/* Platform Risk Limits */}
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4">
          <div className="flex items-center justify-between font-semibold text-destructive">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4" />
              <span>Platform Risk Guardrails (L3 Enforced)</span>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">Max Daily Loss (₹)</label>
              <input
                type="number"
                step={50}
                min={100}
                value={maxDailyLoss}
                onChange={(e) => setMaxDailyLoss(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm font-medium"
              />
              <span className="text-[10px] text-muted-foreground">{inr(maxDailyLoss)}</span>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Max Position Size</label>
              <input
                type="number"
                min={1}
                max={100}
                value={maxPositionSize}
                onChange={(e) => setMaxPositionSize(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm font-medium"
              />
              <span className="text-[10px] text-muted-foreground">Max units held</span>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Max Orders / min</label>
              <input
                type="number"
                min={1}
                max={30}
                value={maxOrdersPerMinute}
                onChange={(e) => setMaxOrdersPerMinute(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm font-medium"
              />
              <span className="text-[10px] text-muted-foreground">Rate governor</span>
            </div>
          </div>
        </div>

        {m.isError && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-2.5 text-xs text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>Failed to update strategy: {(m.error as Error).message}</span>
          </div>
        )}

        {successMsg && (
          <div className="flex items-center gap-2 rounded-md bg-success/15 p-2.5 text-xs text-success">
            <Check className="h-4 w-4 shrink-0" />
            <span>Parameters saved successfully! Changes active immediately on the server.</span>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose} disabled={m.isPending}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={m.isPending}>
            {m.isPending ? "Applying..." : successMsg ? "Saved!" : "Save & Apply Customization"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
