"use client";

import { useRouter } from "next/navigation";
import { authApi, type UserWithMembershipsOut, type AgencyOut } from "@/lib/api-client";

interface DashboardShellProps {
  user: UserWithMembershipsOut;
  agency: AgencyOut;
  children: React.ReactNode;
}

export function DashboardShell({ user, agency, children }: DashboardShellProps) {
  const router = useRouter();

  async function handleLogout() {
    await authApi.logout();
    router.push("/login");
    router.refresh();
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
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
