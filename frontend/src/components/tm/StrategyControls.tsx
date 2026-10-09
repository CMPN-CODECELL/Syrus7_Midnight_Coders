import { useState } from "react";
import { Play, Square, Sliders, ShieldAlert, RotateCcw } from "lucide-react";
import { Badge, Button, Modal } from "./ui";
import { useKillSwitch, useStrategyAction, useSquareOffStrategy, useResetStrategy } from "@/hooks/queries";
import type { Strategy } from "@/types";
import { inr } from "@/lib/format";
import { StrategyCustomizerModal } from "./StrategyCustomizerModal";

export { StrategyCustomizerModal } from "./StrategyCustomizerModal";

export function StateBadge({ s }: { s: Strategy }) {
  if (s.state === "RUNNING") return <Badge tone="success" dot>Running</Badge>;
  if (s.state === "SUBSCRIBED") return <Badge tone="primary" dot>Subscribed</Badge>;
  if (s.state === "STOPPED") return <Badge tone="neutral" dot>Stopped</Badge>;
  return <Badge tone="neutral">Available</Badge>;
}

export function StrategyActions({ s }: { s: Strategy }) {
  const [openSubscribe, setOpenSubscribe] = useState(false);
  const [openCustomizer, setOpenCustomizer] = useState(false);
  const { data: ks } = useKillSwitch();
  const m = useStrategyAction();
  const blocked = !!ks?.active;

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        onClick={() => setOpenCustomizer(true)}
        className="inline-flex items-center gap-1.5"
      >
        <Sliders className="h-3.5 w-3.5 text-primary" />
        Customize
      </Button>

      {!s.subscribed && (
        <Button size="sm" disabled={blocked} onClick={() => setOpenSubscribe(true)}>
          Subscribe
        </Button>
      )}
      {s.subscribed && s.state !== "RUNNING" && (
        <Button size="sm" disabled={blocked || m.isPending} onClick={() => m.mutate({ id: s.id, action: "start" })}>
          <Play className="h-3.5 w-3.5" /> Start
        </Button>
      )}
      {s.state === "RUNNING" && (
        <Button size="sm" variant="outline" disabled={m.isPending} onClick={() => m.mutate({ id: s.id, action: "stop" })}>
          <Square className="h-3.5 w-3.5" /> Stop
        </Button>
      )}

      {/* Subscribe Confirmation Modal */}
      <Modal open={openSubscribe} onClose={() => setOpenSubscribe(false)} title={`Subscribe to ${s.name}`}>
        <dl className="space-y-3 text-sm">
          <Row k="Symbol" v={s.symbol} />
          <Row k="Candle timeframe" v={s.timeframe} />
          <div className="rounded-lg border bg-muted/40 p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Risk limits (enforced by platform)
            </p>
            <Row k="Maximum daily loss" v={inr(s.limits.maxDailyLoss)} />
            <Row k="Maximum position size" v={String(s.limits.maxPositionSize)} />
            <Row k="Maximum orders / minute" v={String(s.limits.maxOrdersPerMinute)} />
          </div>
        </dl>
        <p className="mt-4 text-xs text-muted-foreground">
          Past performance does not guarantee future results. Every order is checked by the risk engine before it is sent.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setOpenSubscribe(false)}>
            Cancel
          </Button>
          <Button
            disabled={m.isPending}
            onClick={() => m.mutate({ id: s.id, action: "subscribe" }, { onSuccess: () => setOpenSubscribe(false) })}
          >
            Subscribe
          </Button>
        </div>
      </Modal>

      {/* Full Customizer Modal */}
      <StrategyCustomizerModal
        open={openCustomizer}
        onClose={() => setOpenCustomizer(false)}
        strategy={s}
      />
    </>
  );
}

export function StrategySquareOffButton({ s }: { s: Strategy }) {
  const [open, setOpen] = useState(false);
  const sq = useSquareOffStrategy();
  const hasPos = Boolean(s.positionQty && s.positionQty !== 0);

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        disabled={!hasPos || sq.isPending}
        onClick={() => setOpen(true)}
        className="text-destructive hover:bg-destructive/10"
      >
        <ShieldAlert className="h-3.5 w-3.5 mr-1" />
        Square Off
      </Button>

      <Modal open={open} onClose={() => setOpen(false)} title="Confirm Strategy Position Square Off">
        <p className="text-sm text-muted-foreground">
          This will immediately place a market order to close out all open positions held by{" "}
          <strong className="text-foreground">{s.name}</strong> ({s.positionQty} {s.symbol}).
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={sq.isPending}
            onClick={() => sq.mutate(s.id, { onSuccess: () => setOpen(false) })}
          >
            {sq.isPending ? "Closing..." : "Square Off Immediately"}
          </Button>
        </div>
      </Modal>
    </>
  );
}

export function StrategyResetButton({ s }: { s: Strategy }) {
  const reset = useResetStrategy();

  return (
    <Button
      size="sm"
      variant="ghost"
      disabled={reset.isPending}
      onClick={() => reset.mutate(s.id)}
      className="text-xs text-muted-foreground hover:text-foreground"
      title="Reset intraday entry cycles to allow re-entering on demand"
    >
      <RotateCcw className={`h-3 w-3 mr-1 ${reset.isPending ? "animate-spin" : ""}`} />
      Reset Cycle
    </Button>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between py-0.5">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="num font-medium">{v}</dd>
    </div>
  );
}
