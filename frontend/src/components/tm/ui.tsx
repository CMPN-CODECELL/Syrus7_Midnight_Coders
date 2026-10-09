import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { createPortal } from "react-dom";

const btnVariants = {
  primary: "bg-primary text-primary-foreground hover:bg-primary/90",
  outline: "border border-input bg-card text-foreground hover:bg-muted",
  ghost: "text-foreground hover:bg-muted",
  danger: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
  dangerOutline: "border border-destructive/40 bg-danger-soft text-destructive hover:bg-destructive hover:text-destructive-foreground",
} as const;

export function Button({
  variant = "primary", size = "md", className, ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof btnVariants; size?: "sm" | "md" }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-ring",
        size === "sm" ? "h-8 px-3 text-xs" : "h-10 px-4 text-sm",
        btnVariants[variant], className,
      )}
      {...props}
    />
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("rounded-xl border bg-card shadow-card", className)}>{children}</div>;
}

export function CardHeader({ title, action, sub }: { title: string; action?: ReactNode; sub?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b px-5 py-3.5">
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

const tones = {
  success: "bg-success-soft text-success border-success/20",
  danger: "bg-danger-soft text-destructive border-destructive/20",
  warning: "bg-warning-soft text-warning border-warning/30",
  neutral: "bg-muted text-muted-foreground border-border",
  primary: "bg-accent text-accent-foreground border-primary/20",
} as const;
export type Tone = keyof typeof tones;

export function Badge({ tone = "neutral", dot, children, className }: { tone?: Tone; dot?: boolean; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide", tones[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function orderTone(status: string): Tone {
  switch (status) {
    case "FILLED": return "success";
    case "PARTIALLY_FILLED": return "warning";
    case "REJECTED": return "danger";
    case "SUBMITTED": case "CREATED": return "primary";
    default: return "neutral";
  }
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-label={title}
        className={cn("max-h-[90dvh] w-full overflow-y-auto rounded-xl border bg-card shadow-xl", wide ? "max-w-2xl" : "max-w-md")}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-base font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 text-muted-foreground hover:bg-muted"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>,
    document.body
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

export const inputCls =
  "h-10 w-full rounded-md border border-input bg-card px-3 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/20";

export function Pnl({ value, className }: { value: number; className?: string }) {
  return (
    <span className={cn("num font-medium", value > 0 ? "text-success" : value < 0 ? "text-destructive" : "text-muted-foreground", className)}>
      {value >= 0 ? "+" : "−"}₹{Math.abs(value).toLocaleString("en-IN")}
    </span>
  );
}

export function Progress({ value, tone = "success" }: { value: number; tone?: "success" | "warning" | "danger" }) {
  const bg = tone === "success" ? "bg-success" : tone === "warning" ? "bg-warning" : "bg-destructive";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
      <div className={cn("h-full rounded-full transition-all", bg)} style={{ width: `${Math.min(100, value)}%` }} />
    </div>
  );
}

export function PageHeader({ title, sub, action }: { title: string; sub?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {sub && <p className="mt-1 text-sm text-muted-foreground">{sub}</p>}
      </div>
      {action}
    </div>
  );
}
