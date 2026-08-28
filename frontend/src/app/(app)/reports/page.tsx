"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, apiDownload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canViewReports } from "@/lib/permissions";
import { Button, Card, Input, Select, Spinner, ErrorNote } from "@/components/ui";
import { useTheme } from "@/lib/theme";
import type { Report, ReportOptions } from "@/lib/types";

type GroupBy = "season" | "customer" | "vendor";

const GROUPS: { value: GroupBy; label: string }[] = [
  { value: "season", label: "Season" },
  { value: "customer", label: "Customer" },
  { value: "vendor", label: "Vendor" },
];

// colour-blind-safe categorical ramp, readable on both themes
const SERIES = ["#2563eb", "#059669", "#d97706", "#7c3aed", "#dc2626", "#0891b2"];

const nf = new Intl.NumberFormat();
// prices carry up to 4 decimals, so report money is shown exact, not rounded
const moneyFmt = new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 });
const money = (n: number) => moneyFmt.format(n);
// recharts hands formatters a loose ValueType
const fmtValue = (v: unknown) => moneyFmt.format(Number(v ?? 0));

export default function ReportsPage() {
  const { user } = useAuth();
  const { theme } = useTheme();
  const [groupBy, setGroupBy] = useState<GroupBy>("season");
  const [season, setSeason] = useState("");
  const [customer, setCustomer] = useState("");
  const [vendor, setVendor] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const allowed = !!user && canViewReports(user.role);

  const query = () => {
    const q = new URLSearchParams({ group_by: groupBy });
    if (season) q.set("season", season);
    if (customer) q.set("customer", customer);
    if (vendor) q.set("vendor", vendor);
    if (dateFrom) q.set("date_from", dateFrom);
    if (dateTo) q.set("date_to", dateTo);
    return q.toString();
  };

  const options = useQuery({
    queryKey: ["report-options"],
    queryFn: () => api<ReportOptions>("/api/reports/options"),
    enabled: allowed,
  });

  const report = useQuery({
    queryKey: ["report", groupBy, season, customer, vendor, dateFrom, dateTo],
    queryFn: () => api<Report>(`/api/reports/summary?${query()}`),
    enabled: allowed,
  });

  if (user && !allowed)
    return <ErrorNote message="Reports are available to the CEO and admins." />;

  const data = report.data;
  const axisColor = theme === "dark" ? "#94a3b8" : "#64748b";
  const gridColor = theme === "dark" ? "#1e293b" : "#e2e8f0";

  const chartData = (data?.buckets ?? []).slice(0, 12).map((b) => ({
    name: b.label,
    Buyer: b.buyer_value,
    Vendor: b.vendor_value,
    Margin: b.margin,
    qty: b.order_qty,
  }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">Reports</h1>
          <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
            Order and shipping numbers by season, customer or vendor.
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() =>
            apiDownload(`/api/reports/export?${query()}`, `${groupBy} report.xlsx`)
          }
        >
          Download .xlsx
        </Button>
      </div>

      <Card title="Filters">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Field label="Group by">
            <Select value={groupBy} onChange={(e) => setGroupBy(e.target.value as GroupBy)}>
              {GROUPS.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Season">
            <Select value={season} onChange={(e) => setSeason(e.target.value)}>
              <option value="">All</option>
              {(options.data?.seasons ?? []).map((s) => (
                <option key={s.code} value={s.code}>
                  {s.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Customer">
            <Select value={customer} onChange={(e) => setCustomer(e.target.value)}>
              <option value="">All</option>
              {(options.data?.customers ?? []).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Vendor">
            <Select value={vendor} onChange={(e) => setVendor(e.target.value)}>
              <option value="">All</option>
              {(options.data?.vendors ?? []).map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Shipped from">
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </Field>
          <Field label="Shipped to">
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </Field>
        </div>
      </Card>

      {report.error && <ErrorNote message={(report.error as Error).message} />}

      {report.isLoading || !data ? (
        <Spinner />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat label="Purchase orders" value={nf.format(data.totals.po_count)} />
            <Stat label="Order qty" value={nf.format(data.totals.order_qty)} />
            <Stat label="Buyer value" value={money(data.totals.buyer_value)} />
            <Stat
              label="Margin"
              value={`${money(data.totals.margin)}${
                data.totals.margin_pct !== null ? ` (${data.totals.margin_pct}%)` : ""
              }`}
            />
          </div>

          {chartData.length > 0 && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <Card title="Buyer vs vendor value" className="lg:col-span-2">
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                      <CartesianGrid stroke={gridColor} vertical={false} />
                      <XAxis
                        dataKey="name"
                        tick={{ fill: axisColor, fontSize: 11 }}
                        stroke={gridColor}
                      />
                      <YAxis tick={{ fill: axisColor, fontSize: 11 }} stroke={gridColor} />
                      <Tooltip
                        formatter={fmtValue}
                        contentStyle={{
                          background: theme === "dark" ? "#0f172a" : "#fff",
                          border: `1px solid ${gridColor}`,
                          borderRadius: 6,
                          fontSize: 12,
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="Buyer" fill={SERIES[0]} radius={[3, 3, 0, 0]} />
                      <Bar dataKey="Vendor" fill={SERIES[1]} radius={[3, 3, 0, 0]} />
                      <Bar dataKey="Margin" fill={SERIES[2]} radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>

              <Card title="Share of order quantity">
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={chartData}
                        dataKey="qty"
                        nameKey="name"
                        innerRadius="45%"
                        outerRadius="75%"
                      >
                        {chartData.map((_, i) => (
                          <Cell key={i} fill={SERIES[i % SERIES.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={fmtValue}
                        contentStyle={{
                          background: theme === "dark" ? "#0f172a" : "#fff",
                          border: `1px solid ${gridColor}`,
                          borderRadius: 6,
                          fontSize: 12,
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            </div>
          )}

          <Card title={`By ${data.group_by} (${data.buckets.length})`}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500">
                    <th className="py-2 pr-4">
                      {GROUPS.find((g) => g.value === data.group_by)?.label}
                    </th>
                    <th className="py-2 pr-4 text-right">POs</th>
                    <th className="py-2 pr-4 text-right">Lines</th>
                    <th className="py-2 pr-4 text-right">Order qty</th>
                    <th className="py-2 pr-4 text-right">Ship qty</th>
                    <th className="py-2 pr-4 text-right">Buyer value</th>
                    <th className="py-2 pr-4 text-right">Vendor value</th>
                    <th className="py-2 pr-4 text-right">Margin</th>
                    <th className="py-2 pr-4 text-right">Margin %</th>
                    <th className="py-2 pr-4 text-right">Shipped</th>
                    <th className="py-2 pr-4 text-right">Pending</th>
                    <th className="py-2 pr-4 text-right">Avg delay</th>
                  </tr>
                </thead>
                <tbody>
                  {data.buckets.map((b) => (
                    <tr key={b.key} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="py-2.5 pr-4 font-medium">{b.label}</td>
                      <td className="py-2.5 pr-4 text-right">{b.po_count}</td>
                      <td className="py-2.5 pr-4 text-right">{b.line_count}</td>
                      <td className="py-2.5 pr-4 text-right">{nf.format(b.order_qty)}</td>
                      <td className="py-2.5 pr-4 text-right">{nf.format(b.ship_qty)}</td>
                      <td className="py-2.5 pr-4 text-right">{money(b.buyer_value)}</td>
                      <td className="py-2.5 pr-4 text-right">{money(b.vendor_value)}</td>
                      <td className="py-2.5 pr-4 text-right">{money(b.margin)}</td>
                      <td className="py-2.5 pr-4 text-right">
                        {b.margin_pct === null ? "—" : `${b.margin_pct}%`}
                      </td>
                      <td className="py-2.5 pr-4 text-right">{b.shipped_lines}</td>
                      <td className="py-2.5 pr-4 text-right">{b.pending_lines}</td>
                      <td className="py-2.5 pr-4 text-right">
                        {b.avg_shipment_delay === null ? "—" : b.avg_shipment_delay}
                      </td>
                    </tr>
                  ))}
                  {data.buckets.length === 0 && (
                    <tr>
                      <td colSpan={12} className="py-6 text-center text-slate-400">
                        Nothing matches these filters.
                      </td>
                    </tr>
                  )}
                </tbody>
                {data.buckets.length > 0 && (
                  <tfoot>
                    <tr className="border-t-2 border-slate-200 font-semibold dark:border-slate-700">
                      <td className="py-2.5 pr-4">Total</td>
                      <td className="py-2.5 pr-4 text-right">{data.totals.po_count}</td>
                      <td className="py-2.5 pr-4 text-right">{data.totals.line_count}</td>
                      <td className="py-2.5 pr-4 text-right">
                        {nf.format(data.totals.order_qty)}
                      </td>
                      <td className="py-2.5 pr-4 text-right">
                        {nf.format(data.totals.ship_qty)}
                      </td>
                      <td className="py-2.5 pr-4 text-right">
                        {money(data.totals.buyer_value)}
                      </td>
                      <td className="py-2.5 pr-4 text-right">
                        {money(data.totals.vendor_value)}
                      </td>
                      <td className="py-2.5 pr-4 text-right">{money(data.totals.margin)}</td>
                      <td className="py-2.5 pr-4 text-right">
                        {data.totals.margin_pct === null ? "—" : `${data.totals.margin_pct}%`}
                      </td>
                      <td className="py-2.5 pr-4 text-right">{data.totals.shipped_lines}</td>
                      <td className="py-2.5 pr-4 text-right">{data.totals.pending_lines}</td>
                      <td className="py-2.5 pr-4 text-right">—</td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</span>
      {children}
    </label>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</div>
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
    </div>
  );
}
