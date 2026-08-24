"use client";

import { useCallback, useMemo, useState } from "react";
import {
  useGridFilter,
  type CustomFilterProps,
  type CustomFloatingFilterProps,
} from "ag-grid-react";
import type { IRowNode } from "ag-grid-community";

/** The Excel autofilter dropdown: tick the values you want to keep.
 *
 * AG Grid's own Set Filter is an Enterprise feature. This is the Community
 * equivalent, which is viable here because the whole tracker is already in
 * memory - distinct values are a Set over the loaded rows, not a query.
 */

export type SetFilterModel = { values: string[] };

/** Text filters also arrive on these columns - the chip bar emits
 * `factory = CRIMSON` as a text model, and a saved view may carry one. Rather
 * than let the two representations fight (or crash on a missing `values`),
 * this filter understands both and renders the tick list either way. */
type TextModel = { filterType?: string; type?: string; filter?: string };
type IncomingModel = SetFilterModel | TextModel | null;

function isSetModel(model: IncomingModel): model is SetFilterModel {
  return !!model && Array.isArray((model as SetFilterModel).values);
}

function textMatches(model: TextModel, value: string): boolean {
  const needle = String(model.filter ?? "").toLowerCase();
  const hay = value.toLowerCase();
  switch (model.type) {
    case "notEqual": return hay !== needle;
    case "contains": return hay.includes(needle);
    case "notContains": return !hay.includes(needle);
    case "startsWith": return hay.startsWith(needle);
    case "endsWith": return hay.endsWith(needle);
    case "blank": return value === BLANK;
    case "notBlank": return value !== BLANK;
    default: return hay === needle;
  }
}

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
}: CustomFilterProps<unknown, unknown, IncomingModel>) {
  const [search, setSearch] = useState("");

  const asKey = useCallback(
    (node: IRowNode) => {
      const v = getValue(node);
      return v === null || v === undefined || v === "" ? BLANK : String(v);
    },
    [getValue],
  );

  const doesFilterPass = useCallback(
    ({ node }: { node: IRowNode }) => {
      if (!model) return true;
      const value = asKey(node);
      return isSetModel(model) ? model.values.includes(value) : textMatches(model, value);
    },
    [model, asKey],
  );

  useGridFilter({
    doesFilterPass,
    getModelAsString: () => {
      if (!model) return "";
      if (!isSetModel(model)) return `${model.type ?? "equals"} ${model.filter ?? ""}`.trim();
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

  // null model means "everything", which is also what an all-ticked list means.
  // A text model has no value list, so the ticks are derived from what it
  // actually matches - the list then reads as the equivalent selection.
  const selected = useMemo(() => {
    if (!model) return new Set(options.map((o) => o.value));
    if (isSetModel(model)) return new Set(model.values);
    return new Set(options.filter((o) => textMatches(model, o.value)).map((o) => o.value));
  }, [model, options]);

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

/** Short read-only label of a tick-list selection, for the header row. */
function summarize(model: SetFilterModel): string {
  const shown = model.values.map((v) => (v === BLANK ? BLANK_LABEL : v));
  if (shown.length === 0) return "(none)";
  return shown.length <= 2 ? shown.join(", ") : `${shown.length} selected`;
}

/** The editable box in the header's floating-filter row. Without it AG Grid
 * gives a custom filter a read-only placeholder, so text columns could only be
 * filtered by opening the dropdown. Typing here emits a `contains` text model,
 * which `SetFilter` already matches; the dropdown's tick-list keeps working and
 * shows here as a read-only summary (its selection isn't editable as text). */
export function SetFloatingFilter({
  model,
  onModelChange,
}: CustomFloatingFilterProps<unknown, unknown, IncomingModel>) {
  const isSet = isSetModel(model);
  const text = model && !isSet ? String((model as TextModel).filter ?? "") : "";

  const onInput = (value: string) => {
    onModelChange(
      value === "" ? null : { filterType: "text", type: "contains", filter: value },
    );
  };

  return (
    <input
      type="search"
      // A tick-list selection can't be shown as editable text, so surface it as
      // a placeholder hint instead - typing over it switches to a text filter.
      value={text}
      placeholder={isSet ? summarize(model as SetFilterModel) : "Search…"}
      onChange={(e) => onInput(e.target.value)}
      className="w-full rounded border border-slate-300 bg-transparent px-1 py-0.5 text-xs outline-none focus:border-blue-500 dark:border-slate-600"
    />
  );
}
