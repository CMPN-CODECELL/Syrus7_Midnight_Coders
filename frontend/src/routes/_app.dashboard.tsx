import { createFileRoute, Link } from "@tanstack/react-router";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card, CardHeader, Pnl, orderTone } from "@/components/tm/ui";
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

function Metric({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
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

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Account Value"><span className="num">{acc ? inr(acc.accountValue) : "—"}</span></Metric>
        <Metric label="Available Balance"><span className="num">{acc ? inr(acc.availableBalance) : "—"}</span></Metric>
        <Metric label="Today's P&L" hint="Realised + unrealised">{acc ? <Pnl value={acc.todayPnl} /> : "—"}</Metric>
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
    </div>
  );
}
