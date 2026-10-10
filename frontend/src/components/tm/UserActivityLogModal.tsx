import { useState } from "react";
import { Activity, ArrowUpRight, CheckCircle, Clock, RefreshCw, Shield, ShoppingBag, Wallet } from "lucide-react";
import { Badge, Button, Modal } from "./ui";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services";

interface UserActivityLogModalProps {
  open: boolean;
  onClose: () => void;
}

export function UserActivityLogModal({ open, onClose }: UserActivityLogModalProps) {
  const { data: activities = [], isLoading, refetch } = useQuery({
    queryKey: ["user-activities"],
    queryFn: async () => {
      const res = await fetch("http://127.0.0.1:8001/api/user/activities", {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("tm_token") || ""}`,
        },
      });
      if (res.ok) return await res.json();
      return [];
    },
    enabled: open,
  });

  const getActionBadge = (actionType: string) => {
    if (actionType.includes("BUY")) return <Badge tone="success">Buy Trade</Badge>;
    if (actionType.includes("SELL")) return <Badge tone="danger">Sell Trade</Badge>;
    if (actionType.includes("SQUARE_OFF")) return <Badge tone="warning">Square Off</Badge>;
    if (actionType.includes("SUBSCRIBE")) return <Badge tone="primary">Subscription</Badge>;
    if (actionType.includes("CANCEL")) return <Badge tone="neutral">Cancelled</Badge>;
    if (actionType.includes("TOPUP")) return <Badge tone="success">Wallet Top-up</Badge>;
    return <Badge tone="neutral">{actionType}</Badge>;
  };

  return (
    <Modal open={open} onClose={onClose} title="">
      <div className="space-y-4">
        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary" />
            <div>
              <h2 className="text-base font-bold text-foreground">User Audit Trail & Activity Logs</h2>
              <p className="text-xs text-muted-foreground">Every user action, order intent, and subscription change recorded on backend.</p>
            </div>
          </div>
          <Button size="sm" variant="ghost" onClick={() => refetch()} className="h-8 px-2">
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </Button>
        </div>

        {isLoading ? (
          <div className="py-8 text-center text-xs text-muted-foreground">Loading audit log entries...</div>
        ) : activities.length === 0 ? (
          <div className="py-8 text-center text-xs text-muted-foreground">No recent activity recorded.</div>
        ) : (
          <div className="max-h-[380px] overflow-y-auto space-y-2 pr-1">
            {activities.map((act: any) => (
              <div key={act.id} className="rounded-lg border bg-card p-3 text-xs flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    {getActionBadge(act.actionType)}
                    <span className="font-semibold text-foreground">{act.message}</span>
                  </div>
                  {act.symbol && (
                    <div className="text-[11px] text-muted-foreground">
                      Instrument: <strong className="text-foreground">{act.symbol}</strong> | Qty: {act.quantity}
                    </div>
                  )}
                  {act.priceInr > 0 && (
                    <div className="text-[11px] text-muted-foreground">
                      Amount: <strong className="text-foreground">₹{act.priceInr.toFixed(2)}</strong>
                    </div>
                  )}
                </div>
                <div className="text-right text-[10px] text-muted-foreground shrink-0">
                  <Clock className="inline h-3 w-3 mr-1" />
                  {act.timestamp ? new Date(act.timestamp).toLocaleTimeString() : ""}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 flex justify-end border-t pt-3">
          <Button variant="outline" onClick={onClose}>
            Close Audit Trail
          </Button>
        </div>
      </div>
    </Modal>
  );
}
