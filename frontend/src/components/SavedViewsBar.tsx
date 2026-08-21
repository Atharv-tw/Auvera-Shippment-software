"use client";

import { useState } from "react";
import type { SavedView } from "@/lib/savedViews";

/** Load, save and delete named tracker layouts.
 *
 * The point is that nobody rebuilds a filter set every morning - in Excel they
 * keep a filtered copy of the file. This is that, without the copy.
 */
export function SavedViewsBar({
  views,
  activeName,
  onApply,
  onSave,
  onDelete,
}: {
  views: SavedView[];
  activeName: string | null;
  onApply: (view: SavedView) => void;
  onSave: (name: string) => void;
  onDelete: (name: string) => void;
}) {
  const [naming, setNaming] = useState(false);
  const [draft, setDraft] = useState("");

  const commit = () => {
    const name = draft.trim();
    if (name) onSave(name);
    setDraft("");
    setNaming(false);
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <span className="text-slate-400">Views:</span>

      {views.length === 0 && !naming && (
        <span className="text-slate-400">none saved yet</span>
      )}

      {views.map((v) => (
        <span
          key={v.name}
          className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 ${
            v.name === activeName
              ? "border-blue-500 bg-blue-50 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200"
              : "border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-300"
          }`}
        >
          <button type="button" onClick={() => onApply(v)} title={`Saved ${new Date(v.savedAt).toLocaleString()}`}>
            {v.name}
          </button>
          <button
            type="button"
            aria-label={`Delete view ${v.name}`}
            className="opacity-50 hover:opacity-100"
            onClick={() => onDelete(v.name)}
          >
            ×
          </button>
        </span>
      ))}

      {naming ? (
        <span className="inline-flex items-center gap-1">
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit();
              if (e.key === "Escape") { setDraft(""); setNaming(false); }
            }}
            onBlur={commit}
            placeholder="View name…"
            aria-label="Name for this view"
            className="w-32 rounded border border-slate-300 px-1.5 py-0.5 outline-none focus:border-blue-500 dark:border-slate-600 dark:bg-slate-800"
          />
        </span>
      ) : (
        <button
          type="button"
          onClick={() => setNaming(true)}
          className="rounded border border-dashed border-slate-300 px-2 py-0.5 text-slate-500 hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-800"
        >
          + Save current view
        </button>
      )}
    </div>
  );
}
