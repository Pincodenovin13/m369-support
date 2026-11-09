"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Tags } from "lucide-react";
import { PageHeader, Loading, ErrorState, EmptyState } from "@/components/ui";
import { superAdminApi, type PlanOut } from "@/lib/super-admin-api-client";

export default function SuperAdminPlansPage() {
  const [plans, setPlans] = useState<PlanOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    display_name: "",
    price: "19.00",
    trial_days: "7",
    currency: "USD",
  });

  const loadPlans = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await superAdminApi.plans.list({ limit: 100, offset: 0 });
      setPlans(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load plans");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPlans();
  }, [loadPlans]);

  async function createPlan(event: React.FormEvent) {
    event.preventDefault();
    if (saving) return;
    const price = Number(form.price);
    const trialDays = Number(form.trial_days);
    if (!Number.isFinite(price) || price < 0 || !Number.isInteger(trialDays) || trialDays < 0) {
      setError("Enter a valid non-negative price and whole-number trial period.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await superAdminApi.plans.create({
        name: form.name.trim().toLowerCase(),
        display_name: form.display_name.trim(),
        price_monthly: Math.round(price * 100),
        currency: form.currency,
        is_active: true,
        sort_order: plans.length,
        features: {},
        limits: {},
        trial_days: trialDays,
      });
      setShowCreate(false);
      setForm({ name: "", display_name: "", price: "19.00", trial_days: "7", currency: "USD" });
      await loadPlans();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create plan");
    } finally {
      setSaving(false);
    }
  }

  async function togglePlan(plan: PlanOut) {
    setSavingId(plan.id);
    setError(null);
    try {
      await superAdminApi.plans.update(plan.id, { is_active: !plan.is_active });
      await loadPlans();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update plan");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Plans and pricing"
        description="Control the subscription plans offered to agencies. Prices are stored in minor currency units."
        action={
          <button
            type="button"
            onClick={() => setShowCreate((value) => !value)}
            className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-xs font-extrabold text-white shadow-lg shadow-orange-500/20 transition hover:bg-brand-600"
          >
            <Plus size={15} />
            {showCreate ? "Close form" : "New plan"}
          </button>
        }
      />

      {error && <div className="mb-4"><ErrorState message={error} onRetry={loadPlans} /></div>}

      {showCreate && (
        <form onSubmit={createPlan} className="mb-6 rounded-2xl border border-orange-100 bg-white p-5 shadow-sm">
          <div className="mb-4">
            <h2 className="text-sm font-extrabold text-slate-900">Create subscription plan</h2>
            <p className="mt-1 text-xs text-slate-500">The internal name is a stable identifier and cannot be changed later.</p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <label className="block">
              <span className="text-[11px] font-bold text-slate-600">Internal name</span>
              <input required minLength={2} maxLength={60} pattern="[a-z0-9_-]+" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value.toLowerCase().replace(/\s+/g, "-") })} placeholder="starter" className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-brand-400 focus:ring-4 focus:ring-orange-500/10" />
            </label>
            <label className="block">
              <span className="text-[11px] font-bold text-slate-600">Display name</span>
              <input required minLength={1} maxLength={120} value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="Starter" className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-brand-400 focus:ring-4 focus:ring-orange-500/10" />
            </label>
            <label className="block">
              <span className="text-[11px] font-bold text-slate-600">Monthly price</span>
              <input required type="number" min="0" step="0.01" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-brand-400 focus:ring-4 focus:ring-orange-500/10" />
            </label>
            <label className="block">
              <span className="text-[11px] font-bold text-slate-600">Currency</span>
              <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-brand-400">
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
              </select>
            </label>
            <label className="block">
              <span className="text-[11px] font-bold text-slate-600">Trial days</span>
              <input required type="number" min="0" max="365" step="1" value={form.trial_days} onChange={(e) => setForm({ ...form, trial_days: e.target.value })} className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-brand-400 focus:ring-4 focus:ring-orange-500/10" />
            </label>
          </div>
          <div className="mt-5 flex justify-end">
            <button type="submit" disabled={saving} className="min-h-10 rounded-xl bg-slate-900 px-5 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-50">
              {saving ? "Creating…" : "Create plan"}
            </button>
          </div>
        </form>
      )}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="text-sm font-extrabold text-slate-900">Available plans</h2>
            <p className="mt-1 text-xs text-slate-500">{plans.length} plans loaded</p>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-50 text-brand-600"><Tags size={17} /></div>
        </div>
        {loading ? (
          <Loading label="Loading plans..." />
        ) : plans.length === 0 ? (
          <EmptyState title="No plans found" description="Create the first plan to make it available to agencies." />
        ) : (
          <div className="divide-y divide-slate-100">
            {plans.map((plan) => (
              <div key={plan.id} className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-extrabold text-slate-800">{plan.display_name}</span>
                    <span className="rounded-md bg-slate-100 px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-slate-500">{plan.name}</span>
                    <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold ${plan.is_active ? "border-emerald-100 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-100 text-slate-500"}`}>{plan.is_active ? "Active" : "Inactive"}</span>
                  </div>
                  <div className="mt-2 text-xs text-slate-500">
                    <strong className="text-lg font-black text-slate-900">{(plan.price_monthly / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {plan.currency}</strong>
                    <span className="ml-1">/ month</span>
                    <span className="mx-2 text-slate-300">·</span>
                    {plan.trial_days} trial days
                  </div>
                </div>
                <button
                  type="button"
                  disabled={savingId === plan.id}
                  onClick={() => void togglePlan(plan)}
                  className={`min-h-9 shrink-0 rounded-lg border px-3 text-[10px] font-bold transition disabled:opacity-50 ${plan.is_active ? "border-red-100 text-red-600 hover:bg-red-50" : "border-emerald-100 text-emerald-700 hover:bg-emerald-50"}`}
                >
                  {savingId === plan.id ? "Saving…" : plan.is_active ? "Deactivate plan" : "Activate plan"}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
