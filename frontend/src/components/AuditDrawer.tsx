"use client";

import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, ErrorNote } from "@/components/ui";
import { toDisplayDate } from "@/lib/dateFormat";
import type { AuditEntry } from "@/lib/types";

/** The change trail for one field: who set it, from what, to what, and when.
 *
 * Shared by the tracker's row view and the per-PO view — the trail is the same
 * question in both places, only the endpoint differs.
 */
export function AuditDrawer({
  path,
  label,
  isDate,
  onClose,
}: {
  /** Fully-formed API path, already carrying the field filter. */
  path: string;
  label: string;
  isDate: boolean;
  onClose: () => void;
}) {
  const q = useQuery({
    queryKey: ["audit", path],
    queryFn: () => api<AuditEntry[]>(path),
  });

  const show = (value: string | null) =>
    value ? (isDate ? toDisplayDate(value) : value) : "(empty)";

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="relative z-50 flex h-full w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-start justify-between border-b border-slate-100 px-5 py-4 dark:border-slate-800">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-400">Change trail</div>
            <div className="mt-0.5 font-semibold text-slate-900 dark:text-slate-100">
              {label}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close the change trail"
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {q.isLoading && <div className="text-sm text-slate-400">Loading…</div>}
          {q.error && <ErrorNote message={(q.error as Error).message} />}
          {q.data && q.data.length === 0 && (
            <div className="text-sm text-slate-400">
              No recorded changes for this field yet.
            </div>
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
                    color={
                      e.action === "import" ? "gray" : e.action === "manual" ? "blue" : "green"
                    }
                  >
                    {e.action}
                  </Badge>
                  <span className="ml-auto text-xs text-slate-400">
                    {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
                  </span>
                </div>
                <div className="mt-1.5 text-xs text-slate-600 dark:text-slate-400">
                  <span className="text-slate-400 line-through">{show(e.old_value)}</span>
                  {" → "}
                  <span className="font-medium text-slate-800 dark:text-slate-200">
                    {show(e.new_value)}
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
