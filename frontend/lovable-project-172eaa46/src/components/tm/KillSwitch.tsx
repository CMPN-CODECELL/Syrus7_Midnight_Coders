import { useState } from "react";
import { OctagonAlert, Check, Loader2 } from "lucide-react";
import { Button, Modal } from "./ui";
import { useKillSwitch, useKillSwitchActions } from "@/hooks/queries";

export function KillSwitchButton() {
  const [open, setOpen] = useState(false);
  const { data: ks } = useKillSwitch();
  const { activate, reset } = useKillSwitchActions();
  const active = !!ks?.active;

  return (
    <>
      <Button variant={active ? "danger" : "dangerOutline"} size="sm" onClick={() => setOpen(true)}>
        <OctagonAlert className="h-4 w-4" />
        {active ? "Kill Switch Active" : "Kill Switch"}
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} title={active ? "Kill switch active" : "Activate Kill Switch?"}>
        {active ? (
          <div className="space-y-4">
            <KillSwitchSummary seconds={ks?.executionTimeSec} />
            <p className="text-xs text-muted-foreground">Resetting is available for demo purposes only.</p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)}>Close</Button>
              {/* <Button variant="primary" disabled={reset.isPending} onClick={() => reset.mutate(undefined, { onSuccess: () => setOpen(false) })}>
                Reset Kill Switch
              </Button> */}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">This is an emergency stop for the whole account. It will:</p>
            <ul className="space-y-2 text-sm">
              {["Stop all strategies", "Cancel open orders", "Close open positions", "Block new orders"].map((t) => (
                <li key={t} className="flex items-center gap-2"><Check className="h-4 w-4 text-destructive" />{t}</li>
              ))}
            </ul>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="danger" disabled={activate.isPending} onClick={() => activate.mutate()}>
                {activate.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <OctagonAlert className="h-4 w-4" />}
                Activate Kill Switch
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}

export function KillSwitchSummary({ seconds }: { seconds?: number | undefined }) {
  return (
    <div className="rounded-lg border border-destructive/30 bg-danger-soft p-4">
      <div className="flex items-center gap-2 font-semibold text-destructive">
        <OctagonAlert className="h-5 w-5" /> KILL SWITCH ACTIVE
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-1.5 text-sm">
        {["Strategies stopped", "Orders cancelled", "Positions closed", "New orders blocked"].map((t) => (
          <li key={t} className="flex items-center gap-1.5"><Check className="h-4 w-4 text-success" />{t}</li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted-foreground">Execution time: <span className="num font-medium text-foreground">{seconds ?? 4.3} seconds</span></p>
    </div>
  );
}
