import { useState } from "react";
import { Plus, Sliders, Shield, Sparkles } from "lucide-react";
import { Button, Modal } from "./ui";
import { useCreateStrategy } from "@/hooks/queries";

interface CreateStrategyModalProps {
  open: boolean;
  onClose: () => void;
}

const POPULAR_SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "TATAMOTORS", "ICICIBANK", "SBIN"];

export function CreateStrategyModal({ open, onClose }: CreateStrategyModalProps) {
  const m = useCreateStrategy();

  const [strategyType, setStrategyType] = useState<"MovingAverageCross" | "Breakout" | "TimeBased">("MovingAverageCross");
  const [name, setName] = useState("");
  const [symbol, setSymbol] = useState("RELIANCE");
  const [customSymbol, setCustomSymbol] = useState("");
  const [quantity, setQuantity] = useState(5);
  const [description, setDescription] = useState("");

  // MA Cross
  const [fastPeriod, setFastPeriod] = useState(5);
  const [slowPeriod, setSlowPeriod] = useState(20);
  const [timeframe, setTimeframe] = useState("1m");

  // Breakout
  const [breakoutPct, setBreakoutPct] = useState(1.0);
  const [direction, setDirection] = useState("BOTH");

  // Common Targets
  const [targetPct, setTargetPct] = useState(2.0);
  const [stopLossPct, setStopLossPct] = useState(1.0);

  // Time-based
  const [entryTime, setEntryTime] = useState("09:15");
  const [exitTime, setExitTime] = useState("15:15");
  const [side, setSide] = useState("BUY");

  // Risk Limits
  const [maxDailyLoss, setMaxDailyLoss] = useState(500);
  const [maxPositionSize, setMaxPositionSize] = useState(10);
  const [maxOrdersPerMinute, setMaxOrdersPerMinute] = useState(5);

  const selectedSymbol = customSymbol.trim() ? customSymbol.trim().toUpperCase() : symbol;

  const handleCreate = async () => {
    const finalName = name.trim() || `${selectedSymbol} ${strategyType}`;

    const parameters: any = {
      quantity: Number(quantity),
    };

    if (strategyType === "MovingAverageCross") {
      parameters.fast_period = Number(fastPeriod);
      parameters.slow_period = Number(slowPeriod);
      parameters.take_profit_pct = Number(targetPct);
      parameters.stop_loss_pct = Number(stopLossPct);
      parameters.timeframe = timeframe;
      parameters.exit_time = exitTime;
    } else if (strategyType === "Breakout") {
      parameters.breakout_pct = Number(breakoutPct);
      parameters.target_pct = Number(targetPct);
      parameters.stop_loss_pct = Number(stopLossPct);
      parameters.direction = direction;
    } else {
      parameters.entry_time = entryTime;
      parameters.exit_time = exitTime;
      parameters.side = side;
      parameters.target_pct = targetPct ? Number(targetPct) : null;
      parameters.stop_loss_pct = stopLossPct ? Number(stopLossPct) : null;
    }

    const limits = {
      maxDailyLoss: Number(maxDailyLoss),
      maxPositionSize: Number(maxPositionSize),
      maxOrdersPerMinute: Number(maxOrdersPerMinute),
    };

    try {
      await m.mutateAsync({
        name: finalName,
        strategy_type: strategyType,
        symbol: selectedSymbol,
        description: description.trim() || `User-customized ${strategyType} automated trading on ${selectedSymbol}`,
        parameters,
        limits,
      });
      onClose();
    } catch {
      // Handled by query mutation
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create Custom Trading Strategy"
    >
      <div className="space-y-4 text-sm">
        {/* Strategy Type Picker */}
        <div>
          <label className="text-xs font-semibold text-muted-foreground">Select Strategy Archetype</label>
          <div className="mt-1.5 grid grid-cols-3 gap-2">
            {[
              { id: "MovingAverageCross", label: "MA Crossover", desc: "Dual SMA candle cross" },
              { id: "Breakout", label: "Open Breakout", desc: "% Breakout from open" },
              { id: "TimeBased", label: "Time-based", desc: "Timed entry & square-off" },
            ].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  setStrategyType(t.id as any);
                  if (t.id === "Breakout") {
                    setTargetPct(5.0);
                    setStopLossPct(5.0);
                  } else {
                    setTargetPct(2.0);
                    setStopLossPct(1.0);
                  }
                }}
                className={`rounded-lg border p-2.5 text-left transition-colors ${
                  strategyType === t.id
                    ? "border-primary bg-primary/10 text-primary font-semibold"
                    : "border-input bg-card hover:bg-muted/50"
                }`}
              >
                <div className="text-xs font-medium">{t.label}</div>
                <div className="mt-0.5 text-[10px] text-muted-foreground">{t.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Name and Symbol */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-muted-foreground">Strategy Name</label>
            <input
              type="text"
              placeholder={`e.g. My ${selectedSymbol} Alpha`}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">Instrument Symbol</label>
            <div className="mt-1 flex gap-2">
              <select
                value={symbol}
                onChange={(e) => {
                  setSymbol(e.target.value);
                  setCustomSymbol("");
                }}
                className="w-1/2 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm"
              >
                {POPULAR_SYMBOLS.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <input
                type="text"
                placeholder="Or custom"
                value={customSymbol}
                onChange={(e) => setCustomSymbol(e.target.value.toUpperCase())}
                className="w-1/2 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm uppercase"
              />
            </div>
          </div>
        </div>

        {/* Strategy Specific Parameters */}
        <div className="rounded-lg border bg-card p-3.5 space-y-3">
          <div className="flex items-center gap-2 font-semibold">
            <Sliders className="h-4 w-4 text-primary" />
            <span>Logic Parameters</span>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">Order Quantity</label>
              <input
                type="number"
                min={1}
                value={quantity}
                onChange={(e) => setQuantity(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm font-medium"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Profit Target (%)</label>
              <input
                type="number"
                step="0.5"
                min={0.5}
                value={targetPct}
                onChange={(e) => setTargetPct(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm font-medium"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Stop Loss (%)</label>
              <input
                type="number"
                step="0.5"
                min={0.2}
                value={stopLossPct}
                onChange={(e) => setStopLossPct(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm font-medium"
              />
            </div>
          </div>

          {strategyType === "MovingAverageCross" && (
            <div className="grid grid-cols-3 gap-3 border-t pt-2.5">
              <div>
                <label className="text-xs text-muted-foreground">Fast SMA ({fastPeriod})</label>
                <input
                  type="number"
                  min={2}
                  max={30}
                  value={fastPeriod}
                  onChange={(e) => setFastPeriod(Number(e.target.value))}
                  className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Slow SMA ({slowPeriod})</label>
                <input
                  type="number"
                  min={10}
                  max={60}
                  value={slowPeriod}
                  onChange={(e) => setSlowPeriod(Number(e.target.value))}
                  className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Timeframe</label>
                <select
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm"
                >
                  <option value="1m">1m</option>
                  <option value="5m">5m</option>
                </select>
              </div>
            </div>
          )}

          {strategyType === "Breakout" && (
            <div className="grid grid-cols-2 gap-3 border-t pt-2.5">
              <div>
                <label className="text-xs text-muted-foreground">Breakout % from Open</label>
                <input
                  type="number"
                  step="0.2"
                  min={0.2}
                  max={5}
                  value={breakoutPct}
                  onChange={(e) => setBreakoutPct(Number(e.target.value))}
                  className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Direction</label>
                <select
                  value={direction}
                  onChange={(e) => setDirection(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm"
                >
                  <option value="BOTH">Both (Long & Short)</option>
                  <option value="LONG_ONLY">Long Only</option>
                  <option value="SHORT_ONLY">Short Only</option>
                </select>
              </div>
            </div>
          )}

          {strategyType === "TimeBased" && (
            <div className="grid grid-cols-3 gap-3 border-t pt-2.5">
              <div>
                <label className="text-xs text-muted-foreground">Entry Time</label>
                <input
                  type="time"
                  value={entryTime}
                  onChange={(e) => setEntryTime(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Exit Time</label>
                <input
                  type="time"
                  value={exitTime}
                  onChange={(e) => setExitTime(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Side</label>
                <select
                  value={side}
                  onChange={(e) => setSide(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1 text-sm"
                >
                  <option value="BUY">BUY</option>
                  <option value="SELL">SELL</option>
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Risk limits */}
        <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3.5 space-y-2">
          <div className="flex items-center gap-2 font-semibold text-destructive">
            <Shield className="h-4 w-4" />
            <span>Platform Enforced Risk Limits</span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-muted-foreground">Max Daily Loss (₹)</label>
              <input
                type="number"
                min={100}
                value={maxDailyLoss}
                onChange={(e) => setMaxDailyLoss(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Max Position</label>
              <input
                type="number"
                min={1}
                value={maxPositionSize}
                onChange={(e) => setMaxPositionSize(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Max Orders/min</label>
              <input
                type="number"
                min={1}
                value={maxOrdersPerMinute}
                onChange={(e) => setMaxOrdersPerMinute(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onClose} disabled={m.isPending}>
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={m.isPending}>
            <Sparkles className="h-4 w-4 mr-1" />
            {m.isPending ? "Creating..." : "Deploy Strategy"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
