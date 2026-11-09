"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Building2,
  CheckCircle2,
  Clock3,
  Inbox,
  Layers3,
  ShieldCheck,
  Users,
  UsersRound,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { ErrorState, Loading, PageHeader } from "@/components/ui";
import { workspaceApi, type WorkspaceOut } from "@/lib/api-client";

const QUICK_LINKS = [
  {
    href: "/conversations",
    title: "Open inbox",
    description: "Review and respond to customer conversations.",
    icon: Inbox,
  },
  {
    href: "/contacts",
    title: "Manage contacts",
    description: "Find the people connected to your workspace.",
    icon: Users,
  },
  {
    href: "/teams",
    title: "Coordinate your team",
    description: "Review teams and their members.",
    icon: UsersRound,
  },
  {
    href: "/kb",
    title: "Knowledge base",
    description: "Maintain helpful articles for your customers.",
    icon: BookOpen,
  },
];

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export default function DashboardPage() {
  const { user, agency, loading, error, refresh } = useAuth();
  const [workspaces, setWorkspaces] = useState<WorkspaceOut[]>([]);
  const [wsLoading, setWsLoading] = useState(true);
  const [wsError, setWsError] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !agency) {
      setWorkspaces([]);
      setWsLoading(false);
      setWsError(null);
      return;
    }

    let active = true;
    setWsLoading(true);
    setWsError(null);

    workspaceApi
      .list()
      .then((items) => {
        if (!active) return;
        setWorkspaces(items);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setWsError(
          err instanceof Error
            ? err.message
            : "We could not load workspaces. Please try again.",
        );
      })
      .finally(() => {
        if (active) setWsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [user?.id, agency?.id]);

  if (loading) return <Loading label="Loading your workspace..." />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!user || !agency) return <Loading label="Preparing your workspace..." />;

  const role =
    user.memberships.find((membership) => membership.agency_id === agency.id)?.role ??
    "member";
  const activeWorkspaces = workspaces.filter((workspace) => workspace.is_active).length;

  return (
    <DashboardShell user={user} agency={agency}>
      <div className="space-y-8">
        <section className="relative overflow-hidden rounded-[28px] bg-[#142238] px-6 py-7 text-white shadow-[0_18px_45px_-28px_rgba(15,23,42,0.55)] sm:px-8 sm:py-9">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-16 -top-24 h-72 w-72 rounded-full opacity-20 blur-3xl"
            style={{ backgroundColor: agency.brand_color || "#f26a3d" }}
          />
          <div className="relative flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
            <div className="max-w-2xl">
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.07] px-3 py-1.5 text-[11px] font-semibold text-slate-200">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                Agency workspace
              </div>
              <p className="text-sm font-medium text-slate-300">Good to see you, {user.name}</p>
              <h1 className="mt-2 text-3xl font-extrabold tracking-tight sm:text-4xl">
                Your support hub.
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-slate-300">
                A clear view of {agency.name}, your workspaces, and the tools your team uses
                to support customers.
              </p>
            </div>
            <Link
              href="/conversations"
              className="inline-flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-xl px-5 text-sm font-bold text-white shadow-lg transition hover:-translate-y-0.5 hover:brightness-105 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
              style={{ backgroundColor: agency.brand_color || "#f26a3d" }}
            >
              Go to inbox
              <ArrowUpRight size={17} />
            </Link>
          </div>
        </section>

        <section aria-label="Agency summary" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm shadow-slate-200/40">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500">Your access</p>
                <p className="mt-3 text-2xl font-extrabold capitalize tracking-tight text-slate-900">
                  {role.replaceAll("_", " ")}
                </p>
              </div>
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                <ShieldCheck size={21} />
              </span>
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-500">
              Your current role in {agency.name}.
            </p>
          </article>

          <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm shadow-slate-200/40">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500">Workspaces</p>
                {wsLoading ? (
                  <div className="mt-3 h-8 w-14 animate-pulse rounded-lg bg-slate-100" />
                ) : (
                  <p className="mt-3 text-3xl font-extrabold tracking-tight text-slate-900 tabular-nums">
                    {workspaces.length}
                  </p>
                )}
              </div>
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-orange-50 text-brand-600">
                <Layers3 size={21} />
              </span>
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-500">
              {wsLoading ? "Loading workspace data..." : `${activeWorkspaces} active workspace${activeWorkspaces === 1 ? "" : "s"}`}
            </p>
          </article>

          <article className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm shadow-slate-200/40 sm:col-span-2 xl:col-span-1">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500">Agency status</p>
                <p className="mt-3 text-2xl font-extrabold tracking-tight text-slate-900">
                  {agency.is_active ? "Active" : "Inactive"}
                </p>
              </div>
              <span className={`flex h-11 w-11 items-center justify-center rounded-2xl ${agency.is_active ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-500"}`}>
                <Building2 size={21} />
              </span>
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-500">
              Agency account · {agency.slug}
            </p>
          </article>
        </section>

        <section>
          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-lg font-extrabold tracking-tight text-slate-900">Your workspace tools</h2>
              <p className="mt-1 text-sm text-slate-500">Jump back into the work that matters.</p>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {QUICK_LINKS.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="group flex min-h-36 flex-col rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm shadow-slate-200/30 transition duration-200 hover:-translate-y-1 hover:border-slate-300 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500"
                >
                  <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-slate-50 text-slate-600 transition group-hover:bg-orange-50 group-hover:text-brand-600">
                    <Icon size={19} />
                  </span>
                  <span className="flex items-center justify-between gap-2 text-sm font-bold text-slate-800">
                    {item.title}
                    <ArrowRight size={15} className="text-slate-300 transition group-hover:translate-x-1 group-hover:text-brand-600" />
                  </span>
                  <span className="mt-1.5 text-xs leading-5 text-slate-500">{item.description}</span>
                </Link>
              );
            })}
          </div>
        </section>

        <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm shadow-slate-200/30">
          <div className="flex flex-col gap-2 border-b border-slate-100 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div>
              <h2 className="text-base font-extrabold text-slate-900">Workspace directory</h2>
              <p className="mt-1 text-xs text-slate-500">Workspaces available inside this agency.</p>
            </div>
            <div className="inline-flex items-center gap-2 text-xs font-medium text-slate-400">
              <Clock3 size={14} />
              Updated from your agency account
            </div>
          </div>

          {wsLoading ? (
            <div className="space-y-3 p-5">
              <div className="h-16 animate-pulse rounded-xl bg-slate-50" />
              <div className="h-16 animate-pulse rounded-xl bg-slate-50" />
            </div>
          ) : wsError ? (
            <div className="p-4 sm:p-6">
              <ErrorState message={wsError} />
            </div>
          ) : workspaces.length === 0 ? (
            <div className="flex flex-col items-center px-5 py-12 text-center">
              <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-50 text-slate-400">
                <Layers3 size={22} />
              </span>
              <h3 className="text-sm font-bold text-slate-800">No workspaces yet</h3>
              <p className="mt-1 max-w-md text-xs leading-5 text-slate-500">
                Your agency does not have a workspace yet. An agency owner or administrator can create one.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {workspaces.map((workspace) => (
                <li key={workspace.id} className="flex flex-col gap-3 px-5 py-4 transition hover:bg-slate-50/70 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-slate-500">
                      <Building2 size={18} />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-slate-800">{workspace.name}</p>
                      <p className="mt-1 truncate text-xs text-slate-500">
                        {workspace.slug} <span className="px-1 text-slate-300">·</span> {workspace.timezone}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between gap-4 pl-[52px] sm:pl-0">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold ${workspace.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                      {workspace.is_active ? <CheckCircle2 size={12} /> : <Clock3 size={12} />}
                      {workspace.is_active ? "Active" : "Inactive"}
                    </span>
                    <span className="text-[11px] text-slate-400">{formatDate(workspace.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </DashboardShell>
  );
}
