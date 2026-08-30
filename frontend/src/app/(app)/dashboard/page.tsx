"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api, apiPaged } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Card, Input, Spinner, ErrorNote } from "@/components/ui";
import {
  canViewTracker,
  canReadTrackerRows,
  canUpload,
  canEditIdentity,
  canViewPos,
} from "@/lib/permissions";
import { poLinePath } from "@/lib/routes";
import { toDisplayDate } from "@/lib/dateFormat";
import { useDebounced } from "@/lib/useDebounced";
import type { Order, TrackerRow, VendorOrder } from "@/lib/types";

const nf = new Intl.NumberFormat();
// prices carry up to 4 decimals; the default formatter caps at 3 and would drop
// the fourth place, so money is formatted with its own 4-decimal cap
const moneyFmt = new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 });

/** Tracker money cells arrive as numbers or as whatever the sheet held. */
function money(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  return Number.isFinite(n) ? moneyFmt.format(n) : String(value);
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</div>
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
    </div>
  );
}

/** Rows per page in the dashboard panel. The tracker page itself shows all of them. */
const PANEL_ROWS = 15;

export default function DashboardPage() {
  const { user } = useAuth();
  // the panel is order data, open to merchants; the tracker page is not
  const showTracker = !!user && canReadTrackerRows(user.role);
  const canOpenTracker = !!user && canViewTracker(user.role);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const orders = useQuery({ queryKey: ["orders"], queryFn: () => api<Order[]>("/api/orders") });
  const vendors = useQuery({
    queryKey: ["vendor-orders"],
    queryFn: () => api<VendorOrder[]>("/api/vendor-orders"),
  });

  // One page at a time. This panel shows 7 columns of 15 rows; it used to pull
  // the entire 56-column tracker and throw almost all of it away.
  // Debounced because searching moved server-side: undebounced this would be one
  // request per keystroke, where the old client-side filter cost nothing.
  const needle = useDebounced(search.trim(), 300);
  const tracker = useQuery({
    queryKey: ["tracker-panel", needle, page],
    queryFn: () => {
      const qs = new URLSearchParams({
        limit: String(PANEL_ROWS),
        offset: String(page * PANEL_ROWS),
        sort: "updated_at",
        order: "desc",
      });
      if (needle) qs.set("search", needle);
      return apiPaged<TrackerRow>(`/api/tracker?${qs}`);
    },
    enabled: showTracker,
    placeholderData: (previous) => previous, // keep the table steady while paging
  });

  // Counts come from X-Total-Count on a zero-row query - cheaper than fetching
  // every row purely to call .length on it.
  const totalRows = useQuery({
    queryKey: ["tracker-count"],
    queryFn: () => apiPaged<TrackerRow>("/api/tracker?limit=0"),
    enabled: showTracker,
  });
  const reconciledRows = useQuery({
    queryKey: ["tracker-count", "reconciled"],
    queryFn: () => apiPaged<TrackerRow>("/api/tracker?limit=0&reconciled=true"),
    enabled: showTracker,
  });

  if (orders.isLoading || (showTracker && tracker.isLoading)) return <Spinner />;
  const error = orders.error || (showTracker && tracker.error) || vendors.error;

  // Searching server-side now. It reaches factory_name and shipment_status,
  // which the old client-side filter could only approximate over one page.
  const matches = tracker.data?.items ?? [];
  const total = tracker.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PANEL_ROWS));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">Dashboard</h1>
        <div className="flex gap-2">
          {user && canViewPos(user.role) && (
            <Link href="/pos">
              <Button variant="secondary">Purchase orders</Button>
            </Link>
          )}
          {user && canUpload(user.role) && (
            <Link href="/upload">
              <Button>Upload sheets</Button>
            </Link>
          )}
          {user && canEditIdentity(user.role) && (
            <Link href="/manual">
              <Button variant="secondary">New tracker row</Button>
            </Link>
          )}
        </div>
      </div>

      {error && <ErrorNote message={(error as Error).message} />}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Customer orders" value={orders.data?.length ?? 0} />
        <StatCard label="Vendor orders" value={vendors.data?.length ?? 0} />
        {showTracker && (
          <>
            <StatCard label="Tracker rows" value={totalRows.data?.total ?? 0} />
            <StatCard
              label="Reconciled (both sides)"
              value={reconciledRows.data?.total ?? 0}
            />
          </>
        )}
      </div>

      {showTracker && (
      <Card
        title="Shipment Tracker"
        actions={
          <div className="flex items-center gap-3">
            <div className="w-56">
              <Input
                type="search"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(0); // a narrower result set may not have the page you were on
                }}
                placeholder="Search PO, style, colour, factory, status…"
              />
            </div>
            {canOpenTracker && (
              <Link href="/tracker" className="shrink-0 text-sm text-blue-600 hover:underline">
                Open tracker →
              </Link>
            )}
          </div>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-2 pr-4">PO#</th>
                <th className="py-2 pr-4">Style</th>
                <th className="py-2 pr-4">Colour</th>
                <th className="py-2 pr-4">Factory</th>
                <th className="py-2 pr-4">Order qty</th>
                <th className="py-2 pr-4">Factory cost</th>
                <th className="py-2 pr-4">Buyer delivery</th>
              </tr>
            </thead>
            <tbody>
              {matches.map((r) => (
                <tr key={r.id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-2 pr-4">
                    <Link
                      href={poLinePath(r.buyer_po ?? "", r.style_no, r.colour)}
                      className="text-blue-600 hover:underline"
                    >
                      {r.buyer_po}
                    </Link>
                  </td>
                  <td className="py-2 pr-4">{r.style_no}</td>
                  <td className="py-2 pr-4">{r.colour}</td>
                  <td className="py-2 pr-4">{String(r.data.factory_name ?? "—")}</td>
                  <td className="py-2 pr-4">{String(r.data.order_qty ?? "—")}</td>
                  <td className="py-2 pr-4 tabular-nums">
                    {money(r.data.vendor_total_value)}
                  </td>
                  <td className="py-2 pr-4">
                    {toDisplayDate(r.data.buyer_po_delivery_date) || "—"}
                  </td>
                </tr>
              ))}
              {matches.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-6 text-center text-slate-400">
                    {needle
                      ? `Nothing matches “${search.trim()}”.`
                      : `No tracker rows yet. ${
                          user && canUpload(user.role) ? "Upload some order sheets." : ""
                        }`}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {total > 0 && (
          <div className="mt-3 flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {page * PANEL_ROWS + 1}–{page * PANEL_ROWS + matches.length} of {nf.format(total)}
              {needle ? " matching" : ""} rows
            </p>
            {pageCount > 1 && (
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  Previous
                </Button>
                <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400">
                  {page + 1} / {pageCount}
                </span>
                <Button
                  variant="secondary"
                  onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                  disabled={page >= pageCount - 1}
                >
                  Next
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>
      )}

      <Card title="Customer orders">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-2 pr-4">Order #</th>
                <th className="py-2 pr-4">Supplier</th>
                <th className="py-2 pr-4">Country</th>
                <th className="py-2 pr-4">Lines</th>
                <th className="py-2 pr-4">File</th>
              </tr>
            </thead>
            <tbody>
              {(orders.data ?? []).map((o) => (
                <tr key={o.id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-2 pr-4">
                    <Link href={`/orders/${o.id}`} className="text-blue-600 hover:underline">
                      {o.order_number}
                    </Link>
                  </td>
                  <td className="py-2 pr-4">{o.supplier}</td>
                  <td className="py-2 pr-4">{o.country_of_payment}</td>
                  <td className="py-2 pr-4">{o.lines.length}</td>
                  <td className="py-2 pr-4 text-xs text-slate-400">{o.source_filename}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
