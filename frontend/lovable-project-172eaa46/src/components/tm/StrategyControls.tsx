import { useState } from "react";
import { Play, Square } from "lucide-react";
import { Badge, Button, Modal } from "./ui";
import { useKillSwitch, useStrategyAction } from "@/hooks/queries";
import type { Strategy } from "@/types";
import { inr } from "@/lib/format";

export function StateBadge({ s }: { s: Strategy }) {
  if (s.state === "RUNNING") return <Badge tone="success" dot>Running</Badge>;
  if (s.state === "SUBSCRIBED") return <Badge tone="primary" dot>Subscribed</Badge>;
  if (s.state === "STOPPED") return <Badge tone="neutral" dot>Stopped</Badge>;
  return <Badge tone="neutral">Available</Badge>;
}

export function StrategyActions({ s }: { s: Strategy }) {
  const [open, setOpen] = useState(false);
  const { data: ks } = useKillSwitch();
  const m = useStrategyAction();
  const blocked = !!ks?.active;

  return (
    <>
      {!s.subscribed && (
        <Button size="sm" disabled={blocked} onClick={() => setOpen(true)}>Subscribe</Button>
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
      <Modal open={open} onClose={() => setOpen(false)} title={`Subscribe to ${s.name}`}>
        <dl className="space-y-3 text-sm">
          <Row k="Symbol" v={s.symbol} />
          <Row k="Candle timeframe" v={s.timeframe} />
          <div className="rounded-lg border bg-muted/40 p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Risk limits (enforced by platform)</p>
            <Row k="Maximum daily loss" v={inr(s.limits.maxDailyLoss)} />
            <Row k="Maximum position size" v={String(s.limits.maxPositionSize)} />
            <Row k="Maximum orders / minute" v={String(s.limits.maxOrdersPerMinute)} />
          </div>
        </dl>
        <p className="mt-4 text-xs text-muted-foreground">Past performance does not guarantee future results. Every order is checked by the risk engine before it is sent.</p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          <Button disabled={m.isPending} onClick={() => m.mutate({ id: s.id, action: "subscribe" }, { onSuccess: () => setOpen(false) })}>Subscribe</Button>
        </div>
      </Modal>
    </>
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
