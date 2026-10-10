import { useState } from "react";
import { CheckCircle2, CreditCard, ShieldCheck, Sparkles, Wallet, Zap } from "lucide-react";
import { Badge, Button, Modal } from "./ui";
import { inr } from "@/lib/format";
import { authService, api } from "@/services";
import { useMutation, useQueryClient } from "@tanstack/react-query";

interface SubscribeModalProps {
  open: boolean;
  onClose: () => void;
  strategyId?: string;
  strategyName?: string;
  symbol?: string;
  priceInr?: number;
  planCode?: string;
  planName?: string;
}

export function SubscribeModal({
  open,
  onClose,
  strategyId,
  strategyName = "Algo Strategy Pass",
  symbol = "RELIANCE",
  priceInr = 499,
  planCode,
  planName,
}: SubscribeModalProps) {
  const user = authService.getCurrentUser();
  const queryClient = useQueryClient();

  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("monthly");
  const [paymentMethod, setPaymentMethod] = useState<"WALLET" | "UPI" | "CREDIT_CARD">("WALLET");
  const [receipt, setReceipt] = useState<any | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const basePrice = billingCycle === "annual" ? Math.round(priceInr * 10 * 0.8) : priceInr;
  const gstAmount = Math.round(basePrice * 0.18);
  const totalPrice = basePrice + gstAmount;

  const walletBalance = user?.account_balance_inr ?? 100000;
  const hasSufficientWallet = walletBalance >= totalPrice;

  const buyMutation = useMutation({
    mutationFn: async () => {
      setErrorMsg(null);
      const payload: Record<string, string> = {
        billing_cycle: billingCycle,
        payment_method: paymentMethod,
      };
      if (strategyId) payload.strategy_id = strategyId;
      if (planCode) payload.plan_code = planCode;
      return await api.buySubscription(payload);
    },
    onSuccess: (data) => {
      setReceipt(data);
      queryClient.invalidateQueries({ queryKey: ["strategies"] });
      queryClient.invalidateQueries({ queryKey: ["user-subscriptions"] });
      queryClient.invalidateQueries({ queryKey: ["payment-transactions"] });
      authService.getMe();
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Failed to complete subscription purchase.");
    },
  });


  const handleClose = () => {
    setReceipt(null);
    setErrorMsg(null);
    onClose();
  };

  return (
    <Modal open={open} onClose={handleClose} title="">
      {!receipt ? (
        <div className="space-y-4">
          <div className="flex items-start justify-between border-b pb-3">
            <div>
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-primary">
                <Sparkles className="h-3.5 w-3.5" /> Premium Algo Subscription
              </span>
              <h2 className="text-lg font-bold text-foreground">
                {planName || strategyName}
              </h2>
              {symbol && <p className="text-xs text-muted-foreground">Target Instrument: {symbol}</p>}
            </div>
            <div className="text-right">
              <span className="text-2xl font-extrabold text-foreground">{inr(totalPrice)}</span>
              <span className="block text-[10px] text-muted-foreground">incl. 18% GST / {billingCycle}</span>
            </div>
          </div>

          {errorMsg && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
              {errorMsg}
            </div>
          )}

          {/* Billing Cycle Selector */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Select Billing Cycle</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setBillingCycle("monthly")}
                className={`rounded-lg border p-2.5 text-left text-xs transition-all ${
                  billingCycle === "monthly"
                    ? "border-primary bg-primary/10 font-semibold text-primary"
                    : "border-input bg-card text-muted-foreground hover:bg-muted"
                }`}
              >
                <div className="font-semibold text-foreground">Monthly Billing</div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">{inr(priceInr)} / mo</div>
              </button>
              <button
                type="button"
                onClick={() => setBillingCycle("annual")}
                className={`relative rounded-lg border p-2.5 text-left text-xs transition-all ${
                  billingCycle === "annual"
                    ? "border-primary bg-primary/10 font-semibold text-primary"
                    : "border-input bg-card text-muted-foreground hover:bg-muted"
                }`}
              >
                <span className="absolute -top-2 right-2 rounded-full bg-success px-1.5 py-0.5 text-[9px] font-bold text-white">
                  Save 20%
                </span>
                <div className="font-semibold text-foreground">Annual Pass</div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">{inr(Math.round(priceInr * 10 * 0.8))} / yr</div>
              </button>
            </div>
          </div>

          {/* Price Breakdown */}
          <div className="rounded-lg border bg-muted/40 p-3 text-xs space-y-1.5">
            <div className="flex justify-between text-muted-foreground">
              <span>Base Subscription Fee</span>
              <span>{inr(basePrice)}</span>
            </div>
            <div className="flex justify-between text-muted-foreground">
              <span>GST (18%)</span>
              <span>{inr(gstAmount)}</span>
            </div>
            <div className="border-t pt-1.5 flex justify-between font-semibold text-foreground">
              <span>Total Payable</span>
              <span className="text-primary">{inr(totalPrice)}</span>
            </div>
          </div>

          {/* Payment Method Selector */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Choose Payment Method</label>
            <div className="space-y-2">
              <label
                className={`flex items-center justify-between rounded-lg border p-3 cursor-pointer text-xs transition-all ${
                  paymentMethod === "WALLET"
                    ? "border-primary bg-primary/5 font-medium"
                    : "border-input bg-card text-muted-foreground"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <input
                    type="radio"
                    name="pay_method"
                    checked={paymentMethod === "WALLET"}
                    onChange={() => setPaymentMethod("WALLET")}
                    className="accent-primary"
                  />
                  <Wallet className="h-4 w-4 text-primary" />
                  <div>
                    <span className="font-semibold text-foreground">TradeShield Demo Wallet</span>
                    <span className="block text-[11px] text-muted-foreground">
                      Balance: {inr(walletBalance)}
                    </span>
                  </div>
                </div>
                {!hasSufficientWallet && (
                  <Badge tone="danger">Insufficient Balance</Badge>
                )}
              </label>

              <label
                className={`flex items-center justify-between rounded-lg border p-3 cursor-pointer text-xs transition-all ${
                  paymentMethod === "UPI"
                    ? "border-primary bg-primary/5 font-medium"
                    : "border-input bg-card text-muted-foreground"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <input
                    type="radio"
                    name="pay_method"
                    checked={paymentMethod === "UPI"}
                    onChange={() => setPaymentMethod("UPI")}
                    className="accent-primary"
                  />
                  <Zap className="h-4 w-4 text-warning" />
                  <span className="font-semibold text-foreground">Instant UPI (GPay / PhonePe)</span>
                </div>
                <Badge tone="success">Instant Clearance</Badge>
              </label>

              <label
                className={`flex items-center justify-between rounded-lg border p-3 cursor-pointer text-xs transition-all ${
                  paymentMethod === "CREDIT_CARD"
                    ? "border-primary bg-primary/5 font-medium"
                    : "border-input bg-card text-muted-foreground"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <input
                    type="radio"
                    name="pay_method"
                    checked={paymentMethod === "CREDIT_CARD"}
                    onChange={() => setPaymentMethod("CREDIT_CARD")}
                    className="accent-primary"
                  />
                  <CreditCard className="h-4 w-4 text-info" />
                  <span className="font-semibold text-foreground">Credit / Debit Card</span>
                </div>
              </label>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-lg bg-primary/10 p-2.5 text-[11px] text-primary">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            <span>Sub-millisecond trade execution & Level 3 Risk Control enabled upon subscription.</span>
          </div>

          {/* Action Buttons */}
          <div className="mt-5 flex items-center justify-end gap-2 border-t pt-3">
            <Button variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              disabled={buyMutation.isPending || (paymentMethod === "WALLET" && !hasSufficientWallet)}
              onClick={() => buyMutation.mutate()}
              className="min-w-[140px]"
            >
              {buyMutation.isPending ? "Processing..." : `Pay & Subscribe ${inr(totalPrice)}`}
            </Button>
          </div>
        </div>
      ) : (
        /* Invoice Receipt View */
        <div className="space-y-4 text-center py-2">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/20 text-success">
            <CheckCircle2 className="h-7 w-7" />
          </div>

          <div>
            <h3 className="text-lg font-bold text-foreground">Subscription Confirmed!</h3>
            <p className="text-xs text-muted-foreground">{receipt.message}</p>
          </div>

          <div className="rounded-lg border bg-card p-4 text-xs space-y-2 text-left">
            <div className="flex justify-between border-b pb-2">
              <span className="text-muted-foreground">Invoice Reference:</span>
              <span className="font-mono font-semibold">{receipt.payment_reference}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Plan Tier:</span>
              <span className="font-semibold text-primary">{receipt.plan_tier}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Amount Paid:</span>
              <span className="font-semibold">{inr(receipt.amount_paid_inr)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Subscribed At:</span>
              <span>{new Date(receipt.subscribed_at).toLocaleDateString()}</span>
            </div>
            {receipt.expires_at && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Valid Until:</span>
                <span>{new Date(receipt.expires_at).toLocaleDateString()}</span>
              </div>
            )}
            <div className="flex justify-between border-t pt-2 font-medium">
              <span className="text-muted-foreground">Remaining Wallet Balance:</span>
              <span className="text-success">{inr(receipt.remaining_balance_inr)}</span>
            </div>
          </div>

          <Button onClick={handleClose} className="w-full">
            Done & Start Trading
          </Button>
        </div>
      )}
    </Modal>
  );
}
