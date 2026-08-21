"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Card, Badge, Spinner, ErrorNote } from "@/components/ui";
import { canViewTracker, canUpload, canEditIdentity, canViewPos } from "@/lib/permissions";
import type { Order, TrackerRow, VendorOrder } from "@/lib/types";

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</div>
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const showTracker = !!user && canViewTracker(user.role);
  const orders = useQuery({ queryKey: ["orders"], queryFn: () => api<Order[]>("/api/orders") });
  const vendors = useQuery({
    queryKey: ["vendor-orders"],
    queryFn: () => api<VendorOrder[]>("/api/vendor-orders"),
  });
  const tracker = useQuery({
    queryKey: ["tracker"],
    queryFn: () => api<TrackerRow[]>("/api/tracker"),
    enabled: showTracker,
  });

  if (orders.isLoading || (showTracker && tracker.isLoading)) return <Spinner />;
  const error = orders.error || (showTracker && tracker.error) || vendors.error;

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
            <StatCard label="Tracker rows" value={tracker.data?.length ?? 0} />
            <StatCard
              label="Reconciled (both sides)"
              value={tracker.data?.filter((r) => r.has_buyer && r.has_vendor).length ?? 0}
            />
          </>
        )}
      </div>

      {showTracker && (
      <Card
        title="Shipment Tracker"
        actions={
          <Link href="/tracker" className="text-sm text-blue-600 hover:underline">
            Open tracker →
          </Link>
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
                <th className="py-2 pr-4">Sides</th>
              </tr>
            </thead>
            <tbody>
              {(tracker.data ?? []).slice(0, 12).map((r) => (
                <tr key={r.id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="py-2 pr-4">
                    <Link
                      href={`/pos/${encodeURIComponent(r.buyer_po ?? "")}`}
                      className="text-blue-600 hover:underline"
                    >
                      {r.buyer_po}
                    </Link>
                  </td>
                  <td className="py-2 pr-4">{r.style_no}</td>
                  <td className="py-2 pr-4">{r.colour}</td>
                  <td className="py-2 pr-4">{String(r.data.factory_name ?? "—")}</td>
                  <td className="py-2 pr-4">{String(r.data.order_qty ?? "—")}</td>
                  <td className="py-2 pr-4">
                    {r.has_buyer && <Badge color="blue">buyer</Badge>}{" "}
                    {r.has_vendor && <Badge color="green">vendor</Badge>}
                  </td>
                </tr>
              ))}
              {tracker.data?.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-400">
                    No tracker rows yet. {user && canUpload(user.role) ? "Upload some order sheets." : ""}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
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
