"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { api, setToken, getToken } from "./api";
import type { TokenResponse, User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    name: string,
    role: string,
  ) => Promise<void>;
  logout: () => void;
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
      .catch(() => setToken(null))
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
      setUser(data.user);
      router.push("/dashboard");
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
    async (email: string, password: string, name: string, role: string) => {
      startSession(
        await api<TokenResponse>("/api/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password, name, role }),
        }),
      );
    },
    [startSession],
  );

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    queryClient.clear();
    router.push("/login");
  }, [queryClient, router]);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
