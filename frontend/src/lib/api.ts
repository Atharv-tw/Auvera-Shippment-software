const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function setToken(token: string | null) {
  if (token === null) localStorage.removeItem("token");
  else localStorage.setItem("token", token);
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
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body && typeof options.body === "string")
    headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
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
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) await parseError(res);
  const items = (await res.json()) as T[];
  const header = res.headers.get("X-Total-Count");
  return { items, total: header === null ? items.length : Number(header) };
}

export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: form, headers });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function apiDownload(path: string, filename: string, body?: unknown) {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  // a body means POST: exporting the current view sends the filtered row ids,
  // which is far past what a query string can carry
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_BASE}${path}`, {
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
