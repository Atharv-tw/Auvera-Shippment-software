"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiDownload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Card, Input, Spinner, ErrorNote } from "@/components/ui";
import { TrackerGrid } from "@/components/TrackerGrid";
import type { TrackerColumn, TrackerRow } from "@/lib/types";

export default function TrackerPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");

  const columns = useQuery({
    queryKey: ["tracker-columns"],
    queryFn: () => api<TrackerColumn[]>("/api/tracker/columns"),
    staleTime: Infinity,
  });
  const rows = useQuery({
    queryKey: ["tracker", search],
    queryFn: () =>
      api<TrackerRow[]>(`/api/tracker${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">Shipment Tracker</h1>
        <Button
          variant="secondary"
          onClick={() =>
            apiDownload("/api/tracker/export", `Shipment Tracker ${new Date().toISOString().slice(0, 10)}.xlsx`)
          }
        >
          Download .xlsx
        </Button>
      </div>

      <div className="max-w-xs">
        <Input
          placeholder="Search PO / style / colour…"
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
            canEdit={!!user}
            onSaved={() => qc.invalidateQueries({ queryKey: ["tracker"] })}
          />
        )}
      </Card>
      <p className="text-xs text-slate-400">
        Tip: open a row from the Dashboard for a form view of a single shipment line.
      </p>
    </div>
  );
}
