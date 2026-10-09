const inrFmt = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const inr0 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export const inr = (n: number, decimals = false) => (decimals ? inrFmt : inr0).format(n);
export const signedInr = (n: number) => `${n >= 0 ? "+" : "−"}${inr(Math.abs(n))}`;
export const num = (n: number) => n.toLocaleString("en-IN");
export const hms = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { hour12: false });
export const statusLabel = (s: string) => s.replace(/_/g, " ");
