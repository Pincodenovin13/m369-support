"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { Loading, ErrorState, EmptyState, PageHeader } from "@/components/ui";
import { cannedResponseApi, type CannedResponseOut, type PaginatedResponse } from "@/lib/api-client";

export default function CannedResponsesPage() {
  const { user, agency, loading, error, refresh } = useAuth();
  const [responses, setResponses] = useState<CannedResponseOut[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setListLoading(true);
    cannedResponseApi.list({ limit: 50 })
      .then((res: PaginatedResponse<CannedResponseOut>) => {
        setResponses(res.items);
        setListLoading(false);
      })
      .catch((err) => {
        setListError(err instanceof Error ? err.message : "Failed to load canned responses");
        setListLoading(false);
      });
  }, [user]);

  if (loading) return <Loading label="Loading session..." />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!user || !agency) return <Loading />;

  return (
    <DashboardShell user={user} agency={agency}>
      <PageHeader title="Canned Responses" description="Pre-written reply templates for common questions." />
      <div className="bg-white rounded-lg border border-gray-200">
        {listLoading ? (
          <Loading label="Loading canned responses..." />
        ) : listError ? (
          <ErrorState message={listError} />
        ) : responses.length === 0 ? (
          <EmptyState title="No canned responses" description="Create templates to speed up replies." />
        ) : (
          <ul className="divide-y divide-gray-200">
            {responses.map((cr) => (
              <li key={cr.id} className="px-4 py-3">
                <button
                  onClick={() => setExpandedId(expandedId === cr.id ? null : cr.id)}
                  className="w-full text-left flex items-center justify-between"
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-gray-900 truncate">{cr.title}</div>
                    <div className="text-xs text-gray-500 truncate">
                      {cr.body.slice(0, 80)}
                      {cr.body.length > 80 ? "..." : ""}
                    </div>
                  </div>
                  <span className="text-xs text-gray-400 ml-4">
                    Updated {new Date(cr.updated_at).toLocaleDateString()}
                  </span>
                </button>
                {expandedId === cr.id && (
                  <div className="mt-3 px-3 py-2 bg-gray-50 rounded-md text-sm text-gray-700 whitespace-pre-wrap">
                    {cr.body}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </DashboardShell>
  );
}
