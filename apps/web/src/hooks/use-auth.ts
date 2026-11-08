"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { authApi, agencyApi, ApiError, type UserWithMembershipsOut, type AgencyOut } from "@/lib/api-client";

interface AuthState {
  user: UserWithMembershipsOut | null;
  agency: AgencyOut | null;
  loading: boolean;
  error: string | null;
}

export function useAuth(): AuthState & { refresh: () => Promise<void> } {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({
    user: null,
    agency: null,
    loading: true,
    error: null,
  });

  const load = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const [me, agency] = await Promise.all([authApi.me(), agencyApi.current()]);
      setState({ user: me, agency, loading: false, error: null });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        setState({ user: null, agency: null, loading: false, error: null });
        return;
      }
      const msg = err instanceof Error ? err.message : "Failed to load session";
      setState({ user: null, agency: null, loading: false, error: msg });
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refresh: load };
}
