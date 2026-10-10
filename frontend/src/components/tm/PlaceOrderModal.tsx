import { useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, Send } from "lucide-react";
import { Badge, Button, Field, Modal, inputCls } from "@/components/tm/ui";
import { useInstruments, usePlaceOrder, useStrategies } from "@/hooks/queries";
import { inr } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PlaceOrderModalProps {
  open: boolean;
  onClose: () => void;
  defaultSymbol?: string;
}

const DEFAULT_SYMBOLS = [
  { symbol: "RELIANCE", ltp: 1424.0 },
  { symbol: "TCS", ltp: 3410.0 },
  { symbol: "INFY", ltp: 1520.0 },
  { symbol: "HDFCBANK", ltp: 1645.0 },
  { symbol: "TATAMOTORS", ltp: 980.0 },
  { symbol: "NIFTY50", ltp: 22450.0 },
];

export function PlaceOrderModal({ open, onClose, defaultSymbol }: PlaceOrderModalProps) {
  const { data: strats = [] } = useStrategies();
  const { data: instruments = [] } = useInstruments();
  const placeOrder = usePlaceOrder();

  const availableSymbols = instruments.length > 0
    ? instruments.map((inst) => {
        const baseMap: Record<string, number> = { RELIANCE: 1424.0, TCS: 3410.0, INFY: 1520.0, HDFCBANK: 1645.0, TATAMOTORS: 980.0, NIFTY50: 22450.0 };
        return { symbol: inst.symbol, ltp: baseMap[inst.symbol] || 1000.0 };
      })
    : DEFAULT_SYMBOLS;

  const [symbol, setSymbol] = useState(defaultSymbol || "RELIANCE");
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [quantity, setQuantity] = useState<number>(1);
  const [price, setPrice] = useState<string>("");
  const [strategyId, setStrategyId] = useState<string>("strat_time");

  const [lastResult, setLastResult] = useState<{
    status: string;
    order_id?: string;
    average_price?: number;
    rejection_reason?: string;
  } | null>(null);

  const selectedSymbolObj = availableSymbols.find((s) => s.symbol === symbol) ?? availableSymbols[0];
  const refPrice = selectedSymbolObj ? selectedSymbolObj.ltp : 1424.0;
  const numPrice = price ? parseFloat(price) : refPrice;
  const estValue = (numPrice || 0) * (quantity || 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLastResult(null);
    try {
      const res = await placeOrder.mutateAsync({
        strategyId,
        symbol,
        side,
        orderType,
        quantity: Number(quantity),
        price: orderType === "LIMIT" && price ? parseFloat(price) : undefined,
      });
      if (res) {
        setLastResult(res);
      }
    } catch (err: unknown) {
      setLastResult({
        status: "REJECTED",
        rejection_reason: err instanceof Error ? err.message : "Order placement failed",
      });
    }
  };

  const resetForm = () => {
    setLastResult(null);
    onClose();
  };

  return (
    <Modal open={open} onClose={resetForm} title="Place Instant Order">
      <form onSubmit={handleSubmit} className="space-y-5">
        <p className="text-xs text-muted-foreground">
          Submit live order directly to the TradeMint Risk Engine & Execution Broker.
        </p>

        {/* Result Feedback Alert */}
        {lastResult && (
          <div
            className={cn(
              "rounded-lg border p-4 text-sm animate-in fade-in slide-in-from-top-2",
              lastResult.status === "FILLED"
                ? "border-success/30 bg-success-soft text-success"
                : "border-destructive/30 bg-danger-soft text-destructive",
            )}
          >
            <div className="flex items-start gap-3">
              {lastResult.status === "FILLED" ? (
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
              ) : (
                <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
              )}
              <div className="space-y-1">
                <p className="font-semibold">
                  {lastResult.status === "FILLED"
                    ? `Order FILLED @ ₹${lastResult.average_price?.toFixed(2)}`
                    : "Order REJECTED by Risk Engine"}
                </p>
                {lastResult.rejection_reason ? (
                  <p className="text-xs leading-relaxed opacity-90">{lastResult.rejection_reason}</p>
                ) : (
                  <p className="text-xs opacity-90">
                    Order {lastResult.order_id} routed successfully. Positions and Intraday P&L updated in real-time.
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Strategy Selection */}
        <Field label="Target Strategy">
          <select
            className={inputCls}
            value={strategyId}
            onChange={(e) => setStrategyId(e.target.value)}
          >
            {strats.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.symbol})
              </option>
            ))}
          </select>
        </Field>

        {/* Symbol Selection */}
        <Field label="Symbol">
          <div className="grid grid-cols-4 gap-2">
            {availableSymbols.slice(0, 4).map((s) => (
              <button
                key={s.symbol}
                type="button"
                onClick={() => {
                  setSymbol(s.symbol);
                  if (orderType === "LIMIT") setPrice(String(s.ltp));
                }}
                className={cn(
                  "flex flex-col items-center justify-center rounded-lg border p-2.5 text-center transition-all",
                  symbol === s.symbol
                    ? "border-primary bg-primary/10 font-semibold text-primary shadow-sm"
                    : "bg-card hover:bg-muted text-muted-foreground",
                )}
              >
                <span className="text-xs">{s.symbol}</span>
                <span className="num mt-0.5 text-[11px] opacity-80">₹{s.ltp}</span>
              </button>
            ))}
          </div>
        </Field>

        {/* Side Selection */}
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setSide("BUY")}
            className={cn(
              "flex items-center justify-center gap-2 rounded-lg border py-2.5 font-semibold text-sm transition-all",
              side === "BUY"
                ? "border-success bg-success text-success-foreground shadow"
                : "border-input bg-card text-muted-foreground hover:bg-muted",
            )}
          >
            BUY
          </button>
          <button
            type="button"
            onClick={() => setSide("SELL")}
            className={cn(
              "flex items-center justify-center gap-2 rounded-lg border py-2.5 font-semibold text-sm transition-all",
              side === "SELL"
                ? "border-destructive bg-destructive text-destructive-foreground shadow"
                : "border-input bg-card text-muted-foreground hover:bg-muted",
            )}
          >
            SELL
          </button>
        </div>

        {/* Order Type & Price */}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Order Type">
            <select
              className={inputCls}
              value={orderType}
              onChange={(e) => setOrderType(e.target.value as "MARKET" | "LIMIT")}
            >
              <option value="MARKET">MARKET</option>
              <option value="LIMIT">LIMIT</option>
            </select>
          </Field>
          <Field label={orderType === "LIMIT" ? "Limit Price (₹)" : "Ref Price (₹)"}>
            <input
              className={inputCls}
              type="number"
              step="0.05"
              disabled={orderType === "MARKET"}
              value={orderType === "MARKET" ? refPrice : price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder={String(refPrice)}
            />
          </Field>
        </div>

        {/* Quantity & Quick Presets */}
        <Field label="Quantity">
          <div className="space-y-2">
            <input
              className={inputCls}
              type="number"
              min="1"
              max="500"
              required
              value={quantity}
              onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
            />
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-muted-foreground">Presets:</span>
              {[1, 2, 5, 10].map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => setQuantity(q)}
                  className={cn(
                    "rounded border px-2 py-0.5 text-xs transition-colors",
                    quantity === q
                      ? "border-primary bg-primary/10 text-primary font-medium"
                      : "bg-card text-muted-foreground hover:bg-muted",
                  )}
                >
                  {q} qty
                </button>
              ))}
              <button
                type="button"
                onClick={() => setQuantity(50)}
                className="rounded border border-destructive/40 bg-danger-soft px-2 py-0.5 text-xs text-destructive hover:bg-destructive/20"
                title="Test Risk Breach Limit"
              >
                50 (Test Limit Breach)
              </button>
            </div>
          </div>
        </Field>

        {/* Order Summary Footer */}
        <div className="flex items-center justify-between rounded-lg border bg-muted/40 p-3.5 text-xs">
          <div>
            <span className="text-muted-foreground">Estimated Notional:</span>
            <span className="num ml-2 font-semibold text-foreground">{inr(estValue)}</span>
          </div>
          <Badge tone={side === "BUY" ? "success" : "danger"}>
            {side} {quantity} x {symbol}
          </Badge>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="outline" onClick={resetForm}>
            Close
          </Button>
          <Button type="submit" disabled={placeOrder.isPending}>
            {placeOrder.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Evaluating Risk…
              </>
            ) : (
              <>
                <Send className="h-4 w-4" /> Submit Order
              </>
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
