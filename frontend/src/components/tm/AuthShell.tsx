import type { ReactNode } from "react";
import { Logo } from "./Logo";

export function AuthShell({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <Logo />
          <p className="mt-2 text-xs text-muted-foreground">Automate strategies. Manage risk. Trade smarter.</p>
        </div>
        <div className="rounded-xl border bg-card p-7 shadow-card">
          <h1 className="text-lg font-semibold">{title}</h1>
          {sub && <p className="mt-1 text-sm text-muted-foreground">{sub}</p>}
          <div className="mt-6">{children}</div>
        </div>
        <p className="mt-6 text-center text-[11px] text-muted-foreground">021 Developer OMS Engine · Real-time Risk Gate & Execution Environment</p>
      </div>
    </div>
  );
}
