"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canEditOrderDetails, canEditSource } from "@/lib/permissions";
import { Button, Card, Spinner, ErrorNote } from "@/components/ui";
import type { TrackerColumn, TrackerRow } from "@/lib/types";

const GROUPS: { title: string; sources: string[] }[] = [
  { title: "Buyer", sources: ["buyer", "const"] },
  { title: "Factory / Vendor", sources: ["vendor", "calc"] },
  { title: "Operational", sources: ["operational"] },
];

export default function ManualEntryPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const allowed = !!user && canEditOrderDetails(user.role);

  const columns = useQuery({
    queryKey: ["tracker-columns"],
    queryFn: () => api<TrackerColumn[]>("/api/tracker/columns"),
    staleTime: Infinity,
    enabled: allowed,
  });

  if (user && !allowed)
    return (
      <ErrorNote message="Only CEO / admin can create a tracker row (it sets the order identity)." />
    );

  const submit = async () => {
    if (!fields.buyer_po || !fields.style_no) {
      setError("Buyer PO# and Style No. are required (they form the row identity).");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const cleaned = Object.fromEntries(Object.entries(fields).filter(([, v]) => v !== ""));
      const row = await api<TrackerRow>("/api/tracker", {
        method: "POST",
        body: JSON.stringify({ fields: cleaned }),
      });
      qc.invalidateQueries({ queryKey: ["tracker"] });
      router.push(`/tracker/${row.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create row");
    } finally {
      setBusy(false);
    }
  };

  if (columns.isLoading) return <Spinner />;
  const cols = columns.data ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">Manual tracker row</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Create a shipment tracker row by hand. Buyer PO# + Style No. + Colour identify the row.
      </p>
      {error && <ErrorNote message={error} />}

      {GROUPS.map((g) => {
        const groupCols = cols.filter(
          (c) => g.sources.includes(c.source) && canEditSource(user!.role, c.source),
        );
        if (groupCols.length === 0) return null;
        return (
        <Card key={g.title} title={g.title}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {groupCols
              .map((c) => (
                <div key={c.key}>
                  <label className="text-[11px] text-slate-400 dark:text-slate-500">{c.label}</label>
                  <input
                    className="mt-0.5 w-full rounded border border-slate-200 px-2 py-1 text-sm outline-none focus:border-blue-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                    type={c.type === "number" ? "number" : c.type === "date" ? "date" : "text"}
                    value={fields[c.key] ?? ""}
                    onChange={(e) => setFields((f) => ({ ...f, [c.key]: e.target.value }))}
                  />
                </div>
              ))}
          </div>
        </Card>
        );
      })}

      <div className="flex gap-2">
        <Button onClick={submit} disabled={busy}>
          {busy ? "Creating…" : "Create tracker row"}
        </Button>
        <Button variant="ghost" onClick={() => setFields({})} disabled={busy}>
          Clear
        </Button>
      </div>
    </div>
  );
}
