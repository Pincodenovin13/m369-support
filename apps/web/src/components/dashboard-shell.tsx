"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { authApi, ApiError, type UserWithMembershipsOut, type AgencyOut } from "@/lib/api-client";

interface DashboardShellProps {
  user: UserWithMembershipsOut;
  agency: AgencyOut;
  children: React.ReactNode;
}

const NAV_ITEMS: { href: string; label: string }[] = [
  { href: "/dashboard", label: "Overview" },
  { href: "/contacts", label: "Contacts" },
  { href: "/conversations", label: "Inbox" },
  { href: "/teams", label: "Teams" },
  { href: "/channels", label: "Channels" },
  { href: "/canned-responses", label: "Canned" },
  { href: "/kb", label: "Knowledge Base" },
];

export function DashboardShell({ user, agency, children }: DashboardShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [logoutLoading, setLogoutLoading] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  async function handleLogout() {
    if (logoutLoading) return;
    setLogoutLoading(true);
    setLogoutError(null);
    try {
      await authApi.logout();
      router.push("/login");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        router.replace("/login");
        router.refresh();
      } else {
        setLogoutError(
          err instanceof Error ? err.message : "Failed to sign out. Please check your connection."
        );
      }
    } finally {
      setLogoutLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-sm font-bold"
                style={{ backgroundColor: agency.brand_color || "#FF6B35" }}
              >
                M
              </div>
              <span className="font-semibold text-gray-900">{agency.name}</span>
              <button
                onClick={() => setMobileNavOpen(!mobileNavOpen)}
                className="md:hidden ml-2 p-1 text-gray-600 hover:text-gray-900"
                aria-label="Toggle navigation"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-sm text-gray-600 hidden sm:block">{user.email}</div>
              <button
                onClick={handleLogout}
                disabled={logoutLoading}
                className="text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {logoutLoading ? "Signing out..." : "Sign out"}
              </button>
            </div>
          </div>
          {logoutError && (
            <div className="px-4 pb-2 text-xs text-red-600">{logoutError}</div>
          )}
        </div>
      </header>

      <nav className="bg-white border-b border-gray-200 hidden md:block">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-1">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-3 text-sm font-medium border-b-2 ${
                    isActive
                      ? "border-brand-500 text-brand-600"
                      : "border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </nav>

      {mobileNavOpen && (
        <nav className="bg-white border-b border-gray-200 md:hidden">
          <div className="px-4 py-2 space-y-1">
            {NAV_ITEMS.map((item) => {
              const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileNavOpen(false)}
                  className={`block px-3 py-2 rounded-md text-sm font-medium ${
                    isActive ? "bg-brand-50 text-brand-700" : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>
      )}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>
    </div>
  );
}
