"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, CreditCard, XCircle } from "lucide-react";
import { PageHeader, Loading, ErrorState, EmptyState } from "@/components/ui";
import { superAdminApi, type PaymentOut } from "@/lib/super-admin-api-client";

const PAYMENT_STATUSES = ["pending", "verifying", "verified", "rejected", "expired"];

function decimalToInteger(value: string, scale: number): bigint {
  const match = /^(\d+)(?:\.(\d*))?$/.exec(value.trim());
  if (!match) throw new Error("Enter a valid non-negative decimal amount.");
  const whole = match[1];
  const fraction = match[2] ?? "";
  if (fraction.length > scale) {
    throw new Error(`This value supports at most ${scale} decimal places.`);
  }
  const multiplier = BigInt(10) ** BigInt(scale);
  return BigInt(whole) * multiplier + BigInt(fraction.padEnd(scale, "0") || "0");
}

function calculatePaymentAmounts(tokenAmount: string, decimalsValue: string, rateValue: string) {
  const decimals = Number(decimalsValue);
  if (!Number.isInteger(decimals) || decimals < 0 || decimals > 18) {
    throw new Error("Token decimals must be a whole number from 0 to 18.");
  }
  const raw = decimalToInteger(tokenAmount, decimals);
  if (raw <= BigInt(0) || raw.toString().length > 78) {
    throw new Error("Raw token amount must fit the supported uint256 precision.");
  }
  const rateScaled = decimalToInteger(rateValue, 6);
  if (rateScaled <= BigInt(0)) throw new Error("Exchange rate must be greater than zero.");
  const denominator = (BigInt(10) ** BigInt(decimals)) * BigInt(1000000);
  const numerator = raw * rateScaled * BigInt(100);
  const baseCents = (numerator + denominator / BigInt(2)) / denominator;
  if (baseCents < BigInt(0) || baseCents > BigInt(2147483647)) {
    throw new Error("Converted base amount exceeds the database INTEGER limit.");
  }
  return {
    raw,
    baseCents: Number(baseCents),
    exchangeRate: Number(rateScaled) / 1000000,
  };
}

function previewBaseAmount(tokenAmount: string, decimals: string, rate: string, currency: string): string {
  if (!tokenAmount || !decimals || !rate) return "—";
  try {
    const calculated = calculatePaymentAmounts(tokenAmount, decimals, rate);
    return `${(calculated.baseCents / 100).toFixed(2)} ${currency}`;
  } catch {
    return "Invalid amount or rate";
  }
}


export default function SuperAdminPaymentsPage() {
  const [items, setItems] = useState<PaymentOut[]>([]);
  const [filter, setFilter] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activePayment, setActivePayment] = useState<string | null>(null);
  const [mode, setMode] = useState<"verify" | "reject">("verify");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    tokenAmount: "",
    paidCurrency: "",
    decimals: "",
    exchangeRate: "",
    network: "",
    note: "",
    failureReason: "",
  });

  const loadPayments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await superAdminApi.payments.list({
        status: filter === "all" ? undefined : filter,
        limit: 100,
        offset: 0,
      });
      setItems(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load payments");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void loadPayments();
  }, [loadPayments]);

  function openAction(payment: PaymentOut, action: "verify" | "reject") {
    setActivePayment(payment.id);
    setMode(action);
    setForm({
      tokenAmount: "",
      paidCurrency: payment.paid_currency || "",
      decimals: payment.paid_amount_decimals == null ? "" : String(payment.paid_amount_decimals),
      exchangeRate: payment.exchange_rate == null ? "" : String(payment.exchange_rate),
      network: payment.network || "",
      note: "",
      failureReason: "",
    });
    setError(null);
  }

  async function submitAction(event: React.FormEvent) {
    event.preventDefault();
    if (!activePayment || saving) return;
    setSaving(true);
    setError(null);
    try {
      if (mode === "reject") {
        if (!form.failureReason.trim()) throw new Error("Enter a reason for rejecting this payment.");
        await superAdminApi.payments.reject(activePayment, form.failureReason.trim());
      } else {
        const calculated = calculatePaymentAmounts(form.tokenAmount, form.decimals, form.exchangeRate);
        await superAdminApi.payments.verify(activePayment, {
          amount_paid: calculated.baseCents,
          paid_currency: form.paidCurrency.trim().toUpperCase(),
          paid_amount_raw: calculated.raw,
          paid_amount_decimals: Number(form.decimals),
          exchange_rate: calculated.exchangeRate,
          network: form.network.trim().toUpperCase() || undefined,
          note: form.note.trim() || undefined,
        });
      }
      setActivePayment(null);
      await loadPayments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to process payment");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Payment review"
        description="Payments are manually verified in Phase 1. Confirm the on-chain amount and conversion rate before approving."
      />

      {error && <div className="mb-4"><ErrorState message={error} onRetry={loadPayments} /></div>}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-extrabold text-slate-900">Payment ledger</h2>
            <p className="mt-1 text-xs text-slate-500">{items.length} records loaded</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-50 text-amber-700"><CreditCard size={17} /></div>
            <label className="sr-only" htmlFor="payment-status-filter">Filter payment status</label>
            <select id="payment-status-filter" value={filter} onChange={(e) => { setFilter(e.target.value); setActivePayment(null); }} className="min-h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700">
              <option value="all">All statuses</option>
              {PAYMENT_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
            </select>
          </div>
        </div>

        {loading ? (
          <Loading label="Loading payments..." />
        ) : items.length === 0 ? (
          <EmptyState title="No payments found" description="There are no payment records for this status." />
        ) : (
          <div className="divide-y divide-slate-100">
            {items.map((payment) => {
              const terminal = payment.status === "verified" || payment.status === "rejected" || payment.status === "expired";
              return (
                <article key={payment.id} className="px-5 py-4">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-extrabold text-slate-800">{(payment.amount_expected / 100).toFixed(2)} {payment.currency}</span>
                        <span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${payment.status === "verified" ? "border-emerald-100 bg-emerald-50 text-emerald-700" : payment.status === "pending" || payment.status === "verifying" ? "border-amber-100 bg-amber-50 text-amber-700" : "border-slate-200 bg-slate-100 text-slate-500"}`}>{payment.status}</span>
                      </div>
                      <div className="mt-1 break-all font-mono text-[10px] text-slate-400">TXID: {payment.txid}</div>
                      <div className="mt-1 text-[10px] text-slate-400">Agency {payment.agency_id.slice(0, 8)}… · {new Date(payment.created_at).toLocaleString()}</div>
                      {payment.failure_reason && <div className="mt-2 text-xs text-red-600">Reason: {payment.failure_reason}</div>}
                    </div>
                    {!terminal && (
                      <div className="flex shrink-0 gap-2">
                        <button type="button" onClick={() => openAction(payment, "verify")} className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-emerald-600 px-3 text-[10px] font-bold text-white hover:bg-emerald-700">
                          <CheckCircle2 size={14} /> Verify
                        </button>
                        <button type="button" onClick={() => openAction(payment, "reject")} className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-red-100 px-3 text-[10px] font-bold text-red-600 hover:bg-red-50">
                          <XCircle size={14} /> Reject
                        </button>
                      </div>
                    )}
                  </div>

                  {activePayment === payment.id && (
                    <form onSubmit={submitAction} className="mt-5 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-xs font-extrabold text-slate-800">{mode === "verify" ? "Verify payment details" : "Reject payment"}</h3>
                        <button type="button" onClick={() => setActivePayment(null)} className="text-[10px] font-bold text-slate-400 hover:text-slate-700">Close</button>
                      </div>
                      {mode === "verify" ? (
                        <>
                          <p className="mb-4 text-[11px] leading-5 text-slate-500">
                            Enter the actual received token amount and the base-currency value of one token at the time of payment. The API stores the base amount in cents (two decimal places) and the raw token integer for the audit record. No exchange rate, network, or token precision is assumed.
                          </p>
                          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                            <label className="text-[10px] font-bold text-slate-600">Received amount
                              <input required type="number" min="0.00000001" step="any" value={form.tokenAmount} onChange={(e) => setForm({ ...form, tokenAmount: e.target.value })} className="mt-1.5 min-h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs" placeholder="125.50" />
                            </label>
                            <label className="text-[10px] font-bold text-slate-600">Paid currency
                              <input required maxLength={10} value={form.paidCurrency} onChange={(e) => setForm({ ...form, paidCurrency: e.target.value })} className="mt-1.5 min-h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs" placeholder="USDT" />
                            </label>
                            <label className="text-[10px] font-bold text-slate-600">Token decimals
                              <input required type="number" min="0" max="18" step="1" value={form.decimals} onChange={(e) => setForm({ ...form, decimals: e.target.value })} className="mt-1.5 min-h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs" />
                            </label>
                            <label className="text-[10px] font-bold text-slate-600">Base units per token
                              <input required type="number" min="0.00000001" step="any" value={form.exchangeRate} onChange={(e) => setForm({ ...form, exchangeRate: e.target.value })} className="mt-1.5 min-h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs" />
                            </label>
                            <label className="text-[10px] font-bold text-slate-600">Network
                              <input maxLength={20} value={form.network} onChange={(e) => setForm({ ...form, network: e.target.value })} className="mt-1.5 min-h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs" placeholder="TRC20 / BEP20" />
                            </label>
                            <label className="text-[10px] font-bold text-slate-600 sm:col-span-2">Audit note (optional)
                              <input maxLength={500} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} className="mt-1.5 min-h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs" />
                            </label>
                          </div>
                          <div className="mt-3 text-[10px] text-slate-500">
                            Calculated base amount (cents): {previewBaseAmount(form.tokenAmount, form.decimals, form.exchangeRate, payment.currency)}
                          </div>
                        </>
                      ) : (
                        <label className="block text-[10px] font-bold text-slate-600">Reason for rejection
                          <textarea required maxLength={2000} rows={3} value={form.failureReason} onChange={(e) => setForm({ ...form, failureReason: e.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs" placeholder="Explain why the transaction could not be verified." />
                        </label>
                      )}
                      <div className="mt-4 flex flex-wrap justify-end gap-2">
                        <button type="button" onClick={() => setActivePayment(null)} className="min-h-9 rounded-lg border border-slate-200 bg-white px-4 text-[10px] font-bold text-slate-600">Cancel</button>
                        <button type="submit" disabled={saving} className={`min-h-9 rounded-lg px-4 text-[10px] font-bold text-white disabled:opacity-50 ${mode === "verify" ? "bg-emerald-600 hover:bg-emerald-700" : "bg-red-600 hover:bg-red-700"}`}>
                          {saving ? "Processing…" : mode === "verify" ? "Confirm verification" : "Confirm rejection"}
                        </button>
                      </div>
                    </form>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </>
  );
}
