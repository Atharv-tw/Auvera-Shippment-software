"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Info, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { AuditEntry, Role, TrackerColumn, TrackerRow } from "@/lib/types";
import {
  canEditSource,
  canEditAnyTracker,
  canViewAudit,
  isOrderDetailSource,
} from "@/lib/permissions";
import { Button, ErrorNote, Badge } from "@/components/ui";

const GROUPS: { title: string; sources: string[] }[] = [
  { title: "Buyer", sources: ["buyer", "const"] },
  { title: "Factory / Vendor", sources: ["vendor", "calc"] },
  { title: "Operational (shipment, docs, booking)", sources: ["operational"] },
];

/** Label/value form view of a single tracker row.
 *
 * Editing is role-aware per field class: order-detail fields (buyer/vendor) are
 * editable by CEO/admin, operational fields by shipping-manager/admin. CEO/admin
 * also get an info button on each order-detail field that opens the change trail.
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

  const editable = (source: string) => canEditSource(role, source);
  const showAudit = canViewAudit(role);
  const canEdit = canEditAnyTracker(role);

  const value = (key: string) => (key in draft ? draft[key] : (row.data[key] ?? ""));

  const changes = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(draft).filter(
          ([k, v]) => String(v ?? "") !== String(row.data[k] ?? ""),
        ),
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
                const fieldEditable = editing && editable(c.source);
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
                      <div className="mt-0.5 text-sm text-slate-800 dark:text-slate-200">
                        {String(row.data[c.key] ?? "—")}
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
          rowId={row.id}
          field={auditCol.key}
          label={auditCol.label}
          onClose={() => setAuditKey(null)}
        />
      )}
    </div>
  );
}

function AuditDrawer({
  rowId,
  field,
  label,
  onClose,
}: {
  rowId: number;
  field: string;
  label: string;
  onClose: () => void;
}) {
  const q = useQuery({
    queryKey: ["audit", rowId, field],
    queryFn: () =>
      api<AuditEntry[]>(`/api/tracker/${rowId}/audit?field=${encodeURIComponent(field)}`),
  });

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="relative z-50 flex h-full w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-start justify-between border-b border-slate-100 px-5 py-4 dark:border-slate-800">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-400">Change trail</div>
            <div className="mt-0.5 font-semibold text-slate-900 dark:text-slate-100">{label}</div>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {q.isLoading && <div className="text-sm text-slate-400">Loading…</div>}
          {q.error && <ErrorNote message={(q.error as Error).message} />}
          {q.data && q.data.length === 0 && (
            <div className="text-sm text-slate-400">No recorded changes for this field yet.</div>
          )}
          <ol className="space-y-3">
            {(q.data ?? []).map((e) => (
              <li
                key={e.id}
                className="rounded-md border border-slate-100 p-3 text-sm dark:border-slate-800"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-800 dark:text-slate-200">
                    {e.user_name ?? "Unknown"}
                  </span>
                  <Badge
                    color={e.action === "import" ? "gray" : e.action === "manual" ? "blue" : "green"}
                  >
                    {e.action}
                  </Badge>
                  <span className="ml-auto text-xs text-slate-400">
                    {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
                  </span>
                </div>
                <div className="mt-1.5 text-xs text-slate-600 dark:text-slate-400">
                  <span className="text-slate-400 line-through">{e.old_value ?? "(empty)"}</span>
                  {" → "}
                  <span className="font-medium text-slate-800 dark:text-slate-200">
                    {e.new_value ?? "(empty)"}
                  </span>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </aside>
    </div>
  );
}
