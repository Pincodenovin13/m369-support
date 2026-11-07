"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, ApiError, type UserWithMembershipsOut, type AgencyOut } from "@/lib/api-client";

interface DashboardShellProps {
  user: UserWithMembershipsOut;
  agency: AgencyOut;
  children: React.ReactNode;
}

export function DashboardShell({ user, agency, children }: DashboardShellProps) {
  const router = useRouter();
  const [logoutLoading, setLogoutLoading] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  async function handleLogout() {
    if (logoutLoading) return; // prevent double-click

    setLogoutLoading(true);
    setLogoutError(null);

    try {
      await authApi.logout();
      router.push("/login");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        // Already logged out or session expired — redirect to login
        router.replace("/login");
        router.refresh();
      } else {
        // Network or server error — show error, re-enable button
        setLogoutError(
          err instanceof Error
            ? err.message
            : "Failed to sign out. Please check your connection."
        );
      }
    } finally {
      setLogoutLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
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
            </div>
            <div className="flex items-center gap-4">
              <div className="text-sm text-gray-600">{user.email}</div>
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
            <div className="px-4 pb-2 text-xs text-red-600">
              {logoutError}
            </div>
          )}
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
