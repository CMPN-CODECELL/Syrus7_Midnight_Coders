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
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password.length < 8) {
      return setError("Password must be at least 8 characters long.");
    }
    if (!anyLetter(form.password) || !anyDigitOrSpecial(form.password)) {
      return setError("Password must contain at least one letter and one number or special character.");
    }
    if (form.password !== form.confirm) {
      return setError("Passwords do not match.");
    }
    setError("");
    setLoading(true);
    try {
      await authService.signup(form.name, form.email, form.password);
      nav({ to: "/dashboard" });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create account. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const anyLetter = (s: string) => /[a-zA-Z]/.test(s);
  const anyDigitOrSpecial = (s: string) => /[^a-zA-Z]/.test(s);

  return (
    <AuthShell title="Create your account" sub="Start paper-trading with automated strategy execution.">
      <form onSubmit={submit} className="space-y-4">
        {error && (
          <div className="rounded-md border border-destructive/30 bg-danger-soft p-3 text-xs text-destructive">
            {error}
          </div>
        )}
        <Field label="Full name">
          <input className={inputCls} required value={form.name} onChange={set("name")} placeholder="Your Name" />
        </Field>
        <Field label="Email">
          <input className={inputCls} type="email" required value={form.email} onChange={set("email")} placeholder="you@example.com" />
        </Field>
        <Field label="Password">
          <input className={inputCls} type="password" required value={form.password} onChange={set("password")} placeholder="At least 8 characters" />
        </Field>
        <Field label="Confirm password">
          <input className={inputCls} type="password" required value={form.confirm} onChange={set("confirm")} placeholder="Re-enter password" />
        </Field>
        <Button className="w-full" disabled={loading}>{loading ? "Creating…" : "Create Account"}</Button>
      </form>
      <p className="mt-5 text-center text-sm text-muted-foreground">
        Already have an account? <Link to="/login" className="font-medium text-primary hover:underline">Login</Link>
      </p>
    </AuthShell>
  );
}
