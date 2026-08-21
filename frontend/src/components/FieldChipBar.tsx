"use client";

import { useMemo, useRef, useState } from "react";
import {
  chipId,
  chipLabel,
  parseChip,
  searchVocabulary,
  type Chip,
  type FieldEntry,
} from "@/lib/fieldVocabulary";

/** Typed field/filter picker, shared by the tracker grid and the per-PO view.
 *
 * "Show me only these fields" and "show me only these rows" are the same
 * gesture to a user, so they are the same control here: a field chip projects a
 * column, a filter chip narrows the rows.
 *
 * Chips commit atomically. Comma is one of the commit keys, but it is never a
 * delimiter - tracker column AV is named "Approval, Carting, DO date" and
 * remarks hold commas, so splitting on them would mangle real values.
 */
export function FieldChipBar({
  vocabulary,
  chips,
  onChange,
  presets,
  placeholder = "Add a field, or filter like  factory = CRIMSON …",
}: {
  vocabulary: FieldEntry[];
  chips: Chip[];
  onChange: (chips: Chip[]) => void;
  presets?: { label: string; keys: string[] }[];
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");
  const [highlighted, setHighlighted] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const suggestions = useMemo(
    () => searchVocabulary(vocabulary, draft),
    [vocabulary, draft],
  );
  // A partially typed filter ("factory = CRIM") should not offer field
  // suggestions - the user is past choosing the field.
  const typingFilter = /[<>=~!]/.test(draft);
  const open = draft.trim().length > 0 && suggestions.length > 0 && !typingFilter;

  const add = (chip: Chip | null) => {
    if (!chip) return;
    const id = chipId(chip);
    if (!chips.some((c) => chipId(c) === id)) onChange([...chips, chip]);
    setDraft("");
    setHighlighted(0);
  };

  const commitDraft = () => add(parseChip(draft, vocabulary));

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" && open) {
      e.preventDefault();
      setHighlighted((h) => Math.min(h + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp" && open) {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter" || e.key === "Tab" || e.key === ",") {
      if (!draft.trim()) return;
      e.preventDefault();
      const picked = open ? suggestions[highlighted] : undefined;
      if (picked) add({ kind: "field", key: picked.key, label: picked.label });
      else commitDraft();
    } else if (e.key === "Backspace" && !draft && chips.length) {
      onChange(chips.slice(0, -1));
    } else if (e.key === "Escape") {
      setDraft("");
    }
  };

  const applyPreset = (keys: string[]) => {
    const byKey = new Map(vocabulary.map((v) => [v.key, v]));
    const next = [...chips];
    for (const key of keys) {
      const field = byKey.get(key);
      if (!field) continue;
      const chip: Chip = { kind: "field", key, label: field.label };
      if (!next.some((c) => chipId(c) === chipId(chip))) next.push(chip);
    }
    onChange(next);
  };

  return (
    <div className="space-y-2">
      <div className="relative">
        <div
          className="flex flex-wrap items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2 py-1.5 focus-within:border-blue-500 dark:border-slate-700 dark:bg-slate-900"
          onClick={() => inputRef.current?.focus()}
        >
          {chips.map((chip) => (
            <span
              key={chipId(chip)}
              className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs ${
                chip.kind === "filter"
                  ? "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200"
                  : chip.kind === "field"
                    ? "bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-200"
                    : "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200"
              }`}
            >
              {chipLabel(chip)}
              <button
                type="button"
                aria-label={`Remove ${chipLabel(chip)}`}
                className="opacity-60 hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  onChange(chips.filter((c) => chipId(c) !== chipId(chip)));
                }}
              >
                ×
              </button>
            </span>
          ))}
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            onBlur={() => setDraft((d) => (d.trim() ? (commitDraft(), "") : d))}
            placeholder={chips.length ? "" : placeholder}
            className="min-w-[14rem] flex-1 bg-transparent py-0.5 text-sm outline-none placeholder:text-slate-400"
            aria-label="Add a field or filter"
          />
        </div>

        {open && (
          <ul className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-md border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-900">
            {suggestions.map((s, i) => (
              <li key={s.key}>
                <button
                  type="button"
                  className={`flex w-full items-center justify-between px-3 py-1.5 text-left text-sm ${
                    i === highlighted
                      ? "bg-blue-50 dark:bg-slate-800"
                      : "hover:bg-slate-50 dark:hover:bg-slate-800"
                  }`}
                  onMouseEnter={() => setHighlighted(i)}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => add({ kind: "field", key: s.key, label: s.label })}
                >
                  <span>{s.label}</span>
                  <span className="ml-3 shrink-0 text-xs text-slate-400">{s.type}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {presets && presets.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-slate-400">Quick sets:</span>
          {presets.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => applyPreset(p.keys)}
              className="rounded border border-slate-300 px-2 py-0.5 text-xs text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {p.label}
            </button>
          ))}
          {chips.length > 0 && (
            <button
              type="button"
              onClick={() => onChange([])}
              className="ml-1 text-xs text-blue-600 hover:underline"
            >
              Clear all
            </button>
          )}
        </div>
      )}
    </div>
  );
}
