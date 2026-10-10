import { useState } from "react";
import { Play, Square, Sliders, ShieldAlert, RotateCcw, ShoppingCart, XCircle } from "lucide-react";
import { Badge, Button, Modal } from "./ui";
import { useKillSwitch, useStrategyAction, useSquareOffStrategy, useResetStrategy } from "@/hooks/queries";
import type { Strategy } from "@/types";
import { inr } from "@/lib/format";
import { StrategyCustomizerModal } from "./StrategyCustomizerModal";
import { SubscribeModal } from "./SubscribeModal";
import { CancelSubscriptionModal } from "./CancelSubscriptionModal";

export { StrategyCustomizerModal } from "./StrategyCustomizerModal";

export function StateBadge({ s }: { s: Strategy }) {
  if (s.state === "RUNNING") return <Badge tone="success" dot>Running</Badge>;
  if (s.state === "SUBSCRIBED") return <Badge tone="primary" dot>Subscribed</Badge>;
  if (s.state === "STOPPED") return <Badge tone="neutral" dot>Stopped</Badge>;
  return <Badge tone="neutral">Available</Badge>;
}

export function StrategyActions({ s }: { s: Strategy }) {
  const [openSubscribe, setOpenSubscribe] = useState(false);
  const [openCancel, setOpenCancel] = useState(false);
  const [openCustomizer, setOpenCustomizer] = useState(false);
  const { data: ks } = useKillSwitch();
  const m = useStrategyAction();
  const blocked = !!ks?.active;

  // Determine real price per strategy
  const priceInr = s.id === "strat_breakout" ? 499 : s.id === "strat_ma" ? 999 : s.id === "strat_rsi" ? 1499 : 499;

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
        <Button size="sm" disabled={blocked} onClick={() => setOpenSubscribe(true)} className="gap-1">
          <ShoppingCart className="h-3.5 w-3.5" />
          Subscribe (₹{priceInr})
        </Button>
      )}

      {s.subscribed && (
        <div className="flex items-center gap-1.5">
          {s.state !== "RUNNING" ? (
            <Button size="sm" disabled={blocked || m.isPending} onClick={() => m.mutate({ id: s.id, action: "start" })}>
              <Play className="h-3.5 w-3.5 mr-1" /> Start
            </Button>
          ) : (
            <Button size="sm" variant="outline" disabled={m.isPending} onClick={() => m.mutate({ id: s.id, action: "stop" })}>
              <Square className="h-3.5 w-3.5 mr-1" /> Stop
            </Button>
          )}

          <Button
            size="sm"
            variant="ghost"
            onClick={() => setOpenCancel(true)}
            className="text-xs text-muted-foreground hover:bg-destructive/10 hover:text-destructive h-8 px-2.5"
            title="Unsubscribe from strategy"
          >
            <XCircle className="h-3.5 w-3.5 mr-1" />
            Unsubscribe
          </Button>
        </div>
      )}

      {/* Subscribe Confirmation & Checkout Modal */}
      <SubscribeModal
        open={openSubscribe}
        onClose={() => setOpenSubscribe(false)}
        strategyId={s.id}
        strategyName={s.name}
        symbol={s.symbol}
        priceInr={priceInr}
      />

      {/* Cancellation Confirmation Modal */}
      <CancelSubscriptionModal
        open={openCancel}
        onClose={() => setOpenCancel(false)}
        strategyId={s.id}
        strategyName={s.name}
        symbol={s.symbol}
      />

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
