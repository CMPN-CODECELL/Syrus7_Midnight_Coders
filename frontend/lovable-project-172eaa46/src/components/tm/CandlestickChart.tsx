import { useMemo, useRef, useState } from "react";
import type { Candle } from "@/types";

interface Props {
  candles: Candle[];
  onHover?: (c: Candle | null) => void;
  height?: number;
}

/** Pure presentational SVG candlestick + volume chart. Data-source agnostic. */
export function CandlestickChart({ candles, onHover, height = 420 }: Props) {
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const W = 1000;
  const padR = 64;
  const priceH = height * 0.74;
  const volTop = priceH + 16;
  const volH = height - volTop - 22;

  const { min, max, maxVol } = useMemo(() => {
    let min = Infinity, max = -Infinity, maxVol = 0;
    for (const c of candles) { min = Math.min(min, c.low); max = Math.max(max, c.high); maxVol = Math.max(maxVol, c.volume); }
    const pad = (max - min) * 0.08;
    return { min: min - pad, max: max + pad, maxVol };
  }, [candles]);

  if (!candles.length) return <div style={{ height }} />;
  const plotW = W - padR;
  const cw = plotW / candles.length;
  const y = (p: number) => ((max - p) / (max - min)) * priceH;
  const ticks = Array.from({ length: 5 }, (_, i) => min + ((max - min) * (i + 0.5)) / 5);
  const last = candles[candles.length - 1]!;

  const move = (e: React.MouseEvent) => {
    const r = ref.current!.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * W;
    const i = Math.floor(x / cw);
    if (i >= 0 && i < candles.length) { setHover(i); onHover?.(candles[i] ?? null); }
  };

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${W} ${height}`}
      className="h-auto w-full select-none"
      onMouseMove={move}
      onMouseLeave={() => { setHover(null); onHover?.(null); }}
    >
      {ticks.map((t) => (
        <g key={t}>
          <line x1={0} x2={plotW} y1={y(t)} y2={y(t)} className="stroke-border" strokeDasharray="3 4" />
          <text x={plotW + 8} y={y(t) + 4} className="fill-muted-foreground num" fontSize={11}>{t.toFixed(1)}</text>
        </g>
      ))}
      <line x1={0} x2={plotW} y1={volTop - 6} y2={volTop - 6} className="stroke-border" />
      {candles.map((c, i) => {
        const up = c.close >= c.open;
        const cls = up ? "fill-success stroke-success" : "fill-destructive stroke-destructive";
        const x = i * cw + cw / 2;
        const bw = Math.max(1, cw * 0.62);
        const top = y(Math.max(c.open, c.close));
        const bh = Math.max(1, Math.abs(y(c.open) - y(c.close)));
        const vh = (c.volume / maxVol) * volH;
        return (
          <g key={c.timestamp} className={cls} opacity={hover === null || hover === i ? 1 : 0.75}>
            <line x1={x} x2={x} y1={y(c.high)} y2={y(c.low)} strokeWidth={1} />
            <rect x={x - bw / 2} y={top} width={bw} height={bh} strokeWidth={0} />
            <rect x={x - bw / 2} y={volTop + volH - vh} width={bw} height={vh} opacity={0.35} strokeWidth={0} />
          </g>
        );
      })}
      {/* last price line */}
      <line x1={0} x2={plotW} y1={y(last.close)} y2={y(last.close)} className="stroke-primary" strokeDasharray="2 3" />
      <rect x={plotW + 2} y={y(last.close) - 10} width={padR - 4} height={20} rx={3} className="fill-primary" />
      <text x={plotW + 8} y={y(last.close) + 4} fontSize={11} className="fill-primary-foreground num">{last.close.toFixed(1)}</text>
      {hover !== null && (
        <g>
          <line x1={hover * cw + cw / 2} x2={hover * cw + cw / 2} y1={0} y2={height - 20} className="stroke-muted-foreground" strokeDasharray="3 3" />
          <text x={Math.min(Math.max(hover * cw + cw / 2, 30), plotW - 30)} y={height - 4} textAnchor="middle" fontSize={11} className="fill-muted-foreground num">
            {new Date(candles[hover]!.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}
          </text>
        </g>
      )}
    </svg>
  );
}
