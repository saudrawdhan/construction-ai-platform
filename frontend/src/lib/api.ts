import { currentLang, translate } from "./i18n";

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

/** A FastAPI validation failure returns `detail` as a LIST of per-field errors, not a string.
 *  Without unpacking it the form could only say "request failed", leaving the user to guess which
 *  field the server rejected. `loc` is a path like ["body", "budget"]; the transport segment is
 *  dropped so the message names the field the user can actually see. */
function fieldErrors(detail: unknown): string | null {
  if (!Array.isArray(detail)) return null;
  const messages = detail
    .map((entry) => {
      const item = entry as { loc?: unknown; msg?: unknown };
      const message = typeof item.msg === "string" ? item.msg : "";
      if (!message) return "";
      const path = Array.isArray(item.loc)
        ? item.loc.filter((part): part is string => typeof part === "string" && part !== "body")
        : [];
      return path.length ? `${path.join(".")}: ${message}` : message;
    })
    .filter(Boolean);
  return messages.length ? messages.join("; ") : null;
}

async function readError(res: Response, fallback: string): Promise<string> {
  let detail: unknown = res.statusText;
  try {
    detail = (await res.json()).detail ?? detail;
  } catch {
    /* body was not JSON */
  }
  if (typeof detail === "string") return detail;
  return fieldErrors(detail) ?? fallback;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  // The backend generates AI prose in this language: a workflow analyzes stored records rather
  // than a written question, so the interface language is the only signal it has to go on.
  const headers: Record<string, string> = { "Accept-Language": currentLang() };
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
