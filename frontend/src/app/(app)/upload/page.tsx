"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { apiUpload, ApiError } from "@/lib/api";
import { Button, Card, Badge, ErrorNote } from "@/components/ui";
import { clsx } from "@/components/clsx";
import type { UploadResponse, UploadFileResult } from "@/lib/types";

export default function UploadPage() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<UploadFileResult[] | null>(null);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const xlsx = Array.from(list).filter((f) => f.name.toLowerCase().endsWith(".xlsx"));
    setFiles((prev) => [...prev, ...xlsx]);
    setError(xlsx.length < list.length ? "Some files were skipped (only .xlsx accepted)" : null);
  };

  const submit = async () => {
    if (files.length === 0) return;
    setBusy(true);
    setError(null);
    setResults(null);
    try {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      const res = await apiUpload<UploadResponse>("/api/orders/upload", form);
      setResults(res.results);
      setFiles([]);
      qc.invalidateQueries();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">Upload order sheets</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Drop one or more Customer-Order / Order-Confirmation or Vendor-Order{" "}
        <code>.xlsx</code> files. Each file is one order; the type is detected automatically and
        reconciled into the tracker.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={clsx(
          "cursor-pointer rounded-lg border-2 border-dashed p-10 text-center transition-colors",
          dragActive
            ? "border-blue-400 bg-blue-50 dark:bg-blue-500/10"
            : "border-slate-300 bg-white dark:border-slate-700 dark:bg-slate-900",
        )}
      >
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
          Drag &amp; drop .xlsx files here, or click to browse
        </p>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">Multiple files supported</p>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx"
          multiple
          hidden
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {error && <ErrorNote message={error} />}

      {files.length > 0 && (
        <Card title={`Selected files (${files.length})`}>
          <ul className="space-y-1 text-sm">
            {files.map((f, i) => (
              <li key={i} className="flex items-center justify-between">
                <span>{f.name}</span>
                <button
                  className="text-xs text-slate-400 hover:text-red-600"
                  onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
                >
                  remove
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-4 flex gap-2">
            <Button onClick={submit} disabled={busy}>
              {busy ? "Uploading…" : `Upload ${files.length} file(s)`}
            </Button>
            <Button variant="ghost" onClick={() => setFiles([])} disabled={busy}>
              Clear
            </Button>
          </div>
        </Card>
      )}

      {results && (
        <Card
          title="Results"
          actions={
            <Link href="/tracker" className="text-sm text-blue-600 hover:underline">
              View tracker →
            </Link>
          }
        >
          <ul className="space-y-3 text-sm">
            {results.map((r, i) => (
              <li key={i} className="rounded-md border border-slate-100 p-3">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{r.filename}</span>
                  {r.kind && <Badge color={r.kind === "vendor" ? "green" : "blue"}>{r.kind}</Badge>}
                  <Badge color={r.status === "error" ? "red" : "green"}>{r.status}</Badge>
                  {r.status !== "error" && (
                    <span className="text-xs text-slate-500">
                      {r.tracker_rows_touched} tracker row(s)
                    </span>
                  )}
                </div>
                {r.error && <div className="mt-1 text-xs text-red-600">{r.error}</div>}
                {r.warnings.length > 0 && (
                  <ul className="mt-1 list-disc pl-5 text-xs text-amber-600">
                    {r.warnings.map((w, j) => (
                      <li key={j}>{w}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
