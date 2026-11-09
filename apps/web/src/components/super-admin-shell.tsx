"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Building2,
  CreditCard,
  LayoutDashboard,
  LogOut,
  ShieldCheck,
  Tags,
} from "lucide-react";
import {
  superAdminAuthApi,
  SuperAdminApiError,
  type SuperAdminOut,
} from "@/lib/super-admin-api-client";

const NAV = [
  { href: "/super-admin", label: "Overview", icon: LayoutDashboard },
  { href: "/super-admin/agencies", label: "Agencies", icon: Building2 },
  { href: "/super-admin/plans", label: "Plans", icon: Tags },
  { href: "/super-admin/subscriptions", label: "Subscriptions", icon: CreditCard },
  { href: "/super-admin/payments", label: "Payments", icon: ShieldCheck },
];

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("") || "SA";
}

export function SuperAdminShell({
  admin,
  children,
}: {
  admin: SuperAdminOut;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [logoutLoading, setLogoutLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function logout() {
    if (logoutLoading) return;
    setLogoutLoading(true);
    setError(null);
    try {
      await superAdminAuthApi.logout();
      router.replace("/super-admin/login");
      router.refresh();
    } catch (err) {
      if (err instanceof SuperAdminApiError && err.status === 401) {
        router.replace("/super-admin/login");
        router.refresh();
      } else {
        setError(err instanceof Error ? err.message : "Unable to sign out");
      }
    } finally {
      setLogoutLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f4f6fa] text-slate-900">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-white/5 bg-[#101a2b] text-white lg:flex">
        <div className="flex h-[76px] items-center gap-3 border-b border-white/10 px-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 text-base font-black shadow-lg shadow-orange-950/20">
            M
          </div>
          <div>
            <div className="text-sm font-extrabold">M369 <span className="font-medium text-slate-300">Control</span></div>
            <div className="mt-0.5 text-[9px] font-bold uppercase tracking-[0.18em] text-slate-500">Platform administration</div>
          </div>
        </div>
        <div className="mx-3 mt-5 rounded-xl border border-amber-400/15 bg-amber-400/[0.06] px-3 py-3">
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-amber-300">
            <ShieldCheck size={13} />
            Privileged area
          </div>
          <p className="mt-1.5 text-[10px] leading-5 text-slate-400">Cross-agency controls. Actions are audited.</p>
        </div>
        <nav aria-label="Super Admin navigation" className="flex-1 space-y-1 px-3 py-6">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || (item.href !== "/super-admin" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-11 items-center gap-3 rounded-xl px-3 text-[13px] font-semibold transition-colors ${
                  active ? "bg-brand-500 text-white shadow-sm" : "text-slate-300 hover:bg-white/8 hover:text-white"
                }`}
              >
                <Icon size={17} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-white/10 p-3">
          <div className="flex items-center gap-3 rounded-xl px-2 py-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-700 text-xs font-bold">{initials(admin.name)}</div>
            <div className="min-w-0">
              <div className="truncate text-xs font-semibold">{admin.name}</div>
              <div className="truncate text-[10px] text-slate-500">{admin.email}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={logout}
            disabled={logoutLoading}
            className="flex min-h-10 w-full items-center gap-3 rounded-xl px-3 text-xs font-semibold text-slate-400 transition hover:bg-white/8 hover:text-white disabled:opacity-50"
          >
            <LogOut size={16} />
            {logoutLoading ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/95 backdrop-blur-xl">
          <div className="flex h-[76px] items-center justify-between px-4 sm:px-6 lg:px-8">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-[0.17em] text-slate-400">M369 Control</div>
              <div className="mt-0.5 text-sm font-bold text-slate-800">
                {NAV.find((item) => pathname === item.href || (item.href !== "/super-admin" && pathname.startsWith(item.href)))?.label ?? "Platform"}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden text-right sm:block">
                <div className="text-xs font-semibold text-slate-700">{admin.name}</div>
                <div className="text-[10px] text-slate-400">Super Administrator</div>
              </div>
              <div className="flex h-9 w-9 items-center justify-center rounded-full border border-orange-100 bg-orange-50 text-xs font-bold text-brand-700">
                {initials(admin.name)}
              </div>
              <button
                type="button"
                onClick={logout}
                disabled={logoutLoading}
                className="rounded-lg border border-slate-200 px-2.5 py-2 text-[10px] font-bold text-slate-500 hover:bg-slate-50 disabled:opacity-50 lg:hidden"
              >
                {logoutLoading ? "…" : "Sign out"}
              </button>
            </div>
          </div>
        </header>
        <nav aria-label="Super Admin mobile navigation" className="flex gap-1 overflow-x-auto border-b border-slate-200 bg-white px-3 py-2 lg:hidden">
          {NAV.map((item) => {
            const active = pathname === item.href || (item.href !== "/super-admin" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`shrink-0 rounded-lg px-3 py-2 text-[10px] font-bold transition ${active ? "bg-brand-500 text-white" : "text-slate-500 hover:bg-slate-50"}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        {error && <div role="alert" className="mx-4 mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700 sm:mx-6 lg:mx-8">{error}</div>}
        <main className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-9">
          {children}
        </main>
      </div>
    </div>
  );
}
