import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { Badge, Card, CardHeader, Pnl, orderTone } from "@/components/tm/ui";
import { StateBadge, StrategyActions } from "@/components/tm/StrategyControls";
import { useOrders, useStrategy } from "@/hooks/queries";
import { hms, inr, statusLabel } from "@/lib/format";

export const Route = createFileRoute("/_app/strategies/$id")({
  head: () => ({
    meta: [
      { title: "Strategy details — TradeMint" },
      { name: "description", content: "Entry rules, risk limits, signals, orders and P&L for a single strategy." },
      { property: "og:title", content: "Strategy details — TradeMint" },
      { property: "og:description", content: "Inspect a strategy's logic, limits and live activity." },
    ],
  }),
  component: StrategyDetail,
});

function StrategyDetail() {
  const { id } = Route.useParams();
  const { data: s, isError } = useStrategy(id);
  const { data: orders = [] } = useOrders();

  if (isError) return <p className="text-sm text-muted-foreground">Strategy not found. <Link to="/strategies" className="text-primary">Back to strategies</Link></p>;
  if (!s) return <div className="h-64 animate-pulse rounded-xl bg-muted" />;
  const mine = orders.filter((o) => o.strategyId === s.id);

  return (
    <div className="space-y-6">
      <Link to="/strategies" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"><ArrowLeft className="h-3.5 w-3.5" />Strategies</Link>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3"><h1 className="text-xl font-semibold">{s.name}</h1><StateBadge s={s} /></div>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{s.description}</p>
        </div>
        <div className="flex gap-2"><StrategyActions s={s} /></div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {[
          ["Market", s.symbol], ["Timeframe", `${s.timeframe} candles`],
          ["Position", s.positionQty ? `${s.positionQty > 0 ? "+" : ""}${s.positionQty}` : "Flat"],
          ["Orders / Trades", `${s.ordersCount} / ${s.tradesCount}`],
        ].map(([k, v]) => (
          <Card key={k} className="p-4"><p className="text-xs text-muted-foreground">{k}</p><p className="num mt-1 font-semibold">{v}</p></Card>
        ))}
        <Card className="p-4"><p className="text-xs text-muted-foreground">P&L</p><Pnl value={s.pnl} className="mt-1 block font-semibold" /></Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Entry condition" sub="Informational — strategy logic runs on the server" />
          <p className="p-5 text-sm leading-relaxed">{s.entryCondition}</p>
        </Card>
        <Card>
          <CardHeader title="Risk limits" />
          <dl className="space-y-2.5 p-5 text-sm">
            <div className="flex justify-between"><dt className="text-muted-foreground">Max daily loss</dt><dd className="num font-medium">{inr(s.limits.maxDailyLoss)}</dd></div>
            <div className="flex justify-between"><dt className="text-muted-foreground">Max position size</dt><dd className="num font-medium">{s.limits.maxPositionSize}</dd></div>
            <div className="flex justify-between"><dt className="text-muted-foreground">Max orders / minute</dt><dd className="num font-medium">{s.limits.maxOrdersPerMinute}</dd></div>
          </dl>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Recent signals" />
          <ul className="divide-y">
            {s.signals.map((g) => (
              <li key={g.time} className="flex items-center justify-between px-5 py-3 text-sm">
                <div className="flex items-center gap-3">
                  <Badge tone={g.type === "BUY" ? "success" : "danger"}>{g.type}</Badge>
                  <span>{g.note}</span>
                </div>
                <span className="num text-xs text-muted-foreground">{g.time} · ₹{g.price}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Orders" />
          {mine.length ? (
            <ul className="divide-y">
              {mine.map((o) => (
                <li key={o.id} className="flex items-center justify-between px-5 py-3 text-sm">
                  <span className="num">{o.id} · <span className={o.side === "BUY" ? "text-success" : "text-destructive"}>{o.side}</span> {o.quantity} {o.symbol}</span>
                  <span className="flex items-center gap-2"><Badge tone={orderTone(o.status)}>{statusLabel(o.status)}</Badge><span className="num text-xs text-muted-foreground">{hms(o.time)}</span></span>
                </li>
              ))}
            </ul>
          ) : <p className="p-5 text-sm text-muted-foreground">No orders yet.</p>}
        </Card>
      </div>
    </div>
  );
}
