"use client";

import { useCallback, useEffect, useState } from "react";
import { ClipboardList, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { PageHeader, Loading, ErrorState, EmptyState } from "@/components/ui";
import { superAdminApi, type SuperAdminAuditLogOut } from "@/lib/super-admin-api-client";

const PAGE_SIZE = 50;

export default function SuperAdminAuditLogsPage() {
  const [items, setItems] = useState<SuperAdminAuditLogOut[]>([]);
  const [total, setTotal] = useState(0);
  const [actionInput, setActionInput] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await superAdminApi.auditLogs.list({
        action: actionFilter || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setItems(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load audit events");
    } finally {
      setLoading(false);
    }
  }, [actionFilter, offset]);

  useEffect(() => {
    void load();
  }, [load]);

  function applyFilter(event: React.FormEvent) {
    event.preventDefault();
    setOffset(0);
    setActionFilter(actionInput.trim());
  }

  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + items.length, total);

  return (
    <>
      <PageHeader
        title="Audit log"
        description="A read-only record of privileged platform actions and security-relevant changes."
      />

      <form onSubmit={applyFilter} className="mb-5 flex flex-col gap-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row">
        <label className="relative block flex-1">
          <span className="sr-only">Filter by exact action name</span>
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={actionInput}
            onChange={(event) => setActionInput(event.target.value)}
            placeholder="Filter by exact action, e.g. payment.verify"
            className="min-h-10 w-full rounded-xl border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none focus:border-brand-400 focus:bg-white"
          />
        </label>
        <button type="submit" className="min-h-10 rounded-xl bg-slate-900 px-5 text-xs font-bold text-white hover:bg-slate-800">Apply filter</button>
        {actionFilter && (
          <button type="button" onClick={() => { setActionInput(""); setActionFilter(""); setOffset(0); }} className="min-h-10 rounded-xl border border-slate-200 px-4 text-xs font-bold text-slate-600 hover:bg-slate-50">
            Clear
          </button>
        )}
      </form>

      {error && <div className="mb-4"><ErrorState message={error} onRetry={load} /></div>}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="text-sm font-extrabold text-slate-900">Privileged activity</h2>
            <p className="mt-1 text-xs text-slate-500">{total.toLocaleString()} events</p>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-blue-700"><ClipboardList size={17} /></div>
        </div>

        {loading ? (
          <Loading label="Loading audit events..." />
        ) : items.length === 0 ? (
          <EmptyState title="No audit events found" description="No events match the current filter." />
        ) : (
          <div className="divide-y divide-slate-100">
            {items.map((item) => (
              <article key={item.id} className="px-5 py-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-md bg-slate-900 px-2 py-1 font-mono text-[9px] font-bold text-white">#{item.id}</span>
                      <span className="text-xs font-extrabold text-slate-800">{item.action}</span>
                    </div>
                    <div className="mt-2 text-[10px] text-slate-500">
                      {item.target_type ?? "Platform"}{item.target_id ? ` · ${item.target_id}` : ""}
                    </div>
                  </div>
                  <div className="shrink-0 text-left sm:text-right">
                    <div className="text-[10px] font-semibold text-slate-600">{new Date(item.created_at).toLocaleString()}</div>
                    <div className="mt-1 font-mono text-[10px] text-slate-400">{item.ip_address ?? "IP unavailable"}</div>
                  </div>
                </div>
                <details className="mt-3">
                  <summary className="cursor-pointer text-[10px] font-bold text-brand-700 hover:text-brand-800">View event metadata</summary>
                  <pre className="mt-2 max-h-64 overflow-auto rounded-xl border border-slate-100 bg-slate-50 p-3 text-[10px] leading-5 text-slate-600">{JSON.stringify(item.metadata_, null, 2)}</pre>
                </details>
              </article>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3">
          <span className="text-[11px] text-slate-400">Showing {start}–{end} of {total}</span>
          <div className="flex items-center gap-2">
            <button type="button" disabled={offset === 0 || loading} onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))} aria-label="Previous page" className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 disabled:opacity-40"><ChevronLeft size={15} /></button>
            <button type="button" disabled={offset + PAGE_SIZE >= total || loading} onClick={() => setOffset((value) => value + PAGE_SIZE)} aria-label="Next page" className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 disabled:opacity-40"><ChevronRight size={15} /></button>
          </div>
        </div>
      </section>
    </>
  );
}
