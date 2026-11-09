"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loading, ErrorState } from "@/components/ui";
import { SuperAdminShell } from "@/components/super-admin-shell";
import { useSuperAdminAuth } from "@/hooks/use-super-admin-auth";

export default function SuperAdminConsoleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { admin, loading, error, refresh } = useSuperAdminAuth();

  useEffect(() => {
    if (!loading && !admin && !error) {
      router.replace("/super-admin/login");
    }
  }, [admin, error, loading, router]);

  if (loading || (!admin && !error)) {
    return <Loading label="Verifying privileged session..." />;
  }
  if (error) {
    return <ErrorState message={error} onRetry={refresh} />;
  }
  if (!admin) {
    return <Loading label="Redirecting to secure sign in..." />;
  }

  return <SuperAdminShell admin={admin}>{children}</SuperAdminShell>;
}
