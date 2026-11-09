"use client";

import { useCallback, useEffect, useState } from "react";
import {
  superAdminAuthApi,
  SuperAdminApiError,
  type SuperAdminOut,
} from "@/lib/super-admin-api-client";

export function useSuperAdminAuth() {
  const [admin, setAdmin] = useState<SuperAdminOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const current = await superAdminAuthApi.me();
      setAdmin(current);
    } catch (err) {
      setAdmin(null);
      if (!(err instanceof SuperAdminApiError && err.status === 401)) {
        setError(err instanceof Error ? err.message : "Unable to verify Super Admin session");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { admin, loading, error, refresh };
}
