"use client";

import { useMemo, useState } from "react";
import { Info } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Role, TrackerColumn, TrackerRow } from "@/lib/types";
import {
  canEditTracker,
  canViewAudit,
  isOrderDetailSource,
  lockReason,
} from "@/lib/permissions";
import { Button, ErrorNote } from "@/components/ui";
import { AuditDrawer } from "@/components/AuditDrawer";
import { toDisplayDate, toIsoDate } from "@/lib/dateFormat";
import { clsx } from "@/components/clsx";

const GROUPS: { title: string; sources: string[] }[] = [
  { title: "Buyer", sources: ["buyer", "const"] },
  { title: "Factory / Vendor", sources: ["vendor", "calc"] },
  { title: "Operational (shipment, docs, booking)", sources: ["operational"] },
];

/** Label/value form view of a single tracker row.
 *
 * Which fields open for editing is the column's own `editable`, as the columns
 * endpoint answered it for this user. CEO/admin also get an info button on each
 * order-detail field that opens the change trail.
 */
export function TrackerFieldView({
  row,
  columns,
  role,
  onSaved,
}: {
  row: TrackerRow;
  columns: TrackerColumn[];
  role: Role;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [auditKey, setAuditKey] = useState<string | null>(null);

  const showAudit = canViewAudit(role);
  const canEdit = canEditTracker(role);
  const typeByKey = useMemo(
    () => Object.fromEntries(columns.map((c) => [c.key, c.type])),
    [columns],
  );
  const displayValue = (key: string, raw: unknown) =>
    typeByKey[key] === "date" ? toDisplayDate(raw) : String(raw ?? "");

  const value = (key: string) =>
    key in draft ? draft[key] : displayValue(key, row.data[key] ?? "");

  const changes = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(draft)
          .filter(([k, v]) => String(v ?? "") !== displayValue(k, row.data[k]))
          .map(([k, v]) => [k, typeByKey[k] === "date" ? toIsoDate(v) : v]),
      ),
    [draft, row.data, typeByKey],
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

  const auditCol = columns.find((c) => c.key === auditKey) ?? null;

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
        if (cols.length === 0) return null;
        return (
          <div key={g.title}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
              {g.title}
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {cols.map((c) => {
                const fieldEditable = editing && c.editable;
                const locked = editing ? lockReason(c) : null;
                const auditable = showAudit && isOrderDetailSource(c.source);
                return (
                  <div
                    key={c.key}
                    className="rounded-md border border-slate-100 bg-white p-2 dark:border-slate-800 dark:bg-slate-900"
                  >
                    <div className="flex items-center gap-1">
                      <div className="text-[11px] text-slate-400 dark:text-slate-500">
                        {c.label}
                      </div>
                      {auditable && (
                        <button
                          type="button"
                          title="Who entered this? View the change trail"
                          onClick={() => setAuditKey(c.key)}
                          className="ml-auto text-slate-300 hover:text-blue-600 dark:text-slate-600 dark:hover:text-blue-400"
                        >
                          <Info size={13} />
                        </button>
                      )}
                    </div>
                    {fieldEditable ? (
                      <input
                        className="mt-0.5 w-full rounded border border-slate-200 px-1.5 py-1 text-sm outline-none focus:border-blue-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                        value={String(value(c.key) ?? "")}
                        onChange={(e) => setDraft((d) => ({ ...d, [c.key]: e.target.value }))}
                      />
                    ) : (
                      <div
                        title={locked ?? undefined}
                        className={clsx(
                          "mt-0.5 text-sm text-slate-800 dark:text-slate-200",
                          locked && "cursor-not-allowed opacity-60",
                        )}
                      >
                        {row.data[c.key] != null && row.data[c.key] !== ""
                          ? displayValue(c.key, row.data[c.key])
                          : "—"}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {auditCol && (
        <AuditDrawer
          path={`/api/tracker/${row.id}/audit?field=${encodeURIComponent(auditCol.key)}`}
          label={auditCol.label}
          isDate={auditCol.type === "date"}
          onClose={() => setAuditKey(null)}
        />
      )}
    </div>
  );
}
