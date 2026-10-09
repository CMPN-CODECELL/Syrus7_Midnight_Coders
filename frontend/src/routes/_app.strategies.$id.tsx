import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowLeft,
  Sliders,
  ShieldAlert,
  Play,
  RotateCcw,
  Zap,
  TrendingUp,
  TrendingDown,
  Clock,
  Shield,
  Layers,
} from "lucide-react";
import { Badge, Button, Card, CardHeader, Modal, Pnl, orderTone } from "@/components/tm/ui";
import { StateBadge, StrategyActions } from "@/components/tm/StrategyControls";
import { StrategyCustomizerModal } from "@/components/tm/StrategyCustomizerModal";
import {
  useOrders,
  useStrategy,
  useSquareOffStrategy,
  useManualTradeStrategy,
  useResetStrategy,
} from "@/hooks/queries";
import { hms, inr, statusLabel } from "@/lib/format";
import type { Strategy } from "@/types";

export const Route = createFileRoute("/_app/strategies/$id")({
  head: () => ({
    meta: [
      { title: "Strategy details — TradeMint" },
      { name: "description", content: "Entry rules, custom parameters, manual trade controls, risk limits, signals, orders and P&L." },
      { property: "og:title", content: "Strategy details — TradeMint" },
      { property: "og:description", content: "Inspect and customize a strategy's logic, limits, manual trade overrides and live activity." },
    ],
  }),
  component: StrategyDetail,
});

function StrategyParametersCard({ s }: { s: Strategy }) {
  const p = s.parameters || {};

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between border-b pb-3">
        <div className="flex items-center gap-2">
          <Sliders className="h-4 w-4 text-primary" />
          <h3 className="font-semibold text-sm">Configured Strategy Parameters</h3>
        </div>
        <span className="text-xs text-muted-foreground">{s.strategyType || "Custom"}</span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
        <div className="rounded-lg bg-muted/40 p-2.5">
          <span className="text-xs text-muted-foreground">Order Quantity</span>
          <p className="mt-0.5 font-semibold font-mono">{p.quantity || 1} units</p>
        </div>

        {p.fast_period && (
          <div className="rounded-lg bg-muted/40 p-2.5">
            <span className="text-xs text-muted-foreground">Fast SMA / Slow SMA</span>
            <p className="mt-0.5 font-semibold font-mono">{p.fast_period} / {p.slow_period} periods</p>
          </div>
        )}

        {p.breakout_pct && (
          <div className="rounded-lg bg-muted/40 p-2.5">
            <span className="text-xs text-muted-foreground">Breakout Threshold</span>
            <p className="mt-0.5 font-semibold font-mono">{p.breakout_pct}% from Open</p>
          </div>
        )}

        {p.target_pct && (
          <div className="rounded-lg bg-success/10 p-2.5 border border-success/20">
            <span className="text-xs text-success font-medium">Profit Target (TP)</span>
            <p className="mt-0.5 font-semibold text-success font-mono">+{p.target_pct}%</p>
          </div>
        )}

        {p.stop_loss_pct && (
          <div className="rounded-lg bg-destructive/10 p-2.5 border border-destructive/20">
            <span className="text-xs text-destructive font-medium">Stop-Loss (SL)</span>
            <p className="mt-0.5 font-semibold text-destructive font-mono">-{p.stop_loss_pct}%</p>
          </div>
        )}

        {p.direction && (
          <div className="rounded-lg bg-muted/40 p-2.5">
            <span className="text-xs text-muted-foreground">Direction Filter</span>
            <p className="mt-0.5 font-semibold font-mono">{p.direction}</p>
          </div>
        )}

        {p.entry_time && (
          <div className="rounded-lg bg-muted/40 p-2.5">
            <span className="text-xs text-muted-foreground">Active Window</span>
            <p className="mt-0.5 font-semibold font-mono">{p.entry_time} → {p.exit_time}</p>
          </div>
        )}

        {p.trailing_stop_pct && (
          <div className="rounded-lg bg-muted/40 p-2.5">
            <span className="text-xs text-muted-foreground">Trailing Stop</span>
            <p className="mt-0.5 font-semibold font-mono">{p.trailing_stop_pct}%</p>
          </div>
        )}
      </div>
    </Card>
  );
}

function ManualTradeControls({ s }: { s: Strategy }) {
  const sq = useSquareOffStrategy();
  const trade = useManualTradeStrategy();
  const reset = useResetStrategy();

  const [squareOffModal, setSquareOffModal] = useState(false);
  const [tradeModal, setTradeModal] = useState(false);
  const [tradeSide, setTradeSide] = useState<"BUY" | "SELL">("BUY");
  const [tradeQty, setTradeQty] = useState(s.parameters?.quantity || 1);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const hasPosition = Boolean(s.positionQty && s.positionQty !== 0);

  const handleManualTrade = async () => {
    try {
      await trade.mutateAsync({
        id: s.id,
        side: tradeSide,
        quantity: Number(tradeQty),
      });
      setStatusMsg(`Order executed: ${tradeSide} ${tradeQty} ${s.symbol}`);
      setTradeModal(false);
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (e: any) {
      setStatusMsg(`Trade error: ${e.message}`);
    }
  };

  const handleSquareOff = async () => {
    try {
      await sq.mutateAsync(s.id);
      setSquareOffModal(false);
      setStatusMsg(`Flattened open position (${s.positionQty} ${s.symbol})`);
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (e: any) {
      setStatusMsg(`Square-off error: ${e.message}`);
    }
  };

  const handleReset = async () => {
    try {
      await reset.mutateAsync(s.id);
      setStatusMsg("Strategy trade cycle state reset successfully");
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (e: any) {
      setStatusMsg(`Reset error: ${e.message}`);
    }
  };

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between border-b pb-3">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-warning" />
          <h3 className="font-semibold text-sm">User Trade Controls & Overrides</h3>
        </div>
        <span className="text-xs text-muted-foreground">Full Manual Control</span>
      </div>

      <p className="mt-2 text-xs text-muted-foreground">
        Directly intervene, test order flow, flatten risk, or trigger test trades isolated to this strategy.
      </p>

      {statusMsg && (
        <div className="mt-3 rounded-md bg-muted px-3 py-2 text-xs font-medium text-primary">
          {statusMsg}
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2.5">
        {/* Square Off Button */}
        <Button
          size="sm"
          variant="outline"
          disabled={!hasPosition || sq.isPending}
          onClick={() => setSquareOffModal(true)}
          className="border-destructive/30 text-destructive hover:bg-destructive/10"
        >
          <ShieldAlert className="h-3.5 w-3.5 mr-1" />
          {hasPosition ? `Square Off (${s.positionQty > 0 ? "+" : ""}${s.positionQty})` : "Flat (No Open Position)"}
        </Button>

        {/* Manual Trade Order Button */}
        <Button
          size="sm"
          variant="outline"
          onClick={() => setTradeModal(true)}
          className="inline-flex items-center gap-1.5"
        >
          <Play className="h-3.5 w-3.5 text-primary" />
          Manual Trade / Instant Order
        </Button>

        {/* Reset State */}
        <Button
          size="sm"
          variant="ghost"
          disabled={reset.isPending}
          onClick={handleReset}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          <RotateCcw className={`h-3.5 w-3.5 mr-1 ${reset.isPending ? "animate-spin" : ""}`} />
          Reset Intraday Cycle
        </Button>
      </div>

      {/* Square Off Modal */}
      <Modal open={squareOffModal} onClose={() => setSquareOffModal(false)} title="Confirm Strategy Position Square-Off">
        <p className="text-sm text-muted-foreground">
          Are you sure you want to immediately exit your active position of{" "}
          <strong className="text-foreground">{s.positionQty} {s.symbol}</strong>?
          A market order will be submitted to flatten this strategy's position.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setSquareOffModal(false)}>
            Cancel
          </Button>
          <Button variant="danger" disabled={sq.isPending} onClick={handleSquareOff}>
            {sq.isPending ? "Closing..." : "Exit Position Now"}
          </Button>
        </div>
      </Modal>

      {/* Manual Trade Modal */}
      <Modal open={tradeModal} onClose={() => setTradeModal(false)} title={`Enter Manual Trade for ${s.name}`}>
        <div className="space-y-4 text-sm">
          <p className="text-xs text-muted-foreground">
            Place an on-demand market order for <strong className="text-foreground">{s.symbol}</strong>. The order will be routed through platform risk gates and allocated exclusively to this strategy's isolated P&L.
          </p>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-muted-foreground">Trade Side</label>
              <div className="mt-1.5 flex gap-2">
                <button
                  type="button"
                  onClick={() => setTradeSide("BUY")}
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-md border py-2 text-xs font-semibold transition-colors ${
                    tradeSide === "BUY"
                      ? "border-success bg-success/15 text-success"
                      : "border-input bg-card text-muted-foreground hover:bg-muted/50"
                  }`}
                >
                  <TrendingUp className="h-3.5 w-3.5" />
                  BUY (Long)
                </button>
                <button
                  type="button"
                  onClick={() => setTradeSide("SELL")}
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-md border py-2 text-xs font-semibold transition-colors ${
                    tradeSide === "SELL"
                      ? "border-destructive bg-destructive/15 text-destructive"
                      : "border-input bg-card text-muted-foreground hover:bg-muted/50"
                  }`}
                >
                  <TrendingDown className="h-3.5 w-3.5" />
                  SELL (Short)
                </button>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-muted-foreground">Quantity (units)</label>
              <input
                type="number"
                min={1}
                max={s.limits.maxPositionSize}
                value={tradeQty}
                onChange={(e) => setTradeQty(Number(e.target.value))}
                className="mt-1.5 w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium"
              />
            </div>
          </div>

          <div className="rounded-lg border bg-muted/40 p-3 text-xs text-muted-foreground">
            Instrument: <span className="font-semibold text-foreground">{s.symbol} (NSE)</span> · Product:{" "}
            <span className="font-semibold text-foreground">INTRADAY</span> · Type:{" "}
            <span className="font-semibold text-foreground">MARKET</span>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setTradeModal(false)}>
              Cancel
            </Button>
            <Button disabled={trade.isPending} onClick={handleManualTrade}>
              {trade.isPending ? "Submitting..." : `Execute ${tradeSide} Order`}
            </Button>
          </div>
        </div>
      </Modal>
    </Card>
  );
}

function StrategyDetail() {
  const { id } = Route.useParams();
  const { data: s, isError } = useStrategy(id);
  const { data: orders = [] } = useOrders();
  const [customizerOpen, setCustomizerOpen] = useState(false);

  if (isError) {
    return (
      <p className="text-sm text-muted-foreground">
        Strategy not found.{" "}
        <Link to="/strategies" className="text-primary">
          Back to strategies
        </Link>
      </p>
    );
  }
  if (!s) return <div className="h-64 animate-pulse rounded-xl bg-muted" />;
  const mine = orders.filter((o) => o.strategyId === s.id);

  return (
    <div className="space-y-6">
      <Link
        to="/strategies"
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Strategies
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold">{s.name}</h1>
            <StateBadge s={s} />
          </div>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{s.description}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setCustomizerOpen(true)}
            className="inline-flex items-center gap-1.5"
          >
            <Sliders className="h-3.5 w-3.5 text-primary" />
            Customize Strategy
          </Button>
          <StrategyActions s={s} />
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {[
          ["Market", s.symbol],
          ["Timeframe", `${s.timeframe} candles`],
          ["Position", s.positionQty ? `${s.positionQty > 0 ? "+" : ""}${s.positionQty} ${s.symbol}` : "Flat"],
          ["Orders / Trades", `${s.ordersCount} / ${s.tradesCount}`],
        ].map(([k, v]) => (
          <Card key={k} className="p-4">
            <p className="text-xs text-muted-foreground">{k}</p>
            <p className="num mt-1 font-semibold">{v}</p>
          </Card>
        ))}
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">Net P&L</p>
          <Pnl value={s.pnl} className="mt-1 block font-semibold text-lg" />
        </Card>
      </div>

      {/* User Trade Controls & Customization Summary */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ManualTradeControls s={s} />
        <StrategyParametersCard s={s} />
      </div>

      {/* Entry condition & Risk Limits */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Automated entry & exit condition" sub="Logic runs on server market feed" />
          <p className="p-5 text-sm leading-relaxed">{s.entryCondition}</p>
        </Card>
        <Card>
          <CardHeader title="Platform Enforced Risk limits" sub="L3 platform protection" />
          <dl className="space-y-2.5 p-5 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Max daily loss</dt>
              <dd className="num font-medium">{inr(s.limits.maxDailyLoss)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Max position size</dt>
              <dd className="num font-medium">{s.limits.maxPositionSize} units</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Max orders / minute</dt>
              <dd className="num font-medium">{s.limits.maxOrdersPerMinute} / min</dd>
            </div>
          </dl>
        </Card>
      </div>

      {/* Recent Signals & Orders */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Real-time Strategy Signals" sub="Triggered by ticks and candle aggregations" />
          {s.signals && s.signals.length ? (
            <ul className="divide-y max-h-96 overflow-y-auto">
              {s.signals.map((g, idx) => (
                <li key={`${g.time}-${idx}`} className="flex items-center justify-between px-5 py-3 text-sm">
                  <div className="flex items-center gap-3">
                    <Badge tone={g.type === "BUY" ? "success" : "danger"}>{g.type}</Badge>
                    <span className="font-medium text-xs sm:text-sm">{g.note}</span>
                  </div>
                  <span className="num text-xs text-muted-foreground shrink-0">
                    {g.time} · {g.price > 0 ? `₹${g.price}` : "MKT"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-5 text-sm text-muted-foreground">No signals triggered yet in this session.</p>
          )}
        </Card>

        <Card>
          <CardHeader title="Filled & Working Orders" sub="Audited order execution records" />
          {mine.length ? (
            <ul className="divide-y max-h-96 overflow-y-auto">
              {mine.map((o) => (
                <li key={o.id} className="flex items-center justify-between px-5 py-3 text-sm">
                  <span className="num">
                    {o.id} ·{" "}
                    <span className={o.side === "BUY" ? "text-success" : "text-destructive"}>
                      {o.side}
                    </span>{" "}
                    {o.quantity} {o.symbol}
                  </span>
                  <span className="flex items-center gap-2">
                    <Badge tone={orderTone(o.status)}>{statusLabel(o.status)}</Badge>
                    <span className="num text-xs text-muted-foreground">{hms(o.time)}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-5 text-sm text-muted-foreground">No orders generated yet for this strategy.</p>
          )}
        </Card>
      </div>

      {/* Customizer Modal */}
      <StrategyCustomizerModal
        open={customizerOpen}
        onClose={() => setCustomizerOpen(false)}
        strategy={s}
      />
    </div>
  );
}
