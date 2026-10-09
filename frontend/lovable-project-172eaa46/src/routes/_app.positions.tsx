import { createFileRoute } from "@tanstack/react-router";
import { Badge, Card, PageHeader, Pnl } from "@/components/tm/ui";
import { usePositions } from "@/hooks/queries";
import type { Position } from "@/types";

export const Route = createFileRoute("/_app/positions")({
  head: () => ({
    meta: [
      { title: "Positions — TradeMint" },
      { name: "description", content: "Open positions tracked independently per strategy, even on the same stock." },
      { property: "og:title", content: "Positions — TradeMint" },
      { property: "og:description", content: "Per-strategy positions, entry, current price and P&L." },
    ],
  }),
  component: Positions,
});

const pnlOf = (p: Position) => Math.round((p.currentPrice - p.entryPrice) * p.quantity);

function Positions() {
  const { data = [], isLoading } = usePositions();
  const bySymbol = data.reduce<Record<string, Position[]>>((acc, p) => ((acc[p.symbol] ??= []).push(p), acc), {});

  return (
    <div>
      <PageHeader title="Positions" sub="Each strategy holds its own independent position. They are never netted together." />
      {!isLoading && data.length === 0 && <Card className="p-10 text-center text-sm text-muted-foreground">No open positions.</Card>}
      <div className="space-y-6">
        {Object.entries(bySymbol).map(([symbol, list]) => {
          const net = list.reduce((a, p) => a + p.quantity, 0);
          return (
            <Card key={symbol}>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b px-5 py-4">
                <div className="flex items-center gap-3">
                  <h3 className="text-base font-semibold">{symbol}</h3>
                  <span className="num text-sm text-muted-foreground">LTP ₹{list[0]!.currentPrice.toLocaleString("en-IN")}</span>
                </div>
                <span className="text-xs text-muted-foreground">{list.length} strategies · broker net qty <span className="num font-medium text-foreground">{net > 0 ? "+" : ""}{net}</span></span>
              </div>
              <div className="grid grid-cols-1 divide-y md:grid-cols-3 md:divide-x md:divide-y-0">
                {list.map((p) => (
                  <div key={p.id} className="p-5">
                    <p className="text-sm font-medium">{p.strategyName}</p>
                    <div className="mt-2 flex items-center gap-2">
                      <Badge tone={p.quantity > 0 ? "success" : "danger"}>{p.quantity > 0 ? "Long" : "Short"}</Badge>
                      <span className="num text-lg font-semibold">{p.quantity > 0 ? "+" : ""}{p.quantity}</span>
                    </div>
                    <dl className="mt-4 grid grid-cols-3 gap-2 text-sm">
                      <div><dt className="text-xs text-muted-foreground">Entry</dt><dd className="num font-medium">₹{p.entryPrice.toLocaleString("en-IN")}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Current</dt><dd className="num font-medium">₹{p.currentPrice.toLocaleString("en-IN")}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">P&L</dt><dd><Pnl value={pnlOf(p)} /></dd></div>
                    </dl>
                  </div>
                ))}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
