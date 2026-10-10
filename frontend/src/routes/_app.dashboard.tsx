import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Mail, ShieldCheck, ArrowRight } from "lucide-react";
import { Badge, Button, Card, CardHeader, Pnl, orderTone } from "@/components/tm/ui";
import { EmailStatementModal } from "@/components/tm/EmailStatementModal";
import { useAccount, useKillSwitch, useOrders, usePnlHistory, useStrategies } from "@/hooks/queries";
import { hms, inr, statusLabel } from "@/lib/format";

export const Route = createFileRoute("/_app/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — TradeShield" },
      { name: "description", content: "Account value, today's P&L, strategy performance and risk status at a glance." },
      { property: "og:title", content: "Dashboard — TradeShield" },
      { property: "og:description", content: "Your algorithmic trading overview." },
    ],
  }),
  component: Dashboard,
});

function Metric({
  label,
  children,
  hint,
  action,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        {action}
      </div>
      <div className="mt-2 text-2xl font-semibold">{children}</div>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </Card>
  );
}

function Dashboard() {
  const { data: acc } = useAccount();
  const { data: pnl = [] } = usePnlHistory();
  const { data: strategies = [] } = useStrategies();
  const { data: orders = [] } = useOrders();
  const { data: ks } = useKillSwitch();
  const [emailModalOpen, setEmailModalOpen] = useState(false);

  return (
    <div className="space-y-6">
      {/* Daily P&L Statement & Regulatory Tax Breakdown Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-xl border border-primary/20 bg-primary/5 p-4 shadow-sm">
        <div className="flex items-start sm:items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Mail className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold">Daily P&amp;L Statement &amp; Regulatory Tax Invoicing</h3>
              <Badge tone="success" dot className="hidden sm:inline-flex">
                SEBI SCRA Rule 15
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Automated institutional statement with itemized tariffs (Brokerage ₹20, STT 0.025%, GST 18%, Stamp Duty) dispatched via SMTP.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Button
            size="sm"
            onClick={() => setEmailModalOpen(true)}
            className="gap-1.5 w-full sm:w-auto shadow-sm"
          >
            <Mail className="h-4 w-4" /> Email P&amp;L Statement
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Account Value"><span className="num">{acc ? inr(acc.accountValue) : "—"}</span></Metric>
        <Metric label="Available Balance"><span className="num">{acc ? inr(acc.availableBalance) : "—"}</span></Metric>
        <Metric
          label="Today's P&L"
          hint="Realised + unrealised"
          action={
            <button
              onClick={() => setEmailModalOpen(true)}
              className="text-[11px] font-medium text-primary hover:underline inline-flex items-center gap-1 cursor-pointer"
              title="Email P&L Statement"
            >
              <Mail className="h-3 w-3" /> Email Report
            </button>
          }
        >
          {acc ? <Pnl value={acc.todayPnl} /> : "—"}
        </Metric>
        <Metric label="Risk Status" hint={ks?.active ? "Kill switch engaged" : "All limits within range"}>
          {ks?.active ? <Badge tone="danger" dot className="text-sm">Halted</Badge> : <Badge tone="success" dot className="text-sm">{acc?.riskStatus ?? "SAFE"}</Badge>}
        </Metric>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Intraday P&L" sub="Today, all strategies" />
          <div className="h-72 p-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={pnl} margin={{ left: 8, right: 8, top: 8 }}>
                <defs>
                  <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.18} />
                    <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 4" vertical={false} />
                <XAxis dataKey="time" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${v}`} width={60} />
                <Tooltip contentStyle={{ borderRadius: 8, border: "1px solid var(--border)", fontSize: 12 }} formatter={(v) => [inr(Number(v)), "P&L"]} />
                <Area type="monotone" dataKey="pnl" stroke="var(--primary)" strokeWidth={2} fill="url(#pnlFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader title="Strategy Performance" action={<Link to="/strategies" className="text-xs text-primary hover:underline">View all</Link>} />
          <ul className="divide-y">
            {strategies.map((s) => (
              <li key={s.id} className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="text-sm font-medium">{s.name}</p>
                  <p className="text-xs text-muted-foreground">{s.symbol} · {s.timeframe}</p>
                </div>
                <div className="text-right">
                  <Pnl value={s.pnl} className="text-sm" />
                  <div className="mt-1">
                    <Badge tone={s.state === "RUNNING" ? "success" : "neutral"} dot>{s.state === "RUNNING" ? "Running" : s.state === "AVAILABLE" ? "Not subscribed" : "Stopped"}</Badge>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card>
        <CardHeader title="Recent Orders" action={<Link to="/orders" className="text-xs text-primary hover:underline">All orders</Link>} />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b">{["Strategy", "Symbol", "Side", "Qty", "Filled", "Status", "Time"].map((h) => <th key={h} className="px-5 py-2.5 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody>
              {orders.slice(0, 5).map((o) => (
                <tr key={o.id} className="border-b last:border-0">
                  <td className="px-5 py-3">{o.strategyName}</td>
                  <td className="px-5 py-3 font-medium">{o.symbol}</td>
                  <td className={`px-5 py-3 font-semibold ${o.side === "BUY" ? "text-success" : "text-destructive"}`}>{o.side}</td>
                  <td className="num px-5 py-3">{o.quantity}</td>
                  <td className="num px-5 py-3">{o.filledQuantity}</td>
                  <td className="px-5 py-3"><Badge tone={orderTone(o.status)}>{statusLabel(o.status)}</Badge></td>
                  <td className="num px-5 py-3 text-muted-foreground">{hms(o.time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <EmailStatementModal open={emailModalOpen} onClose={() => setEmailModalOpen(false)} />
    </div>
  );
}

