"use client";

import { useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { TrackerColumn, TrackerRow } from "@/lib/types";
import { Button, ErrorNote } from "@/components/ui";

const GROUPS: { title: string; sources: string[] }[] = [
  { title: "Buyer", sources: ["buyer", "const"] },
  { title: "Factory / Vendor", sources: ["vendor", "calc"] },
  { title: "Operational (shipment, docs, booking)", sources: ["operational"] },
];

/** Label/value form view of a single tracker row, editable, grouped by source. */
export function TrackerFieldView({
  row,
  columns,
  canEdit,
  onSaved,
}: {
  row: TrackerRow;
  columns: TrackerColumn[];
  canEdit: boolean;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const value = (key: string) =>
    key in draft ? draft[key] : (row.data[key] ?? "");

  const changes = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(draft).filter(([k, v]) => String(v ?? "") !== String(row.data[k] ?? "")),
      ),
    [draft, row.data],
  );

  const save = async () => {
    if (Object.keys(changes).length === 0) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api(`/api/tracker/${row.id}`, {
        method: "PATCH",
        body: JSON.stringify({ fields: changes }),
      });
      setDraft({});
      setEditing(false);
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        {error && <ErrorNote message={error} />}
        <div className="ml-auto flex gap-2">
          {editing ? (
            <>
              <Button
                variant="ghost"
                disabled={saving}
                onClick={() => {
                  setDraft({});
                  setEditing(false);
                }}
              >
                Cancel
              </Button>
              <Button disabled={saving} onClick={save}>
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </>
          ) : (
            canEdit && (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )
          )}
        </div>
      </div>

      {GROUPS.map((g) => {
        const cols = columns.filter((c) => g.sources.includes(c.source));
        return (
          <div key={g.title}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
              {g.title}
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {cols.map((c) => (
                <div
                  key={c.key}
                  className="rounded-md border border-slate-100 bg-white p-2 dark:border-slate-800 dark:bg-slate-900"
                >
                  <div className="text-[11px] text-slate-400 dark:text-slate-500">{c.label}</div>
                  {editing ? (
                    <input
                      className="mt-0.5 w-full rounded border border-slate-200 px-1.5 py-1 text-sm outline-none focus:border-blue-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                      value={String(value(c.key) ?? "")}
                      onChange={(e) =>
                        setDraft((d) => ({ ...d, [c.key]: e.target.value }))
                      }
                    />
                  ) : (
                    <div className="mt-0.5 text-sm text-slate-800 dark:text-slate-200">
                      {String(row.data[c.key] ?? "—")}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
