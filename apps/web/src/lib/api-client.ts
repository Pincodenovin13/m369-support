// M369 Support API client — typed fetch wrapper with cookie-based auth.
// All endpoints map 1:1 to the backend routers in apps/api/app/api/v1/.

const API_BASE = "/api/v1";

// ---------------------------------------------------------------------------
// Types — mirror apps/api/app/schemas/*.py
// ---------------------------------------------------------------------------

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
  agency_name?: string;
}

export interface RegisterInput {
  agency_name: string;
  name: string;
  email: string;
  password: string;
}

export interface ContactOut {
  id: string;
  workspace_id: string;
  agency_id: string;
  email: string | null;
  phone: string | null;
  name: string;
  created_at: string;
}

export interface ContactCreate {
  workspace_id: string;
  email?: string | null;
  phone?: string | null;
  name?: string;
}

export interface ContactUpdate {
  email?: string | null;
  phone?: string | null;
  name?: string;
}

export interface ConversationOut {
  id: string;
  workspace_id: string;
  agency_id: string;
  contact_id: string;
  assigned_user_id: string | null;
  assigned_team_id: string | null;
  subject: string;
  status: "open" | "pending" | "resolved" | "closed";
  created_at: string;
  updated_at: string;
}

export interface ConversationCreate {
  workspace_id: string;
  contact_id: string;
  subject?: string;
  assigned_user_id?: string | null;
  assigned_team_id?: string | null;
}

export interface ConversationUpdate {
  status?: "open" | "pending" | "resolved" | "closed" | null;
  assigned_user_id?: string | null;
  assigned_team_id?: string | null;
  subject?: string | null;
}

export interface MessageOut {
  id: string;
  conversation_id: string;
  agency_id: string;
  sender_type: string;
  sender_user_id: string | null;
  content: string;
  is_internal: boolean;
  delivery_status: string | null;
  created_at: string;
}

export interface MessageCreate {
  conversation_id: string;
  content: string;
  is_internal?: boolean;
  reply_to_message_id?: string | null;
}

export interface TeamOut {
  id: string;
  workspace_id: string;
  agency_id: string;
  name: string;
  is_default: boolean;
  created_at: string;
}

export interface TeamCreate {
  workspace_id: string;
  name: string;
}

export interface TeamMembershipOut {
  team_id: string;
  user_id: string;
  agency_id: string;
}

export interface ChannelOut {
  id: string;
  workspace_id: string;
  agency_id: string;
  type: "widget" | "email" | "whatsapp_cloud" | "telegram" | "instagram" | "messenger";
  name: string;
  config: Record<string, unknown>;
  is_enabled: boolean;
  public_id: string | null;
  created_at: string;
}

export interface ChannelCreate {
  workspace_id: string;
  type: "widget" | "email" | "whatsapp_cloud" | "telegram" | "instagram" | "messenger";
  name: string;
  config: Record<string, unknown>;
  is_enabled: boolean;
}

export interface ChannelUpdate {
  name?: string;
  config?: Record<string, unknown>;
  is_enabled?: boolean;
}

export interface CannedResponseOut {
  id: string;
  workspace_id: string;
  agency_id: string;
  shortcut: string;
  content: string;
  created_at: string;
}

export interface CannedResponseCreate {
  workspace_id: string;
  shortcut: string;
  content: string;
}

export interface CannedResponseUpdate {
  content?: string;
}

export interface KBCategoryOut {
  id: string;
  workspace_id: string;
  agency_id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  position: number;
  created_at: string;
}

export interface KBCategoryCreate {
  workspace_id: string;
  name: string;
  parent_id?: string | null;
  position?: number;
}

export interface KBArticleOut {
  id: string;
  workspace_id: string;
  agency_id: string;
  category_id: string | null;
  title: string;
  slug: string;
  content_md: string;
  is_published: boolean;
  views_count: number;
  helpful_count: number;
  not_helpful_count: number;
  author_id: string | null;
  created_at: string;
}

export interface KBArticleCreate {
  workspace_id: string;
  category_id?: string | null;
  title: string;
  content_md: string;
  is_published?: boolean;
}

export interface KBArticleUpdate {
  category_id?: string | null;
  title?: string;
  content_md?: string;
  is_published?: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
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

// ---------------------------------------------------------------------------
// Request infrastructure
// ---------------------------------------------------------------------------

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
      await requestRaw<void>("/auth/refresh", { method: "POST" });
    } catch {
      throw error;
    }

    return requestRaw<T>(path, init);
  }
}

function buildQuery(params?: Record<string, string | number | undefined>): string {
  if (!params) return "";
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) usp.set(k, String(v));
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

// ---------------------------------------------------------------------------
// API modules — one per backend router
// ---------------------------------------------------------------------------

export const authApi = {
  register(input: RegisterInput): Promise<UserOut> {
    return request<UserOut>(
      "/auth/register",
      { method: "POST", body: JSON.stringify(input) },
      { retryAfterRefresh: false },
    );
  },
  login(email: string, password: string, agencyId?: string): Promise<UserOut> {
    const body: { email: string; password: string; agency_id?: string } = { email, password };
    if (agencyId) body.agency_id = agencyId;
    return request<UserOut>(
      "/auth/login",
      { method: "POST", body: JSON.stringify(body) },
      { retryAfterRefresh: false },
    );
  },
  refresh(): Promise<void> {
    return request<void>("/auth/refresh", { method: "POST" }, { retryAfterRefresh: false });
  },
  logout(): Promise<void> {
    return request<void>("/auth/logout", { method: "POST" }, { retryAfterRefresh: false });
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
  create(input: { name: string; slug: string; timezone?: string }): Promise<WorkspaceOut> {
    return request<WorkspaceOut>("/workspaces", { method: "POST", body: JSON.stringify(input) });
  },
};

export const contactApi = {
  list(params?: { limit?: number; offset?: number; search?: string; workspace_id?: string }): Promise<PaginatedResponse<ContactOut>> {
    return request<PaginatedResponse<ContactOut>>(`/contacts${buildQuery(params as Record<string, string | number | undefined> | undefined)}`);
  },
  get(contactId: string): Promise<ContactOut> {
    return request<ContactOut>(`/contacts/${contactId}`);
  },
  create(input: ContactCreate): Promise<ContactOut> {
    return request<ContactOut>("/contacts", { method: "POST", body: JSON.stringify(input) });
  },
  update(contactId: string, input: ContactUpdate): Promise<ContactOut> {
    return request<ContactOut>(`/contacts/${contactId}`, { method: "PATCH", body: JSON.stringify(input) });
  },
};

export const conversationApi = {
  list(params?: { limit?: number; offset?: number; status?: string }): Promise<PaginatedResponse<ConversationOut>> {
    return request<PaginatedResponse<ConversationOut>>(`/conversations${buildQuery(params as Record<string, string | number | undefined> | undefined)}`);
  },
  get(conversationId: string): Promise<ConversationOut> {
    return request<ConversationOut>(`/conversations/${conversationId}`);
  },
  create(input: ConversationCreate): Promise<ConversationOut> {
    return request<ConversationOut>("/conversations", { method: "POST", body: JSON.stringify(input) });
  },
  update(conversationId: string, input: ConversationUpdate): Promise<ConversationOut> {
    return request<ConversationOut>(`/conversations/${conversationId}`, { method: "PATCH", body: JSON.stringify(input) });
  },
};

export const messageApi = {
  list(conversationId: string, params?: { limit?: number; offset?: number }): Promise<PaginatedResponse<MessageOut>> {
    return request<PaginatedResponse<MessageOut>>(`/messages${buildQuery({ conversation_id: conversationId, ...params } as Record<string, string | number | undefined>)}`);
  },
  send(input: MessageCreate): Promise<MessageOut> {
    return request<MessageOut>("/messages", { method: "POST", body: JSON.stringify(input) });
  },
};

export const teamApi = {
  list(params?: { limit?: number; offset?: number }): Promise<PaginatedResponse<TeamOut>> {
    return request<PaginatedResponse<TeamOut>>(`/teams${buildQuery(params as Record<string, string | number | undefined> | undefined)}`);
  },
  create(input: TeamCreate): Promise<TeamOut> {
    return request<TeamOut>("/teams", { method: "POST", body: JSON.stringify(input) });
  },
  listMembers(teamId: string): Promise<TeamMembershipOut[]> {
    return request<TeamMembershipOut[]>(`/teams/${teamId}/members`);
  },
  addMember(teamId: string, userId: string): Promise<TeamMembershipOut> {
    return request<TeamMembershipOut>(`/teams/${teamId}/members`, { method: "POST", body: JSON.stringify({ user_id: userId }) });
  },
  removeMember(teamId: string, userId: string): Promise<void> {
    return request<void>(`/teams/${teamId}/members/${userId}`, { method: "DELETE" });
  },
};

export const channelApi = {
  list(params?: { limit?: number; offset?: number }): Promise<PaginatedResponse<ChannelOut>> {
    return request<PaginatedResponse<ChannelOut>>(`/channels${buildQuery(params as Record<string, string | number | undefined> | undefined)}`);
  },
  create(input: ChannelCreate): Promise<ChannelOut> {
    return request<ChannelOut>("/channels", { method: "POST", body: JSON.stringify(input) });
  },
  update(channelId: string, input: ChannelUpdate): Promise<ChannelOut> {
    return request<ChannelOut>(`/channels/${channelId}`, { method: "PATCH", body: JSON.stringify(input) });
  },
  delete(channelId: string): Promise<void> {
    return request<void>(`/channels/${channelId}`, { method: "DELETE" });
  },
};

export const cannedResponseApi = {
  list(params?: { limit?: number; offset?: number }): Promise<PaginatedResponse<CannedResponseOut>> {
    return request<PaginatedResponse<CannedResponseOut>>(`/canned-responses${buildQuery(params as Record<string, string | number | undefined> | undefined)}`);
  },
  create(input: CannedResponseCreate): Promise<CannedResponseOut> {
    return request<CannedResponseOut>("/canned-responses", { method: "POST", body: JSON.stringify(input) });
  },
  update(crId: string, input: CannedResponseUpdate): Promise<CannedResponseOut> {
    return request<CannedResponseOut>(`/canned-responses/${crId}`, { method: "PATCH", body: JSON.stringify(input) });
  },
  delete(crId: string): Promise<void> {
    return request<void>(`/canned-responses/${crId}`, { method: "DELETE" });
  },
};

export const kbApi = {
  listCategories(params?: { limit?: number; offset?: number }): Promise<PaginatedResponse<KBCategoryOut>> {
    return request<PaginatedResponse<KBCategoryOut>>(`/kb/categories${buildQuery(params as Record<string, string | number | undefined> | undefined)}`);
  },
  createCategory(input: KBCategoryCreate): Promise<KBCategoryOut> {
    return request<KBCategoryOut>("/kb/categories", { method: "POST", body: JSON.stringify(input) });
  },
  listArticles(params?: { limit?: number; offset?: number }): Promise<PaginatedResponse<KBArticleOut>> {
    return request<PaginatedResponse<KBArticleOut>>(`/kb/articles${buildQuery(params as Record<string, string | number | undefined> | undefined)}`);
  },
  getArticle(articleId: string): Promise<KBArticleOut> {
    return request<KBArticleOut>(`/kb/articles/${articleId}`);
  },
  createArticle(input: KBArticleCreate): Promise<KBArticleOut> {
    return request<KBArticleOut>("/kb/articles", { method: "POST", body: JSON.stringify(input) });
  },
  updateArticle(articleId: string, input: KBArticleUpdate): Promise<KBArticleOut> {
    return request<KBArticleOut>(`/kb/articles/${articleId}`, { method: "PATCH", body: JSON.stringify(input) });
  },
};
