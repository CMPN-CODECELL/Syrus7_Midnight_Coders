import { createFileRoute, Link } from "@tanstack/react-router";
import { Clock } from "lucide-react";
import { Card, PageHeader, Pnl } from "@/components/tm/ui";
import { StateBadge, StrategyActions } from "@/components/tm/StrategyControls";
import { useStrategies } from "@/hooks/queries";
import type { Strategy } from "@/types";

export const Route = createFileRoute("/_app/strategies/")({
  head: () => ({
    meta: [
      { title: "Strategies — TradeMint" },
      { name: "description", content: "Browse, subscribe to, start and stop algorithmic trading strategies." },
      { property: "og:title", content: "Strategies — TradeMint" },
      { property: "og:description", content: "Momentum, Mean Reversion and Breakout strategies with platform-enforced risk limits." },
    ],
  }),
  component: Strategies,
});

function position(s: Strategy) {
  if (!s.positionQty) return "Flat";
  return `${s.positionQty > 0 ? "+" : ""}${s.positionQty} ${s.symbol}`;
}

function StrategyCard({ s, active }: { s: Strategy; active?: boolean }) {
  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold">{s.name}</h3>
        <StateBadge s={s} />
      </div>
      <p className="mt-2 flex-1 text-sm text-muted-foreground">{s.description}</p>
      <dl className="mt-4 grid grid-cols-2 gap-3 border-t pt-4 text-sm">
        <div><dt className="text-xs text-muted-foreground">Timeframe</dt><dd className="mt-0.5 flex items-center gap-1 font-medium"><Clock className="h-3.5 w-3.5" />{s.timeframe} candles</dd></div>
        <div><dt className="text-xs text-muted-foreground">Symbol</dt><dd className="mt-0.5 font-medium">{s.symbol}</dd></div>
        {active && <>
          <div><dt className="text-xs text-muted-foreground">P&L</dt><dd className="mt-0.5"><Pnl value={s.pnl} /></dd></div>
          <div><dt className="text-xs text-muted-foreground">Position</dt><dd className="num mt-0.5 font-medium">{position(s)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Orders</dt><dd className="num mt-0.5 font-medium">{s.ordersCount}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Subscription</dt><dd className="mt-0.5 font-medium text-success">Subscribed</dd></div>
        </>}
      </dl>
      <div className="mt-4 flex gap-2">
        <Link to="/strategies/$id" params={{ id: s.id }} className="inline-flex h-8 items-center rounded-md border border-input bg-card px-3 text-xs font-medium hover:bg-muted">View Details</Link>
        <StrategyActions s={s} />
      </div>
    </Card>
  );
}

function Strategies() {
  const { data = [] } = useStrategies();
  const mine = data.filter((s) => s.subscribed);
  const available = data.filter((s) => !s.subscribed);

  return (
    <div>
      <PageHeader title="Strategies" sub="Multiple strategies can run on the same account — each keeps its own positions and P&L." />
      <section>
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">My Active Strategies ({mine.length})</h2>
        {mine.length ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">{mine.map((s) => <StrategyCard key={s.id} s={s} active />)}</div>
        ) : <p className="text-sm text-muted-foreground">You haven't subscribed to any strategies yet.</p>}
      </section>
      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">Available Strategies ({available.length})</h2>
        {available.length ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">{available.map((s) => <StrategyCard key={s.id} s={s} />)}</div>
        ) : <p className="text-sm text-muted-foreground">You're subscribed to every available strategy.</p>}
      </section>
    </div>
  );
}
