"use client";

import { useCallback, useEffect, useState } from "react";
import { CreditCard } from "lucide-react";
import { PageHeader, Loading, ErrorState, EmptyState } from "@/components/ui";
import { superAdminApi, type SubscriptionOut } from "@/lib/super-admin-api-client";

const STATUSES = ["trial", "active", "past_due", "suspended", "cancelled", "superseded"];

export default function SuperAdminSubscriptionsPage() {
  const [items, setItems] = useState<SubscriptionOut[]>([]);
  const [filter, setFilter] = useState("all");
  const [pendingStatus, setPendingStatus] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await superAdminApi.subscriptions.list({
        status: filter === "all" ? undefined : filter,
        limit: 100,
        offset: 0,
      });
      setItems(result.items);
      setPendingStatus({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load subscriptions");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function saveStatus(subscription: SubscriptionOut) {
    const status = pendingStatus[subscription.id];
    if (!status || status === subscription.status) return;
    setSavingId(subscription.id);
    setError(null);
    try {
      await superAdminApi.subscriptions.update(subscription.id, { status });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The subscription transition was rejected");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Subscriptions"
        description="Review subscription state and request lifecycle transitions. The backend validates every transition."
      />
      {error && <div className="mb-4"><ErrorState message={error} onRetry={load} /></div>}
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-extrabold text-slate-900">Subscription ledger</h2>
            <p className="mt-1 text-xs text-slate-500">{items.length} records loaded</p>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-blue-700"><CreditCard size={17} /></div>
          <label className="sr-only" htmlFor="subscription-status-filter">Filter subscription status</label>
          <select id="subscription-status-filter" value={filter} onChange={(e) => setFilter(e.target.value)} className="min-h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700">
            <option value="all">All statuses</option>
            {STATUSES.map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}
          </select>
        </div>
        {loading ? (
          <Loading label="Loading subscriptions..." />
        ) : items.length === 0 ? (
          <EmptyState title="No subscriptions found" description="There are no subscription records for this filter." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[850px] text-left">
              <thead className="bg-slate-50/80 text-[10px] font-bold uppercase tracking-[0.13em] text-slate-400">
                <tr>
                  <th className="px-5 py-3">Plan / subscription</th>
                  <th className="px-4 py-3">Agency ID</th>
                  <th className="px-4 py-3">Price snapshot</th>
                  <th className="px-4 py-3">Current status</th>
                  <th className="px-5 py-3 text-right">Update status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((item) => {
                  const nextStatus = pendingStatus[item.id] ?? item.status;
                  return (
                    <tr key={item.id} className="hover:bg-slate-50/70">
                      <td className="px-5 py-4">
                        <div className="text-sm font-bold text-slate-800">{item.plan_name_snapshot}</div>
                        <div className="mt-1 text-[10px] text-slate-400">{item.id.slice(0, 8)}… · {new Date(item.created_at).toLocaleDateString()}</div>
                      </td>
                      <td className="px-4 py-4 font-mono text-[10px] text-slate-500">{item.agency_id.slice(0, 8)}…</td>
                      <td className="px-4 py-4 text-xs font-bold text-slate-700">
                        {(item.price_monthly_snapshot / 100).toFixed(2)} {item.currency_snapshot}
                      </td>
                      <td className="px-4 py-4">
                        <span className="rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-[10px] font-bold capitalize text-slate-600">{item.status.replaceAll("_", " ")}</span>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center justify-end gap-2">
                          <select
                            value={nextStatus}
                            onChange={(e) => setPendingStatus((current) => ({ ...current, [item.id]: e.target.value }))}
                            className="min-h-9 rounded-lg border border-slate-200 bg-white px-2 text-[10px] font-semibold text-slate-700"
                            aria-label={`New status for subscription ${item.id}`}
                          >
                            {STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
                          </select>
                          <button
                            type="button"
                            disabled={savingId === item.id || nextStatus === item.status}
                            onClick={() => void saveStatus(item)}
                            className="min-h-9 rounded-lg bg-slate-900 px-3 text-[10px] font-bold text-white disabled:cursor-not-allowed disabled:opacity-30"
                          >
                            {savingId === item.id ? "Saving…" : "Save"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
