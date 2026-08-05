// Typed fetch client for the Silent Honor Rust API.
// In dev, requests are relative ("/api/...") and proxied by Vite (see vite.config.ts).
// In production, they go to the API's absolute origin, cross-origin, with cookies.

const API_BASE: string = import.meta.env.DEV
  ? ""
  : (import.meta.env.VITE_API_BASE as string | undefined) ??
    "https://e1tyj5meuc.execute-api.us-east-1.amazonaws.com";

/** Absolute URL for a given API path (for anchors / file links). */
export function apiUrl(path: string): string {
  return API_BASE + path;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  // Set false for endpoints that return no JSON (204 etc.)
  json?: boolean;
  headers?: Record<string, string>;
};

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const { method = "GET", body, json = true, headers = {} } = opts;

  // Dev fixtures (VITE_MOCK=1) — short-circuit before any network call.
  if (import.meta.env.DEV) {
    const { MOCK_ON, mockResponse } = await import("./mock");
    if (MOCK_ON) {
      const m = mockResponse(path, method);
      if (m !== undefined) return m as T;
    }
  }

  const isForm = typeof FormData !== "undefined" && body instanceof FormData;

  const res = await fetch(API_BASE + path, {
    method,
    credentials: "include",
    headers: {
      ...(body !== undefined && !isForm ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
  });

  if (res.status === 401) {
    throw new ApiError(401, "Not authenticated");
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      detail = data.detail || data.message || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }

  if (!json || res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// Convenience verbs
export const get = <T>(p: string) => api<T>(p);
export const post = <T>(p: string, body?: unknown) => api<T>(p, { method: "POST", body });
export const put = <T>(p: string, body?: unknown) => api<T>(p, { method: "PUT", body });
export const patch = <T>(p: string, body?: unknown) => api<T>(p, { method: "PATCH", body });
export const del = <T>(p: string) => api<T>(p, { method: "DELETE" });

/** Redirect to the static login page, preserving return-to admin. */
export function goToLogin() {
  window.location.href = "../login.html";
}
