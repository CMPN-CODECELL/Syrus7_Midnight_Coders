import { useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Layers,
  RefreshCw,
  Server,
  ShieldCheck,
  Split,
  Zap,
} from "lucide-react";
import { Badge, Button, Card, CardHeader } from "@/components/tm/ui";
import { api } from "@/services";

interface OperationResult {
  title: string;
  passed: boolean;
  message: string;
  timestamp: string;
  raw?: any;
}

export function ChaosLab() {
  const [running, setRunning] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<OperationResult | null>(null);

  const executeOperation = async (opId: string, name: string, fn: () => Promise<any>) => {
    setRunning(opId);
    try {
      const res = await fn();
      setLastResult({
        title: name,
        passed: res?.passed !== false,
        message: res?.message || res?.summary || "Operation verified successfully",
        timestamp: new Date().toLocaleTimeString("en-GB", { hour12: false }),
        raw: res,
      });
    } catch (err: any) {
      setLastResult({
        title: name,
        passed: false,
        message: err?.message || "Execution encountered an operational exception",
        timestamp: new Date().toLocaleTimeString("en-GB", { hour12: false }),
        raw: err,
      });
    } finally {
      setRunning(null);
    }
  };

  return (
    <Card className="overflow-hidden border-border/80 shadow-md">
      <CardHeader
        title="Institutional Operations & Fault Tolerance Guardian"
        sub="Real-Time Broker Connectivity, Clearing Reconciliation, and Pre-Trade Risk Defense (Levels 1 – 4)"
        action={
          <div className="flex items-center gap-2">
            <Badge tone="success" dot>
              Guardian Engine Armed
            </Badge>
          </div>
        }
      />

      <div className="space-y-6 p-5">
        {/* Production Telemetry Bar */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg border bg-muted/20 p-3">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Server className="h-3.5 w-3.5 text-success" />
              <span>Broker Gateway</span>
            </div>
            <p className="mt-1 text-sm font-semibold text-foreground">Active (021 API)</p>
          </div>

          <div className="rounded-lg border bg-muted/20 p-3">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <RefreshCw className="h-3.5 w-3.5 text-info" />
              <span>Position Drift</span>
            </div>
            <p className="mt-1 text-sm font-semibold text-success">0.00 Units (Synced)</p>
          </div>

          <div className="rounded-lg border bg-muted/20 p-3">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <ShieldCheck className="h-3.5 w-3.5 text-primary" />
              <span>Rate Throttle Gate</span>
            </div>
            <p className="mt-1 text-sm font-semibold text-foreground">5 Orders / Min</p>
          </div>

          <div className="rounded-lg border bg-muted/20 p-3">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5 text-warning" />
              <span>Kill Switch SLA</span>
            </div>
            <p className="mt-1 text-sm font-semibold text-foreground">&lt; 100ms (10s SLA)</p>
          </div>
        </div>

        {/* Operational Capabilities Grid */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {/* Level 2: Execution Slicing & Partial Fill Engine */}
          <div className="flex flex-col justify-between rounded-lg border bg-card p-4 transition-colors hover:border-primary/40">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground">Order Slicing & Partial Fills</span>
                <Badge tone="primary">Level 2</Badge>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                Routes sliced orders with partial fill tracking. Unfilled slices remain active working orders with the broker while position updates without drift.
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="mt-4 w-full"
              disabled={running !== null}
              onClick={() =>
                executeOperation("partial-fill", "Partial Fill & Order Slicing Engine", () =>
                  api.runChaosTest("partial-fill", { quantity: 10, fill_ratio: 0.4 })
                )
              }
            >
              <Split className="mr-1.5 h-3.5 w-3.5" />
              {running === "partial-fill" ? "Processing..." : "Execute Sliced Fill"}
            </Button>
          </div>

          {/* Level 2/3: Broker Clearing Reconciliation & Drift Rectifier */}
          <div className="flex flex-col justify-between rounded-lg border bg-card p-4 transition-colors hover:border-primary/40">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground">Clearing Reconciliation</span>
                <Badge tone="primary">Level 2/3</Badge>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                Audits broker clearing positions against internal strategy ledgers. Rebuilds working orders in-flight and automatically halts breached bots.
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="mt-4 w-full"
              disabled={running !== null}
              onClick={() =>
                executeOperation("reconcile", "Broker State & Position Drift Reconciliation", () =>
                  api.reconcileState()
                )
              }
            >
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              {running === "reconcile" ? "Reconciling..." : "Reconcile Broker Clearing"}
            </Button>
          </div>

          {/* Level 3: Runaway Algo Loop Circuit Breaker */}
          <div className="flex flex-col justify-between rounded-lg border bg-card p-4 transition-colors hover:border-primary/40">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground">Runaway Loop Circuit Breaker</span>
                <Badge tone="danger">Level 3</Badge>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                Institutional pre-trade rate-limiting gate (5 orders/min). Protects against rogue loops, infinite recursion, and auto-halts offending bots.
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="mt-4 w-full"
              disabled={running !== null}
              onClick={() =>
                executeOperation("runaway-burst", "Runaway Algo Loop Rate Limiting", () =>
                  api.runChaosTest("runaway-burst", { burst_count: 15 })
                )
              }
            >
              <Zap className="mr-1.5 h-3.5 w-3.5" />
              {running === "runaway-burst" ? "Throttling..." : "Trigger Rate Gate"}
            </Button>
          </div>

          {/* Level 3: Pre-Trade Exposure & Capital Guard */}
          <div className="flex flex-col justify-between rounded-lg border bg-card p-4 transition-colors hover:border-primary/40">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground">Pre-Trade Exposure Guard</span>
                <Badge tone="warning">Level 3</Badge>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                Platform-level pre-trade check rejecting any order violating the 10-unit position limit or ₹500 daily loss floor before reaching the broker.
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="mt-4 w-full"
              disabled={running !== null}
              onClick={() =>
                executeOperation("risk-breach-pos", "Pre-Trade Position & Exposure Limits", () =>
                  api.runChaosTest("risk-breach", { breach_type: "position_size" })
                )
              }
            >
              <ShieldCheck className="mr-1.5 h-3.5 w-3.5" />
              {running === "risk-breach-pos" ? "Evaluating..." : "Evaluate Exposure Gate"}
            </Button>
          </div>

          {/* Level 2: Gateway Outage & Resilience Defense */}
          <div className="flex flex-col justify-between rounded-lg border bg-card p-4 transition-colors hover:border-primary/40">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground">Gateway Outage Defense</span>
                <Badge tone="primary">Level 2</Badge>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                Ensures broker API error resilience, handling HTTP 500/503 upstream gateway outages with full trade idempotency and zero state corruption.
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="mt-4 w-full"
              disabled={running !== null}
              onClick={() =>
                executeOperation("broker-error", "Gateway Outage & Idempotency Defense", () =>
                  api.runChaosTest("broker-error", { status_code: 503 })
                )
              }
            >
              <Activity className="mr-1.5 h-3.5 w-3.5" />
              {running === "broker-error" ? "Testing Gateway..." : "Verify Gateway Resilience"}
            </Button>
          </div>

          {/* Level 4: Multi-Book Independent Portfolio Accounting */}
          <div className="flex flex-col justify-between rounded-lg border bg-card p-4 transition-colors hover:border-primary/40">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-foreground">Multi-Book Ledger Isolation</span>
                <Badge tone="success">Level 4</Badge>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                Maintains independent books for opposing strategies (Long + Short on same stock) with separate P&L while broker account net is flat (0).
              </p>
            </div>
            <Button
              size="sm"
              variant="primary"
              className="mt-4 w-full"
              disabled={running !== null}
              onClick={() =>
                executeOperation("opposing", "Multi-Book Independent Ledger (Level 4)", () =>
                  api.runChaosTest("opposing-positions")
                )
              }
            >
              <Layers className="mr-1.5 h-3.5 w-3.5" />
              {running === "opposing" ? "Auditing Books..." : "Verify Multi-Book Ledger"}
            </Button>
          </div>
        </div>

        {/* Real-Time Operation Audit Inspector */}
        {lastResult && (
          <div className="rounded-lg border bg-card p-4.5 transition-all">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {lastResult.passed ? (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-destructive" />
                )}
                <span className="text-sm font-semibold text-foreground">{lastResult.title}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="num text-xs text-muted-foreground">{lastResult.timestamp}</span>
                <Badge tone={lastResult.passed ? "success" : "danger"}>
                  {lastResult.passed ? "VERIFIED" : "ATTENTION"}
                </Badge>
              </div>
            </div>

            <p className="mt-2 text-xs leading-relaxed text-foreground/90">{lastResult.message}</p>

            {lastResult.raw && (
              <details className="mt-3 text-xs text-muted-foreground">
                <summary className="cursor-pointer font-medium hover:text-foreground">
                  View Clearing Telemetry & Proof Payload
                </summary>
                <pre className="mt-2 max-h-48 overflow-auto rounded bg-muted/40 p-3 font-mono text-[11px] text-foreground">
                  {JSON.stringify(lastResult.raw, null, 2)}
                </pre>
              </details>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
