import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Clock, Plus, Sliders, Trash2 } from "lucide-react";
import { Card, PageHeader, Pnl, Button, Badge } from "@/components/tm/ui";
import { StateBadge, StrategyActions } from "@/components/tm/StrategyControls";
import { CreateStrategyModal } from "@/components/tm/CreateStrategyModal";
import { useStrategies, useDeleteStrategy } from "@/hooks/queries";
import type { Strategy } from "@/types";

export const Route = createFileRoute("/_app/strategies/")({
  head: () => ({
    meta: [
      { title: "Strategies — TradeMint" },
      { name: "description", content: "Browse, customize, create, start and stop algorithmic trading strategies." },
      { property: "og:title", content: "Strategies — TradeMint" },
      { property: "og:description", content: "Momentum, Mean Reversion and Breakout strategies with platform-enforced risk limits and user customization." },
    ],
  }),
  component: Strategies,
});

function position(s: Strategy) {
  if (!s.positionQty) return "Flat";
  return `${s.positionQty > 0 ? "+" : ""}${s.positionQty} ${s.symbol}`;
}

function ParameterHighlights({ s }: { s: Strategy }) {
  const p = s.parameters;
  if (!p) return null;

  return (
    <div className="mt-2.5 flex flex-wrap gap-1.5 text-[11px]">
      {p.fast_period && (
        <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-muted-foreground">
          Fast/Slow: {p.fast_period}/{p.slow_period}
        </span>
      )}
      {p.breakout_pct && (
        <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-muted-foreground">
          Breakout: {p.breakout_pct}%
        </span>
      )}
      {p.target_pct && (
        <span className="rounded bg-success/15 px-1.5 py-0.5 font-mono text-success">
          TP: +{p.target_pct}%
        </span>
      )}
      {p.stop_loss_pct && (
        <span className="rounded bg-destructive/15 px-1.5 py-0.5 font-mono text-destructive">
          SL: -{p.stop_loss_pct}%
        </span>
      )}
      {p.entry_time && (
        <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-muted-foreground">
          {p.entry_time} → {p.exit_time}
        </span>
      )}
      {p.direction && p.direction !== "BOTH" && (
        <span className="rounded bg-primary/15 px-1.5 py-0.5 font-mono text-primary">
          {p.direction}
        </span>
      )}
    </div>
  );
}

function StrategyCard({ s, active }: { s: Strategy; active?: boolean }) {
  const del = useDeleteStrategy();

  return (
    <Card className="flex flex-col p-5 transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold">{s.name}</h3>
            {s.canDelete && <Badge tone="neutral">Custom</Badge>}
          </div>
          <ParameterHighlights s={s} />
        </div>
        <StateBadge s={s} />
      </div>

      <p className="mt-2.5 flex-1 text-sm text-muted-foreground">{s.description}</p>

      <dl className="mt-4 grid grid-cols-2 gap-3 border-t pt-4 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">Timeframe</dt>
          <dd className="mt-0.5 flex items-center gap-1 font-medium">
            <Clock className="h-3.5 w-3.5" />
            {s.timeframe} candles
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Symbol</dt>
          <dd className="mt-0.5 font-medium">{s.symbol}</dd>
        </div>
        {active && (
          <>
            <div>
              <dt className="text-xs text-muted-foreground">P&L</dt>
              <dd className="mt-0.5">
                <Pnl value={s.pnl} />
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Position</dt>
              <dd className="num mt-0.5 font-medium">{position(s)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Orders</dt>
              <dd className="num mt-0.5 font-medium">{s.ordersCount}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Subscription</dt>
              <dd className="mt-0.5 font-medium text-success">Subscribed</dd>
            </div>
          </>
        )}
      </dl>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t pt-3">
        <div className="flex items-center gap-2">
          <Link
            to="/strategies/$id"
            params={{ id: s.id }}
            className="inline-flex h-8 items-center rounded-md border border-input bg-card px-3 text-xs font-medium hover:bg-muted"
          >
            Details & Controls
          </Link>
          {s.canDelete && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => del.mutate(s.id)}
              disabled={del.isPending}
              className="text-muted-foreground hover:text-destructive h-8 px-2"
              title="Delete custom strategy"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
        <StrategyActions s={s} />
      </div>
    </Card>
  );
}

function Strategies() {
  const { data = [] } = useStrategies();
  const [createOpen, setCreateOpen] = useState(false);

  const mine = data.filter((s) => s.subscribed);
  const available = data.filter((s) => !s.subscribed);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <PageHeader
          title="Strategies & Customization"
          sub="Build, tune, or subscribe to isolated strategies. Customize parameters, profit targets, and stop-loss levels freely."
        />
        <Button onClick={() => setCreateOpen(true)} className="inline-flex items-center gap-1.5 shrink-0 self-start sm:self-auto">
          <Plus className="h-4 w-4" />
          Create Custom Strategy
        </Button>
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-muted-foreground">
            My Active Strategies ({mine.length})
          </h2>
        </div>
        {mine.length ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {mine.map((s) => (
              <StrategyCard key={s.id} s={s} active />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">You haven't subscribed to any strategies yet.</p>
        )}
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
          Available Strategies ({available.length})
        </h2>
        {available.length ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {available.map((s) => (
              <StrategyCard key={s.id} s={s} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">You're subscribed to every available strategy.</p>
        )}
      </section>

      <CreateStrategyModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}
