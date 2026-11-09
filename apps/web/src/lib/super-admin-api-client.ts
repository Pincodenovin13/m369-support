// Separate Super Admin client. It never calls agency refresh endpoints and
// never stores credentials or tokens in browser storage. Authentication is
// carried only by the HttpOnly super_admin_access_token cookie.
import type { PaginatedResponse } from "@/lib/api-client";

const API_BASE = "/api/v1/super-admin";

export interface SuperAdminOut {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
}

export interface SuperAdminMFARequiredResponse {
  mfa_required: true;
  mfa_challenge: string;
  expires_in_seconds: number;
}

export interface SuperAdminMFASetupResponse {
  secret: string;
  otpauth_url: string;
}

export interface SuperAdminRecoveryCodesOut {
  recovery_codes: string[];
}

export type SuperAdminLoginResult = SuperAdminOut | SuperAdminMFARequiredResponse;

export interface AgencyAdminOut {
  id: string;
  name: string;
  slug: string;
  brand_color: string;
  is_active: boolean;
  created_at: string;
}

export interface AgencyAdminDetailOut extends AgencyAdminOut {
  subscription_id: string | null;
  subscription_status: string | null;
  plan_name: string | null;
  member_count: number;
}

export interface PlanOut {
  id: string;
  name: string;
  display_name: string;
  price_monthly: number;
  currency: string;
  is_active: boolean;
  sort_order: number;
  features: Record<string, unknown>;
  limits: Record<string, unknown>;
  trial_days: number;
  created_at: string;
}

export interface SubscriptionOut {
  id: string;
  agency_id: string;
  plan_id: string;
  status: string;
  price_monthly_snapshot: number;
  currency_snapshot: string;
  plan_name_snapshot: string;
  plan_features_snapshot: Record<string, unknown>;
  plan_limits_snapshot: Record<string, unknown>;
  started_at: string;
  trial_ends_at: string | null;
  current_period_ends_at: string | null;
  cancelled_at: string | null;
  superseded_at: string | null;
  created_at: string;
}

export interface PaymentOut {
  id: string;
  subscription_id: string;
  agency_id: string;
  txid: string;
  idempotency_key: string | null;
  amount_expected: number;
  amount_paid: number;
  currency: string;
  paid_currency: string | null;
  paid_amount_raw: string | null;
  paid_amount_decimals: number | null;
  exchange_rate: number | null;
  status: string;
  verifying_lease_until: string | null;
  verified_at: string | null;
  verified_by_super_admin_id: string | null;
  failure_reason: string | null;
  payment_method: string;
  network: string | null;
  metadata_: Record<string, unknown>;
  created_at: string;
}

export interface SuperAdminAuditLogOut {
  id: number;
  super_admin_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  metadata_: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export class SuperAdminApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "message" in detail
          ? String((detail as { message: unknown }).message)
          : `Super Admin API request failed (${status})`;
    super(message);
    this.name = "SuperAdminApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });

  if (response.status === 204) return undefined as T;

  const raw = await response.text();
  let payload: unknown = null;
  if (raw) {
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = raw;
    }
  }

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload;
    throw new SuperAdminApiError(response.status, detail);
  }
  return payload as T;
}

function query(params?: Record<string, string | number | boolean | undefined>): string {
  if (!params) return "";
  const values = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) values.set(key, String(value));
  }
  const encoded = values.toString();
  return encoded ? `?${encoded}` : "";
}

function stringifyExact(value: unknown): string {
  const marker = "__M369_BIGINT__";
  const serialized = JSON.stringify(value, (_key, item) =>
    typeof item === "bigint" ? `${marker}${item.toString()}` : item,
  );
  return serialized.replace(/"__M369_BIGINT__(-?\\d+)"/g, "$1");
}

export const superAdminAuthApi = {
  login(input: { email: string; password: string }): Promise<SuperAdminLoginResult> {
    return request("/auth/login", { method: "POST", body: JSON.stringify(input) });
  },
  verifyMfa(input: { mfa_challenge: string; code?: string; recovery_code?: string }): Promise<SuperAdminOut> {
    return request("/auth/login/verify-mfa", { method: "POST", body: JSON.stringify(input) });
  },
  me(): Promise<SuperAdminOut> {
    return request("/auth/me");
  },
  logout(): Promise<void> {
    return request("/auth/logout", { method: "POST" });
  },
  setupMfa(): Promise<SuperAdminMFASetupResponse> {
    return request("/auth/mfa/setup", { method: "POST" });
  },
  enableMfa(input: { secret: string; code: string }): Promise<SuperAdminRecoveryCodesOut> {
    return request("/auth/mfa/enable", { method: "POST", body: JSON.stringify(input) });
  },
  disableMfa(input: { code?: string; recovery_code?: string }): Promise<void> {
    return request("/auth/mfa/disable", { method: "POST", body: JSON.stringify(input) });
  },
};

export const superAdminApi = {
  agencies: {
    list(params?: { search?: string; is_active?: boolean; limit?: number; offset?: number }): Promise<PaginatedResponse<AgencyAdminDetailOut>> {
      return request(`/agencies${query(params)}`);
    },
    get(agencyId: string): Promise<AgencyAdminDetailOut> {
      return request(`/agencies/${agencyId}`);
    },
    update(agencyId: string, input: { name?: string; is_active?: boolean; brand_color?: string }): Promise<AgencyAdminOut> {
      return request(`/agencies/${agencyId}`, { method: "PATCH", body: JSON.stringify(input) });
    },
    suspend(agencyId: string): Promise<AgencyAdminOut> {
      return request(`/agencies/${agencyId}/suspend`, { method: "POST" });
    },
    activate(agencyId: string): Promise<AgencyAdminOut> {
      return request(`/agencies/${agencyId}/activate`, { method: "POST" });
    },
  },
  plans: {
    list(params?: { is_active?: boolean; limit?: number; offset?: number }): Promise<PaginatedResponse<PlanOut>> {
      return request(`/plans${query(params)}`);
    },
    create(input: {
      name: string;
      display_name: string;
      price_monthly: number;
      currency: string;
      is_active?: boolean;
      sort_order?: number;
      features?: Record<string, unknown>;
      limits?: Record<string, unknown>;
      trial_days?: number;
    }): Promise<PlanOut> {
      return request("/plans", { method: "POST", body: JSON.stringify(input) });
    },
    update(planId: string, input: {
      display_name?: string;
      price_monthly?: number;
      currency?: string;
      is_active?: boolean;
      sort_order?: number;
      features?: Record<string, unknown>;
      limits?: Record<string, unknown>;
      trial_days?: number;
    }): Promise<PlanOut> {
      return request(`/plans/${planId}`, { method: "PATCH", body: JSON.stringify(input) });
    },
  },
  subscriptions: {
    list(params?: { agency_id?: string; status?: string; limit?: number; offset?: number }): Promise<PaginatedResponse<SubscriptionOut>> {
      return request(`/subscriptions${query(params)}`);
    },
    update(subscriptionId: string, input: { status: string; current_period_ends_at?: string | null }): Promise<SubscriptionOut> {
      return request(`/subscriptions/${subscriptionId}`, { method: "PATCH", body: JSON.stringify(input) });
    },
  },
  payments: {
    list(params?: { agency_id?: string; status?: string; limit?: number; offset?: number }): Promise<PaginatedResponse<PaymentOut>> {
      return request(`/payments${query(params)}`);
    },
    verify(paymentId: string, input: {
      amount_paid: number;
      paid_currency?: string | null;
      paid_amount_raw?: number | bigint | null;
      paid_amount_decimals?: number | null;
      exchange_rate?: number | null;
      network?: string | null;
      note?: string | null;
    }): Promise<PaymentOut> {
      return request(`/payments/${paymentId}/verify`, { method: "POST", body: stringifyExact(input) });
    },
    reject(paymentId: string, failure_reason: string): Promise<PaymentOut> {
      return request(`/payments/${paymentId}/reject`, { method: "POST", body: JSON.stringify({ failure_reason }) });
    },
  },
  auditLogs: {
    list(params?: { action?: string; super_admin_id?: string; since?: string; until?: string; limit?: number; offset?: number }): Promise<PaginatedResponse<SuperAdminAuditLogOut>> {
      return request(`/audit-logs${query(params)}`);
    },
  },
};
