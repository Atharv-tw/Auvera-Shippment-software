"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiPaged } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge, Button, Spinner, ErrorNote } from "@/components/ui";
import { canViewAudit } from "@/lib/permissions";
import type { AuthEvent } from "@/lib/types";

const PAGE = 25;

const LABELS: Record<AuthEvent["event"], string> = {
  login: "Signed in",
  logout: "Signed out",
  logout_all: "Signed out everywhere",
  admin_revoke: "Ended by an admin",
};

const COLORS: Record<AuthEvent["event"], "green" | "gray" | "yellow"> = {
  login: "green",
  logout: "gray",
  logout_all: "gray",
  admin_revoke: "yellow",
};

/** Dates are stored UTC-naive; render them in the reader's own timezone. */
function when(iso: string): string {
  const parsed = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`);
  return Number.isNaN(parsed.getTime())
    ? iso
    : parsed.toLocaleString(undefined, {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

export default function ActivityPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [page, setPage] = useState(0);

  // CEO and admin only. The API refuses anyone else (403); redirect rather
  // than show them an error page.
  useEffect(() => {
    if (user && !canViewAudit(user.role)) router.replace("/dashboard");
  }, [user, router]);

  const allowed = !!user && canViewAudit(user.role);

  const events = useQuery({
    queryKey: ["auth-activity", page],
    queryFn: () =>
      apiPaged<AuthEvent>(`/api/auth/activity?limit=${PAGE}&offset=${page * PAGE}`),
    enabled: allowed,
    placeholderData: (previous) => previous, // keep the table steady while paging
  });

  if (!allowed) return <Spinner />;

  const rows = events.data?.items ?? [];
  const total = events.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE));

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
          Sign-in Activity
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Who signed in and out, newest first. {total} {total === 1 ? "entry" : "entries"}.
        </p>
      </div>

      {events.isLoading ? (
        <Spinner />
      ) : events.error ? (
        <ErrorNote message="Could not load the sign-in activity" />
      ) : rows.length === 0 ? (
        <p className="rounded-lg border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          Nothing recorded yet.
        </p>
      ) : (
        <>
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:text-slate-400">
                  <th className="px-4 py-2.5">When</th>
                  <th className="px-4 py-2.5">Who</th>
                  <th className="px-4 py-2.5">Event</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr
                    key={e.id}
                    className="border-b border-slate-100 last:border-0 dark:border-slate-800"
                  >
                    <td className="whitespace-nowrap px-4 py-2.5 text-slate-600 dark:text-slate-300">
                      {when(e.created_at)}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-slate-900 dark:text-slate-100">
                        {e.user_name ?? "Unknown"}
                      </div>
                      {e.user_email && (
                        <div className="text-xs text-slate-500 dark:text-slate-400">
                          {e.user_email}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge color={COLORS[e.event]}>{LABELS[e.event] ?? e.event}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pageCount > 1 && (
            <div className="flex items-center justify-between text-sm text-slate-500 dark:text-slate-400">
              <span>
                Page {page + 1} of {pageCount}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  disabled={page + 1 >= pageCount}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
