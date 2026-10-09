import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Badge, Card, Modal, PageHeader, orderTone } from "@/components/tm/ui";
import { useOrders } from "@/hooks/queries";
import type { Order, OrderStatus } from "@/types";
import { hms, statusLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/orders")({
  head: () => ({
    meta: [
      { title: "Orders — TradeMint" },
      { name: "description", content: "Every order placed by your strategies, with full lifecycle and fill details." },
      { property: "og:title", content: "Orders — TradeMint" },
      { property: "og:description", content: "Track created, submitted, filled and rejected orders across strategies." },
    ],
  }),
  component: Orders,
});

const FILTERS: (OrderStatus | "ALL")[] = ["ALL", "FILLED", "PARTIALLY_FILLED", "REJECTED", "CANCELLED"];

function Orders() {
  const { data = [] } = useOrders();
  const [filter, setFilter] = useState<OrderStatus | "ALL">("ALL");
  const [selected, setSelected] = useState<Order | null>(null);
  const rows = useMemo(() => (filter === "ALL" ? data : data.filter((o) => o.status === filter)), [data, filter]);

  return (
    <div>
      <PageHeader title="Orders" sub="Click any order to see its lifecycle." />
      <div className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button key={f} onClick={() => setFilter(f)} className={cn("rounded-full border px-3 py-1 text-xs font-medium", filter === f ? "border-primary bg-accent text-accent-foreground" : "bg-card text-muted-foreground hover:text-foreground")}>
            {statusLabel(f)}
          </button>
        ))}
      </div>
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b">
                {["Order ID", "Strategy", "Symbol", "Side", "Type", "Qty", "Filled", "Avg Price", "Status", "Time"].map((h) => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((o) => (
                <tr key={o.id} onClick={() => setSelected(o)} className="cursor-pointer border-b last:border-0 hover:bg-muted/50">
                  <td className="num px-4 py-3 font-medium">{o.id}</td>
                  <td className="px-4 py-3">{o.strategyName}</td>
                  <td className="px-4 py-3 font-medium">{o.symbol}</td>
                  <td className={cn("px-4 py-3 font-semibold", o.side === "BUY" ? "text-success" : "text-destructive")}>{o.side}</td>
                  <td className="px-4 py-3 text-muted-foreground">{o.orderType}</td>
                  <td className="num px-4 py-3">{o.quantity}</td>
                  <td className="num px-4 py-3">{o.filledQuantity}</td>
                  <td className="num px-4 py-3">{o.averagePrice ? `₹${o.averagePrice.toLocaleString("en-IN")}` : "—"}</td>
                  <td className="px-4 py-3"><Badge tone={orderTone(o.status)}>{statusLabel(o.status)}</Badge></td>
                  <td className="num px-4 py-3 text-muted-foreground">{hms(o.time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Modal open={!!selected} onClose={() => setSelected(null)} title={selected ? `Order ${selected.id}` : ""} wide>
        {selected && <OrderDetail o={selected} />}
      </Modal>
    </div>
  );
}

function OrderDetail({ o }: { o: Order }) {
  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
        {[
          ["Strategy", o.strategyName], ["Symbol", o.symbol], ["Side", o.side], ["Quantity", o.quantity],
          ["Filled", o.filledQuantity], ["Avg fill price", o.averagePrice ? `₹${o.averagePrice}` : "—"],
        ].map(([k, v]) => (
          <div key={String(k)}><dt className="text-xs text-muted-foreground">{k}</dt><dd className="num mt-0.5 font-medium">{v}</dd></div>
        ))}
        <div><dt className="text-xs text-muted-foreground">Status</dt><dd className="mt-1"><Badge tone={orderTone(o.status)}>{statusLabel(o.status)}</Badge></dd></div>
      </dl>
      {o.rejectionReason && (
        <div className="rounded-lg border border-destructive/30 bg-danger-soft px-4 py-3 text-sm">
          <span className="font-semibold text-destructive">Rejected by risk engine:</span> <span className="num">{o.rejectionReason}</span>
        </div>
      )}
      <div>
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Lifecycle</h4>
        <ol className="relative ml-2 border-l">
          {o.lifecycle.map((e, i) => (
            <li key={i} className="mb-4 ml-5 last:mb-0">
              <span className={cn("absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full", e.status === "REJECTED" ? "bg-destructive" : e.status === "CANCELLED" ? "bg-muted-foreground" : "bg-success")} />
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{statusLabel(e.status)}</span>
                <span className="num text-xs text-muted-foreground">{hms(e.time)}</span>
              </div>
            </li>
          ))}
        </ol>
      </div>
      {o.fills.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Fills</h4>
          <ul className="divide-y rounded-lg border text-sm">
            {o.fills.map((f, i) => (
              <li key={i} className="num flex justify-between px-4 py-2"><span>{f.quantity} @ ₹{f.price}</span><span className="text-muted-foreground">{hms(f.time)}</span></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
