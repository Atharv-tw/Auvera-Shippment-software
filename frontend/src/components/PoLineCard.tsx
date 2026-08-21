"use client";

import { useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { canEditField, lockReason } from "@/lib/permissions";
import { Badge, Button, ErrorNote } from "@/components/ui";
import { clsx } from "@/components/clsx";
import { toDisplayDate, toIsoDate } from "@/lib/dateFormat";
import type { PoFieldSpec, PoGroup, PoLine, Role } from "@/lib/types";

/** One line of a purchase order, laid out in the four business sections.
 *
 * A line spans two records — the tracker row and the order-sheet line behind
 * it — so edits are split by each field's `origin` and sent in one PATCH.
 */
export function PoLineCard({
  buyerPo,
  line,
  groups,
  fields,
  role,
  showTitle = true,
  onSaved,
}: {
  buyerPo: string;
  line: PoLine;
  groups: { key: PoGroup; label: string }[];
  fields: PoFieldSpec[];
  role: Role;
  /** off when a tab strip above already names the line */
  showTitle?: boolean;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({ product: false });

  const byGroup = useMemo(() => {
    const map = new Map<PoGroup, PoFieldSpec[]>();
    for (const f of fields) {
      if (!map.has(f.group)) map.set(f.group, []);
      map.get(f.group)!.push(f);
    }
    return map;
  }, [fields]);

  const raw = (f: PoFieldSpec) =>
    f.origin === "tracker" ? line.tracker[f.key] : line.line[f.key];

  const shown = (f: PoFieldSpec) => {
    const v = raw(f);
    if (v === null || v === undefined || v === "") return "";
    return f.type === "date" ? toDisplayDate(v) : String(v);
  };

  const value = (f: PoFieldSpec) => (f.key in draft ? draft[f.key] : shown(f));

  const save = async () => {
    const trackerFields: Record<string, unknown> = {};
    const lineFields: Record<string, unknown> = {};
    for (const f of fields) {
      if (!(f.key in draft)) continue;
      if (draft[f.key] === shown(f)) continue;
      const v = f.type === "date" ? toIsoDate(draft[f.key]) : draft[f.key];
      if (f.origin === "tracker") trackerFields[f.key] = v;
      else lineFields[f.key] = v;
    }
    if (!Object.keys(trackerFields).length && !Object.keys(lineFields).length) {
      setEditing(false);
      setDraft({});
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api(`/api/pos/${encodeURIComponent(buyerPo)}/rows/${line.tracker_row_id}`, {
        method: "PATCH",
        body: JSON.stringify({ tracker_fields: trackerFields, line_fields: lineFields }),
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

  const anyEditable = fields.some((f) => canEditField(role, f));

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-3 dark:border-slate-800">
        {showTitle && (
          <>
            <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              {line.style_no ?? "—"} · {line.colour ?? "—"}
            </h3>
            {line.has_buyer && <Badge color="blue">buyer</Badge>}
            {line.has_vendor && <Badge color="green">vendor</Badge>}
          </>
        )}
        {line.article && <span className="text-xs text-slate-400">{line.article}</span>}
        <div className="ml-auto flex gap-2">
          {editing ? (
            <>
              <Button
                variant="ghost"
                disabled={saving}
                onClick={() => {
                  setDraft({});
                  setEditing(false);
                  setError(null);
                }}
              >
                Cancel
              </Button>
              <Button disabled={saving} onClick={save}>
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </>
          ) : (
            anyEditable && (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )
          )}
        </div>
      </div>

      <div className="space-y-4 p-4">
        {error && <ErrorNote message={error} />}

        {groups.map((g) => {
          const groupFields = byGroup.get(g.key) ?? [];
          if (groupFields.length === 0) return null;
          const collapsible = g.key === "product";
          const isOpen = !collapsible || open[g.key];
          return (
            <section key={g.key}>
              <button
                type="button"
                aria-label={
                  collapsible ? `${g.label} (${isOpen ? "collapse" : "expand"})` : g.label
                }
                aria-expanded={collapsible ? isOpen : undefined}
                onClick={() => collapsible && setOpen((o) => ({ ...o, [g.key]: !o[g.key] }))}
                className={clsx(
                  "mb-2 flex w-full items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500",
                  collapsible && "cursor-pointer hover:text-slate-600 dark:hover:text-slate-300",
                )}
              >
                <span>{g.label}</span>
                {collapsible && <span className="text-[10px]">{isOpen ? "▾" : "▸"}</span>}
                <span className="h-px flex-1 bg-slate-100 dark:bg-slate-800" />
              </button>

              {isOpen && (
                <>
                  {g.key === "product" && Object.keys(line.sizes).length > 0 && (
                    <SizeRatio sizes={line.sizes} spec={line.size_header} />
                  )}
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {groupFields.map((f) => {
                      const locked = lockReason(role, f);
                      const canEdit = editing && canEditField(role, f);
                      return (
                        <div
                          key={`${f.origin}:${f.key}`}
                          className="rounded-md border border-slate-100 p-2 dark:border-slate-800"
                        >
                          <div className="flex items-center gap-1">
                            <span className="text-[11px] text-slate-400 dark:text-slate-500">
                              {f.label}
                            </span>
                            {editing && locked && (
                              <span
                                title={locked}
                                className="ml-auto cursor-help text-[10px] text-amber-500"
                              >
                                locked
                              </span>
                            )}
                          </div>
                          {canEdit ? (
                            <input
                              className="mt-0.5 w-full rounded border border-slate-200 px-1.5 py-1 text-sm outline-none focus:border-blue-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                              value={value(f)}
                              onChange={(e) =>
                                setDraft((d) => ({ ...d, [f.key]: e.target.value }))
                              }
                            />
                          ) : (
                            <div
                              title={editing ? locked ?? undefined : undefined}
                              className={clsx(
                                "mt-0.5 text-sm text-slate-800 dark:text-slate-200",
                                editing && locked && "opacity-60",
                              )}
                            >
                              {shown(f) || "—"}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}

/** The order sheet's size ratio, with the alpha sizes it maps onto. */
function SizeRatio({
  sizes,
  spec,
}: {
  sizes: Record<string, number>;
  spec: { uk_size: string | null; alpha_size: string | null; range_label: string | null }[];
}) {
  // keep the sheet's own column order, then anything unexpected
  const ordered = spec.filter((s) => s.uk_size && sizes[s.uk_size] != null);
  const extra = Object.keys(sizes).filter(
    (k) => !spec.some((s) => s.uk_size === k),
  );
  const total = Object.values(sizes).reduce((a, b) => a + b, 0);

  return (
    <div className="mb-3 overflow-x-auto rounded-md border border-slate-100 dark:border-slate-800">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-slate-50 text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
            <th className="px-2 py-1 text-left font-medium">Size ratio</th>
            {ordered.map((s) => (
              <th key={s.uk_size} className="px-2 py-1 text-right font-medium">
                {s.uk_size}
                {s.alpha_size && (
                  <span className="block text-[10px] font-normal text-slate-400">
                    {s.alpha_size}
                  </span>
                )}
              </th>
            ))}
            {extra.map((k) => (
              <th key={k} className="px-2 py-1 text-right font-medium">
                {k}
              </th>
            ))}
            <th className="px-2 py-1 text-right font-medium">Total</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t border-slate-100 dark:border-slate-800">
            <td className="px-2 py-1 text-slate-400">Units</td>
            {ordered.map((s) => (
              <td key={s.uk_size} className="px-2 py-1 text-right">
                {sizes[s.uk_size!]}
              </td>
            ))}
            {extra.map((k) => (
              <td key={k} className="px-2 py-1 text-right">
                {sizes[k]}
              </td>
            ))}
            <td className="px-2 py-1 text-right font-semibold">{total}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
