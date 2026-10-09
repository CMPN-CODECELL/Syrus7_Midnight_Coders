import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Badge, Button, Card, CardHeader, Field, PageHeader, inputCls } from "@/components/tm/ui";
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
  useEffect(() => {
    const u = authService.getCurrentUser();
    if (u) { setName(u.name); setEmail(u.email); }
  }, []);

  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Settings" />
      <Card>
        <CardHeader title="Account" />
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <Field label="Name"><input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Email"><input className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        </div>
      </Card>
      <Card>
        <CardHeader title="Trading environment" />
        <div className="flex items-center justify-between p-5 text-sm">
          <span>021 Sandbox</span>
          <Badge tone="success" dot>Connected</Badge>
        </div>
      </Card>
      <Card>
        <CardHeader title="Application" />
        <div className="divide-y text-sm">
          <div className="flex items-center justify-between p-5"><span>Theme</span><span className="text-muted-foreground">Light</span></div>
          <label className="flex items-center justify-between p-5">
            <span>Risk & order notifications</span>
            <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} className="h-4 w-4 accent-primary" />
          </label>
        </div>
      </Card>
      <Card>
        <CardHeader title="Security" />
        <div className="flex flex-wrap gap-2 p-5">
          <Button variant="outline">Change Password</Button>
          <Button variant="dangerOutline" onClick={() => { authService.logout(); nav({ to: "/login" }); }}>Logout</Button>
        </div>
      </Card>
    </div>
  );
}
