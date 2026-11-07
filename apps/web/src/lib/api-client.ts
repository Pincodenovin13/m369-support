const API_BASE = "/api/v1";

export interface UserOut {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
}

export interface MembershipOut {
  id: string;
  agency_id: string;
  role: string;
}

export interface UserWithMembershipsOut extends UserOut {
  memberships: MembershipOut[];
}

export interface AgencyOut {
  id: string;
  name: string;
  slug: string;
  brand_color: string;
  is_active: boolean;
  created_at: string;
}

export interface WorkspaceOut {
  id: string;
  agency_id: string;
  name: string;
  slug: string;
  timezone: string;
  is_active: boolean;
  created_at: string;
}

export interface AgencyLoginOption {
  agency_id: string;
  role: string;
}

export interface RegisterInput {
  agency_name: string;
  name: string;
  email: string;
  password: string;
}

export interface ApiErrorPayload {
  message?: string;
  available_agencies?: AgencyLoginOption[];
  [key: string]: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    const message =
      typeof detail === "string"
        ? detail
        : detail &&
            typeof detail === "object" &&
            "message" in detail &&
            typeof (detail as ApiErrorPayload).message === "string"
          ? (detail as ApiErrorPayload).message!
          : `API request failed (${status})`;

    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  retryAfterRefresh?: boolean;
}

async function requestRaw<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
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

  if (response.status === 204) {
    return undefined as T;
  }

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
    let detail: unknown = payload;

    if (
      payload &&
      typeof payload === "object" &&
      "detail" in payload
    ) {
      detail = (payload as { detail: unknown }).detail;
    }

    throw new ApiError(response.status, detail);
  }

  return payload as T;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {},
): Promise<T> {
  try {
    return await requestRaw<T>(path, init);
  } catch (error) {
    const shouldRefresh =
      options.retryAfterRefresh !== false &&
      error instanceof ApiError &&
      error.status === 401 &&
      path !== "/auth/refresh" &&
      path !== "/auth/login" &&
      path !== "/auth/register" &&
      path !== "/auth/logout";

    if (!shouldRefresh) {
      throw error;
    }

    try {
      // Refresh uses the HttpOnly cookie. No JSON body is required.
      await requestRaw<void>("/auth/refresh", {
        method: "POST",
      });
    } catch {
      // Preserve the original 401. Do not hide the original API failure.
      throw error;
    }

    // Retry the original request exactly once.
    return requestRaw<T>(path, init);
  }
}

export const authApi = {
  register(input: RegisterInput): Promise<UserOut> {
    return request<UserOut>(
      "/auth/register",
      {
        method: "POST",
        body: JSON.stringify(input),
      },
      { retryAfterRefresh: false },
    );
  },

  login(
    email: string,
    password: string,
    agencyId?: string,
  ): Promise<UserOut> {
    const body: {
      email: string;
      password: string;
      agency_id?: string;
    } = {
      email,
      password,
    };

    if (agencyId) {
      body.agency_id = agencyId;
    }

    return request<UserOut>(
      "/auth/login",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
      { retryAfterRefresh: false },
    );
  },

  refresh(): Promise<void> {
    return request<void>(
      "/auth/refresh",
      { method: "POST" },
      { retryAfterRefresh: false },
    );
  },

  logout(): Promise<void> {
    return request<void>(
      "/auth/logout",
      { method: "POST" },
      { retryAfterRefresh: false },
    );
  },

  me(): Promise<UserWithMembershipsOut> {
    return request<UserWithMembershipsOut>("/auth/me");
  },
};

export const agencyApi = {
  current(): Promise<AgencyOut> {
    return request<AgencyOut>("/agencies/current");
  },
};

export const workspaceApi = {
  list(): Promise<WorkspaceOut[]> {
    return request<WorkspaceOut[]>("/workspaces");
  },
};
