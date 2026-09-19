"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  api,
  clearTokens,
  getRefreshToken,
  getToken,
  setOnAuthLost,
  setRefreshToken,
  setToken,
} from "./api";
import type { TokenResponse, User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
  logoutEverywhere: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api<User>("/api/auth/me")
      .then(setUser)
      .catch(() => clearTokens())
      .finally(() => setLoading(false));
  }, []);

  // Nothing in the query cache belongs to the next user: the column and field
  // lists carry *this* user's `editable` answer, and the rest is their data.
  // Cached with `staleTime: Infinity`, they would otherwise survive a sign-out
  // and hand the next person the previous one's edit rights.
  const startSession = useCallback(
    (data: TokenResponse) => {
      queryClient.clear();
      setToken(data.access_token);
      if (data.refresh_token) setRefreshToken(data.refresh_token);
      setUser(data.user);
      // A brand-new account has no role yet: send it to the waitlist rather than
      // the dashboard, which would only bounce it straight back.
      router.push(data.user.role === "pending" ? "/waitlist" : "/dashboard");
    },
    [queryClient, router],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      startSession(
        await api<TokenResponse>("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        }),
      );
    },
    [startSession],
  );

  const register = useCallback(
    async (email: string, password: string, name: string) => {
      startSession(
        await api<TokenResponse>("/api/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password, name }),
        }),
      );
    },
    [startSession],
  );

  // Local teardown, shared by signing out and by a refresh that finally failed.
  const forget = useCallback(() => {
    clearTokens();
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  const logout = useCallback(async () => {
    // Tell the server first, so the session is actually revoked rather than
    // left alive until it expires. The local clear happens either way: someone
    // on a flaky connection must still be able to sign out of their own browser.
    try {
      await api("/api/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: getRefreshToken() }),
      });
    } catch {
      /* already gone, or offline - sign out locally regardless */
    }
    forget();
    router.push("/login");
  }, [forget, router]);

  const logoutEverywhere = useCallback(async () => {
    try {
      await api("/api/auth/logout-all", { method: "POST" });
    } catch {
      /* as above */
    }
    forget();
    router.push("/login");
  }, [forget, router]);

  // When a refresh fails there is no session left to save; land them on the
  // login page rather than letting every query fail silently behind the UI.
  useEffect(() => {
    setOnAuthLost(() => {
      forget();
      router.replace("/login");
    });
    return () => setOnAuthLost(null);
  }, [forget, router]);

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, logout, logoutEverywhere }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
