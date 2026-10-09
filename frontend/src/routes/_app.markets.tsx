import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { CandlestickChart } from "@/components/tm/CandlestickChart";
import { Card } from "@/components/tm/ui";
import { useCandles } from "@/hooks/queries";
import { marketDataService } from "@/services";
import type { Candle, Timeframe } from "@/types";
import { cn } from "@/lib/utils";
import { num } from "@/lib/format";

export const Route = createFileRoute("/_app/markets")({
  head: () => ({
    meta: [
      { title: "Markets — TradeMint" },
      { name: "description", content: "Candlestick charts with OHLC and volume for NSE symbols on 1m and 5m timeframes." },
      { property: "og:title", content: "Markets — TradeMint" },
      { property: "og:description", content: "Live-style candlestick charts for RELIANCE, TCS, INFY and HDFCBANK." },
    ],
  }),
  component: Markets,
});

function Seg<T extends string>({ value, options, onChange }: { value: T; options: readonly T[]; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-md border bg-card p-0.5">
      {options.map((o) => (
        <button key={o} onClick={() => onChange(o)} className={cn("rounded px-3 py-1.5 text-xs font-medium", value === o ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>
          {o}
        </button>
      ))}
    </div>
  );
}

function Markets() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [tf, setTf] = useState<Timeframe>("1m");
  const [hover, setHover] = useState<Candle | null>(null);
  const { data: candles = [], isLoading } = useCandles(symbol, tf);
  const last = candles[candles.length - 1];
  const prev = candles[0];
  const c = hover ?? last;
  const change = last && prev ? last.close - prev.open : 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Seg value={symbol} options={marketDataService.symbols} onChange={setSymbol} />
        <Seg value={tf} options={["1m", "5m", "1D", "1W", "1M"] as const} onChange={setTf} />
      </div>
      <Card>
        <div className="flex flex-wrap items-end justify-between gap-4 border-b px-5 py-4">
          <div>
            <p className="text-xs text-muted-foreground">NSE · {symbol} · {tf} candles</p>
            <div className="mt-1 flex items-baseline gap-3">
              <span className="num text-2xl font-semibold">{last ? `₹${last.close.toFixed(2)}` : "—"}</span>
              <span className={cn("num text-sm font-medium", change >= 0 ? "text-success" : "text-destructive")}>
                {change >= 0 ? "+" : ""}{change.toFixed(2)} ({prev ? ((change / prev.open) * 100).toFixed(2) : "0"}%)
              </span>
            </div>
          </div>
          {c && (
            <dl className="grid grid-cols-5 gap-x-5 text-xs">
              {([["Open", c.open], ["High", c.high], ["Low", c.low], ["Close", c.close]] as const).map(([k, v]) => (
                <div key={k}><dt className="text-muted-foreground">{k}</dt><dd className="num mt-0.5 font-medium">₹{v.toFixed(2)}</dd></div>
              ))}
              <div><dt className="text-muted-foreground">Volume</dt><dd className="num mt-0.5 font-medium">{num(c.volume)}</dd></div>
            </dl>
          )}
        </div>
        <div className="p-3">
          {isLoading ? <div className="h-[420px] animate-pulse rounded bg-muted" /> : <CandlestickChart candles={candles} timeframe={tf} onHover={setHover} />}
        </div>
      </Card>
      <p className="text-xs text-muted-foreground">Real-time aggregated OHLCV candlesticks built from tick streams. Hover over the chart to inspect individual candles.</p>
    </div>
  );
}

