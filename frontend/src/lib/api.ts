const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "token";
const REFRESH_KEY = "refresh_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function read(key: string): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(key);
}

function write(key: string, value: string | null) {
  if (typeof window === "undefined") return;
  if (value === null) localStorage.removeItem(key);
  else localStorage.setItem(key, value);
}

export function getToken(): string | null {
  return read(TOKEN_KEY);
}

export function setToken(token: string | null) {
  write(TOKEN_KEY, token);
}

export function getRefreshToken(): string | null {
  return read(REFRESH_KEY);
}

export function setRefreshToken(token: string | null) {
  write(REFRESH_KEY, token);
}

export function clearTokens() {
  setToken(null);
  setRefreshToken(null);
}

// The access token now lasts minutes rather than a day, so a 401 mid-session is
// routine rather than exceptional. `auth.tsx` registers what should happen when
// a refresh finally fails; keeping it a callback leaves this file free of
// next/navigation.
let onAuthLost: (() => void) | null = null;

export function setOnAuthLost(cb: (() => void) | null) {
  onAuthLost = cb;
}

// One refresh at a time. A dashboard mounts half a dozen queries at once, and
// without this every one of them that 401s would fire its own refresh - a
// stampede where all but one of the answers is thrown away.
let refreshInFlight: Promise<string | null> | null = null;

function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const refresh_token = getRefreshToken();
    if (!refresh_token) return null;
    try {
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token }),
      });
      if (!res.ok) return null;
      const data = await res.json();
      setToken(data.access_token);
      if (data.refresh_token) setRefreshToken(data.refresh_token);
      return data.access_token as string;
    } catch {
      return null; // offline: treat as "not refreshed", never as "signed out"
    }
  })().finally(() => {
    // Safe to clear here: everyone already waiting holds the promise itself, and
    // the next 401 after this settles should start a genuinely new attempt.
    refreshInFlight = null;
  });

  return refreshInFlight;
}

// A 401 from these is a real answer about the credentials, not a stale token.
const NEVER_RETRY = ["/api/auth/refresh", "/api/auth/login", "/api/auth/register"];

async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const send = (token: string | null) => {
    const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
    if (token) headers.Authorization = `Bearer ${token}`;
    return fetch(`${API_BASE}${path}`, { ...init, headers });
  };

  const token = getToken();
  const res = await send(token);

  if (res.status !== 401 || !token || NEVER_RETRY.some((p) => path.startsWith(p))) {
    return res;
  }

  const fresh = await refreshAccessToken();
  if (!fresh) {
    clearTokens();
    onAuthLost?.();
    return res;
  }
  return send(fresh); // one retry, never a loop
}

async function parseError(res: Response): Promise<never> {
  let message = res.statusText;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") message = body.detail;
    else if (Array.isArray(body.detail))
      message = body.detail
        .map((d: { msg?: string }) => d.msg ?? JSON.stringify(d))
        .join("; ");
  } catch {
    /* keep statusText */
  }
  throw new ApiError(res.status, message);
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (options.body && typeof options.body === "string")
    headers["Content-Type"] = "application/json";

  const res = await authedFetch(path, { ...options, headers });
  if (!res.ok) await parseError(res);
  if (res.status === 204) return undefined as T;
  return res.json();
}

export type Paged<T> = { items: T[]; total: number };

/** A list endpoint plus its `X-Total-Count`, for pagers.
 *
 * The header only reaches this code because the API names it in CORS
 * `expose_headers` - custom response headers are invisible to JS otherwise, and
 * that list does not accept a wildcard. If `total` ever reads back as the page
 * length, check there first.
 */
export async function apiPaged<T>(path: string, options: RequestInit = {}): Promise<Paged<T>> {
  const res = await authedFetch(path, options);
  if (!res.ok) await parseError(res);
  const items = (await res.json()) as T[];
  const header = res.headers.get("X-Total-Count");
  return { items, total: header === null ? items.length : Number(header) };
}

export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  // FormData is re-sendable, so this survives the retry inside authedFetch.
  const res = await authedFetch(path, { method: "POST", body: form });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function apiDownload(path: string, filename: string, body?: unknown) {
  const headers: Record<string, string> = {};
  // a body means POST: exporting the current view sends the filtered row ids,
  // which is far past what a query string can carry
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await authedFetch(path, {
    headers,
    ...(body !== undefined ? { method: "POST", body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) await parseError(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
