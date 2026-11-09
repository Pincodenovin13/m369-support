"use client";

import { useAuth } from "@/hooks/use-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { Loading, ErrorState, PageHeader } from "@/components/ui";
import { workspaceApi } from "@/lib/api-client";
import { useEffect, useState } from "react";
import type { WorkspaceOut } from "@/lib/api-client";

export default function DashboardPage() {
  const { user, agency, loading, error, refresh } = useAuth();
  const [workspaces, setWorkspaces] = useState<WorkspaceOut[]>([]);
  const [wsLoading, setWsLoading] = useState(true);
  const [wsError, setWsError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setWsLoading(true);
    workspaceApi.list()
      .then((ws) => {
        setWorkspaces(ws);
        setWsLoading(false);
      })
      .catch((err) => {
        setWsError(err instanceof Error ? err.message : "Failed to load workspaces");
        setWsLoading(false);
      });
  }, [user]);

  if (loading) return <Loading label="Loading dashboard..." />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!user || !agency) return <Loading />;

  return (
    <DashboardShell user={user} agency={agency}>
      <PageHeader
        title={`Welcome, ${user.name}`}
        description={`You are signed in to ${agency.name} (${agency.slug}).`}
      />

      <div className="mb-7 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">Your role</div>
          <div className="mt-3 text-xl font-extrabold capitalize tracking-tight text-slate-900">
            {user.memberships.find((m) => m.agency_id === agency.id)?.role || "agent"}
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">Workspaces</div>
          <div className="mt-1 text-lg font-semibold text-gray-900">{workspaces.length}</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">Agency status</div>
          <div className="mt-1 text-lg font-semibold text-gray-900">
            {agency.is_active ? "Active" : "Inactive"}
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-5 py-4">
          <h2 className="text-sm font-extrabold text-slate-900">Your workspaces</h2>
          <p className="mt-1 text-xs text-slate-500">Spaces available inside this agency</p>
        </div>
        {wsLoading ? (
          <Loading label="Loading workspaces..." />
        ) : wsError ? (
          <ErrorState message={wsError} />
        ) : workspaces.length === 0 ? (
          <div className="px-5 py-8 text-sm text-slate-500">No workspaces yet.</div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {workspaces.map((ws) => (
              <li key={ws.id} className="flex items-center justify-between px-5 py-4 transition-colors hover:bg-slate-50/80">
                <div>
                  <div className="text-sm font-bold text-slate-800">{ws.name}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {ws.slug} · {ws.timezone} · {ws.is_active ? "Active" : "Inactive"}
                  </div>
                </div>
                <span className="text-[11px] font-medium text-slate-400">
                  Created {new Date(ws.created_at).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </DashboardShell>
  );
}
