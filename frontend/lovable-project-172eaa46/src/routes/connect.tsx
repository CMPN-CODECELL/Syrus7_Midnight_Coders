import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { CheckCircle2, Loader2, Lock } from "lucide-react";
import { AuthShell } from "@/components/tm/AuthShell";
import { Badge, Button, Field, inputCls } from "@/components/tm/ui";
import { connectionService } from "@/services";

export const Route = createFileRoute("/connect")({
  head: () => ({
    meta: [
      { title: "Connect 021 Sandbox — TradeMint" },
      { name: "description", content: "Connect your 021 Sandbox trading environment to TradeMint." },
      { property: "og:title", content: "Connect 021 Sandbox — TradeMint" },
      { property: "og:description", content: "Link a sandbox brokerage account to start paper-trading strategies." },
    ],
  }),
  component: Connect,
});

function Connect() {
  const nav = useNavigate();
  const [env, setEnv] = useState("sandbox");
  const [key, setKey] = useState("");
  const [secret, setSecret] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "done">("idle");

  const connect = async (e: React.FormEvent) => {
    e.preventDefault();
    setState("loading");
    await connectionService.connect(key, secret, env);
    setSecret("");
    setState("done");
  };

  return (
    <AuthShell title="Connect your trading environment" sub="Link your 021 account. Only the Sandbox environment is available.">
      <div className="mb-5 flex items-center justify-between rounded-lg border bg-muted/50 px-4 py-3 text-sm">
        <span className="text-muted-foreground">Connection status</span>
        {state === "done" ? <Badge tone="success" dot>Connected</Badge> : <Badge tone="neutral" dot>Not connected</Badge>}
      </div>
      {state === "done" ? (
        <div className="space-y-5 text-center">
          <div className="flex flex-col items-center gap-2 py-4">
            <CheckCircle2 className="h-10 w-10 text-success" />
            <p className="font-semibold">021 Sandbox Connected</p>
            <p className="text-sm text-muted-foreground">Your trading environment is ready.</p>
          </div>
          <Button className="w-full" onClick={() => nav({ to: "/dashboard" })}>Continue to Dashboard</Button>
        </div>
      ) : (
        <form onSubmit={connect} className="space-y-4">
          <Field label="Environment">
            <select className={inputCls} value={env} onChange={(e) => setEnv(e.target.value)}>
              <option value="sandbox">021 Sandbox</option>
              <option value="live" disabled>Live (not available)</option>
            </select>
          </Field>
          <Field label="API key"><input className={inputCls} required value={key} onChange={(e) => setKey(e.target.value)} placeholder="sbx_••••••••" /></Field>
          <Field label="API secret"><input className={inputCls} type="password" required value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="••••••••••••" /></Field>
          <p className="flex items-start gap-2 text-xs text-muted-foreground">
            <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" /> Demo only — credentials are not sent or stored anywhere.
          </p>
          <Button className="w-full" disabled={state === "loading"}>
            {state === "loading" && <Loader2 className="h-4 w-4 animate-spin" />} Connect Sandbox
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
