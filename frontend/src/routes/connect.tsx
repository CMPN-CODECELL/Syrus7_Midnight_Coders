import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { CheckCircle2, Loader2, Lock } from "lucide-react";
import { AuthShell } from "@/components/tm/AuthShell";
import { Badge, Button, Field, inputCls } from "@/components/tm/ui";
import { connectionService } from "@/services";

export const Route = createFileRoute("/connect")({
  head: () => ({
    meta: [
      { title: "Trading Environment — TradeMint" },
      { name: "description", content: "Connect your trading environment to TradeMint." },
      { property: "og:title", content: "Trading Environment — TradeMint" },
      { property: "og:description", content: "Link your paper-trading environment to start executing strategies." },
    ],
  }),
  component: Connect,
});

function Connect() {
  const nav = useNavigate();
  const [env, setEnv] = useState("simulated");
  const [key, setKey] = useState("HACK342");
  const [secret, setSecret] = useState("••••••••••••");
  const [state, setState] = useState<"idle" | "loading" | "done">("done");

  const connect = async (e: React.FormEvent) => {
    e.preventDefault();
    setState("loading");
    await connectionService.connect(key || "HACK342", secret, env);
    setSecret("");
    setState("done");
  };

  return (
    <AuthShell title="Trading Environment" sub="Your execution engine is active and ready.">
      <div className="mb-5 flex items-center justify-between rounded-lg border bg-muted/50 px-4 py-3 text-sm">
        <span className="text-muted-foreground">Connection status</span>
        <Badge tone="success" dot>Connected</Badge>
      </div>
      <div className="space-y-5 text-center">
        <div className="flex flex-col items-center gap-2 py-4">
          <CheckCircle2 className="h-10 w-10 text-success" />
          <p className="font-semibold">Execution Engine Ready</p>
          <p className="text-sm text-muted-foreground">Automated risk controls and strategy execution are online.</p>
        </div>
        <Button className="w-full" onClick={() => nav({ to: "/dashboard" })}>Continue to Dashboard</Button>
      </div>
    </AuthShell>
  );
}
