"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiDownload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canViewTracker } from "@/lib/permissions";
import { Button, Card, Spinner, ErrorNote } from "@/components/ui";
import { TrackerGrid } from "@/components/TrackerGrid";
import { FieldChipBar } from "@/components/FieldChipBar";
import { SavedViewsBar } from "@/components/SavedViewsBar";
import { deleteView, loadViews, saveView, type SavedView } from "@/lib/savedViews";
import type { GridApi } from "ag-grid-community";
import {
  chipsToFilterModel,
  quickFilterFromChips,
  visibleKeysFromChips,
  vocabularyFromColumns,
  type Chip,
} from "@/lib/fieldVocabulary";
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
  const [chips, setChips] = useState<Chip[]>([]);
  const [views, setViews] = useState<SavedView[]>([]);
  const [activeView, setActiveView] = useState<string | null>(null);
  const gridApiRef = useRef<GridApi | null>(null);
  const allowed = !!user && canViewTracker(user.role);

  // localStorage is only readable on the client, so views load after mount
  useEffect(() => {
    if (user) setViews(loadViews(user.id));
  }, [user]);

  const handleSaveView = useCallback(
    (name: string) => {
      const grid = gridApiRef.current;
      if (!user || !grid) return;
      setViews(
        saveView(user.id, {
          name,
          chips,
          columnState: grid.getColumnState(),
          filterModel: grid.getFilterModel() ?? {},
          savedAt: new Date().toISOString(),
        }),
      );
      setActiveView(name);
    },
    [user, chips],
  );

  const handleApplyView = useCallback((view: SavedView) => {
    const grid = gridApiRef.current;
    setChips(view.chips);
    setActiveView(view.name);
    if (!grid) return;
    // order matters: chips re-derive their own filters on the next effect, so
    // the column state goes on first and the saved model is applied after.
    grid.applyColumnState({ state: view.columnState as never, applyOrder: true });
    grid.setFilterModel(Object.keys(view.filterModel).length ? view.filterModel : null);
  }, []);

  const handleDeleteView = useCallback(
    (name: string) => {
      if (!user) return;
      setViews(deleteView(user.id, name));
      setActiveView((current) => (current === name ? null : current));
    },
    [user],
  );

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

  const cols = useMemo(() => columns.data ?? [], [columns.data]);
  const vocabulary = useMemo(() => vocabularyFromColumns(cols), [cols]);

  // Presets come from the column's own `source`, the same grouping the per-PO
  // view uses, so there is no second taxonomy to keep in step. The typed bar is
  // the power path; these are the discoverable one.
  const presets = useMemo(() => {
    const of = (...sources: TrackerColumn["source"][]) =>
      cols.filter((c) => sources.includes(c.source)).map((c) => c.key);
    return [
      { label: "Buyer", keys: of("buyer", "const") },
      { label: "Vendor", keys: of("vendor", "calc") },
      { label: "Shipping", keys: of("operational") },
      { label: "Money", keys: cols.filter((c) => c.is_price).map((c) => c.key) },
    ].filter((p) => p.keys.length > 0);
  }, [cols]);

  const visibleKeys = useMemo(() => visibleKeysFromChips(chips), [chips]);
  const filterModel = useMemo(() => chipsToFilterModel(chips), [chips]);
  const quickFilter = useMemo(() => quickFilterFromChips(chips), [chips]);

  if (user && !allowed)
    return <ErrorNote message="Your role does not have access to the shipment tracker." />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">Shipment Tracker</h1>
        <Button
          variant="secondary"
          onClick={() => {
            const grid = gridApiRef.current;
            // Export what is on screen: the filtered rows in their displayed
            // order, and only the visible columns. Falls back to the whole
            // sheet before the grid is ready.
            const rowIds: number[] = [];
            grid?.forEachNodeAfterFilterAndSort((node) => {
              const id = (node.data as { __id?: number } | undefined)?.__id;
              if (typeof id === "number") rowIds.push(id);
            });
            const keys = grid
              ?.getAllDisplayedColumns()
              .map((c) => c.getColId())
              .filter((k) => k !== "__id");
            apiDownload(
              "/api/tracker/export",
              `Shipment Tracker ${todayDdMmYyyy()}.xlsx`,
              grid ? { row_ids: rowIds, keys } : { row_ids: null, keys: null },
            );
          }}
        >
          Download .xlsx
        </Button>
      </div>

      <FieldChipBar
        vocabulary={vocabulary}
        chips={chips}
        onChange={(next) => {
          setChips(next);
          setActiveView(null); // the view no longer matches what is on screen
        }}
        presets={presets}
      />

      <SavedViewsBar
        views={views}
        activeName={activeView}
        onApply={handleApplyView}
        onSave={handleSaveView}
        onDelete={handleDeleteView}
      />

      {(columns.error || rows.error) && (
        <ErrorNote message={((columns.error || rows.error) as Error).message} />
      )}

      <Card>
        {columns.isLoading || rows.isLoading ? (
          <Spinner />
        ) : (
          <TrackerGrid
            rows={rows.data ?? []}
            columns={cols}
            role={user!.role}
            quickFilterText={quickFilter}
            visibleKeys={visibleKeys}
            filterModel={filterModel}
            onApiReady={(gridApi) => { gridApiRef.current = gridApi; }}
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
