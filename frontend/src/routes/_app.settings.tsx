import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Badge, Button, Card, CardHeader, Field, Modal, PageHeader, inputCls } from "@/components/tm/ui";
import { authService } from "@/services";

export const Route = createFileRoute("/_app/settings")({
  head: () => ({
    meta: [
      { title: "Settings — TradeMint" },
      { name: "description", content: "Manage your TradeMint account, trading environment and preferences." },
      { property: "og:title", content: "Settings — TradeMint" },
      { property: "og:description", content: "Account, environment, application and security settings." },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [notify, setNotify] = useState(true);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  const [savingAccount, setSavingAccount] = useState(false);
  const [accountMsg, setAccountMsg] = useState("");
  const [accountErr, setAccountErr] = useState("");

  const [savingPref, setSavingPref] = useState(false);
  const [prefMsg, setPrefMsg] = useState("");

  // Change Password Modal
  const [pwModalOpen, setPwModalOpen] = useState(false);
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwErr, setPwErr] = useState("");
  const [pwSuccess, setPwSuccess] = useState("");
  const [pwLoading, setPwLoading] = useState(false);

  useEffect(() => {
    const loadProfile = async () => {
      const u = (await authService.getMe()) ?? authService.getCurrentUser();
      if (u) {
        setName(u.name);
        setEmail(u.email);
        if (u.notifications_enabled !== undefined) {
          setNotify(Boolean(u.notifications_enabled));
        } else {
          setNotify(authService.isNotificationsEnabled());
        }
        if (u.theme === "dark" || u.theme === "light") {
          setTheme(u.theme);
          authService.applyTheme(u.theme);
        } else if (typeof document !== "undefined") {
          const isDark = document.documentElement.classList.contains("dark");
          setTheme(isDark ? "dark" : "light");
        }
      }
    };
    loadProfile();
  }, []);

  const saveAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setAccountErr("");
    setAccountMsg("");
    setSavingAccount(true);
    try {
      await authService.updateSettings({ name, email });
      setAccountMsg("Account profile updated successfully.");
      setTimeout(() => setAccountMsg(""), 3500);
    } catch (err: unknown) {
      setAccountErr(err instanceof Error ? err.message : "Failed to update account.");
    } finally {
      setSavingAccount(false);
    }
  };

  const toggleNotify = async (val: boolean) => {
    setNotify(val);
    setSavingPref(true);
    setPrefMsg("");
    try {
      await authService.updateSettings({ notifications_enabled: val });
      setPrefMsg(`Notifications ${val ? "enabled" : "disabled"}.`);
      setTimeout(() => setPrefMsg(""), 3000);
    } catch {
      // rollback if failed
      setNotify(!val);
    } finally {
      setSavingPref(false);
    }
  };

  const changeTheme = async (newTheme: "light" | "dark") => {
    setTheme(newTheme);
    authService.applyTheme(newTheme);
    try {
      await authService.updateSettings({ theme: newTheme });
    } catch {
      // persisted in local helper
    }
  };

  const submitChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwErr("");
    setPwSuccess("");
    if (newPw.length < 8) {
      setPwErr("New password must be at least 8 characters long.");
      return;
    }
    if (newPw !== confirmPw) {
      setPwErr("New passwords do not match.");
      return;
    }
    setPwLoading(true);
    try {
      const res = await authService.changePassword(currentPw, newPw);
      setPwSuccess(res.message);
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
      setTimeout(() => {
        setPwModalOpen(false);
        setPwSuccess("");
      }, 1800);
    } catch (err: unknown) {
      setPwErr(err instanceof Error ? err.message : "Failed to change password.");
    } finally {
      setPwLoading(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Settings" />

      {/* Account Settings */}
      <Card>
        <CardHeader title="Account" />
        <form onSubmit={saveAccount} className="space-y-4 p-5">
          {accountMsg && (
            <div className="rounded-md border border-success/30 bg-success-soft p-3 text-xs text-success">
              {accountMsg}
            </div>
          )}
          {accountErr && (
            <div className="rounded-md border border-destructive/30 bg-danger-soft p-3 text-xs text-destructive">
              {accountErr}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name">
              <input
                className={inputCls}
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <Field label="Email">
              <input
                className={inputCls}
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
          </div>
          <div className="flex justify-end pt-2">
            <Button type="submit" disabled={savingAccount}>
              {savingAccount ? "Saving…" : "Save Account Changes"}
            </Button>
          </div>
        </form>
      </Card>

      {/* Trading Environment */}
      <Card>
        <CardHeader title="Trading environment" />
        <div className="flex items-center justify-between p-5 text-sm">
          <div>
            <p className="font-medium">Trading Engine</p>
            <p className="text-xs text-muted-foreground">Simulated Execution Engine Adapter</p>
          </div>
          <Badge tone="success" dot>Connected</Badge>
        </div>
      </Card>

      {/* Application Settings */}
      <Card>
        <CardHeader title="Application" />
        <div className="divide-y text-sm">
          {prefMsg && (
            <div className="p-3 text-xs text-success bg-success-soft border-b border-success/30">
              {prefMsg}
            </div>
          )}
          <div className="flex items-center justify-between p-5">
            <div>
              <p className="font-medium">Theme</p>
              <p className="text-xs text-muted-foreground">Toggle application color palette</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => changeTheme("light")}
                className={`rounded px-3 py-1 text-xs font-medium border transition-colors ${
                  theme === "light"
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-card text-muted-foreground hover:text-foreground"
                }`}
              >
                Light
              </button>
              <button
                type="button"
                onClick={() => changeTheme("dark")}
                className={`rounded px-3 py-1 text-xs font-medium border transition-colors ${
                  theme === "dark"
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-card text-muted-foreground hover:text-foreground"
                }`}
              >
                Dark
              </button>
            </div>
          </div>
          <label className="flex items-center justify-between p-5 cursor-pointer">
            <div>
              <p className="font-medium">Risk & order notifications</p>
              <p className="text-xs text-muted-foreground">
                {notify
                  ? "Notifications enabled — alerts and toasts are delivered."
                  : "Notifications disabled — all toast alerts are suppressed."}
              </p>
            </div>
            <input
              type="checkbox"
              checked={notify}
              disabled={savingPref}
              onChange={(e) => toggleNotify(e.target.checked)}
              className="h-4 w-4 accent-primary cursor-pointer"
            />
          </label>
        </div>
      </Card>

      {/* Security Settings */}
      <Card>
        <CardHeader title="Security" />
        <div className="flex flex-wrap gap-2 p-5">
          <Button
            variant="outline"
            onClick={() => {
              setCurrentPw("");
              setNewPw("");
              setConfirmPw("");
              setPwErr("");
              setPwSuccess("");
              setPwModalOpen(true);
            }}
          >
            Change Password
          </Button>
          <Button
            variant="dangerOutline"
            onClick={async () => {
              await authService.logout();
              nav({ to: "/login" });
            }}
          >
            Logout
          </Button>
        </div>
      </Card>

      {/* Change Password Modal */}
      <Modal open={pwModalOpen} onClose={() => setPwModalOpen(false)} title="Change Password">
        <form onSubmit={submitChangePassword} className="space-y-4">
          {pwSuccess && (
            <div className="rounded-md border border-success/30 bg-success-soft p-3 text-xs text-success">
              {pwSuccess}
            </div>
          )}
          {pwErr && (
            <div className="rounded-md border border-destructive/30 bg-danger-soft p-3 text-xs text-destructive">
              {pwErr}
            </div>
          )}
          <Field label="Current password">
            <input
              className={inputCls}
              type="password"
              required
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              placeholder="••••••••••••"
            />
          </Field>
          <Field label="New password (min 8 characters)">
            <input
              className={inputCls}
              type="password"
              required
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              placeholder="••••••••••••"
            />
          </Field>
          <Field label="Confirm new password">
            <input
              className={inputCls}
              type="password"
              required
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              placeholder="••••••••••••"
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => setPwModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={pwLoading}>
              {pwLoading ? "Updating…" : "Update Password"}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
