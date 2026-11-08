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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-sm text-gray-500">Your role</div>
          <div className="mt-1 text-lg font-semibold text-gray-900">
            {user.memberships.find((m) => m.agency_id === agency.id)?.role || "agent"}
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-sm text-gray-500">Workspaces</div>
          <div className="mt-1 text-lg font-semibold text-gray-900">{workspaces.length}</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-sm text-gray-500">Agency status</div>
          <div className="mt-1 text-lg font-semibold text-gray-900">
            {agency.is_active ? "Active" : "Inactive"}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200">
          <h2 className="text-sm font-semibold text-gray-900">Workspaces</h2>
        </div>
        {wsLoading ? (
          <Loading label="Loading workspaces..." />
        ) : wsError ? (
          <ErrorState message={wsError} />
        ) : workspaces.length === 0 ? (
          <div className="px-4 py-6 text-sm text-gray-500">No workspaces yet.</div>
        ) : (
          <ul className="divide-y divide-gray-200">
            {workspaces.map((ws) => (
              <li key={ws.id} className="px-4 py-3 flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium text-gray-900">{ws.name}</div>
                  <div className="text-xs text-gray-500">
                    {ws.slug} · {ws.timezone} · {ws.is_active ? "Active" : "Inactive"}
                  </div>
                </div>
                <span className="text-xs text-gray-400">
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
