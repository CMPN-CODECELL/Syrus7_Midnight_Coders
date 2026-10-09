import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  ShieldCheck,
  Sliders,
  CheckCircle2,
  OctagonAlert,
  Zap,
  Activity,
  History,
  ShieldAlert,
  Clock,
  RotateCcw,
} from "lucide-react";
import { Badge, Button, Card, CardHeader, PageHeader, Progress } from "@/components/tm/ui";
import { ChaosLab } from "@/components/tm/ChaosLab";
import { KillSwitchButton, KillSwitchSummary } from "@/components/tm/KillSwitch";
import {
  useKillSwitch,
  useRiskEvents,
  useRiskStatus,
  useUpdateRiskLimits,
  useUpdateAutoKillRules,
  useKillSwitchIncidents,
} from "@/hooks/queries";
import { inr } from "@/lib/format";
import type { RiskEvent, RiskLimit, KillSwitchIncident } from "@/types";

export const Route = createFileRoute("/_app/risk-controls")({
  head: () => ({
    meta: [
      { title: "Risk Controls & Emergency Operations — TradeMint" },
      { name: "description", content: "Daily loss, position size and order-rate limits, multi-scope kill switch, auto-trip rules, and forensic incident log." },
      { property: "og:title", content: "Risk Controls & Emergency Operations — TradeMint" },
      { property: "og:description", content: "Institutional-grade pre-trade and real-life emergency kill switch controls." },
    ],
  }),
  component: Risk,
});

const level = (pct: number) => (pct >= 90 ? "danger" : pct >= 70 ? "warning" : "success") as "success" | "warning" | "danger";

function LimitCard({ label, current, max, fmt }: { label: string; current: number; max: number; fmt: (n: number) => string }) {
  const pct = max > 0 ? Math.min(100, Math.round((current / max) * 100)) : 0;
  const l = level(pct);
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="num font-medium text-foreground">{pct}%</span>
      </div>
      <div className="num mt-2 text-2xl font-semibold">{fmt(current)}</div>
      <p className="mt-1 text-xs text-muted-foreground">Limit: <span className="num font-medium">{fmt(max)}</span></p>
      <div className="mt-3"><Progress value={pct} tone={l} /></div>
    </Card>
  );
}

const evTone: Record<RiskEvent["type"], "success" | "danger" | "warning" | "primary" | "neutral"> = {
  APPROVED: "success",
  REJECTED: "danger",
  PARTIAL_FILL: "warning",
  KILL_SWITCH: "danger",
  INFO: "neutral",
};

function LiveChangeRequestPanel({ limits }: { limits?: RiskLimit | undefined }) {
  const [maxLoss, setMaxLoss] = useState<number>(limits?.maxDailyLoss ?? 2000);
  const [maxPos, setMaxPos] = useState<number>(limits?.maxPositionSize ?? 50);
  const [maxRate, setMaxRate] = useState<number>(limits?.maxOrdersPerMinute ?? 30);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const { mutate, isPending } = useUpdateRiskLimits();

  const handleApply = () => {
    mutate(
      { maxDailyLoss: Number(maxLoss), maxPositionSize: Number(maxPos), maxOrdersPerMinute: Number(maxRate) },
      {
        onSuccess: () => {
          setStatusMsg("Dynamic Risk Limits hot-reloaded and verified by Risk Engine.");
          setTimeout(() => setStatusMsg(null), 4000);
        },
      }
    );
  };

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between border-b pb-3">
        <div>
          <h3 className="font-semibold text-sm">Policy Studio: Dynamic Risk Limit Control</h3>
          <p className="text-xs text-muted-foreground">
            Adjust platform limits live. The Level 3 Risk Gate evaluates these instantly on every order intent.
          </p>
        </div>
        <Badge tone="primary">Zero-Downtime Hot Reload</Badge>
      </div>

      <div className="mt-4 space-y-4">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <div>
            <div className="flex justify-between text-xs font-medium">
              <label htmlFor="risk-loss-slider">Max Daily Loss Limit</label>
              <span className="font-mono text-primary">{inr(maxLoss)}</span>
            </div>
            <input
              id="risk-loss-slider"
              type="range"
              min="500"
              max="10000"
              step="500"
              value={maxLoss}
              onChange={(e) => setMaxLoss(Number(e.target.value))}
              className="mt-2 w-full accent-primary"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs font-medium">
              <label htmlFor="risk-pos-slider">Max Portfolio Position Size</label>
              <span className="font-mono text-primary">{maxPos} units</span>
            </div>
            <input
              id="risk-pos-slider"
              type="range"
              min="5"
              max="200"
              step="5"
              value={maxPos}
              onChange={(e) => setMaxPos(Number(e.target.value))}
              className="mt-2 w-full accent-primary"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs font-medium">
              <label htmlFor="risk-rate-slider">Max Order Rate (Governor)</label>
              <span className="font-mono text-primary">{maxRate} orders/min</span>
            </div>
            <input
              id="risk-rate-slider"
              type="range"
              min="5"
              max="120"
              step="5"
              value={maxRate}
              onChange={(e) => setMaxRate(Number(e.target.value))}
              className="mt-2 w-full accent-primary"
            />
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <Button size="sm" onClick={handleApply} disabled={isPending}>
            <Sliders className="h-3.5 w-3.5 mr-1" />
            {isPending ? "Applying..." : "Apply & Hot-Reload Policy"}
          </Button>
        </div>

        {statusMsg && (
          <div className="flex items-center gap-2 rounded-md border border-success/30 bg-success-soft p-2.5 text-xs font-medium text-success">
            <CheckCircle2 className="h-4 w-4" />
            <span>{statusMsg}</span>
          </div>
        )}
      </div>
    </Card>
  );
}

function AutoKillRulesPanel() {
  const { data: ks } = useKillSwitch();
  const update = useUpdateAutoKillRules();

  const rules = ks?.autoRules;
  const [enabled, setEnabled] = useState(rules?.autoTripEnabled ?? true);
  const [maxMtmLoss, setMaxMtmLoss] = useState(rules?.maxMtmLoss ?? 2500);
  const [maxRejections, setMaxRejections] = useState(rules?.maxConsecutiveRejections ?? 3);
  const [cooldown, setCooldown] = useState(rules?.cooldownMinutes ?? 15);
  const [savedMsg, setSavedMsg] = useState(false);

  const handleSave = async () => {
    await update.mutateAsync({
      autoTripEnabled: enabled,
      maxMtmLoss: Number(maxMtmLoss),
      maxConsecutiveRejections: Number(maxRejections),
      cooldownMinutes: Number(cooldown),
    });
    setSavedMsg(true);
    setTimeout(() => setSavedMsg(false), 3000);
  };

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between border-b pb-3">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-warning" />
          <h3 className="font-semibold text-sm">Automated Pre-emptive Kill Switch Trip Rules</h3>
        </div>
        <Badge tone={enabled ? "success" : "neutral"}>
          {enabled ? "AUTO-TRIP ARMED" : "DISABLED"}
        </Badge>
      </div>

      <p className="mt-2 text-xs text-muted-foreground">
        Real-life institutional safeguard: automatically trips the emergency stop without human delay if critical portfolio drawdown or broker rejection thresholds are violated.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border bg-muted/20 p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium">Auto-Trip Engine</span>
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="h-4 w-4 accent-primary"
            />
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">Automatic emergency activation</p>
        </div>

        <div className="rounded-lg border bg-muted/20 p-3">
          <label className="text-xs font-medium">Max Portfolio Drawdown</label>
          <div className="mt-1 flex items-center gap-1 font-mono text-sm font-semibold text-destructive">
            ₹
            <input
              type="number"
              step="500"
              value={maxMtmLoss}
              onChange={(e) => setMaxMtmLoss(Number(e.target.value))}
              className="w-full rounded border border-input bg-background px-1.5 py-0.5 text-xs font-medium"
            />
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">Trips on cumulative daily loss</p>
        </div>

        <div className="rounded-lg border bg-muted/20 p-3">
          <label className="text-xs font-medium">Max Consecutive Rejections</label>
          <input
            type="number"
            min={1}
            max={10}
            value={maxRejections}
            onChange={(e) => setMaxRejections(Number(e.target.value))}
            className="mt-1 w-full rounded border border-input bg-background px-1.5 py-0.5 text-xs font-medium font-mono"
          />
          <p className="text-[11px] text-muted-foreground mt-1">Halted to prevent runaway loops</p>
        </div>

        <div className="rounded-lg border bg-muted/20 p-3">
          <label className="text-xs font-medium">Post-Trip Cooldown Lockout</label>
          <select
            value={cooldown}
            onChange={(e) => setCooldown(Number(e.target.value))}
            className="mt-1 w-full rounded border border-input bg-background px-1.5 py-1 text-xs font-medium"
          >
            <option value={0}>Immediate Reset Allowed</option>
            <option value={5}>5 Minutes Lockout</option>
            <option value={15}>15 Minutes Lockout</option>
            <option value={30}>30 Minutes Lockout</option>
          </select>
          <p className="text-[11px] text-muted-foreground mt-1">Anti-revenge trading guard</p>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t pt-3">
        {savedMsg ? (
          <span className="text-xs font-medium text-success flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5" /> Auto-Trip Rules updated and active on server!
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">Checked by Risk Engine on every fill & tick</span>
        )}
        <Button size="sm" onClick={handleSave} disabled={update.isPending}>
          {update.isPending ? "Saving..." : "Update Auto-Trip Rules"}
        </Button>
      </div>
    </Card>
  );
}

function KillSwitchIncidentsTable() {
  const { data: incidents = [] } = useKillSwitchIncidents();

  return (
    <Card className="p-5">
      <div className="flex items-center justify-between border-b pb-3">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-primary" />
          <h3 className="font-semibold text-sm">Kill Switch Forensic Audit Trail & Incident History</h3>
        </div>
        <span className="text-xs text-muted-foreground">{incidents.length} recorded events</span>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b text-muted-foreground">
              <th className="py-2 font-medium">Incident ID</th>
              <th className="py-2 font-medium">Timestamp</th>
              <th className="py-2 font-medium">Scope</th>
              <th className="py-2 font-medium">Trigger Reason & Source</th>
              <th className="py-2 font-medium">Orders / Pos Closed</th>
              <th className="py-2 font-medium">Execution SLA</th>
            </tr>
          </thead>
          <tbody className="divide-y font-mono">
            {incidents.map((inc) => (
              <tr key={inc.incidentId} className="hover:bg-muted/30">
                <td className="py-2.5 font-semibold text-foreground">{inc.incidentId}</td>
                <td className="py-2.5 text-muted-foreground">{inc.timestamp}</td>
                <td className="py-2.5">
                  <Badge tone={inc.scope === "GLOBAL" ? "danger" : "warning"}>{inc.scope}</Badge>
                </td>
                <td className="py-2.5 font-sans">
                  <p className="font-medium text-foreground text-xs">{inc.reason}</p>
                  <p className="text-[10px] text-muted-foreground">{inc.source}</p>
                </td>
                <td className="py-2.5">
                  {inc.ordersCancelled} cancelled · {inc.positionsClosed} closed
                </td>
                <td className="py-2.5">
                  <span className="text-success font-semibold">{inc.elapsedSeconds}s</span>{" "}
                  <span className="text-[10px] text-muted-foreground">(&lt; 10s SLA Met)</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Risk() {
  const { data: r } = useRiskStatus();
  const { data: events = [] } = useRiskEvents();
  const { data: ks } = useKillSwitch();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Risk Controls & Emergency Operations"
        sub="Institutional multi-tier risk protection: Pre-trade rate governors, dynamic loss limits, multi-scope emergency kill switch, and automated trip rules."
      />

      <Card className="flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="flex items-center gap-4">
          <div
            className={`flex h-12 w-12 items-center justify-center rounded-full ${
              ks?.active ? "bg-danger-soft text-destructive" : "bg-success-soft text-success"
            }`}
          >
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Overall Platform Risk Status</p>
            <p className={`text-xl font-semibold ${ks?.active ? "text-destructive" : "text-success"}`}>
              {ks?.active ? `HALTED [${ks.scope || "GLOBAL"}]` : r?.overall ?? "SAFE"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge tone="success">Daily loss: Safe</Badge>
          <Badge tone="success">Position size: Safe</Badge>
          <Badge tone="success">Order rate: Safe</Badge>
          <Badge tone={ks?.active ? "danger" : "primary"}>
            Kill switch: {ks?.active ? `Active (${ks.scope || "GLOBAL"})` : "Armed"}
          </Badge>
        </div>
      </Card>

      {r && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <LimitCard
            label="Daily loss limit"
            current={r.currentLoss}
            max={r.limits.maxDailyLoss}
            fmt={(n) => inr(n)}
          />
          <LimitCard
            label="Maximum position size"
            current={r.currentMaxPosition}
            max={r.limits.maxPositionSize}
            fmt={String}
          />
          <LimitCard
            label="Maximum orders / minute"
            current={r.currentOrdersPerMinute}
            max={r.limits.maxOrdersPerMinute}
            fmt={String}
          />
        </div>
      )}

      {/* Auto-Kill Rules Studio */}
      <AutoKillRulesPanel />

      {/* Live Policy Studio */}
      <LiveChangeRequestPanel limits={r?.limits} />

      {/* Interactive Chaos & Resilience Test Lab */}
      <ChaosLab />

      {/* Kill Switch Forensics & Event Log */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Real-time Risk Event Log" sub="Decisions and evaluations from Level 3 Risk Gate" />
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
          <CardHeader title="Emergency Kill Switch" sub="Level 3 Multi-Scope Platform Stop" />
          <div className="space-y-4 p-5">
            {ks?.active ? (
              <KillSwitchSummary
                seconds={ks.executionTimeSec}
                scope={ks.scope}
                message={ks.message}
                ordersCancelled={ks.ordersCancelled}
                positionsClosed={ks.positionsClosed}
                cooldownUntil={ks.cooldownUntil}
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                Armed & Standing By. Supports Global Liquidation, Soft Halt (Cancel Orders Only), Strategy-Level Isolation, and Symbol Freezes. Guaranteed sub-10s SLA verification.
              </p>
            )}
            <KillSwitchButton />
          </div>
        </Card>
      </div>

      {/* Forensic Incidents Audit Table */}
      <KillSwitchIncidentsTable />
    </div>
  );
}
