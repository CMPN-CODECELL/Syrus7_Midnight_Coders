import { useEffect, useState } from "react";
import {
  Mail,
  Send,
  CheckCircle2,
  AlertCircle,
  FileText,
  ShieldCheck,
  Building2,
  Clock,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { Badge, Button, Modal } from "@/components/tm/ui";
import { emailReportService, authService } from "@/services";

interface Props {
  open: boolean;
  onClose: () => void;
  defaultEmail?: string;
}

export function EmailStatementModal({ open, onClose, defaultEmail }: Props) {
  const [recipient, setRecipient] = useState<string>("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{
    status: string;
    deliveryStatus: string;
    message: string;
    statementId: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [smtpStatus, setSmtpStatus] = useState<{
    smtpHost: string;
    smtpUser: string;
    isConfigured: boolean;
  }>({
    smtpHost: "smtp.gmail.com",
    smtpUser: "",
    isConfigured: false,
  });

  useEffect(() => {
    if (open) {
      const u = authService.getCurrentUser();
      setRecipient(defaultEmail || u?.email || "trader@trademint.io");
      setResult(null);
      setError(null);
      emailReportService
        .getSmtpStatus()
        .then((res) => setSmtpStatus(res))
        .catch(() => {});
    }
  }, [open, defaultEmail]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipient.trim()) return;

    setSending(true);
    setError(null);
    setResult(null);

    try {
      const res = await emailReportService.sendPnlStatement(recipient.trim());
      setResult(res);
    } catch (err: any) {
      setError(err?.message || "Failed to dispatch email statement. Please verify SMTP settings.");
    } finally {
      setSending(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Daily P&L Statement & SEBI Tax Invoicing"
      wide
    >
      <div className="space-y-5 text-foreground">
        {/* Institutional Clearing Header */}
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <FileText className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold tracking-tight">TradeMint Institutional Dispatcher</h4>
                  <Badge tone="success" dot>
                    SEBI SCRA Rule 15
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  Automated electronic profit &amp; loss statement with itemized statutory tariff charges.
                </p>
              </div>
            </div>
            <Badge tone={smtpStatus.isConfigured ? "success" : "neutral"} dot className="self-start sm:self-auto">
              {smtpStatus.isConfigured ? `SMTP Ready: ${smtpStatus.smtpHost}` : "SMTP Standby"}
            </Badge>
          </div>
        </div>

        {/* Feature Summary Cards */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-lg border bg-muted/20 p-3 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-foreground">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <span>Statutory Tariffs</span>
            </div>
            <p className="mt-1 text-muted-foreground">
              STT (0.025%), GST (18%), NSE charges, SEBI turnover, &amp; stamp duty itemized.
            </p>
          </div>

          <div className="rounded-lg border bg-muted/20 p-3 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-foreground">
              <Building2 className="h-4 w-4 text-primary" />
              <span>Multi-Strategy P&amp;L</span>
            </div>
            <p className="mt-1 text-muted-foreground">
              Live telemetry aggregation across running algorithms and open market positions.
            </p>
          </div>

          <div className="rounded-lg border bg-muted/20 p-3 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-foreground">
              <Clock className="h-4 w-4 text-primary" />
              <span>TLS Direct Dispatch</span>
            </div>
            <p className="mt-1 text-muted-foreground">
              Instant delivery via secure Gmail SMTP with full audit trail logging.
            </p>
          </div>
        </div>

        {/* Dispatch Result Alerts */}
        {result && (
          <div
            className={`rounded-xl border p-4 text-xs ${
              result.status === "SUCCESS"
                ? "border-success/30 bg-success-soft text-success"
                : "border-destructive/30 bg-danger-soft text-destructive"
            }`}
          >
            <div className="flex items-start gap-2.5">
              {result.status === "SUCCESS" ? (
                <CheckCircle2 className="h-5 w-5 shrink-0 mt-0.5 text-success" />
              ) : (
                <AlertCircle className="h-5 w-5 shrink-0 mt-0.5 text-destructive" />
              )}
              <div className="space-y-1">
                <p className="font-semibold text-sm">{result.message}</p>
                <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] opacity-90">
                  <span>Statement ID: {result.statementId}</span>
                  <span>Delivery: {result.deliveryStatus}</span>
                  <span>Target: {recipient}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-destructive/30 bg-danger-soft p-4 text-xs text-destructive">
            <div className="flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Recipient Form */}
        <form onSubmit={handleSend} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">
              Recipient Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                type="email"
                required
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
                placeholder="trader@domain.com"
                className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-4 text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <p className="text-[11px] text-muted-foreground">
              The email will contain the executive summary, itemized regulatory taxes, active strategies breakdown, and open positions.
            </p>
          </div>

          <div className="flex items-center justify-between pt-2 border-t">
            <div className="text-xs text-muted-foreground">
              Sender: <span className="font-medium text-foreground">{smtpStatus.smtpUser || "darshanmali44444@gmail.com"}</span>
            </div>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" size="sm" onClick={onClose}>
                Close
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={sending || !recipient.trim()}
                className="gap-1.5 px-4"
              >
                {sending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Sending Statement…
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" />
                    Send Statement Now
                  </>
                )}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </Modal>
  );
}
