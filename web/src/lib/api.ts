import { getToken, clearToken } from "./auth";
import type {
  Article,
  ArticleDetail,
  Client,
  ClientCreate,
  Income,
  IncomeCreate,
  Investment,
  InvestmentCreate,
  MeResponse,
  NewsRefreshResult,
  Newspaper,
  Page,
  PortfolioView,
  PriceRefreshResult,
  Reminder,
  StoredFile,
  TokenResponse,
} from "./types";

function resolveApiUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (raw === "" || raw === "/backend") return "/backend";
  if (raw) return raw.replace(/\/$/, "");
  // Local default; Cloud Run images set NEXT_PUBLIC_API_URL at build time.
  return "http://127.0.0.1:8000";
}

const API_URL = resolveApiUrl();

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  formData?: FormData;
  token?: string | null;
  auth?: boolean;
  query?: Record<string, string | number | boolean | null | undefined>;
};

function buildUrl(
  path: string,
  query?: RequestOptions["query"],
): string {
  const url = new URL(path.startsWith("http") ? path : `${API_URL}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === "") continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, formData, auth = true, query } = options;
  const headers: Record<string, string> = {};

  if (auth) {
    const token = options.token === undefined ? getToken() : options.token;
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let payload: BodyInit | undefined;
  if (formData) {
    payload = formData;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: payload,
    cache: "no-store",
  });

  if (res.status === 401 && auth) {
    clearToken();
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const data = isJson ? await res.json().catch(() => null) : await res.text();

  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : res.statusText || "Request failed";
    throw new ApiError(detail, res.status, data);
  }

  return data as T;
}

export const api = {
  login(username: string, password: string) {
    return apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: { username, password },
      auth: false,
    });
  },
  me(token?: string | null) {
    return apiFetch<MeResponse>("/auth/me", { token });
  },
  listClients(params: { q?: string; page?: number; page_size?: number } = {}) {
    return apiFetch<Page<Client>>("/clients", { query: params });
  },
  getClient(id: number) {
    return apiFetch<Client>(`/clients/${id}`);
  },
  createClient(body: ClientCreate) {
    return apiFetch<Client>("/clients", { method: "POST", body });
  },
  updateClient(id: number, body: Partial<ClientCreate>) {
    return apiFetch<Client>(`/clients/${id}`, { method: "PATCH", body });
  },
  deleteClient(id: number) {
    return apiFetch<{ detail: string }>(`/clients/${id}`, {
      method: "DELETE",
    });
  },
  listInvestments(params: {
    client_id?: number;
    is_done?: boolean;
    page?: number;
    page_size?: number;
  } = {}) {
    return apiFetch<Page<Investment>>("/investments", { query: params });
  },
  getInvestment(id: number) {
    return apiFetch<Investment>(`/investments/${id}`);
  },
  createInvestment(body: InvestmentCreate) {
    return apiFetch<Investment>("/investments", {
      method: "POST",
      body,
    });
  },
  updateInvestment(id: number, body: Partial<Investment>) {
    return apiFetch<Investment>(`/investments/${id}`, {
      method: "PATCH",
      body,
    });
  },
  deleteInvestment(id: number) {
    return apiFetch<{ detail: string }>(`/investments/${id}`, {
      method: "DELETE",
    });
  },
  createIncome(body: IncomeCreate) {
    return apiFetch<Income>("/incomes", {
      method: "POST",
      body,
    });
  },
  updateIncome(id: number, body: Partial<Income>) {
    return apiFetch<Income>(`/incomes/${id}`, {
      method: "PATCH",
      body,
    });
  },
  deleteIncome(id: number) {
    return apiFetch<{ detail: string }>(`/incomes/${id}`, {
      method: "DELETE",
    });
  },
  portfolioView(params: {
    client_id?: number;
    is_done?: boolean | null;
    display_currency?: string;
    live?: boolean;
  } = {}) {
    const query: Record<string, string | number | boolean | null | undefined> = {
      client_id: params.client_id,
      display_currency: params.display_currency || "VND",
      live: params.live ? true : undefined,
    };
    if (params.is_done !== null && params.is_done !== undefined) {
      query.is_done = params.is_done;
    } else if (params.is_done === null) {
      // omit filter — include completed
    } else {
      query.is_done = false;
    }
    return apiFetch<PortfolioView>("/portfolio/view", { query });
  },
  refreshPrices(params: { client_id?: number; is_done?: boolean } = {}) {
    return apiFetch<PriceRefreshResult>("/investments/refresh-prices", {
      method: "POST",
      query: {
        client_id: params.client_id,
        is_done: params.is_done ?? false,
      },
    });
  },
  refreshNews(params: { region?: string } = {}) {
    return apiFetch<NewsRefreshResult>("/news/refresh", {
      method: "POST",
      query: params,
    });
  },
  listIncomes(params: {
    client_id?: number;
    page?: number;
    page_size?: number;
  } = {}) {
    return apiFetch<Page<Income>>("/incomes", { query: params });
  },
  listReminders(params: {
    client_id?: number;
    from_date?: string;
    to_date?: string;
    page?: number;
    page_size?: number;
  } = {}) {
    return apiFetch<Page<Reminder>>("/reminders", { query: params });
  },
  listArticles(params: {
    q?: string;
    region?: string;
    category?: string;
    sort?: string;
    vietnam_focus?: boolean;
    max_age_hours?: number;
    page?: number;
    page_size?: number;
  } = {}) {
    return apiFetch<Page<Article>>("/news/articles", { query: params });
  },
  getArticle(id: number) {
    return apiFetch<ArticleDetail>(`/news/articles/${id}`);
  },
  addBookmark(article_id: number) {
    return apiFetch("/news/bookmarks", {
      method: "POST",
      body: { article_id },
    });
  },
  removeBookmark(article_id: number) {
    return apiFetch<{ detail: string }>(`/news/bookmarks/${article_id}`, {
      method: "DELETE",
    });
  },
  newspaperToday() {
    return apiFetch<Newspaper>("/newspaper/today");
  },
  listNewspapers(params: { page?: number; page_size?: number } = {}) {
    return apiFetch<Page<Newspaper>>("/newspaper", { query: params });
  },
  getNewspaper(date: string) {
    return apiFetch<Newspaper>(`/newspaper/${date}`);
  },
  listAttachments(clientId: number, params: { page?: number } = {}) {
    return apiFetch<Page<StoredFile>>(`/clients/${clientId}/attachments`, {
      query: params,
    });
  },
  uploadAttachment(clientId: number, file: File, label?: string) {
    const formData = new FormData();
    formData.append("file", file);
    if (label) formData.append("label", label);
    return apiFetch<StoredFile>(`/clients/${clientId}/attachments`, {
      method: "POST",
      formData,
    });
  },
  deleteAttachment(clientId: number, fileId: number) {
    return apiFetch<{ detail: string }>(
      `/clients/${clientId}/attachments/${fileId}`,
      { method: "DELETE" },
    );
  },
  listTechcombankReports(params: { page?: number; page_size?: number } = {}) {
    return apiFetch<Page<StoredFile>>("/files/techcombank/reports", {
      query: params,
    });
  },
  syncTechcombank(limit = 8) {
    return apiFetch<{
      found: number;
      synced: number;
      skipped: number;
      errors: string[];
    }>("/files/techcombank/sync", {
      method: "POST",
      query: { limit },
    });
  },
  exportClientZipUrl(clientId: number) {
    return `${API_URL}/clients/${clientId}/export.zip`;
  },
  absoluteUrl(pathOrUrl: string | null | undefined) {
    if (!pathOrUrl) return null;
    if (pathOrUrl.startsWith("http")) return pathOrUrl;
    return `${API_URL}${pathOrUrl.startsWith("/") ? "" : "/"}${pathOrUrl}`;
  },
  apiUrl: API_URL,
};
