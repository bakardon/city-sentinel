import { getServerUrlSnapshot } from "@/lib/stores/serverUrl";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export function buildUrl(path: string, params?: Record<string, unknown>): string {
  const base = getServerUrlSnapshot();
  const url = new URL(
    path.startsWith("http") ? path : `${base.replace(/\/$/, "")}${path.startsWith("/") ? path : "/" + path}`
  );
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === "") continue;
      url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

async function parseResponse<T>(res: Response): Promise<T> {
  const text = await res.text();
  let data: unknown = text;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      // keep as text
    }
  }
  if (!res.ok) {
    const message =
      (typeof data === "object" && data && "detail" in (data as Record<string, unknown>)
        ? String((data as Record<string, unknown>).detail)
        : "") ||
      res.statusText ||
      `HTTP ${res.status}`;
    throw new ApiError(message, res.status, data);
  }
  return data as T;
}

export async function apiGet<T>(path: string, params?: Record<string, unknown>, signal?: AbortSignal): Promise<T> {
  const res = await fetch(buildUrl(path, params), { method: "GET", signal });
  return parseResponse<T>(res);
}

export async function apiPostJson<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  return parseResponse<T>(res);
}

export async function apiPostForm<T>(path: string, form: FormData, signal?: AbortSignal): Promise<T> {
  const res = await fetch(buildUrl(path), { method: "POST", body: form, signal });
  return parseResponse<T>(res);
}

export async function apiDelete<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(buildUrl(path), { method: "DELETE", signal });
  return parseResponse<T>(res);
}

export function artifactUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return buildUrl(path);
}
