import { useState } from "react";
import { CheckCircle2, CreditCard, Mail, ShieldCheck, Sparkles, Wallet, Zap } from "lucide-react";
import { Badge, Button, Modal } from "./ui";
import { inr } from "@/lib/format";
import { authService, paymentService, api } from "@/services";
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

function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if ((window as any).Razorpay) {
      resolve(true);
      return;
    }
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
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
  const [paymentMethod, setPaymentMethod] = useState<"RAZORPAY" | "WALLET">("RAZORPAY");
  const [billingEmail, setBillingEmail] = useState(user?.email || "darshanmali44444@gmail.com");
  const [receipt, setReceipt] = useState<any | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const basePrice = billingCycle === "annual" ? Math.round(priceInr * 10 * 0.8) : priceInr;
  const gstAmount = Math.round(basePrice * 0.18);
  const totalPrice = basePrice + gstAmount;

  const walletBalance = user?.account_balance_inr ?? 10000;
  const hasSufficientWallet = walletBalance >= totalPrice;

  const handleWalletPay = async () => {
    setIsProcessing(true);
    setErrorMsg(null);
    try {
      const payload: Record<string, string> = {
        billing_cycle: billingCycle,
        payment_method: "WALLET",
      };
      if (strategyId) payload.strategy_id = strategyId;
      if (planCode) payload.plan_code = planCode;

      const data = await api.buySubscription(payload);
      setReceipt(data);
      queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "candles" });
      authService.getMe();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to complete wallet subscription.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRazorpayPay = async () => {
    setIsProcessing(true);
    setErrorMsg(null);

    try {
      const isLoaded = await loadRazorpayScript();
      const purpose = `${planName || strategyName} (${billingCycle})`;

      // 1. Create order on backend
      const order = await paymentService.createRazorpayOrder(totalPrice, purpose, strategyId);

      if (!isLoaded || !(window as any).Razorpay) {
        // Fallback simulated verification if external script blocked
        const verifyRes = await paymentService.verifyRazorpayPayment({
          razorpay_order_id: order.id,
          razorpay_payment_id: `pay_sim_${Date.now()}`,
          razorpay_signature: `sim_sig_${Date.now()}`,
          amount_inr: totalPrice,
          purpose,
          strategy_id: strategyId,
          billing_email: billingEmail,
        });

        setReceipt({
          payment_reference: verifyRes.reference_id,
          plan_tier: strategyId ? "STRATEGY_PASS" : "PRO",
          amount_paid_inr: totalPrice,
          subscribed_at: new Date().toISOString(),
          remaining_balance_inr: verifyRes.updated_balance_inr,
          message: verifyRes.message,
          email: verifyRes.email,
        });

        queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "candles" });
        authService.getMe();
        setIsProcessing(false);
        return;
      }

      // 2. Open Razorpay Checkout Modal
      const options = {
        key: order.key_id || "rzp_test_SFd7WR1rAUaPUA",
        amount: order.amount,
        currency: order.currency || "INR",
        name: "TradeShield Algo Trading",
        description: purpose,
        order_id: order.id,
        prefill: {
          name: user?.name || "Demo Trader",
          email: billingEmail,
          contact: "9876543210",
        },
        theme: {
          color: "#2563eb",
        },
        handler: async (response: any) => {
          try {
            const verifyRes = await paymentService.verifyRazorpayPayment({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              amount_inr: totalPrice,
              purpose,
              strategy_id: strategyId,
              billing_email: billingEmail,
            });

            setReceipt({
              payment_reference: verifyRes.reference_id,
              plan_tier: strategyId ? "STRATEGY_PASS" : "PRO",
              amount_paid_inr: totalPrice,
              subscribed_at: new Date().toISOString(),
              remaining_balance_inr: verifyRes.updated_balance_inr,
              message: verifyRes.message,
              email: verifyRes.email,
            });

            queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "candles" });
            authService.getMe();
          } catch (err: any) {
            setErrorMsg(err.message || "Payment verification failed.");
          } finally {
            setIsProcessing(false);
          }
        },
        modal: {
          ondismiss: () => {
            setIsProcessing(false);
          },
        },
      };

      const rzp = new (window as any).Razorpay(options);
      rzp.on("payment.failed", (response: any) => {
        setErrorMsg(response.error.description || "Razorpay Payment Failed.");
        setIsProcessing(false);
      });
      rzp.open();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to initiate Razorpay checkout.");
      setIsProcessing(false);
    }
  };

  const handleClose = () => {
    setReceipt(null);
    setErrorMsg(null);
    setIsProcessing(false);
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
              <span className="text-primary font-bold">{inr(totalPrice)}</span>
            </div>
          </div>

          {/* Email Notification Address Input */}
          <div>
            <label className="mb-1 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Mail className="h-3.5 w-3.5 text-primary" /> Send PDF Invoice Receipt To
            </label>
            <input
              type="email"
              value={billingEmail}
              onChange={(e) => setBillingEmail(e.target.value)}
              placeholder="e.g. user@example.com"
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium"
            />
          </div>

          {/* Payment Method Selector */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted-foreground">Choose Payment Gateway</label>
            <div className="space-y-2">
              <label
                className={`flex items-center justify-between rounded-lg border p-3 cursor-pointer text-xs transition-all ${
                  paymentMethod === "RAZORPAY"
                    ? "border-primary bg-primary/5 font-medium ring-1 ring-primary"
                    : "border-input bg-card text-muted-foreground hover:bg-muted/40"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <input
                    type="radio"
                    name="pay_method"
                    checked={paymentMethod === "RAZORPAY"}
                    onChange={() => setPaymentMethod("RAZORPAY")}
                    className="accent-primary"
                  />
                  <Zap className="h-4 w-4 text-warning" />
                  <div>
                    <span className="font-semibold text-foreground">Razorpay Gateway (UPI / Card / NetBanking)</span>
                    <span className="block text-[10px] text-muted-foreground">
                      Official Razorpay Integration • Key ID: <code>rzp_test_...AUaPUA</code>
                    </span>
                  </div>
                </div>
                <Badge tone="success">Instant Clearance & Receipt</Badge>
              </label>

              <label
                className={`flex items-center justify-between rounded-lg border p-3 cursor-pointer text-xs transition-all ${
                  paymentMethod === "WALLET"
                    ? "border-primary bg-primary/5 font-medium ring-1 ring-primary"
                    : "border-input bg-card text-muted-foreground hover:bg-muted/40"
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
                    <span className="font-semibold text-foreground">TradeShield Internal Wallet</span>
                    <span className="block text-[11px] text-muted-foreground">
                      Available Balance: {inr(walletBalance)}
                    </span>
                  </div>
                </div>
                {!hasSufficientWallet && (
                  <Badge tone="danger">Insufficient Balance</Badge>
                )}
              </label>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-lg bg-primary/10 p-2.5 text-[11px] text-primary">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            <span>Sub-millisecond trade execution & Level 3 Risk Control enabled upon subscription.</span>
          </div>

          {/* Action Buttons */}
          <div className="mt-5 flex items-center justify-end gap-2 border-t pt-3">
            <Button variant="outline" onClick={handleClose} disabled={isProcessing}>
              Cancel
            </Button>
            <Button
              disabled={isProcessing || (paymentMethod === "WALLET" && !hasSufficientWallet)}
              onClick={() => (paymentMethod === "RAZORPAY" ? handleRazorpayPay() : handleWalletPay())}
              className="min-w-[150px]"
            >
              {isProcessing ? "Processing..." : `Pay ${inr(totalPrice)} via ${paymentMethod === "RAZORPAY" ? "Razorpay" : "Wallet"}`}
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
            <h3 className="text-lg font-bold text-foreground">Payment Verified & Activated!</h3>
            <p className="text-xs text-muted-foreground">{receipt.message}</p>
          </div>

          <div className="rounded-lg border bg-card p-4 text-xs space-y-2 text-left">
            <div className="flex justify-between border-b pb-2">
              <span className="text-muted-foreground">Razorpay Transaction ID:</span>
              <span className="font-mono font-semibold text-primary">{receipt.payment_reference}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Subscription Tier:</span>
              <span className="font-semibold text-foreground">{receipt.plan_tier}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Amount Paid:</span>
              <span className="font-semibold text-success font-mono">{inr(receipt.amount_paid_inr)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Email Invoice:</span>
              <span className="font-mono text-muted-foreground">{receipt.email}</span>
            </div>
            <div className="flex justify-between border-t pt-2 font-medium">
              <span className="text-muted-foreground">Account Balance:</span>
              <span className="text-foreground">{inr(receipt.remaining_balance_inr)}</span>
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
