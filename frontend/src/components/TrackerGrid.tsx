"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule,
  ModuleRegistry,
  colorSchemeDark,
  themeQuartz,
  type CellKeyDownEvent,
  type CellValueChangedEvent,
  type ColDef,
  type GridApi,
  type GridReadyEvent,
  type IRowNode,
} from "ag-grid-community";
import { api, ApiError } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { Role, TrackerColumn, TrackerRow } from "@/lib/types";
import { canUseExcelView, lockReason } from "@/lib/permissions";
import { Button, ErrorNote } from "@/components/ui";
import { toDisplayDate, toIsoDate } from "@/lib/dateFormat";
import { cellClassRulesFor, isoToNumber, trackerRowClass } from "@/lib/trackerHighlights";
import { SetFilter } from "@/components/SetFilter";

ModuleRegistry.registerModules([AllCommunityModule]);

const nf = new Intl.NumberFormat();
const money = (n: number) =>
  n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const lightTheme = themeQuartz;
const darkTheme = themeQuartz.withPart(colorSchemeDark);

type Row = Record<string, unknown> & { __id: number; __hasVendorData: boolean };

/** The Excel status-bar answer: what is this set of rows worth? */
type Totals = { count: number; qty: number; buyer: number; vendor: number; diff: number };
const EMPTY_TOTALS: Totals = { count: 0, qty: 0, buyer: 0, vendor: 0, diff: 0 };

/** Frozen to the left while you scroll. Deliberately narrower than the row's
 * identity: every pinned column is width the other 50-odd never get back. */
const PINNED_COLUMNS = ["buyer_po", "style_no"];

/** Never hidden by a field projection - without these you cannot tell which
 * shipment a row is, whatever else the chips are showing. Colour stays here
 * even though it is not pinned: it still identifies the row, it just does not
 * need to follow you across the sheet. */
const IDENTITY_COLUMNS = ["buyer_po", "style_no", "colour"];

/** Excel-style grid over tracker rows: one row per shipment line, one column
 * per tracker column. Edits accumulate per row and save via PATCH /tracker/lines. */
export function TrackerGrid({
  rows,
  columns,
  role,
  onSaved,
  height = 460,
  quickFilterText = "",
  visibleKeys = null,
  filterModel = null,
  onApiReady,
}: {
  rows: TrackerRow[];
  columns: TrackerColumn[];
  role: Role;
  onSaved: () => void;
  height?: number;
  quickFilterText?: string;
  /** Field chips: show only these columns. null shows every column. */
  visibleKeys?: string[] | null;
  /** Filter chips, already translated to an AG Grid filter model. */
  filterModel?: Record<string, unknown> | null;
  /** Hands the grid API up so saved views can capture and restore column state. */
  onApiReady?: (api: GridApi) => void;
}) {
  const { theme } = useTheme();
  const canEdit = canUseExcelView(role);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  // Bumping this rebuilds rowData from `rows`, discarding in-grid edits. It
  // used to remount the whole grid via `key`, which also threw away every
  // filter, sort, pin and column width the user had set up.
  const [dataEpoch, setDataEpoch] = useState(0);
  const [highlight, setHighlight] = useState(true);
  const [totals, setTotals] = useState<Totals>(EMPTY_TOTALS);
  const apiRef = useRef<GridApi | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dirtyCount, setDirtyCount] = useState(0);
  const changesRef = useRef<Map<number, Record<string, unknown>>>(new Map());

  const vendorKeys = useMemo(
    () => columns.filter((c) => c.source === "vendor").map((c) => c.key),
    [columns],
  );

  const rowData: Row[] = useMemo(
    // eslint-disable-next-line react-hooks/exhaustive-deps -- dataEpoch is the cancel signal
    () =>
      rows.map((r) => ({
        __id: r.id,
        // Whether the factory side has any values, NOT r.has_vendor. That flag
        // records "a vendor sheet was reconciled in", which stays false when
        // the same details arrive by paste - so a row could show a factory and
        // still be marked as awaiting one.
        __hasVendorData: vendorKeys.some(
          (k) => r.data[k] !== undefined && r.data[k] !== null && r.data[k] !== "",
        ),
        ...r.data,
      })),
    [rows, dataEpoch, vendorKeys],
  );

  const columnDefs: ColDef[] = useMemo(
    () =>
      columns.map((c) => {
        const canEditThis = canUseExcelView(role) && c.editable;
        // While editing, a column this role cannot write is greyed out and
        // says why on hover - otherwise the only way to find out is to
        // double-click it and watch nothing happen.
        const locked = editing && !canEditThis;
        const reason = lockReason(c);
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
        // PO# and Style stay put while you scroll right - Excel's freeze panes.
        // Colour is not pinned: it is part of the row's identity but rarely the
        // part you need mid-scroll, and pinned width is taken from the 50-odd
        // columns you are scrolling to reach.
        pinned: PINNED_COLUMNS.includes(c.key) ? ("left" as const) : undefined,
        // Identity is never hidden by a projection: without PO#/Style/Colour
        // the remaining columns cannot be attributed to a shipment.
        hide: visibleKeys
          ? !visibleKeys.includes(c.key) && !IDENTITY_COLUMNS.includes(c.key)
          : false,
        // Type-aware filters + the always-visible floating filter row. This is
        // the Excel autofilter bar; it was switched off by `filter: false`.
        // Text columns get the tick-list; numbers and dates keep their range
        // filters, which say more about a quantity than a list of values would.
        filter:
          c.type === "number"
            ? "agNumberColumnFilter"
            : c.type === "date"
              ? "agDateColumnFilter"
              : SetFilter,
        cellClassRules: highlight ? cellClassRulesFor(c.key) : undefined,
        ...(c.type === "date"
          ? {
              valueFormatter: (p: { value: unknown }) => toDisplayDate(p.value),
              valueParser: (p: { newValue: unknown }) => toIsoDate(p.newValue),
              cellEditorParams: { useFormatter: true },
              // Dates are stored ISO but shown dd-mm-yyyy. The quick filter
              // matches the stored value by default, so searching the date you
              // can actually see on screen would find nothing. Offer both.
              getQuickFilterText: (p: { value: unknown }) => {
                const shown = toDisplayDate(p.value);
                const raw = p.value == null ? "" : String(p.value);
                return shown && shown !== raw ? `${shown} ${raw}` : raw;
              },
              // Cells hold ISO strings, and agDateColumnFilter compares Dates -
              // without this the date filters silently match nothing.
              filterParams: {
                comparator: (filterDate: Date, cellValue: unknown) => {
                  const cell = isoToNumber(cellValue);
                  if (cell === null) return -1;
                  const f =
                    filterDate.getFullYear() * 10000 +
                    (filterDate.getMonth() + 1) * 100 +
                    filterDate.getDate();
                  return cell < f ? -1 : cell > f ? 1 : 0;
                },
              },
            }
          : {}),
        } as ColDef;
      }),
    [columns, editing, role, highlight, visibleKeys],
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

  /** Totals over the selected rows, or over everything the filters left if
   * nothing is selected - the number Excel puts in the status bar when you drag
   * across a column. */
  const recomputeTotals = useCallback(() => {
    const grid = apiRef.current;
    if (!grid) return;
    const selected = grid.getSelectedNodes();
    const nodes: IRowNode[] = [];
    if (selected.length > 0) nodes.push(...selected);
    else grid.forEachNodeAfterFilter((n) => nodes.push(n));

    const sum = (key: string) =>
      nodes.reduce((acc, n) => {
        const v = Number((n.data as Row | undefined)?.[key]);
        return acc + (Number.isFinite(v) ? v : 0);
      }, 0);

    setTotals({
      count: nodes.length,
      qty: sum("order_qty"),
      buyer: sum("buyer_total_value"),
      vendor: sum("vendor_total_value"),
      diff: sum("price_difference"),
    });
  }, []);

  // Chips and the floating filter row are one state, not two: chips write into
  // the same model the header row edits. Merged rather than replaced, and only
  // the keys chips previously owned are withdrawn - otherwise adding a chip
  // would silently wipe a filter the user had set by hand in the header row.
  const chipFilterKeys = useRef<string[]>([]);
  useEffect(() => {
    const grid = apiRef.current;
    if (!grid) return;
    const next: Record<string, unknown> = { ...(grid.getFilterModel() ?? {}) };
    for (const key of chipFilterKeys.current) {
      if (!filterModel || !(key in filterModel)) delete next[key];
    }
    Object.assign(next, filterModel ?? {});
    chipFilterKeys.current = Object.keys(filterModel ?? {});
    grid.setFilterModel(Object.keys(next).length ? next : null);
  }, [filterModel]);

  const onGridReady = (event: GridReadyEvent) => {
    apiRef.current = event.api;
    onApiReady?.(event.api);
    recomputeTotals();
  };

  const cancel = () => {
    changesRef.current.clear();
    setDirtyCount(0);
    setEditing(false);
    // Rebuild the row data rather than remounting the grid: a remount would
    // also discard the user's filters, pins, sort and column widths.
    setDataEpoch((n) => n + 1);
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
        {highlight && (
          <p className="text-xs text-slate-400">
            <span className="mr-1 inline-block h-2.5 w-1 translate-y-px bg-rose-500 align-middle" />
            needs attention
            <span className="ml-3 mr-1 inline-block h-2.5 w-1 translate-y-px bg-amber-500 align-middle" />
            overdue or off-quantity
            <span className="ml-3 mr-1 inline-block h-2.5 w-1 translate-y-px bg-slate-400 align-middle" />
            awaiting the factory side
          </p>
        )}
        <div className="ml-auto flex items-center gap-2">
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              checked={highlight}
              onChange={(e) => setHighlight(e.target.checked)}
              className="h-3.5 w-3.5 accent-blue-600"
            />
            Highlight issues
          </label>
          <Button
            variant="ghost"
            onClick={() => {
              apiRef.current?.setFilterModel(null);
              apiRef.current?.deselectAll();
            }}
          >
            Clear filters
          </Button>
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
        /* Conditional formatting. Tinted background plus a left rule, so the
           signal survives greyscale and the commoner colour-vision deficiencies
           rather than resting on red-vs-amber alone. */
        .tg-bad{background:#fef2f2;box-shadow:inset 3px 0 0 #dc2626}
        .tg-warn{background:#fffbeb;box-shadow:inset 3px 0 0 #d97706}
        /* Awaiting the factory side. A left edge marker, not dimming: greyed
           text reads as "you cannot touch this", and these rows are editable. */
        .tg-row-novendor .ag-cell:first-child{box-shadow:inset 3px 0 0 #94a3b8}
        .dark .tg-head-buyer{background:#172554}
        .dark .tg-head-vendor{background:#052e2b}
        .dark .tg-head-derived{background:#0f172a;font-style:italic}
        .dark .tg-row-novendor .ag-cell:first-child{box-shadow:inset 3px 0 0 #475569}
        .dark .tg-bad{background:#450a0a;box-shadow:inset 3px 0 0 #f87171}
        .dark .tg-warn{background:#422006;box-shadow:inset 3px 0 0 #fbbf24}
        .dark .tg-locked{
          color:#64748b;
          background-image:repeating-linear-gradient(45deg,rgba(148,163,184,.12) 0 4px,transparent 4px 8px);
        }
      `}</style>
      <div style={{ height }}>
        <AgGridReact
          theme={theme === "dark" ? darkTheme : lightTheme}
          columnDefs={columnDefs}
          rowData={rowData}
          defaultColDef={{
            resizable: true,
            sortable: true,
            filter: true,
            floatingFilter: true,
          }}
          quickFilterText={quickFilterText}
          enableBrowserTooltips
          onGridReady={onGridReady}
          onCellValueChanged={onCellValueChanged}
          onCellKeyDown={onCellKeyDown}
          onFilterChanged={recomputeTotals}
          onSelectionChanged={recomputeTotals}
          onRowDataUpdated={recomputeTotals}
          // Click-to-select would fight cell editing, so it is only on while
          // reading. Ctrl/shift-click to build a set, as in a spreadsheet.
          rowSelection={{
            mode: "multiRow",
            checkboxes: false,
            headerCheckbox: false,
            enableClickSelection: !editing,
          }}
          getRowClass={highlight ? trackerRowClass : undefined}
          animateRows={false}
          getRowId={(p) => String((p.data as Row).__id)}
        />
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-slate-600 dark:text-slate-300">
        <span className="font-medium">
          {totals.count === rowData.length
            ? `${nf.format(totals.count)} rows`
            : `${nf.format(totals.count)} of ${nf.format(rowData.length)} rows`}
        </span>
        <span>Order qty <b className="tabular-nums">{nf.format(totals.qty)}</b></span>
        <span>Buyer value <b className="tabular-nums">{money(totals.buyer)}</b></span>
        <span>Vendor value <b className="tabular-nums">{money(totals.vendor)}</b></span>
        <span>
          Price diff{" "}
          <b className={`tabular-nums ${totals.diff < 0 ? "text-rose-600 dark:text-rose-400" : ""}`}>
            {money(totals.diff)}
          </b>
        </span>
      </div>
    </div>
  );
}
