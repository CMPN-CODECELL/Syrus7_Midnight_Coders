import { createFileRoute, Link, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, CandlestickChart, Workflow, ListOrdered, Layers, ShieldCheck, Settings, LogOut, Menu, OctagonAlert, Plus,
} from "lucide-react";
import { Logo } from "@/components/tm/Logo";
import { KillSwitchButton } from "@/components/tm/KillSwitch";
import { PlaceOrderModal } from "@/components/tm/PlaceOrderModal";
import { Badge, Button } from "@/components/tm/ui";
import { authService, connectionService } from "@/services";
import { useKillSwitch } from "@/hooks/queries";
import type { User } from "@/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app")({ component: AppLayout });

const nav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/markets", label: "Markets", icon: CandlestickChart },
  { to: "/strategies", label: "Strategies", icon: Workflow },
  { to: "/orders", label: "Orders", icon: ListOrdered },
  { to: "/positions", label: "Positions", icon: Layers },
  { to: "/risk-controls", label: "Risk Controls", icon: ShieldCheck },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

function Clock() {
  const [now, setNow] = useState<string>("");
  useEffect(() => {
    const tick = () => setNow(new Date().toLocaleTimeString("en-GB", { hour12: false }));
    tick();
    const i = setInterval(tick, 1000);
    return () => clearInterval(i);
  }, []);
  return <span className="num hidden text-xs text-muted-foreground sm:inline">{now} IST</span>;
}

function AppLayout() {
  const navigate = useNavigate();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const [user, setUser] = useState<User | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const { data: ks } = useKillSwitch();

  useEffect(() => {
    const u = authService.getCurrentUser();
    if (!u) {
      navigate({ to: "/login" });
    } else {
      setUser(u);
      if (u.theme) {
        authService.applyTheme(u.theme);
      }
    }
  }, [navigate]);

  useEffect(() => setMobileOpen(false), [path]);

  const title = nav.find((n) => path.startsWith(n.to))?.label ?? "TradeMint";
  if (!user) return <div className="min-h-screen bg-background" />;

  const userInitials = (user.name || "User")
    .trim()
    .split(/\s+/)
    .map((p) => p[0] || "")
    .join("")
    .slice(0, 2)
    .toUpperCase() || "U";

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="px-5 py-5"><Logo /></div>
      <nav className="flex-1 space-y-0.5 px-3">
        {nav.map((n) => {
          const active = path.startsWith(n.to);
          return (
            <Link
              key={n.to}
              to={n.to}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <n.icon className="h-4 w-4" />{n.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-3">
        <div className="flex items-center gap-3 rounded-md px-2 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-semibold">
            {userInitials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{user.name}</p>
            <p className="truncate text-xs text-muted-foreground">{user.email}</p>
          </div>
        </div>
        <button
          onClick={async () => {
            await authService.logout();
            navigate({ to: "/login" });
          }}
          className="mt-1 flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer"
        >
          <LogOut className="h-4 w-4" /> Logout
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen w-full">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 border-r bg-sidebar lg:block">{sidebar}</aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" onClick={() => setMobileOpen(false)}>
          <div className="absolute inset-0 bg-foreground/30" />
          <aside className="relative h-full w-64 border-r bg-sidebar" onClick={(e) => e.stopPropagation()}>{sidebar}</aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-card/95 px-4 backdrop-blur lg:px-6">
          <button className="rounded p-1.5 hover:bg-muted lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <h2 className="text-sm font-semibold">{title}</h2>
          <div className="ml-auto flex items-center gap-3">
            {ks?.active ? (
              <Badge tone="danger" dot>System halted</Badge>
            ) : (
              <Badge tone="success" dot className="hidden sm:inline-flex">Broker Connected</Badge>
            )}
            <Clock />
            <Button size="sm" onClick={() => setOrderModalOpen(true)} className="gap-1 px-3">
              <Plus className="h-4 w-4" /> New Order
            </Button>
            <KillSwitchButton />
          </div>
        </header>
        {ks?.active && (
          <div className="flex items-center gap-2 border-b border-destructive/30 bg-danger-soft px-6 py-2 text-sm font-medium text-destructive">
            <OctagonAlert className="h-4 w-4" />
            KILL SWITCH ACTIVE — all strategies stopped and new orders are blocked.
          </div>
        )}
        <main className="flex-1 p-4 lg:p-6"><Outlet /></main>
      </div>
      <PlaceOrderModal open={orderModalOpen} onClose={() => setOrderModalOpen(false)} />
    </div>
  );
}
