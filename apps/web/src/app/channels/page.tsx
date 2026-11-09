"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { Loading, ErrorState, EmptyState, PageHeader } from "@/components/ui";
import { channelApi, type ChannelOut, type PaginatedResponse } from "@/lib/api-client";

const CHANNEL_TYPES: ChannelOut["type"][] = ["widget", "email", "whatsapp_cloud", "telegram", "instagram", "messenger"];

export default function ChannelsPage() {
  const { user, agency, loading, error, refresh } = useAuth();
  const [channels, setChannels] = useState<ChannelOut[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setListLoading(true);
    channelApi.list({ limit: 50 })
      .then((res: PaginatedResponse<ChannelOut>) => {
        setChannels(res.items);
        setListLoading(false);
      })
      .catch((err) => {
        setListError(err instanceof Error ? err.message : "Failed to load channels");
        setListLoading(false);
      });
  }, [user]);

  async function toggleEnabled(ch: ChannelOut) {
    try {
      const updated = await channelApi.update(ch.id, { is_enabled: !ch.is_enabled });
      setChannels((prev) => prev.map((c) => (c.id === ch.id ? updated : c)));
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Failed to update channel");
    }
  }

  async function handleDelete(ch: ChannelOut) {
    if (!confirm(`Delete channel "${ch.name}"? This cannot be undone.`)) return;
    try {
      await channelApi.delete(ch.id);
      setChannels((prev) => prev.filter((c) => c.id !== ch.id));
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Failed to delete channel");
    }
  }

  if (loading) return <Loading label="Loading session..." />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!user || !agency) return <Loading />;

  return (
    <DashboardShell user={user} agency={agency}>
      <PageHeader title="Channels" description="Communication channels configured for your workspace." />
      <div className="bg-white rounded-lg border border-gray-200">
        {listLoading ? (
          <Loading label="Loading channels..." />
        ) : listError ? (
          <ErrorState message={listError} />
        ) : channels.length === 0 ? (
          <EmptyState title="No channels" description="Channels will appear here once configured." />
        ) : (
          <ul className="divide-y divide-gray-200">
            {channels.map((ch) => (
              <li key={ch.id} className="px-4 py-3 flex items-center justify-between">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-gray-900">{ch.name}</div>
                  <div className="text-xs text-gray-500">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600 mr-2">
                      {ch.type}
                    </span>
                    {ch.public_id && <span>Public ID: {ch.public_id.slice(0, 8)}...</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-4">
                  <button
                    onClick={() => toggleEnabled(ch)}
                    className={`px-2 py-1 text-xs rounded-md font-medium ${
                      ch.is_enabled
                        ? "bg-green-100 text-green-800 hover:bg-green-200"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {ch.is_enabled ? "Enabled" : "Disabled"}
                  </button>
                  <button
                    onClick={() => handleDelete(ch)}
                    className="px-2 py-1 text-xs rounded-md font-medium bg-red-50 text-red-700 hover:bg-red-100"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="mt-4 text-xs text-gray-500">
        Available channel types: {CHANNEL_TYPES.join(", ")}
      </p>
    </DashboardShell>
  );
}
