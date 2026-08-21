"use client";

import { useCallback, useMemo, useState } from "react";
import { useGridFilter, type CustomFilterProps } from "ag-grid-react";
import type { IRowNode } from "ag-grid-community";

/** The Excel autofilter dropdown: tick the values you want to keep.
 *
 * AG Grid's own Set Filter is an Enterprise feature. This is the Community
 * equivalent, which is viable here because the whole tracker is already in
 * memory - distinct values are a Set over the loaded rows, not a query.
 */

export type SetFilterModel = { values: string[] };

/** Empty cells are a value people filter on, so they need a name. Using a
 * sentinel rather than "" keeps them distinguishable from a real empty string. */
const BLANK = "\u0000blank";
const BLANK_LABEL = "(Blanks)";

export function SetFilter({
  model,
  onModelChange,
  getValue,
  api,
  doesRowPassOtherFilter,
}: CustomFilterProps<unknown, unknown, SetFilterModel>) {
  const [search, setSearch] = useState("");

  const asKey = useCallback(
    (node: IRowNode) => {
      const v = getValue(node);
      return v === null || v === undefined || v === "" ? BLANK : String(v);
    },
    [getValue],
  );

  const doesFilterPass = useCallback(
    ({ node }: { node: IRowNode }) => !model || model.values.includes(asKey(node)),
    [model, asKey],
  );

  useGridFilter({
    doesFilterPass,
    getModelAsString: () => {
      if (!model) return "";
      const shown = model.values.map((v) => (v === BLANK ? BLANK_LABEL : v));
      return shown.length <= 2 ? shown.join(", ") : `${shown.length} selected`;
    },
  });

  /** Distinct values, narrowed to what the *other* filters still allow - the
   * same behaviour as Excel, where the dropdown shrinks as you filter
   * elsewhere. Counts come along so the list is informative, not just a list. */
  const options = useMemo(() => {
    const counts = new Map<string, number>();
    api.forEachNode((node) => {
      if (!doesRowPassOtherFilter(node)) return;
      const key = asKey(node);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    });
    return [...counts.entries()]
      .map(([value, count]) => ({ value, count, label: value === BLANK ? BLANK_LABEL : value }))
      .sort((a, b) =>
        a.value === BLANK ? 1 : b.value === BLANK ? -1 : a.label.localeCompare(b.label),
      );
  }, [api, asKey, doesRowPassOtherFilter]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return q ? options.filter((o) => o.label.toLowerCase().includes(q)) : options;
  }, [options, search]);

  // null model means "everything", which is also what an all-ticked list means
  const selected = useMemo(
    () => new Set(model ? model.values : options.map((o) => o.value)),
    [model, options],
  );

  const commit = (next: Set<string>) => {
    onModelChange(next.size === options.length ? null : { values: [...next] });
  };

  const toggle = (value: string) => {
    const next = new Set(selected);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    commit(next);
  };

  return (
    <div className="w-60 p-2 text-sm">
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search values…"
        className="mb-2 w-full rounded border border-slate-300 px-2 py-1 text-xs outline-none focus:border-blue-500 dark:border-slate-600 dark:bg-slate-800"
      />
      <div className="mb-1 flex gap-2 text-xs">
        <button
          type="button"
          className="text-blue-600 hover:underline"
          onClick={() => commit(new Set(visible.map((o) => o.value)))}
        >
          Select {search ? "matching" : "all"}
        </button>
        <button
          type="button"
          className="text-blue-600 hover:underline"
          onClick={() => onModelChange({ values: [] })}
        >
          Clear
        </button>
        <span className="ml-auto text-slate-400">{visible.length}</span>
      </div>
      <ul className="max-h-56 overflow-auto">
        {visible.map((o) => (
          <li key={o.value}>
            <label className="flex cursor-pointer items-center gap-2 px-1 py-0.5 hover:bg-slate-50 dark:hover:bg-slate-800">
              <input
                type="checkbox"
                checked={selected.has(o.value)}
                onChange={() => toggle(o.value)}
                className="h-3.5 w-3.5 accent-blue-600"
              />
              <span className={`flex-1 truncate ${o.value === BLANK ? "italic text-slate-400" : ""}`}>
                {o.label}
              </span>
              <span className="text-xs tabular-nums text-slate-400">{o.count}</span>
            </label>
          </li>
        ))}
        {visible.length === 0 && (
          <li className="px-1 py-2 text-xs text-slate-400">No values match.</li>
        )}
      </ul>
    </div>
  );
}
