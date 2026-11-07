"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, agencyApi, workspaceApi, ApiError } from "@/lib/api-client";
import type { UserWithMembershipsOut, AgencyOut, WorkspaceOut } from "@/lib/api-client";
import { DashboardShell } from "@/components/dashboard-shell";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserWithMembershipsOut | null>(null);
  const [agency, setAgency] = useState<AgencyOut | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authError, setAuthError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const me = await authApi.me();
        if (cancelled) return;
        setUser(me);

        const ag = await agencyApi.current();
        if (cancelled) return;
        setAgency(ag);

        const ws = await workspaceApi.list();
        if (cancelled) return;
        setWorkspaces(ws);
      } catch (err) {
        if (cancelled) return;

        if (err instanceof ApiError && err.status === 401) {
          // Auth error — redirect to login
          setAuthError(true);
          router.replace("/login");
        } else if (err instanceof ApiError && err.status === 403) {
          // Authenticated but not authorized — show error, don't redirect
          setError("You do not have permission to access this dashboard.");
        } else {
          // Network or server error — show error, don't redirect
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load dashboard. Please check your connection."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (authError) {
    return null; // redirecting to login
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md rounded-lg bg-red-50 border border-red-200 p-6 text-center">
          <p className="text-red-700 font-medium mb-2">Something went wrong</p>
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!user || !agency) {
    return null; // should not reach here — authError would have been set
  }

  return (
    <DashboardShell user={user} agency={agency}>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-600 mt-1">
            Welcome back, {user.name}. You are signed in to <strong>{agency.name}</strong>.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <div className="text-sm font-medium text-gray-500">Workspaces</div>
            <div className="mt-2 text-3xl font-bold text-gray-900">{workspaces.length}</div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <div className="text-sm font-medium text-gray-500">Your role</div>
            <div className="mt-2 text-lg font-bold text-gray-900 capitalize">
              {user.memberships.find(
                (membership) => membership.agency_id === agency.id
              )?.role || "—"}
            </div>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <div className="text-sm font-medium text-gray-500">Agency status</div>
            <div className="mt-2 text-lg font-bold text-gray-900">
              {agency.is_active ? "Active" : "Inactive"}
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-5 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Workspaces</h2>
          </div>
          {workspaces.length === 0 ? (
            <div className="px-5 py-8 text-center text-gray-500">
              No workspaces yet. Create your first workspace to get started.
            </div>
          ) : (
            <ul className="divide-y divide-gray-200">
              {workspaces.map((ws) => (
                <li key={ws.id} className="px-5 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium text-gray-900">{ws.name}</div>
                      <div className="text-sm text-gray-500">{ws.slug} · {ws.timezone}</div>
                    </div>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      ws.is_active
                        ? "bg-green-50 text-green-700"
                        : "bg-gray-100 text-gray-600"
                    }`}>
                      {ws.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-600">
          <strong className="text-gray-900">Phase 1 — Foundation only.</strong>{" "}
          Conversations, contacts, knowledge base, channels, and reporting
          are not yet implemented. This dashboard shows the authenticated
          agency context and workspace list.
        </div>
      </div>
    </DashboardShell>
  );
}
