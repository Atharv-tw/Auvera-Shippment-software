"use client";

import { useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule,
  ModuleRegistry,
  colorSchemeDark,
  themeQuartz,
  type CellValueChangedEvent,
  type ColDef,
} from "ag-grid-community";
import { api, ApiError } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { TrackerColumn, TrackerRow } from "@/lib/types";
import { Button, ErrorNote } from "@/components/ui";

ModuleRegistry.registerModules([AllCommunityModule]);

const lightTheme = themeQuartz;
const darkTheme = themeQuartz.withPart(colorSchemeDark);

type Row = Record<string, unknown> & { __id: number };

/** Excel-style grid over tracker rows: one row per shipment line, one column
 * per tracker column. Edits accumulate per row and save via PATCH /tracker/lines. */
export function TrackerGrid({
  rows,
  columns,
  canEdit,
  onSaved,
  height = 460,
}: {
  rows: TrackerRow[];
  columns: TrackerColumn[];
  canEdit: boolean;
  onSaved: () => void;
  height?: number;
}) {
  const { theme } = useTheme();
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
      columns.map((c) => ({
        field: c.key,
        headerName: c.label,
        editable: editing && canEdit,
        minWidth: 130,
        headerClass:
          c.source === "buyer"
            ? "tg-head-buyer"
            : c.source === "vendor"
              ? "tg-head-vendor"
              : c.source === "calc" || c.source === "const"
                ? "tg-head-derived"
                : undefined,
        cellEditor:
          c.type === "number"
            ? "agNumberCellEditor"
            : "agTextCellEditor",
        cellDataType: false,
      })),
    [columns, editing, canEdit],
  );

  const onCellValueChanged = (event: CellValueChangedEvent) => {
    const row = event.data as Row;
    const key = event.colDef.field as string;
    const current = changesRef.current.get(row.__id) ?? {};
    current[key] = event.newValue === undefined ? null : event.newValue;
    changesRef.current.set(row.__id, current);
    setDirtyCount([...changesRef.current.values()].reduce((n, c) => n + Object.keys(c).length, 0));
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
            ? "Double-click a cell to edit. Blue = buyer, green = vendor, grey = derived."
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
      <style>{`.tg-head-buyer{background:#eff6ff}.tg-head-vendor{background:#ecfdf5}.tg-head-derived{background:#f8fafc;font-style:italic}`}</style>
      <div style={{ height }}>
        <AgGridReact
          key={gridEpoch}
          theme={theme === "dark" ? darkTheme : lightTheme}
          columnDefs={columnDefs}
          rowData={rowData}
          defaultColDef={{ resizable: true, sortable: true, filter: false }}
          onCellValueChanged={onCellValueChanged}
          animateRows={false}
          getRowId={(p) => String((p.data as Row).__id)}
        />
      </div>
    </div>
  );
}
