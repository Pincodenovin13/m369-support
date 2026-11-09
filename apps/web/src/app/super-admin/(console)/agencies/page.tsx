"use client";

import { useCallback, useEffect, useState } from "react";
import { Search, ChevronLeft, ChevronRight, Building2 } from "lucide-react";
import { PageHeader, Loading, ErrorState, EmptyState } from "@/components/ui";
import { superAdminApi, type AgencyAdminDetailOut } from "@/lib/super-admin-api-client";

const PAGE_SIZE = 25;

export default function SuperAdminAgenciesPage() {
  const [items, setItems] = useState<AgencyAdminDetailOut[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  const loadAgencies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await superAdminApi.agencies.list({
        search: search.trim() || undefined,
        is_active: statusFilter === "all" ? undefined : statusFilter === "active",
        limit: PAGE_SIZE,
        offset,
      });
      setItems(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load agencies");
    } finally {
      setLoading(false);
    }
  }, [offset, search, statusFilter]);

  useEffect(() => {
    void loadAgencies();
  }, [loadAgencies]);

  async function toggleAgency(agency: AgencyAdminDetailOut) {
    setActionId(agency.id);
    setError(null);
    try {
      if (agency.is_active) {
        await superAdminApi.agencies.suspend(agency.id);
      } else {
        await superAdminApi.agencies.activate(agency.id);
      }
      setConfirmingId(null);
      await loadAgencies();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update agency status");
    } finally {
      setActionId(null);
    }
  }

  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + items.length, total);

  return (
    <>
      <PageHeader
        title="Agencies"
        description="Review tenant accounts, subscription summaries, and agency access."
      />

      <section className="mb-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <label className="relative block w-full md:max-w-md">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setOffset(0);
              }}
              placeholder="Search agency name or slug"
              className="min-h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-3 text-sm text-slate-800 outline-none transition focus:border-brand-400 focus:bg-white focus:ring-4 focus:ring-orange-500/10"
            />
          </label>
          <div className="flex items-center gap-2">
            {(["all", "active", "inactive"] as const).map((filter) => (
              <button
                key={filter}
                type="button"
                onClick={() => {
                  setStatusFilter(filter);
                  setOffset(0);
                }}
                aria-pressed={statusFilter === filter}
                className={`min-h-9 rounded-lg px-3 text-[11px] font-bold capitalize transition ${
                  statusFilter === filter
                    ? "bg-slate-900 text-white"
                    : "border border-slate-200 bg-white text-slate-500 hover:bg-slate-50"
                }`}
              >
                {filter}
              </button>
            ))}
          </div>
        </div>
      </section>

      {error && <div className="mb-4"><ErrorState message={error} onRetry={loadAgencies} /></div>}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="text-sm font-extrabold text-slate-900">Tenant directory</h2>
            <p className="mt-1 text-xs text-slate-500">{total.toLocaleString()} agencies</p>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-50 text-brand-600">
            <Building2 size={17} />
          </div>
        </div>

        {loading ? (
          <Loading label="Loading agencies..." />
        ) : items.length === 0 ? (
          <EmptyState title="No agencies found" description="Try changing the search text or status filter." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead className="bg-slate-50/80 text-[10px] font-bold uppercase tracking-[0.13em] text-slate-400">
                <tr>
                  <th className="px-5 py-3">Agency</th>
                  <th className="px-4 py-3">Subscription</th>
                  <th className="px-4 py-3">Members</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-5 py-3 text-right">Access</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((agency) => (
                  <tr key={agency.id} className="transition hover:bg-slate-50/70">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <span className="h-9 w-9 shrink-0 rounded-xl border border-slate-100" style={{ backgroundColor: agency.brand_color || "#f26a3d" }} />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-bold text-slate-800">{agency.name}</div>
                          <div className="mt-0.5 truncate text-[11px] text-slate-400">{agency.slug}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-xs font-semibold capitalize text-slate-700">{agency.plan_name ?? "No plan"}</div>
                      <div className="mt-0.5 text-[10px] capitalize text-slate-400">{agency.subscription_status?.replaceAll("_", " ") ?? "No subscription"}</div>
                    </td>
                    <td className="px-4 py-4 text-sm font-semibold tabular-nums text-slate-700">{agency.member_count}</td>
                    <td className="px-4 py-4">
                      <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${agency.is_active ? "border-emerald-100 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-100 text-slate-500"}`}>
                        {agency.is_active ? "Active" : "Suspended"}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right">
                      {confirmingId === agency.id ? (
                        <div className="inline-flex items-center gap-2">
                          <button
                            type="button"
                            disabled={actionId === agency.id}
                            onClick={() => void toggleAgency(agency)}
                            className="rounded-lg bg-slate-900 px-3 py-2 text-[10px] font-bold text-white disabled:opacity-50"
                          >
                            {actionId === agency.id ? "Saving…" : `Confirm ${agency.is_active ? "suspend" : "activate"}`}
                          </button>
                          <button type="button" onClick={() => setConfirmingId(null)} className="px-2 py-2 text-[10px] font-bold text-slate-400 hover:text-slate-700">
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmingId(agency.id)}
                          className={`rounded-lg border px-3 py-2 text-[10px] font-bold transition ${agency.is_active ? "border-red-100 text-red-600 hover:bg-red-50" : "border-emerald-100 text-emerald-700 hover:bg-emerald-50"}`}
                        >
                          {agency.is_active ? "Suspend" : "Activate"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3">
          <span className="text-[11px] text-slate-400">Showing {start}–{end} of {total}</span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={offset === 0 || loading}
              onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Previous page"
            >
              <ChevronLeft size={15} />
            </button>
            <button
              type="button"
              disabled={offset + PAGE_SIZE >= total || loading}
              onClick={() => setOffset((value) => value + PAGE_SIZE)}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Next page"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      </section>
    </>
  );
}
