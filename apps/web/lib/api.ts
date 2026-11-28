export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface SessionUser {
  id: string;
  role: "founder" | "reviewer" | "admin";
  display_name?: string;
  is_admin?: boolean;
}

export interface Session {
  access: string;
  // The refresh token lives in an httpOnly cookie; this field is not persisted.
  refresh: string;
  user: SessionUser;
  wallet: { address: string; is_primary?: boolean };
}

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code = "api_error") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const LEGACY_STORAGE_KEY = "trystsol.session";
let session: Session | null = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

export function subscribeSession(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSession(): Session | null {
  return session;
}

export function saveSession(next: Session) {
  session = next;
  if (typeof window !== "undefined") {
    // Remove tokens cached by earlier Phase 0-4 builds.
    window.localStorage.removeItem(LEGACY_STORAGE_KEY);
  }
  emit();
}

export function clearSession() {
  session = null;
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(LEGACY_STORAGE_KEY);
  }
  emit();
}

async function sessionFromAccess(access: string): Promise<Session | null> {
  const response = await fetch(`${API_URL}/api/auth/me/`, {
    headers: { authorization: `Bearer ${access}` },
    credentials: "include",
  });
  if (!response.ok) return null;
  const me = await response.json();
  const primary = me.wallets.find((wallet: any) => wallet.is_primary) ?? me.wallets[0];
  if (!primary) return null;
  return {
    access,
    refresh: "",
    user: {
      id: me.id,
      role: me.role,
      display_name: me.display_name,
      is_admin: me.is_admin,
    },
    wallet: { address: primary.address, is_primary: true },
  };
}

async function refreshSession(): Promise<boolean> {
  const response = await fetch(`${API_URL}/api/auth/refresh/`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "{}",
    credentials: "include",
  });
  if (!response.ok) {
    clearSession();
    return false;
  }
  const data = await response.json();
  if (session) {
    saveSession({ ...session, access: data.access, refresh: "" });
    return true;
  }
  const restored = await sessionFromAccess(data.access);
  if (!restored) {
    clearSession();
    return false;
  }
  saveSession(restored);
  return true;
}

export async function restoreSession(): Promise<boolean> {
  if (session) return true;
  return refreshSession();
}

interface FetchOptions {
  retry?: boolean;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  options: FetchOptions = {},
): Promise<T> {
  const current = getSession();
  const headers = new Headers(init.headers);
  if (current?.access) headers.set("authorization", `Bearer ${current.access}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }

  let response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && options.retry !== false && current?.access) {
    if (await refreshSession()) {
      return apiFetch<T>(path, init, { retry: false });
    }
  }

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const message = data?.error?.message ?? `Request failed (${response.status}).`;
    throw new ApiError(message, response.status, data?.error?.code ?? "api_error");
  }
  return data as T;
}

export async function refreshCurrentUser(): Promise<void> {
  const current = getSession();
  if (!current) return;
  const me = await apiFetch<{
    id: string;
    role: SessionUser["role"];
    display_name: string;
    is_admin: boolean;
    wallets: { address: string; is_primary: boolean }[];
  }>("/api/auth/me/");
  const primary = me.wallets.find((wallet) => wallet.is_primary) ?? me.wallets[0];
  saveSession({
    ...current,
    user: {
      id: me.id,
      role: me.role,
      display_name: me.display_name,
      is_admin: me.is_admin,
    },
    wallet: { address: primary?.address ?? current.wallet.address, is_primary: true },
  });
}
