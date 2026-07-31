"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, Badge, Spinner, ErrorNote } from "@/components/ui";
import { clsx } from "@/components/clsx";
import { TrackerFieldView } from "@/components/TrackerFieldView";
import { TrackerGrid } from "@/components/TrackerGrid";
import type { TrackerColumn, TrackerRow } from "@/lib/types";

export default function TrackerRowPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user } = useAuth();
  const qc = useQueryClient();
  const [view, setView] = useState<"fields" | "excel">("fields");

  const columns = useQuery({
    queryKey: ["tracker-columns"],
    queryFn: () => api<TrackerColumn[]>("/api/tracker/columns"),
    staleTime: Infinity,
  });
  const row = useQuery({
    queryKey: ["tracker-row", id],
    queryFn: () => api<TrackerRow>(`/api/tracker/${id}`),
  });

  if (columns.isLoading || row.isLoading) return <Spinner />;
  if (row.error) return <ErrorNote message={(row.error as Error).message} />;
  const r = row.data!;
  const cols = columns.data ?? [];

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["tracker-row", id] });
    qc.invalidateQueries({ queryKey: ["tracker"] });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link href="/tracker" className="text-sm text-blue-600 hover:underline">
          ← Tracker
        </Link>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">
          {r.buyer_po} · {r.style_no} · {r.colour}
        </h1>
        {r.has_buyer && <Badge color="blue">buyer</Badge>}
        {r.has_vendor && <Badge color="green">vendor</Badge>}
      </div>

      <div className="inline-flex rounded-md border border-slate-200 bg-white p-0.5 dark:border-slate-800 dark:bg-slate-900">
        {(["fields", "excel"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={clsx(
              "rounded px-3 py-1.5 text-sm",
              view === v
                ? "bg-blue-600 text-white"
                : "text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800",
            )}
          >
            {v === "fields" ? "Field view" : "Excel view"}
          </button>
        ))}
      </div>

      <Card>
        {view === "fields" ? (
          <TrackerFieldView row={r} columns={cols} canEdit={!!user} onSaved={refresh} />
        ) : (
          <TrackerGrid
            rows={[r]}
            columns={cols}
            canEdit={!!user}
            onSaved={refresh}
            height={200}
          />
        )}
      </Card>
    </div>
  );
}
