"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { Badge, Button, Card, ErrorNote, Select, Textarea } from "@/components/ui";
import { clsx } from "@/components/clsx";
import type { PastePreview, PasteResult, TrackerColumn } from "@/lib/types";

/** Paste a table of PO details out of an e-mail.
 *
 * Pinned to one PO when `buyerPo` is given (from that PO's page), otherwise
 * standalone, in which case the paste has to carry a PO column. Nothing is
 * written until the preview has been reviewed.
 */
export function PastePanel({
  buyerPo,
  onApplied,
}: {
  buyerPo?: string;
  onApplied?: () => void;
}) {
  const [text, setText] = useState("");
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<PastePreview | null>(null);
  const [result, setResult] = useState<PasteResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const columns = useQuery({
    queryKey: ["tracker-columns"],
    queryFn: () => api<TrackerColumn[]>("/api/tracker/columns"),
    staleTime: Infinity,
  });

  const body = () => ({
    text,
    buyer_po: buyerPo ?? null,
    column_overrides: overrides,
  });

  const run = async <T,>(path: string): Promise<T> =>
    api<T>(path, { method: "POST", body: JSON.stringify(body()) });

  const doPreview = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setPreview(await run<PastePreview>("/api/paste/preview"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Preview failed");
      setPreview(null);
    } finally {
      setBusy(false);
    }
  };

  const doApply = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await run<PasteResult>("/api/paste/apply");
      setResult(res);
      setPreview(null);
      setText("");
      setOverrides({});
      onApplied?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Apply failed");
    } finally {
      setBusy(false);
    }
  };

  const editableColumns = (columns.data ?? []).filter((c) => !c.is_derived);

  return (
    <div className="space-y-3">
      <Textarea
        rows={6}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setPreview(null);
          setResult(null);
        }}
        placeholder={
          buyerPo
            ? `Paste rows for PO ${buyerPo} — include a Style or Colour column so the right line is picked…`
            : "Paste rows from an e-mail or Excel — must include a PO column…"
        }
      />

      <div className="flex items-center gap-2">
        <Button variant="secondary" disabled={busy || !text.trim()} onClick={doPreview}>
          {busy && !preview ? "Checking…" : "Preview"}
        </Button>
        {preview && preview.matched_row_count > 0 && (
          <Button disabled={busy} onClick={doApply}>
            {busy ? "Applying…" : `Apply to ${preview.matched_row_count} line(s)`}
          </Button>
        )}
      </div>

      {error && <ErrorNote message={error} />}

      {preview && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {preview.po_column_header && (
              <Badge color="blue">PO column: {preview.po_column_header}</Badge>
            )}
            <Badge color={preview.matched_row_count ? "green" : "yellow"}>
              {preview.matched_row_count} row(s) matched
            </Badge>
            {preview.error_row_count > 0 && (
              <Badge color="red">{preview.error_row_count} row(s) with problems</Badge>
            )}
            {preview.unmatched_pos.length > 0 && (
              <Badge color="yellow">
                not found: {preview.unmatched_pos.join(", ")}
              </Badge>
            )}
          </div>

          <div>
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Column matching
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {preview.columns.map((c) => {
                const current =
                  overrides[c.excel_header] !== undefined
                    ? overrides[c.excel_header]
                    : c.matched_field_key ?? "";
                const locator = c.purpose === "locator";
                return (
                  <label key={c.excel_header} className="flex flex-col gap-0.5 text-xs">
                    <span className="flex items-center gap-1 text-slate-500">
                      {c.excel_header}
                      {c.purpose === "write" && c.confidence < 0.88 && (
                        <span className="text-amber-600">
                          ({Math.round(c.confidence * 100)}%)
                        </span>
                      )}
                      {locator && (
                        <span
                          title="Used to find the right line. Never overwritten."
                          className="text-blue-600"
                        >
                          matches rows
                        </span>
                      )}
                      {c.purpose === "blocked" && (
                        <span title={c.blocked_reason ?? undefined} className="text-red-600">
                          not allowed
                        </span>
                      )}
                    </span>
                    {locator ? (
                      <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-slate-600 dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-slate-300">
                        {c.matched_field_label}
                      </div>
                    ) : (
                      <Select
                        className={clsx(c.purpose === "blocked" && "border-red-300")}
                        value={current}
                        onChange={(e) =>
                          setOverrides((o) => ({ ...o, [c.excel_header]: e.target.value }))
                        }
                      >
                        <option value="">— ignore —</option>
                        {editableColumns.map((tc) => (
                          <option key={tc.key} value={tc.key}>
                            {tc.label}
                          </option>
                        ))}
                      </Select>
                    )}
                  </label>
                );
              })}
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Change a match and press Preview again to re-check.
            </p>
          </div>

          <div className="max-h-64 overflow-auto rounded border border-slate-200 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800">
                <tr className="text-left text-slate-500">
                  <th className="p-1.5">Row</th>
                  <th className="p-1.5">PO</th>
                  <th className="p-1.5">Will write</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((r) => (
                  <tr
                    key={r.row_number}
                    className={clsx(
                      "border-t border-slate-100 dark:border-slate-800",
                      r.error && "bg-red-50 dark:bg-red-500/10",
                    )}
                  >
                    <td className="p-1.5 text-slate-400">{r.row_number}</td>
                    <td className="p-1.5 font-medium">{r.buyer_po ?? "—"}</td>
                    <td className="p-1.5 text-slate-600 dark:text-slate-400">
                      {r.error ? (
                        <span className="text-red-600">{r.error}</span>
                      ) : (
                        Object.entries(r.mapped)
                          .map(([k, v]) => `${k}=${String(v ?? "")}`)
                          .join(" · ") || "nothing mapped"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result && (
        <Card title="Update applied">
          <p className="text-sm">
            {result.updated_rows} line(s) updated, {result.updated_fields} field(s) changed.
          </p>
          {result.unmatched_pos.length > 0 && (
            <p className="mt-1 text-xs text-slate-500">
              POs not found: {result.unmatched_pos.join(", ")}
            </p>
          )}
          {result.row_errors.length > 0 && (
            <ul className="mt-2 space-y-1">
              {result.row_errors.slice(0, 8).map((r) => (
                <li key={r.row_number} className="text-xs text-red-600">
                  Row {r.row_number}: {r.error}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
