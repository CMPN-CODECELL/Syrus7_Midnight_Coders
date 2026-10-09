import { createFileRoute } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";
import { Badge, Card, CardHeader, PageHeader, Progress } from "@/components/tm/ui";
import { KillSwitchButton, KillSwitchSummary } from "@/components/tm/KillSwitch";
import { useKillSwitch, useRiskEvents, useRiskStatus } from "@/hooks/queries";
import { inr } from "@/lib/format";
import type { RiskEvent } from "@/types";

export const Route = createFileRoute("/_app/risk-controls")({
  head: () => ({
    meta: [
      { title: "Risk Controls — TradeMint" },
      { name: "description", content: "Daily loss, position size and order-rate limits, the kill switch and the risk event log." },
      { property: "og:title", content: "Risk Controls — TradeMint" },
      { property: "og:description", content: "Strategies can fail. Risk controls cannot." },
    ],
  }),
  component: Risk,
});

const level = (pct: number) => (pct >= 90 ? "danger" : pct >= 70 ? "warning" : "success") as "success" | "warning" | "danger";

function LimitCard({ label, current, max, fmt }: { label: string; current: number; max: number; fmt: (n: number) => string }) {
  const pct = (current / max) * 100;
  const l = level(pct);
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">{label}</p>
        <Badge tone={l} dot>{l === "success" ? "Safe" : l === "warning" ? "Warning" : "Breach"}</Badge>
      </div>
      <p className="mt-3 text-sm text-muted-foreground">
        <span className="num text-xl font-semibold text-foreground">{fmt(current)}</span> / <span className="num">{fmt(max)}</span>
      </p>
      <div className="mt-3"><Progress value={pct} tone={l} /></div>
      <p className="num mt-2 text-xs text-muted-foreground">{pct.toFixed(0)}% utilised</p>
    </Card>
  );
}

const evTone: Record<RiskEvent["type"], "success" | "danger" | "warning" | "neutral"> = {
  APPROVED: "success", REJECTED: "danger", PARTIAL_FILL: "warning", KILL_SWITCH: "danger", INFO: "neutral",
};

function Risk() {
  const { data: r } = useRiskStatus();
  const { data: events = [] } = useRiskEvents();
  const { data: ks } = useKillSwitch();

  return (
    <div className="space-y-6">
      <PageHeader title="Risk Controls" sub="Strategies can fail. Risk controls cannot. Every order passes these checks before reaching the broker." />

      <Card className="flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="flex items-center gap-4">
          <div className={`flex h-12 w-12 items-center justify-center rounded-full ${ks?.active ? "bg-danger-soft text-destructive" : "bg-success-soft text-success"}`}>
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Overall risk status</p>
            <p className={`text-xl font-semibold ${ks?.active ? "text-destructive" : "text-success"}`}>{ks?.active ? "HALTED" : r?.overall ?? "SAFE"}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge tone="success">Daily loss: Safe</Badge>
          <Badge tone="success">Position size: Safe</Badge>
          <Badge tone="success">Order rate: Safe</Badge>
          <Badge tone={ks?.active ? "danger" : "primary"}>Kill switch: {ks?.active ? "Active" : "Armed"}</Badge>
        </div>
      </Card>

      {r && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <LimitCard label="Daily loss limit" current={r.currentLoss} max={r.limits.maxDailyLoss} fmt={(n) => inr(n)} />
          <LimitCard label="Maximum position size" current={r.currentMaxPosition} max={r.limits.maxPositionSize} fmt={String} />
          <LimitCard label="Maximum orders / minute" current={r.currentOrdersPerMinute} max={r.limits.maxOrdersPerMinute} fmt={String} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Risk event log" sub="Decisions from the risk engine" />
          <ul className="max-h-[420px] divide-y overflow-y-auto">
            {events.map((e) => (
              <li key={e.id} className="flex gap-4 px-5 py-3 text-sm">
                <span className="num w-16 shrink-0 text-xs text-muted-foreground">{e.time}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={evTone[e.type]}>{e.type.replace("_", " ")}</Badge>
                    <span>{e.message}</span>
                  </div>
                  {e.reason && <p className="num mt-1 text-xs text-destructive">Reason: {e.reason}</p>}
                </div>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <CardHeader title="Kill switch" sub="Platform-level emergency stop" />
          <div className="space-y-4 p-5">
            {ks?.active ? (
              <KillSwitchSummary seconds={ks.executionTimeSec} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Armed. When activated, all strategies stop, open orders are cancelled, positions are closed, and new orders are blocked.
              </p>
            )}
            <KillSwitchButton />
          </div>
        </Card>
      </div>
    </div>
  );
}
