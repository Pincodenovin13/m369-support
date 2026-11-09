"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/hooks/use-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { Loading, ErrorState, EmptyState, PageHeader, Badge } from "@/components/ui";
import { conversationApi, type ConversationOut, type PaginatedResponse } from "@/lib/api-client";

const STATUS_FILTERS: { label: string; value?: string }[] = [
  { label: "All" },
  { label: "Open", value: "open" },
  { label: "Pending", value: "pending" },
  { label: "Resolved", value: "resolved" },
  { label: "Closed", value: "closed" },
];

export default function ConversationsPage() {
  const { user, agency, loading, error, refresh } = useAuth();
  const [conversations, setConversations] = useState<ConversationOut[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!user) return;
    setListLoading(true);
    conversationApi.list({ status: statusFilter, limit: 50 })
      .then((res: PaginatedResponse<ConversationOut>) => {
        setConversations(res.items);
        setListLoading(false);
      })
      .catch((err) => {
        setListError(err instanceof Error ? err.message : "Failed to load conversations");
        setListLoading(false);
      });
  }, [user, statusFilter]);

  if (loading) return <Loading label="Loading session..." />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!user || !agency) return <Loading />;

  return (
    <DashboardShell user={user} agency={agency}>
      <PageHeader title="Inbox" description="Customer conversations across your workspace." />
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200 flex flex-wrap gap-2">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.label}
              onClick={() => setStatusFilter(f.value)}
              className={`px-3 py-1 text-xs rounded-md font-medium ${
                statusFilter === f.value
                  ? "bg-brand-500 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        {listLoading ? (
          <Loading label="Loading conversations..." />
        ) : listError ? (
          <ErrorState message={listError} />
        ) : conversations.length === 0 ? (
          <EmptyState
            title="No conversations"
            description={statusFilter ? `No ${statusFilter} conversations.` : "Conversations will appear here once started."}
          />
        ) : (
          <ul className="divide-y divide-gray-200">
            {conversations.map((c) => (
              <li key={c.id}>
                <Link href={`/conversations/${c.id}`} className="block px-4 py-3 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-gray-900 truncate">
                        {c.subject || "(no subject)"}
                      </div>
                      <div className="text-xs text-gray-500 truncate">
                        Conversation {c.id.slice(0, 8)}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <Badge status={c.status} />
                      <span className="text-xs text-gray-400">
                        {new Date(c.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </DashboardShell>
  );
}
