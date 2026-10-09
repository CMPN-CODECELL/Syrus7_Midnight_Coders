import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { AuthShell } from "@/components/tm/AuthShell";
import { Button, Field, inputCls } from "@/components/tm/ui";
import { authService } from "@/services";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Log in — TradeMint" },
      { name: "description", content: "Log in to TradeMint to run algorithmic strategies with platform-level risk controls." },
      { property: "og:title", content: "Log in — TradeMint" },
      { property: "og:description", content: "Automate strategies. Manage risk. Trade smarter." },
    ],
  }),
  component: Login,
});

function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("demo@trademint.in");
  const [password, setPassword] = useState("demo1234");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    await authService.login(email, password);
    nav({ to: "/connect" });
  };

  return (
    <AuthShell title="Log in" sub="Welcome back. Use any email and password in this demo.">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email"><input className={inputCls} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password"><input className={inputCls} type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        <div className="flex justify-end">
          <button type="button" className="text-xs text-primary hover:underline">Forgot password?</button>
        </div>
        <Button className="w-full" disabled={loading}>{loading ? "Logging in…" : "Login"}</Button>
      </form>
      <p className="mt-5 text-center text-sm text-muted-foreground">
        New to TradeMint? <Link to="/signup" className="font-medium text-primary hover:underline">Create an account</Link>
      </p>
    </AuthShell>
  );
}
