"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BookOpen,
  ChevronRight,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquareText,
  Radio,
  Users,
  UsersRound,
  X,
  Inbox,
} from "lucide-react";
import { authApi, ApiError, type UserWithMembershipsOut, type AgencyOut } from "@/lib/api-client";

interface DashboardShellProps {
  user: UserWithMembershipsOut;
  agency: AgencyOut;
  children: React.ReactNode;
}

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard, group: "Workspace" },
  { href: "/conversations", label: "Inbox", icon: Inbox, group: "Workspace" },
  { href: "/contacts", label: "Contacts", icon: Users, group: "Workspace" },
  { href: "/teams", label: "Teams", icon: UsersRound, group: "Workspace" },
  { href: "/channels", label: "Channels", icon: Radio, group: "Configuration" },
  { href: "/canned-responses", label: "Canned responses", icon: MessageSquareText, group: "Configuration" },
  { href: "/kb", label: "Knowledge base", icon: BookOpen, group: "Configuration" },
];

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "M";
}

export function DashboardShell({ user, agency, children }: DashboardShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [logoutLoading, setLogoutLoading] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const activeItem = NAV_ITEMS.find(
    (item) => pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href)),
  );

  async function handleLogout() {
    if (logoutLoading) return;
    setLogoutLoading(true);
    setLogoutError(null);
    try {
      await authApi.logout();
      router.replace("/login");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        router.replace("/login");
        router.refresh();
      } else {
        setLogoutError(
          err instanceof Error ? err.message : "Unable to sign out. Check your connection and try again.",
        );
      }
    } finally {
      setLogoutLoading(false);
    }
  }

  function Navigation({ mobile = false }: { mobile?: boolean }) {
    return (
      <nav aria-label="Main navigation" className="flex-1 space-y-7 overflow-y-auto px-3 py-6">
        {(["Workspace", "Configuration"] as const).map((group) => (
          <div key={group}>
            <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
              {group}
            </p>
            <div className="space-y-1">
              {NAV_ITEMS.filter((item) => item.group === group).map((item) => {
                const Icon = item.icon;
                const active =
                  pathname === item.href ||
                  (item.href !== "/dashboard" && pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => mobile && setMobileNavOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className={`group flex min-h-11 items-center gap-3 rounded-xl px-3 text-[13px] font-semibold transition-colors ${
                      active
                        ? "bg-brand-500 text-white shadow-sm shadow-orange-950/20"
                        : "text-slate-300 hover:bg-white/8 hover:text-white"
                    }`}
                  >
                    <Icon size={17} strokeWidth={active ? 2.3 : 1.8} />
                    <span className="flex-1">{item.label}</span>
                    {active && <ChevronRight size={15} className="opacity-80" />}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    );
  }

  function Sidebar({ mobile = false }: { mobile?: boolean }) {
    return (
      <aside className="flex h-full w-64 flex-col border-r border-white/5 bg-[#111c2e] text-white">
        <div className="flex h-[76px] items-center gap-3 border-b border-white/10 px-5">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-xl text-base font-black text-white shadow-lg"
            style={{ backgroundColor: agency.brand_color || "#f26a3d" }}
          >
            M
          </div>
          <div className="min-w-0">
            <div className="text-[15px] font-extrabold tracking-tight">M369 <span className="font-medium text-slate-300">Support</span></div>
            <div className="mt-0.5 truncate text-[10px] font-medium uppercase tracking-[0.16em] text-slate-500">Agency workspace</div>
          </div>
          {mobile && (
            <button
              type="button"
              onClick={() => setMobileNavOpen(false)}
              aria-label="Close navigation"
              className="ml-auto rounded-lg p-2 text-slate-300 hover:bg-white/10 hover:text-white"
            >
              <X size={18} />
            </button>
          )}
        </div>

        <div className="mx-3 mt-5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Current agency</div>
          <div className="truncate text-sm font-semibold text-slate-100">{agency.name}</div>
          <div className="mt-1 truncate text-[11px] text-slate-500">{agency.slug}</div>
        </div>

        <Navigation mobile={mobile} />

        <div className="border-t border-white/10 p-3">
          <div className="flex items-center gap-3 rounded-xl px-2 py-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-white">
              {initials(user.name)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-semibold text-slate-100">{user.name}</div>
              <div className="truncate text-[10px] text-slate-500">{user.email}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            disabled={logoutLoading}
            className="flex min-h-10 w-full items-center gap-3 rounded-xl px-3 text-xs font-semibold text-slate-400 transition-colors hover:bg-white/8 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            <LogOut size={16} />
            {logoutLoading ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </aside>
    );
  }

  return (
    <div className="min-h-screen bg-[#f4f6fa] text-slate-900">
      <div className="hidden lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:block">
        <Sidebar />
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation overlay"
            onClick={() => setMobileNavOpen(false)}
            className="absolute inset-0 bg-slate-950/60 backdrop-blur-[2px]"
          />
          <div className="relative h-full w-72 max-w-[85vw] shadow-2xl">
            <Sidebar mobile />
          </div>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/95 backdrop-blur-xl">
          <div className="flex h-[76px] items-center justify-between px-4 sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation"
                className="rounded-xl border border-slate-200 p-2 text-slate-600 hover:bg-slate-50 lg:hidden"
              >
                <Menu size={19} />
              </button>
              <div className="min-w-0">
                <div className="text-[10px] font-bold uppercase tracking-[0.17em] text-slate-400">M369 workspace</div>
                <div className="mt-0.5 truncate text-sm font-bold text-slate-800">
                  {activeItem?.label ?? "Workspace"}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden text-right sm:block">
                <div className="text-xs font-semibold text-slate-700">{user.name}</div>
                <div className="text-[10px] text-slate-400">{user.memberships.find((m) => m.agency_id === agency.id)?.role ?? "member"}</div>
              </div>
              <div className="flex h-9 w-9 items-center justify-center rounded-full border border-orange-100 bg-orange-50 text-xs font-bold text-brand-700">
                {initials(user.name)}
              </div>
            </div>
          </div>
        </header>

        {logoutError && (
          <div role="alert" className="mx-4 mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs font-medium text-red-700 sm:mx-6 lg:mx-8">
            {logoutError}
          </div>
        )}

        <main className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-9">
          {children}
        </main>
      </div>
    </div>
  );
}
