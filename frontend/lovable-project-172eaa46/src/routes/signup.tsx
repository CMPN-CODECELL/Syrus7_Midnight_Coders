import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { AuthShell } from "@/components/tm/AuthShell";
import { Button, Field, inputCls } from "@/components/tm/ui";
import { authService } from "@/services";

export const Route = createFileRoute("/signup")({
  head: () => ({
    meta: [
      { title: "Create account — TradeMint" },
      { name: "description", content: "Create a TradeMint account and start automating strategies with built-in risk management." },
      { property: "og:title", content: "Create account — TradeMint" },
      { property: "og:description", content: "Strategies can fail. Risk controls cannot." },
    ],
  }),
  component: Signup,
});

function Signup() {
  const nav = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password.length < 6) return setError("Password must be at least 6 characters.");
    if (form.password !== form.confirm) return setError("Passwords do not match.");
    setError("");
    setLoading(true);
    await authService.signup(form.name, form.email, form.password);
    nav({ to: "/connect" });
  };

  return (
    <AuthShell title="Create your account" sub="Get started with a sandbox trading environment.">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Full name"><input className={inputCls} required value={form.name} onChange={set("name")} /></Field>
        <Field label="Email"><input className={inputCls} type="email" required value={form.email} onChange={set("email")} /></Field>
        <Field label="Password"><input className={inputCls} type="password" required value={form.password} onChange={set("password")} /></Field>
        <Field label="Confirm password"><input className={inputCls} type="password" required value={form.confirm} onChange={set("confirm")} /></Field>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button className="w-full" disabled={loading}>{loading ? "Creating…" : "Create Account"}</Button>
      </form>
      <p className="mt-5 text-center text-sm text-muted-foreground">
        Already have an account? <Link to="/login" className="font-medium text-primary hover:underline">Login</Link>
      </p>
    </AuthShell>
  );
}
