import { translate } from "./i18n";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000/api/v1";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Authentication rides on an httpOnly cookie the browser attaches automatically, so every
// request is sent with credentials. A 401 broadcasts a logout event the auth provider listens for.
function notifySessionEnded() {
  window.dispatchEvent(new Event("auth:logout"));
}

async function readError(res: Response, fallback: string): Promise<string> {
  let detail = res.statusText;
  try {
    detail = (await res.json()).detail ?? detail;
  } catch {
    /* body was not JSON */
  }
  return typeof detail === "string" ? detail : fallback;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    notifySessionEnded();
    throw new ApiError(401, translate("session.expired"));
  }
  if (!res.ok) throw new ApiError(res.status, await readError(res, translate("common.requestFailed")));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export const api = {
  async login(email: string, password: string): Promise<{ user: User }> {
    const form = new URLSearchParams({ username: email, password });
    const res = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      credentials: "include",
      body: form.toString(),
    });
    if (!res.ok) throw new ApiError(res.status, translate("api.badCredentials"));
    return res.json();
  },
  logout: () => request<void>("POST", "/auth/logout"),
  me: () => request<User>("GET", "/auth/me"),
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
  async download(path: string, filename: string): Promise<void> {
    const res = await fetch(`${BASE}${path}`, { credentials: "include" });
    if (res.status === 401) {
      notifySessionEnded();
      throw new ApiError(401, translate("session.expired"));
    }
    if (!res.ok) throw new ApiError(res.status, await readError(res, translate("api.downloadFailed")));
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
  async upload<T>(path: string, form: FormData): Promise<T> {
    const res = await fetch(`${BASE}${path}`, { method: "POST", credentials: "include", body: form });
    if (res.status === 401) {
      notifySessionEnded();
      throw new ApiError(401, translate("session.expired"));
    }
    if (!res.ok) throw new ApiError(res.status, await readError(res, translate("api.uploadFailed")));
    return (await res.json()) as T;
  },
};
