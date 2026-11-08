"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { Loading, ErrorState, EmptyState, PageHeader } from "@/components/ui";
import { teamApi, ApiError, type TeamOut, type TeamMembershipOut, type PaginatedResponse } from "@/lib/api-client";

export default function TeamsPage() {
  const { user, agency, loading, error, refresh } = useAuth();
  const [teams, setTeams] = useState<TeamOut[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [membersByTeam, setMembersByTeam] = useState<Record<string, TeamMembershipOut[]>>({});
  const [showCreate, setShowCreate] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [creating, setCreating] = useState(false);

  async function loadTeams() {
    if (!user) return;
    setListLoading(true);
    try {
      const res = await teamApi.list({ limit: 50 });
      const items = (res as PaginatedResponse<TeamOut>).items;
      setTeams(items);
      const memberMap: Record<string, TeamMembershipOut[]> = {};
      await Promise.all(
        items.map(async (t) => {
          try {
            memberMap[t.id] = await teamApi.listMembers(t.id);
          } catch {
            memberMap[t.id] = [];
          }
        })
      );
      setMembersByTeam(memberMap);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Failed to load teams");
    } finally {
      setListLoading(false);
    }
  }

  useEffect(() => {
    void loadTeams();
  }, [user]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newTeamName.trim() || creating || !teams[0]?.workspace_id) return;
    setCreating(true);
    try {
      const created = await teamApi.create({ workspace_id: teams[0].workspace_id, name: newTeamName.trim() });
      setTeams((prev) => [...prev, created]);
      setMembersByTeam((prev) => ({ ...prev, [created.id]: [] }));
      setNewTeamName("");
      setShowCreate(false);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Failed to create team");
    } finally {
      setCreating(false);
    }
  }

  if (loading) return <Loading label="Loading session..." />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!user || !agency) return <Loading />;

  return (
    <DashboardShell user={user} agency={agency}>
      <PageHeader
        title="Teams"
        description="Teams in your workspace."
        action={
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="px-3 py-1.5 bg-brand-500 text-white text-sm font-medium rounded-md hover:bg-brand-600"
          >
            {showCreate ? "Cancel" : "New team"}
          </button>
        }
      />
      {showCreate && (
        <form onSubmit={handleCreate} className="mb-4 bg-white rounded-lg border border-gray-200 p-4 flex gap-2">
          <input
            type="text"
            placeholder="Team name"
            value={newTeamName}
            onChange={(e) => setNewTeamName(e.target.value)}
            className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <button
            type="submit"
            disabled={creating || !newTeamName.trim()}
            className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-md hover:bg-brand-600 disabled:opacity-50"
          >
            {creating ? "Creating..." : "Create"}
          </button>
        </form>
      )}
      <div className="bg-white rounded-lg border border-gray-200">
        {listLoading ? (
          <Loading label="Loading teams..." />
        ) : listError ? (
          <ErrorState message={listError} />
        ) : teams.length === 0 ? (
          <EmptyState title="No teams" description="Create a team to organize your agents." />
        ) : (
          <ul className="divide-y divide-gray-200">
            {teams.map((t) => (
              <li key={t.id} className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-gray-900">
                      {t.name}
                      {t.is_default && (
                        <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                          Default
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500">
                      {membersByTeam[t.id]?.length || 0} member(s)
                    </div>
                  </div>
                  <span className="text-xs text-gray-400">
                    Created {new Date(t.created_at).toLocaleDateString()}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </DashboardShell>
  );
}
