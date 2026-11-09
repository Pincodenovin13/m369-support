"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { Loading, ErrorState, EmptyState, PageHeader } from "@/components/ui";
import { contactApi, type ContactOut, type PaginatedResponse } from "@/lib/api-client";

export default function ContactsPage() {
  const { user, agency, loading, error, refresh } = useAuth();
  const [contacts, setContacts] = useState<ContactOut[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!user) return;
    setListLoading(true);
    contactApi.list({ search: search || undefined, limit: 50 })
      .then((res: PaginatedResponse<ContactOut>) => {
        setContacts(res.items);
        setListLoading(false);
      })
      .catch((err) => {
        setListError(err instanceof Error ? err.message : "Failed to load contacts");
        setListLoading(false);
      });
  }, [user, search]);

  if (loading) return <Loading label="Loading session..." />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!user || !agency) return <Loading />;

  return (
    <DashboardShell user={user} agency={agency}>
      <PageHeader
        title="Contacts"
        description="Customer contacts in your workspace."
      />
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="px-4 py-3 border-b border-gray-200">
          <input
            type="text"
            placeholder="Search contacts by name, email, or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
        {listLoading ? (
          <Loading label="Loading contacts..." />
        ) : listError ? (
          <ErrorState message={listError} />
        ) : contacts.length === 0 ? (
          <EmptyState
            title="No contacts found"
            description={search ? "Try a different search term." : "Contacts will appear here once created."}
          />
        ) : (
          <ul className="divide-y divide-gray-200">
            {contacts.map((c) => (
              <li key={c.id} className="px-4 py-3 flex items-center justify-between">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-gray-900 truncate">{c.name || "(unnamed)"}</div>
                  <div className="text-xs text-gray-500 truncate">
                    {[c.email, c.phone].filter(Boolean).join(" · ") || "No contact info"}
                  </div>
                </div>
                <span className="text-xs text-gray-400 ml-4">
                  Created {new Date(c.created_at).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </DashboardShell>
  );
}
