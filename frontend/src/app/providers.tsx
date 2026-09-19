"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";
import { useState } from "react";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // 401/403 are answers, not blips. api.ts already refreshes and
            // retries once on a 401; retrying again here only doubles the
            // failures behind a login bounce.
            retry: (count, error) =>
              !(error instanceof ApiError &&
                (error.status === 401 || error.status === 403)) && count < 1,
            refetchOnWindowFocus: false,
            staleTime: 10_000,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>{children}</AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
