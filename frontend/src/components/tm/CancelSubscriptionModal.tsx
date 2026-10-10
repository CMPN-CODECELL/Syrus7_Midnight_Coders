import { useState } from "react";
import { AlertTriangle, LogOut } from "lucide-react";
import { Button, Modal } from "./ui";
import { useQueryClient } from "@tanstack/react-query";
import { strategyService, api } from "@/services";

interface CancelSubscriptionModalProps {
  open: boolean;
  onClose: () => void;
  strategyId?: string;
  subscriptionId?: number;
  strategyName?: string;
  symbol?: string;
}

export function CancelSubscriptionModal({
  open,
  onClose,
  strategyId,
  subscriptionId,
  strategyName = "Strategy",
  symbol,
}: CancelSubscriptionModalProps) {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleUnsubscribe = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      if (strategyId) {
        await strategyService.unsubscribe(strategyId);
      } else if (subscriptionId) {
        await api.cancelSubscription(subscriptionId);
      }
      queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "candles" });
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to unsubscribe from strategy.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Unsubscribe Strategy">
      <div className="space-y-4">
        <div className="flex items-center gap-3 rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-warning">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <div>
            <strong className="block font-semibold">Confirm Unsubscription</strong>
            You are about to unsubscribe from <strong>{strategyName}</strong> {symbol ? `(${symbol})` : ""}.
            This strategy will be moved to your Available Strategies list.
          </div>
        </div>

        {errorMsg && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            {errorMsg}
          </div>
        )}

        <div className="rounded-lg border bg-muted/40 p-3 text-xs space-y-2 text-muted-foreground">
          <p>• Automated order execution for this strategy will stop immediately.</p>
          <p>• You can re-subscribe to this strategy at any time from Available Strategies.</p>
          <p>• Any existing open positions can be squared off manually from the Positions tab.</p>
        </div>

        <div className="mt-5 flex justify-end gap-2 border-t pt-3">
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Keep Subscribed
          </Button>
          <Button
            variant="danger"
            disabled={loading}
            onClick={handleUnsubscribe}
          >
            <LogOut className="h-3.5 w-3.5 mr-1" />
            {loading ? "Unsubscribing..." : "Confirm Unsubscribe"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
