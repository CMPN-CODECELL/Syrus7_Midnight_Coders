export function Logo({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <svg viewBox="0 0 24 24" className="h-4.5 w-4.5" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 17l5-5 4 3 7-8" />
          <path d="M15 7h5v5" />
        </svg>
      </div>
      {!compact && <span className="text-base font-semibold tracking-tight">TradeMint</span>}
    </div>
  );
}
