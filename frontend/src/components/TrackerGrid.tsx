"use client";

import { useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule,
  ModuleRegistry,
  colorSchemeDark,
  themeQuartz,
  type CellKeyDownEvent,
  type CellValueChangedEvent,
  type ColDef,
} from "ag-grid-community";
import { api, ApiError } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { Role, TrackerColumn, TrackerRow } from "@/lib/types";
import { canEditField, canUseExcelView, lockReason } from "@/lib/permissions";
import { Button, ErrorNote } from "@/components/ui";
import { toDisplayDate, toIsoDate } from "@/lib/dateFormat";

ModuleRegistry.registerModules([AllCommunityModule]);

const lightTheme = themeQuartz;
const darkTheme = themeQuartz.withPart(colorSchemeDark);

type Row = Record<string, unknown> & { __id: number };

/** Excel-style grid over tracker rows: one row per shipment line, one column
 * per tracker column. Edits accumulate per row and save via PATCH /tracker/lines. */
export function TrackerGrid({
  rows,
  columns,
  role,
  onSaved,
  height = 460,
}: {
  rows: TrackerRow[];
  columns: TrackerColumn[];
  role: Role;
  onSaved: () => void;
  height?: number;
}) {
  const { theme } = useTheme();
  const canEdit = canUseExcelView(role);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [gridEpoch, setGridEpoch] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dirtyCount, setDirtyCount] = useState(0);
  const changesRef = useRef<Map<number, Record<string, unknown>>>(new Map());

  const rowData: Row[] = useMemo(
    () => rows.map((r) => ({ __id: r.id, ...r.data })),
    [rows],
  );

  const columnDefs: ColDef[] = useMemo(
    () =>
      columns.map((c) => {
        const canEditThis = canUseExcelView(role) && canEditField(role, c);
        // While editing, a column this role cannot write is greyed out and
        // says why on hover - otherwise the only way to find out is to
        // double-click it and watch nothing happen.
        const locked = editing && !canEditThis;
        const reason = lockReason(role, c);
        return {
        field: c.key,
        headerName: c.label,
        editable: editing && canEditThis,
        minWidth: 130,
        cellClass: locked ? "tg-locked" : undefined,
        headerClass: [
          c.source === "buyer"
            ? "tg-head-buyer"
            : c.source === "vendor"
              ? "tg-head-vendor"
              : c.source === "calc" || c.source === "const"
                ? "tg-head-derived"
                : "",
          locked ? "tg-head-locked" : "",
        ].filter(Boolean).join(" ") || undefined,
        headerTooltip: locked ? reason ?? "Read-only for your role" : undefined,
        tooltipValueGetter: locked
          ? () => reason ?? "Read-only for your role"
          : undefined,
        cellEditor:
          c.type === "number"
            ? "agNumberCellEditor"
            : "agTextCellEditor",
        cellDataType: false,
        ...(c.type === "date"
          ? {
              valueFormatter: (p: { value: unknown }) => toDisplayDate(p.value),
              valueParser: (p: { newValue: unknown }) => toIsoDate(p.newValue),
              cellEditorParams: { useFormatter: true },
            }
          : {}),
        } as ColDef;
      }),
    [columns, editing, role],
  );

  const onCellValueChanged = (event: CellValueChangedEvent) => {
    const row = event.data as Row;
    const key = event.colDef.field as string;
    const current = changesRef.current.get(row.__id) ?? {};
    // undefined / "" both mean "cleared" — send null so the value is really removed
    const v = event.newValue;
    current[key] = v === undefined || v === "" ? null : v;
    changesRef.current.set(row.__id, current);
    setDirtyCount([...changesRef.current.values()].reduce((n, c) => n + Object.keys(c).length, 0));
  };

  /** Delete / Backspace on a focused cell clears it (AG Grid Community has no
   * built-in clear-on-delete). Writes null so the field really empties. */
  const onCellKeyDown = (event: CellKeyDownEvent) => {
    const ke = event.event as KeyboardEvent | null;
    if (!ke || (ke.key !== "Delete" && ke.key !== "Backspace")) return;
    if (event.colDef.editable !== true) return;
    const key = event.colDef.field;
    if (!key || !event.node) return;
    ke.preventDefault();
    if ((event.node.data as Row)?.[key] == null) return;
    event.node.setDataValue(key, null); // fires onCellValueChanged
  };

  const cancel = () => {
    changesRef.current.clear();
    setDirtyCount(0);
    setEditing(false);
    setGridEpoch((n) => n + 1);
  };

  const save = async () => {
    if (changesRef.current.size === 0) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updates: Record<number, Record<string, unknown>> = {};
      for (const [id, changed] of changesRef.current) updates[id] = changed;
      await api("/api/tracker/lines", {
        method: "PATCH",
        body: JSON.stringify({ updates }),
      });
      changesRef.current.clear();
      setDirtyCount(0);
      setEditing(false);
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <p className="text-xs text-slate-500">
          {editing
            ? "Double-click a cell to edit, or select it and press Delete to clear. Blue = buyer, green = vendor, grey = derived. Hatched columns are read-only for your role — hover one to see why."
            : "Read-only view. " + (canEdit ? "Click Edit to change values." : "")}
        </p>
        <div className="ml-auto flex gap-2">
          {editing ? (
            <>
              <Button variant="ghost" disabled={saving} onClick={cancel}>
                Cancel
              </Button>
              <Button disabled={saving} onClick={save}>
                {saving ? "Saving…" : `Save${dirtyCount ? ` (${dirtyCount})` : ""}`}
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
      {error && <ErrorNote message={error} />}
      <style>{`
        .tg-head-buyer{background:#eff6ff}
        .tg-head-vendor{background:#ecfdf5}
        .tg-head-derived{background:#f8fafc;font-style:italic}
        /* Read-only for this role: faint diagonal hatching reads as "not
           available" even to someone who cannot pick the grey out. */
        .tg-locked{
          color:#94a3b8;
          cursor:not-allowed;
          background-image:repeating-linear-gradient(45deg,rgba(100,116,139,.10) 0 4px,transparent 4px 8px);
        }
        .tg-head-locked{opacity:.7}
        .dark .tg-head-buyer{background:#172554}
        .dark .tg-head-vendor{background:#052e2b}
        .dark .tg-head-derived{background:#0f172a;font-style:italic}
        .dark .tg-locked{
          color:#64748b;
          background-image:repeating-linear-gradient(45deg,rgba(148,163,184,.12) 0 4px,transparent 4px 8px);
        }
      `}</style>
      <div style={{ height }}>
        <AgGridReact
          key={gridEpoch}
          theme={theme === "dark" ? darkTheme : lightTheme}
          columnDefs={columnDefs}
          rowData={rowData}
          defaultColDef={{ resizable: true, sortable: true, filter: false }}
          enableBrowserTooltips
          onCellValueChanged={onCellValueChanged}
          onCellKeyDown={onCellKeyDown}
          animateRows={false}
          getRowId={(p) => String((p.data as Row).__id)}
        />
      </div>
    </div>
  );
}
