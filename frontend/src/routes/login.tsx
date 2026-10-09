import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { AuthShell } from "@/components/tm/AuthShell";
import { Button, Field, Modal, inputCls } from "@/components/tm/ui";
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
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Forgot Password modal state
  const [forgotOpen, setForgotOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [forgotStep, setForgotStep] = useState<"request" | "reset">("request");
  const [forgotMsg, setForgotMsg] = useState("");
  const [forgotErr, setForgotErr] = useState("");
  const [forgotLoading, setForgotLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await authService.login(email, password);
      nav({ to: "/connect" });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to log in. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const requestReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setForgotErr("");
    setForgotMsg("");
    setForgotLoading(true);
    try {
      const res = await authService.forgotPassword(forgotEmail);
      if (res.reset_token) {
        setResetToken(res.reset_token);
        setForgotMsg("Reset token generated! Enter your new password below.");
        setForgotStep("reset");
      } else {
        setForgotMsg(res.message);
      }
    } catch (err: unknown) {
      setForgotErr(err instanceof Error ? err.message : "Unable to request password reset.");
    } finally {
      setForgotLoading(false);
    }
  };

  const completeReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      setForgotErr("New password must be at least 8 characters long.");
      return;
    }
    setForgotErr("");
    setForgotMsg("");
    setForgotLoading(true);
    try {
      const res = await authService.resetPassword(resetToken, newPassword);
      setForgotMsg(res.message + " You can now log in.");
      setTimeout(() => {
        setForgotOpen(false);
        setForgotStep("request");
        setForgotMsg("");
      }, 1800);
    } catch (err: unknown) {
      setForgotErr(err instanceof Error ? err.message : "Failed to reset password.");
    } finally {
      setForgotLoading(false);
    }
  };

  return (
    <AuthShell title="Log in" sub="Welcome back. Enter your credentials to access your trading desk.">
      <form onSubmit={submit} className="space-y-4">
        {error && (
          <div className="rounded-md border border-destructive/30 bg-danger-soft p-3 text-xs text-destructive">
            {error}
          </div>
        )}
        <Field label="Email">
          <input
            className={inputCls}
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </Field>
        <Field label="Password">
          <input
            className={inputCls}
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••••••"
          />
        </Field>
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => {
              setForgotEmail(email);
              setForgotErr("");
              setForgotMsg("");
              setForgotStep("request");
              setForgotOpen(true);
            }}
            className="text-xs text-primary hover:underline cursor-pointer"
          >
            Forgot password?
          </button>
        </div>
        <Button className="w-full" disabled={loading}>{loading ? "Logging in…" : "Login"}</Button>
      </form>
      <p className="mt-5 text-center text-sm text-muted-foreground">
        New to TradeMint? <Link to="/signup" className="font-medium text-primary hover:underline">Create an account</Link>
      </p>

      {/* Forgot Password Modal */}
      <Modal open={forgotOpen} onClose={() => setForgotOpen(false)} title="Reset your password">
        {forgotMsg && (
          <div className="mb-4 rounded-md border border-success/30 bg-success-soft p-3 text-xs text-success">
            {forgotMsg}
          </div>
        )}
        {forgotErr && (
          <div className="mb-4 rounded-md border border-destructive/30 bg-danger-soft p-3 text-xs text-destructive">
            {forgotErr}
          </div>
        )}

        {forgotStep === "request" ? (
          <form onSubmit={requestReset} className="space-y-4">
            <p className="text-xs text-muted-foreground">
              Enter your registered email address and we will issue a secure reset token.
            </p>
            <Field label="Email">
              <input
                className={inputCls}
                type="email"
                required
                value={forgotEmail}
                onChange={(e) => setForgotEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </Field>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setForgotOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={forgotLoading}>
                {forgotLoading ? "Requesting…" : "Request Reset"}
              </Button>
            </div>
          </form>
        ) : (
          <form onSubmit={completeReset} className="space-y-4">
            <Field label="Reset token">
              <input
                className={inputCls}
                required
                value={resetToken}
                onChange={(e) => setResetToken(e.target.value)}
                placeholder="Paste token here"
              />
            </Field>
            <Field label="New password (min 8 characters)">
              <input
                className={inputCls}
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••••••"
              />
            </Field>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setForgotStep("request")}>Back</Button>
              <Button type="submit" disabled={forgotLoading}>
                {forgotLoading ? "Resetting…" : "Set New Password"}
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </AuthShell>
  );
}
