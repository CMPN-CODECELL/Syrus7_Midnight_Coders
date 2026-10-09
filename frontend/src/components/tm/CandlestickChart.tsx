import { useMemo, useRef, useState } from "react";
import type { Candle, Timeframe } from "@/types";

interface Props {
  candles: Candle[];
  timeframe?: Timeframe;
  onHover?: (c: Candle | null) => void;
  height?: number;
}

function formatTime(ts: string, tf?: Timeframe): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  if (tf === "1D" || tf === "1W" || tf === "1M") {
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  }
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** Pure presentational SVG candlestick + volume chart. Data-source agnostic. */
export function CandlestickChart({ candles, timeframe = "1m", onHover, height = 420 }: Props) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const W = 1000;
  const padR = 64;
  const priceH = height * 0.74;
  const volTop = priceH + 16;
  const volH = height - volTop - 22;

  const { min, max, maxVol } = useMemo(() => {
    let min = Infinity, max = -Infinity, maxVol = 0;
    for (const c of candles) {
      min = Math.min(min, c.low);
      max = Math.max(max, c.high);
      maxVol = Math.max(maxVol, c.volume);
    }
    const pad = (max - min) * 0.08 || 1;
    return { min: min - pad, max: max + pad, maxVol: maxVol || 1 };
  }, [candles]);

  if (!candles.length) return <div style={{ height }} />;
  const plotW = W - padR;
  const cw = plotW / candles.length;
  const y = (p: number) => ((max - p) / (max - min)) * priceH;
  const ticks = Array.from({ length: 5 }, (_, i) => min + ((max - min) * (i + 0.5)) / 5);
  const last = candles[candles.length - 1]!;

  const activeIdx = hover !== null ? hover : candles.length - 1;
  const activeCandle = candles[activeIdx] ?? last;

  const move = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * W;
    const i = Math.floor(x / cw);
    if (i >= 0 && i < candles.length) {
      setHover(i);
      onHover?.(candles[i] ?? null);
    }
  };

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${W} ${height}`}
      className="h-auto w-full select-none"
      onMouseMove={move}
      onMouseLeave={() => {
        setHover(null);
        onHover?.(null);
      }}
    >
      {/* Price Gridlines */}
      {ticks.map((t) => (
        <g key={t}>
          <line x1={0} x2={plotW} y1={y(t)} y2={y(t)} className="stroke-border" strokeDasharray="3 4" />
          <text x={plotW + 8} y={y(t) + 4} className="fill-muted-foreground num" fontSize={11}>
            {t.toFixed(2)}
          </text>
        </g>
      ))}

      <line x1={0} x2={plotW} y1={volTop - 6} y2={volTop - 6} className="stroke-border" />

      {/* Candlesticks & Volume */}
      {candles.map((c, i) => {
        const up = c.close >= c.open;
        const cls = up ? "fill-success stroke-success" : "fill-destructive stroke-destructive";
        const x = i * cw + cw / 2;
        const bw = Math.max(1, cw * 0.62);
        const top = y(Math.max(c.open, c.close));
        const bh = Math.max(1, Math.abs(y(c.open) - y(c.close)));
        const vh = (c.volume / maxVol) * volH;
        const isSelected = activeIdx === i;

        return (
          <g key={c.timestamp + i} className={cls} opacity={isSelected ? 1 : 0.7}>
            <line x1={x} x2={x} y1={y(c.high)} y2={y(c.low)} strokeWidth={isSelected ? 1.5 : 1} />
            <rect x={x - bw / 2} y={top} width={bw} height={bh} strokeWidth={0} />
            <rect x={x - bw / 2} y={volTop + volH - vh} width={bw} height={vh} opacity={0.35} strokeWidth={0} />
          </g>
        );
      })}

      {/* Last Price Badge & Line */}
      <line x1={0} x2={plotW} y1={y(last.close)} y2={y(last.close)} className="stroke-primary" strokeDasharray="2 3" />
      <rect x={plotW + 2} y={y(last.close) - 10} width={padR - 4} height={20} rx={3} className="fill-primary" />
      <text x={plotW + 8} y={y(last.close) + 4} fontSize={11} className="fill-primary-foreground num font-medium">
        {last.close.toFixed(2)}
      </text>

      {/* Crosshair & Active Time Label */}
      {activeIdx !== null && activeCandle && (
        <g>
          {/* Vertical Crosshair */}
          <line
            x1={activeIdx * cw + cw / 2}
            x2={activeIdx * cw + cw / 2}
            y1={0}
            y2={height - 20}
            className="stroke-muted-foreground"
            strokeDasharray="3 3"
          />

          {/* Horizontal Crosshair on Hover */}
          {hover !== null && (
            <>
              <line
                x1={0}
                x2={plotW}
                y1={y(activeCandle.close)}
                y2={y(activeCandle.close)}
                className="stroke-muted-foreground"
                strokeDasharray="3 3"
              />
              <rect x={plotW + 2} y={y(activeCandle.close) - 10} width={padR - 4} height={20} rx={3} className="fill-muted" />
              <text x={plotW + 8} y={y(activeCandle.close) + 4} fontSize={10} className="fill-foreground num font-medium">
                {activeCandle.close.toFixed(2)}
              </text>
            </>
          )}

          {/* Time Label under Crosshair / Active Candle */}
          <rect
            x={Math.min(Math.max(activeIdx * cw + cw / 2 - 40, 2), plotW - 82)}
            y={height - 18}
            width={80}
            height={18}
            rx={3}
            className="fill-card stroke-border"
          />
          <text
            x={Math.min(Math.max(activeIdx * cw + cw / 2, 42), plotW - 42)}
            y={height - 5}
            textAnchor="middle"
            fontSize={10}
            className="fill-foreground num font-semibold"
          >
            {formatTime(activeCandle.timestamp, timeframe)}
          </text>
        </g>
      )}
    </svg>
  );
}
