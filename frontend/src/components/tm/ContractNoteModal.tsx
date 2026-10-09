import { useState } from "react";
import {
  Building2,
  Check,
  Copy,
  Download,
  FileCheck,
  FileText,
  Printer,
  ShieldCheck,
} from "lucide-react";
import { Badge, Button, Modal } from "@/components/tm/ui";
import type { ContractNote } from "@/types";
import { exportContractNoteCSV } from "@/lib/charges";
import { cn } from "@/lib/utils";

interface Props {
  note: ContractNote | null;
  open: boolean;
  onClose: () => void;
}

export function ContractNoteModal({ note, open, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  if (!note) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(note, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <Modal open={open} onClose={onClose} title="" wide>
      <div className="space-y-6 text-foreground print:p-0">
        {/* Institutional Clearing Header */}
        <div className="rounded-xl border border-border/80 bg-muted/20 p-5 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <FileCheck className="h-6 w-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold tracking-tight">ELECTRONIC CONTRACT NOTE</h3>
                  <Badge tone="success" dot>
                    SEBI Verified
                  </Badge>
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  TradeMint Clearing &amp; Settlement | Member: <span className="font-semibold text-foreground">{note.memberCode}</span>
                </p>
                <p className="text-[11px] text-muted-foreground">
                  SEBI Reg: <span className="font-mono text-foreground">{note.sebiRegistration}</span> | Clearing House: {note.clearingHouse}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
              <Button size="sm" variant="outline" onClick={handleCopy}>
                {copied ? <Check className="mr-1.5 h-3.5 w-3.5 text-success" /> : <Copy className="mr-1.5 h-3.5 w-3.5" />}
                {copied ? "Copied JSON" : "Copy Payload"}
              </Button>
              <Button size="sm" variant="outline" onClick={() => exportContractNoteCSV(note)}>
                <Download className="mr-1.5 h-3.5 w-3.5" />
                Export CSV
              </Button>
              <Button size="sm" variant="outline" onClick={handlePrint} className="hidden sm:inline-flex">
                <Printer className="mr-1.5 h-3.5 w-3.5" />
                Print
              </Button>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 border-t border-border/60 pt-3 text-xs sm:grid-cols-4">
            <div>
              <span className="text-muted-foreground">Contract Note No.</span>
              <p className="font-mono font-semibold text-foreground">{note.noteId}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Trade / Settlement Date</span>
              <p className="font-medium text-foreground">{note.tradeDate} (T+1 Rolling)</p>
            </div>
            <div>
              <span className="text-muted-foreground">Client UCC</span>
              <p className="font-mono font-medium text-foreground">{note.ucc}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Exchange / Segment</span>
              <p className="font-medium text-foreground">{note.exchange} {note.segment}</p>
            </div>
          </div>
        </div>

        {/* Trade Execution Specification */}
        <div className="rounded-xl border bg-card p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Executed Trade Order Summary
          </h4>
          <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <span className="text-xs text-muted-foreground">Order ID</span>
              <p className="font-mono text-sm font-semibold text-foreground">{note.orderId}</p>
              <p className="text-[11px] text-muted-foreground">{note.strategyName}</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Security</span>
              <p className="text-sm font-bold text-foreground">{note.symbol}</p>
              <span className={cn("text-xs font-semibold", note.side === "BUY" ? "text-success" : "text-destructive")}>
                {note.side} ({note.orderType})
              </span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Filled Quantity</span>
              <p className="num text-sm font-bold text-foreground">{note.quantity} Units</p>
              <p className="text-[11px] text-muted-foreground">@ ₹{note.averagePrice.toLocaleString("en-IN")}</p>
            </div>
            <div>
              <span className="text-xs text-muted-foreground">Gross Trade Turnover</span>
              <p className="num text-sm font-bold text-foreground">₹{note.grossTurnover.toLocaleString("en-IN")}</p>
              <p className="text-[11px] font-mono text-muted-foreground">{note.grossTurnoverPaise.toLocaleString()} paise</p>
            </div>
          </div>
        </div>

        {/* Itemized Regulatory Charges Breakdown Table (Integer Paise Precision) */}
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="border-b bg-muted/40 px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-foreground">
                Published Regulatory Charges Table (Integer Paise Precision)
              </h4>
            </div>
            <span className="text-[11px] font-medium text-muted-foreground">
              Rule 15 SCRA Compliant
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b bg-muted/20 text-left text-muted-foreground">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Charge Component</th>
                  <th className="px-4 py-2.5 font-medium">Statutory Rate / Base</th>
                  <th className="px-4 py-2.5 font-medium text-right">Paise Value</th>
                  <th className="px-4 py-2.5 font-medium text-right">Rupee Amount (₹)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                <tr>
                  <td className="px-4 py-2.5 font-medium text-foreground">Brokerage Fee</td>
                  <td className="px-4 py-2.5 text-muted-foreground">Flat ₹20.00 per executed order</td>
                  <td className="num px-4 py-2.5 text-right font-mono text-muted-foreground">{note.charges.brokeragePaise} paise</td>
                  <td className="num px-4 py-2.5 text-right font-semibold text-foreground">₹{note.charges.brokerage.toFixed(2)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-medium text-foreground">Securities Transaction Tax (STT)</td>
                  <td className="px-4 py-2.5 text-muted-foreground">0.025% on Intraday Sell (0% on Buy)</td>
                  <td className="num px-4 py-2.5 text-right font-mono text-muted-foreground">{note.charges.sttPaise} paise</td>
                  <td className="num px-4 py-2.5 text-right font-semibold text-foreground">₹{note.charges.stt.toFixed(2)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-medium text-foreground">Exchange Transaction Charges</td>
                  <td className="px-4 py-2.5 text-muted-foreground">0.00297% on Trade Turnover (NSE)</td>
                  <td className="num px-4 py-2.5 text-right font-mono text-muted-foreground">{note.charges.exchangeTxnFeePaise} paise</td>
                  <td className="num px-4 py-2.5 text-right font-semibold text-foreground">₹{note.charges.exchangeTxnFee.toFixed(2)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-medium text-foreground">SEBI Turnover Fee</td>
                  <td className="px-4 py-2.5 text-muted-foreground">₹10.00 / Crore (0.0001% Turnover)</td>
                  <td className="num px-4 py-2.5 text-right font-mono text-muted-foreground">{note.charges.sebiTurnoverFeePaise} paise</td>
                  <td className="num px-4 py-2.5 text-right font-semibold text-foreground">₹{note.charges.sebiTurnoverFee.toFixed(2)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-medium text-foreground">Stamp Duty (State Stamp Act)</td>
                  <td className="px-4 py-2.5 text-muted-foreground">0.015% on BUY side turnover only</td>
                  <td className="num px-4 py-2.5 text-right font-mono text-muted-foreground">{note.charges.stampDutyPaise} paise</td>
                  <td className="num px-4 py-2.5 text-right font-semibold text-foreground">₹{note.charges.stampDuty.toFixed(2)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 font-medium text-foreground">GST (Goods &amp; Services Tax)</td>
                  <td className="px-4 py-2.5 text-muted-foreground">18.00% on (Brokerage + Txn + SEBI)</td>
                  <td className="num px-4 py-2.5 text-right font-mono text-muted-foreground">{note.charges.gst18Paise} paise</td>
                  <td className="num px-4 py-2.5 text-right font-semibold text-foreground">₹{note.charges.gst18.toFixed(2)}</td>
                </tr>
              </tbody>
              <tfoot className="border-t bg-muted/30 font-semibold">
                <tr>
                  <td colSpan={2} className="px-4 py-3 text-foreground font-bold">
                    Total Statutory &amp; Regulatory Friction
                  </td>
                  <td className="num px-4 py-3 text-right font-mono text-destructive">
                    {note.charges.totalChargesPaise.toLocaleString()} paise
                  </td>
                  <td className="num px-4 py-3 text-right text-destructive text-sm font-bold">
                    ₹{note.charges.totalCharges.toFixed(2)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        {/* Net Settlement Obligation Card */}
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-4.5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <span className="text-xs font-semibold text-muted-foreground">
                Net Settlement Obligation ({note.side === "BUY" ? "Total Payable Debit" : "Net Receivable Credit"})
              </span>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="num text-2xl font-extrabold text-foreground">
                  ₹{note.netObligation.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </span>
                <span className="text-xs font-mono text-muted-foreground">
                  ({note.netObligationPaise.toLocaleString()} paise)
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Gross Turnover (₹{note.grossTurnover.toLocaleString("en-IN")}) {note.side === "BUY" ? "+" : "−"} Total Charges (₹{note.charges.totalCharges.toFixed(2)})
              </p>
            </div>

            <div className="rounded-lg border bg-background/80 p-3 sm:text-right">
              <span className="text-xs text-muted-foreground">Effective Regulatory Friction</span>
              <p className="mt-0.5 text-base font-bold text-primary">{note.chargesPercentage}%</p>
              <p className="text-[11px] text-muted-foreground">Zero float-drift guarantee</p>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
}
