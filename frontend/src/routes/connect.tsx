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
  const [secret, setSecret] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "done">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const connect = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    setState("loading");
    try {
      await connectionService.connect(key || "HACK342", secret, env);
      setState("done");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to connect to trading environment");
      setState("idle");
    }
  };

  if (state === "done") {
    return (
      <AuthShell title="Trading Environment" sub="Your execution engine session is active and linked.">
        <div className="mb-5 flex items-center justify-between rounded-lg border bg-muted/50 px-4 py-3 text-sm">
          <span className="text-muted-foreground">Connection status</span>
          <Badge tone="success" dot>Connected ({env.toUpperCase()})</Badge>
        </div>
        <div className="space-y-5 text-center">
          <div className="flex flex-col items-center gap-2 py-4">
            <CheckCircle2 className="h-10 w-10 text-success" />
            <p className="font-semibold">Execution Engine Online</p>
            <p className="text-xs text-muted-foreground">
              UCC: <span className="font-mono font-medium text-foreground">{key || "HACK342"}</span> · Environment: {env === "api021" ? "021 Live Production API" : "021 Developer OMS Engine"}
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Button className="w-full" onClick={() => nav({ to: "/dashboard" })}>Continue to Dashboard</Button>
            <Button variant="outline" className="w-full text-xs" onClick={() => setState("idle")}>
              Reconfigure Connection
            </Button>
          </div>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Trading Environment" sub="Link your 021 execution session and UCC credentials.">
      <form onSubmit={connect} className="space-y-4">
        {errorMsg && (
          <div className="rounded-lg border border-destructive/30 bg-danger-soft p-3 text-xs text-destructive">
            {errorMsg}
          </div>
        )}

        <Field label="Execution Environment">
          <select
            className={inputCls}
            value={env}
            onChange={(e) => setEnv(e.target.value)}
          >
            <option value="simulated">021 Developer OMS Engine (Paper / Sandbox)</option>
            <option value="api021">021 Production Trading API (Live Market Gateway)</option>
          </select>
        </Field>

        <Field label="UCC / Client API Key">
          <input
            className={inputCls}
            required
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="e.g. HACK342"
          />
        </Field>

        <Field label="API Secret / Password">
          <input
            className={inputCls}
            type="password"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder="••••••••••••"
          />
        </Field>

        <div className="pt-2">
          <Button type="submit" className="w-full" disabled={state === "loading"}>
            {state === "loading" ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Authenticating Session…
              </>
            ) : (
              <>
                <Lock className="mr-2 h-4 w-4" /> Link Trading Session
              </>
            )}
          </Button>
        </div>
      </form>
    </AuthShell>
  );
}
