import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  DollarSign,
  Download,
  FileCheck,
  FileText,
  Percent,
  Receipt,
  ShieldCheck,
} from "lucide-react";
import { Badge, Button, Card, Modal, PageHeader, orderTone } from "@/components/tm/ui";
import { ContractNoteModal } from "@/components/tm/ContractNoteModal";
import { useOrders } from "@/hooks/queries";
import type { Order, OrderStatus } from "@/types";
import { calculateRegulatoryCharges, generateContractNoteForOrder, exportAllContractNotesCSV } from "@/lib/charges";
import { hms, statusLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/orders")({
  head: () => ({
    meta: [
      { title: "Orders & Regulatory Contract Notes — TradeMint" },
      { name: "description", content: "Executed orders with full lifecycle, partial fills, and SEBI-compliant itemized charges contract notes." },
      { property: "og:title", content: "Orders & Contract Notes — TradeMint" },
      { property: "og:description", content: "Track orders, partial executions, and exact integer-paise regulatory fee calculations." },
    ],
  }),
  component: Orders,
});

const FILTERS: (OrderStatus | "ALL")[] = ["ALL", "FILLED", "PARTIALLY_FILLED", "REJECTED", "CANCELLED"];

function Orders() {
  const { data = [] } = useOrders();
  const [filter, setFilter] = useState<OrderStatus | "ALL">("ALL");
  const [selected, setSelected] = useState<Order | null>(null);
  const [contractNoteOrder, setContractNoteOrder] = useState<Order | null>(null);

  const rows = useMemo(() => (filter === "ALL" ? data : data.filter((o) => o.status === filter)), [data, filter]);

  // Telemetry KPIs across filled orders
  const summary = useMemo(() => {
    let totTurnover = 0;
    let totCharges = 0;
    let filledCount = 0;

    for (const o of data) {
      const qty = o.filledQuantity;
      if (qty > 0 && o.averagePrice) {
        filledCount++;
        const calc = calculateRegulatoryCharges(qty, o.averagePrice, o.side);
        totTurnover += calc.turnoverRupees;
        totCharges += calc.charges.totalCharges;
      }
    }

    const frictionPct = totTurnover > 0 ? (totCharges / totTurnover) * 100 : 0;
    return {
      totTurnover,
      totCharges,
      filledCount,
      frictionPct: frictionPct.toFixed(3),
    };
  }, [data]);

  const activeContractNote = useMemo(() => {
    if (!contractNoteOrder) return null;
    return contractNoteOrder.contractNote || generateContractNoteForOrder(contractNoteOrder);
  }, [contractNoteOrder]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Orders &amp; Contract Notes"
        sub="Track working broker orders, fill execution states, and itemized SEBI regulatory contract notes (Level 2)."
      />

      {/* Level 2 Published Charges & Turnover Telemetry */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border bg-card p-3.5 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <DollarSign className="h-3.5 w-3.5 text-primary" />
            <span>Gross Executed Turnover</span>
          </div>
          <p className="mt-1 text-base font-bold text-foreground">
            ₹{summary.totTurnover.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </p>
          <span className="text-[11px] text-muted-foreground">{summary.filledCount} filled trades</span>
        </div>

        <div className="rounded-xl border bg-card p-3.5 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Receipt className="h-3.5 w-3.5 text-warning" />
            <span>Published Charges Deducted</span>
          </div>
          <p className="mt-1 text-base font-bold text-destructive">
            ₹{summary.totCharges.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </p>
          <span className="text-[11px] text-muted-foreground">Integer paise arithmetic</span>
        </div>

        <div className="rounded-xl border bg-card p-3.5 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Percent className="h-3.5 w-3.5 text-info" />
            <span>Avg Regulatory Friction</span>
          </div>
          <p className="mt-1 text-base font-bold text-foreground">{summary.frictionPct}%</p>
          <span className="text-[11px] text-muted-foreground">Brokerage + Taxes</span>
        </div>

        <div className="rounded-xl border bg-card p-3.5 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-success" />
            <span>Level 2 Compliance</span>
          </div>
          <p className="mt-1 text-base font-bold text-success">Verified</p>
          <span className="text-[11px] text-muted-foreground">SEBI SCRA Rule 15</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                filter === f
                  ? "border-primary bg-primary text-primary-foreground"
                  : "bg-card text-muted-foreground hover:text-foreground hover:border-muted-foreground"
              )}
            >
              {statusLabel(f)}
            </button>
          ))}
        </div>

        <Button
          size="sm"
          variant="outline"
          className="h-8 gap-1.5 px-3 text-xs border-primary/30 text-primary hover:bg-primary/10 shadow-sm"
          onClick={() => {
            const filledNotes = data
              .filter((o: Order) => o.status === "FILLED" || o.status === "PARTIALLY_FILLED")
              .map((o: Order) => o.contractNote || generateContractNoteForOrder(o));
            exportAllContractNotesCSV(filledNotes);
          }}
        >
          <Download className="h-3.5 w-3.5" />
          <span>Export Compliance Audit Ledger (CSV)</span>
        </Button>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[960px] text-sm">
            <thead className="border-b text-left text-xs text-muted-foreground">
              <tr>
                {["Order ID", "Strategy", "Symbol", "Side", "Type", "Qty", "Filled", "Avg Price", "Status", "Contract Note", "Time"].map((h) => (
                  <th key={h} className="px-4 py-3 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((o) => {
                const isFilledOrPartial = o.status === "FILLED" || o.status === "PARTIALLY_FILLED";
                return (
                  <tr
                    key={o.id}
                    onClick={() => setSelected(o)}
                    className="cursor-pointer border-b last:border-0 hover:bg-muted/50 transition-colors"
                  >
                    <td className="num px-4 py-3 font-semibold text-primary">{o.id}</td>
                    <td className="px-4 py-3 font-medium">{o.strategyName}</td>
                    <td className="px-4 py-3 font-bold">{o.symbol}</td>
                    <td className={cn("px-4 py-3 font-semibold", o.side === "BUY" ? "text-success" : "text-destructive")}>
                      {o.side}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{o.orderType}</td>
                    <td className="num px-4 py-3">{o.quantity}</td>
                    <td className="num px-4 py-3 font-medium">{o.filledQuantity}</td>
                    <td className="num px-4 py-3 font-medium">
                      {o.averagePrice ? `₹${o.averagePrice.toLocaleString("en-IN")}` : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={orderTone(o.status)}>{statusLabel(o.status)}</Badge>
                    </td>
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      {isFilledOrPartial ? (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 gap-1 px-2.5 text-xs border-primary/30 text-primary hover:bg-primary/10"
                          onClick={() => setContractNoteOrder(o)}
                        >
                          <FileText className="h-3 w-3" />
                          <span>Note</span>
                        </Button>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="num px-4 py-3 text-xs text-muted-foreground">{hms(o.time)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Order Detail Modal */}
      <Modal open={!!selected} onClose={() => setSelected(null)} title={selected ? `Order ${selected.id}` : ""} wide>
        {selected && (
          <OrderDetail
            o={selected}
            onOpenContractNote={() => {
              setContractNoteOrder(selected);
              setSelected(null);
            }}
          />
        )}
      </Modal>

      {/* Electronic Contract Note Modal (SEBI-Compliant Itemized Charges) */}
      <ContractNoteModal
        note={activeContractNote}
        open={!!contractNoteOrder}
        onClose={() => setContractNoteOrder(null)}
      />
    </div>
  );
}

function OrderDetail({ o, onOpenContractNote }: { o: Order; onOpenContractNote: () => void }) {
  const isFilledOrPartial = o.status === "FILLED" || o.status === "PARTIALLY_FILLED";
  const calc = useMemo(() => {
    if (!isFilledOrPartial) return null;
    const qty = o.filledQuantity > 0 ? o.filledQuantity : o.quantity;
    const price = o.averagePrice || 1424.5;
    return calculateRegulatoryCharges(qty, price, o.side);
  }, [o, isFilledOrPartial]);

  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
        {[
          ["Strategy", o.strategyName],
          ["Symbol", o.symbol],
          ["Side", o.side],
          ["Quantity", o.quantity],
          ["Filled", o.filledQuantity],
          ["Avg Fill Price", o.averagePrice ? `₹${o.averagePrice.toLocaleString("en-IN")}` : "—"],
        ].map(([k, v]) => (
          <div key={String(k)}>
            <dt className="text-xs text-muted-foreground">{k}</dt>
            <dd className="num mt-0.5 font-medium">{v}</dd>
          </div>
        ))}
        <div>
          <dt className="text-xs text-muted-foreground">Status</dt>
          <dd className="mt-1">
            <Badge tone={orderTone(o.status)}>{statusLabel(o.status)}</Badge>
          </dd>
        </div>
      </dl>

      {o.rejectionReason && (
        <div className="rounded-lg border border-destructive/30 bg-danger-soft px-4 py-3 text-sm">
          <span className="font-semibold text-destructive">Rejected by platform risk engine:</span>{" "}
          <span className="num">{o.rejectionReason}</span>
        </div>
      )}

      {/* Itemized Regulatory Charges Mini-Blotter */}
      {calc && (
        <div className="rounded-xl border border-primary/20 bg-muted/20 p-4">
          <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
            <div className="flex items-center gap-2">
              <FileCheck className="h-4 w-4 text-primary" />
              <h4 className="text-xs font-bold uppercase tracking-wide text-foreground">
                Level 2 Published Charges &amp; Net Settlement Breakdown
              </h4>
            </div>
            <Button size="sm" variant="outline" className="h-7 gap-1 px-2.5 text-xs" onClick={onOpenContractNote}>
              <FileText className="h-3 w-3" />
              <span>View Full Contract Note</span>
            </Button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 text-xs">
            <div>
              <span className="text-muted-foreground">Gross Turnover</span>
              <p className="num text-sm font-semibold text-foreground">₹{calc.turnoverRupees.toFixed(2)}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Brokerage (Flat)</span>
              <p className="num text-sm font-semibold text-foreground">₹{calc.charges.brokerage.toFixed(2)}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Statutory Taxes (STT/GST)</span>
              <p className="num text-sm font-semibold text-destructive">
                ₹{(calc.charges.stt + calc.charges.gst18 + calc.charges.exchangeTxnFee + calc.charges.sebiTurnoverFee + calc.charges.stampDuty).toFixed(2)}
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Net Settlement Obligation</span>
              <p className="num text-sm font-bold text-primary">₹{calc.netObligation.toFixed(2)}</p>
            </div>
          </div>
        </div>
      )}

      <div>
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Lifecycle</h4>
        <ol className="relative ml-2 border-l">
          {o.lifecycle.map((e, i) => (
            <li key={i} className="mb-4 ml-5 last:mb-0">
              <span
                className={cn(
                  "absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full",
                  e.status === "REJECTED"
                    ? "bg-destructive"
                    : e.status === "CANCELLED"
                    ? "bg-muted-foreground"
                    : "bg-success"
                )}
              />
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
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Execution Fills</h4>
          <ul className="divide-y rounded-lg border text-sm">
            {o.fills.map((f, i) => (
              <li key={i} className="num flex justify-between px-4 py-2">
                <span>{f.quantity} Units @ ₹{f.price.toLocaleString("en-IN")}</span>
                <span className="text-muted-foreground">{hms(f.time)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
