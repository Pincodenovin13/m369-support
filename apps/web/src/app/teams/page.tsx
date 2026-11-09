"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { Loading, ErrorState, EmptyState, PageHeader } from "@/components/ui";
import { teamApi, workspaceApi, type TeamOut, type TeamMembershipOut, type WorkspaceOut } from "@/lib/api-client";

export default function TeamsPage() {
  const { user, agency, loading, error, refresh } = useAuth();
  const [teams, setTeams] = useState<TeamOut[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceOut[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState("");
  const [workspaceLoading, setWorkspaceLoading] = useState(true);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [membersByTeam, setMembersByTeam] = useState<Record<string, TeamMembershipOut[]>>({});
  const [memberErrors, setMemberErrors] = useState<Record<string, string>>({});
  const [showCreate, setShowCreate] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [creating, setCreating] = useState(false);

  const loadTeams = useCallback(async () => {
    if (!user) return;
    if (!selectedWorkspaceId) {
      setTeams([]);
      setMembersByTeam({});
      setMemberErrors({});
      setListLoading(false);
      return;
    }
    setListLoading(true);
    setListError(null);
    try {
      const res = await teamApi.list({ limit: 50, workspace_id: selectedWorkspaceId });
      const items = res.items;
      setTeams(items);
      const memberMap: Record<string, TeamMembershipOut[]> = {};
      const errorMap: Record<string, string> = {};
      await Promise.all(
        items.map(async (team) => {
          try {
            memberMap[team.id] = await teamApi.listMembers(team.id);
          } catch (err) {
            memberMap[team.id] = [];
            errorMap[team.id] =
              err instanceof Error ? err.message : "Unable to load team members";
          }
        })
      );
      setMembersByTeam(memberMap);
      setMemberErrors(errorMap);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Failed to load teams");
    } finally {
      setListLoading(false);
    }
  }, [user, selectedWorkspaceId]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setWorkspaceLoading(true);
    workspaceApi.list()
      .then((items) => {
        if (cancelled) return;
        setWorkspaces(items);
        setSelectedWorkspaceId((current) =>
          current && items.some((workspace) => workspace.id === current)
            ? current
            : items[0]?.id ?? ""
        );
      })
      .catch((err) => {
        if (!cancelled) {
          setListError(err instanceof Error ? err.message : "Failed to load workspaces");
        }
      })
      .finally(() => {
        if (!cancelled) setWorkspaceLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  useEffect(() => {
    void loadTeams();
  }, [loadTeams]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newTeamName.trim() || creating || !selectedWorkspaceId) return;
    setCreating(true);
    try {
      const created = await teamApi.create({ workspace_id: selectedWorkspaceId, name: newTeamName.trim() });
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
        description="Manage teams and their agency members."
        action={
          user.memberships.some(
            (membership) =>
              membership.agency_id === agency.id &&
              ["owner", "admin", "manager"].includes(membership.role)
          ) && workspaces.length > 0 ? (
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="px-3 py-1.5 bg-brand-500 text-white text-sm font-medium rounded-md hover:bg-brand-600"
            >
              {showCreate ? "Cancel" : "New team"}
            </button>
          ) : undefined
        }
      />
      {workspaces.length > 1 && (
        <div className="mb-4 max-w-sm">
          <label htmlFor="team-workspace" className="mb-1 block text-sm font-medium text-gray-700">
            Workspace
          </label>
          <select
            id="team-workspace"
            value={selectedWorkspaceId}
            onChange={(event) => setSelectedWorkspaceId(event.target.value)}
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900"
          >
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>{workspace.name}</option>
            ))}
          </select>
        </div>
      )}
      {showCreate && (
        <form onSubmit={handleCreate} className="mb-4 bg-white rounded-lg border border-gray-200 p-4 flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            placeholder="Team name"
            value={newTeamName}
            onChange={(e) => setNewTeamName(e.target.value)}
            className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <button
            type="submit"
            disabled={creating || !newTeamName.trim() || !selectedWorkspaceId}
            className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-md hover:bg-brand-600 disabled:opacity-50"
          >
            {creating ? "Creating..." : "Create"}
          </button>
        </form>
      )}
      <div className="bg-white rounded-lg border border-gray-200">
        {workspaceLoading || listLoading ? (
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
                      {memberErrors[t.id]
                        ? "Member list unavailable"
                        : `${membersByTeam[t.id]?.length || 0} member(s)`}
                    </div>
                    {memberErrors[t.id] && (
                      <div className="mt-1 text-xs text-red-600" role="alert">
                        {memberErrors[t.id]}
                      </div>
                    )}
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
