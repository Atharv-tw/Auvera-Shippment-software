"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiDownload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canViewTracker } from "@/lib/permissions";
import { Button, Card, Input, Spinner, ErrorNote } from "@/components/ui";
import { TrackerGrid } from "@/components/TrackerGrid";
import type { TrackerColumn, TrackerRow } from "@/lib/types";

function todayDdMmYyyy(): string {
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}-${mm}-${d.getFullYear()}`;
}

export default function TrackerPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const allowed = !!user && canViewTracker(user.role);

  const columns = useQuery({
    queryKey: ["tracker-columns"],
    queryFn: () => api<TrackerColumn[]>("/api/tracker/columns"),
    staleTime: Infinity,
    enabled: allowed,
  });
  // The whole set, once. AG Grid filters and sorts it locally, which is what
  // makes the column filters instant and free. Searching used to round-trip on
  // every keystroke and could only match PO / style / colour; the quick filter
  // below matches all 56 columns without touching the network.
  const rows = useQuery({
    queryKey: ["tracker"],
    queryFn: () => api<TrackerRow[]>("/api/tracker"),
    enabled: allowed,
  });

  if (user && !allowed)
    return <ErrorNote message="Your role does not have access to the shipment tracker." />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">Shipment Tracker</h1>
        <Button
          variant="secondary"
          onClick={() =>
            apiDownload("/api/tracker/export", `Shipment Tracker ${todayDdMmYyyy()}.xlsx`)
          }
        >
          Download .xlsx
        </Button>
      </div>

      <div className="max-w-xs">
        <Input
          type="search"
          placeholder="Search every column…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {(columns.error || rows.error) && (
        <ErrorNote message={((columns.error || rows.error) as Error).message} />
      )}

      <Card>
        {columns.isLoading || rows.isLoading ? (
          <Spinner />
        ) : (
          <TrackerGrid
            rows={rows.data ?? []}
            columns={columns.data ?? []}
            role={user!.role}
            quickFilterText={search}
            onSaved={() => qc.invalidateQueries({ queryKey: ["tracker"] })}
          />
        )}
      </Card>
      <p className="text-xs text-slate-400">
        Tip: use the filter row under the headers to narrow a column, ctrl-click rows to total
        just those, and open a row from the Dashboard for a form view of a single shipment line.
      </p>
    </div>
  );
}
