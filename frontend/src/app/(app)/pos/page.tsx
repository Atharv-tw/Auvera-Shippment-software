"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canViewPos } from "@/lib/permissions";
import { Badge, Card, Input, Select, Spinner, ErrorNote } from "@/components/ui";
import { poLinePath } from "@/lib/routes";
import type { PoSummary, SeasonSummary } from "@/lib/types";

const nf = new Intl.NumberFormat();
// prices carry up to 4 decimals; the default formatter would drop the fourth
const moneyFmt = new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 });

export default function PurchaseOrdersPage() {
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [season, setSeason] = useState("");
  const allowed = !!user && canViewPos(user.role);

  const seasons = useQuery({
    queryKey: ["seasons"],
    queryFn: () => api<SeasonSummary[]>("/api/seasons"),
    enabled: allowed,
  });

  const pos = useQuery({
    queryKey: ["pos", search, season],
    queryFn: () => {
      const q = new URLSearchParams();
      if (search) q.set("search", search);
      if (season) q.set("season", season);
      const qs = q.toString();
      return api<PoSummary[]>(`/api/pos${qs ? `?${qs}` : ""}`);
    },
    enabled: allowed,
  });

  if (user && !allowed)
    return <ErrorNote message="Your role does not have access to purchase orders." />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">
          Purchase Orders
        </h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
          One entry per buyer PO, with every style and colour on it.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <div className="w-64">
          <Input
            placeholder="Search PO number…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="w-56">
          <Select value={season} onChange={(e) => setSeason(e.target.value)}>
            <option value="">All seasons</option>
            {(seasons.data ?? []).map((s) => (
              <option key={s.code} value={s.code}>
                {s.label} ({s.po_count})
              </option>
            ))}
          </Select>
        </div>
      </div>

      {pos.error && <ErrorNote message={(pos.error as Error).message} />}

      {pos.isLoading ? (
        <Spinner />
      ) : (
        <Card title={`Purchase orders (${pos.data?.length ?? 0})`}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th className="py-2 pr-4">PO#</th>
                  <th className="py-2 pr-4">Season</th>
                  <th className="py-2 pr-4">Customer</th>
                  <th className="py-2 pr-4">Factories</th>
                  <th className="py-2 pr-4 text-right">Lines</th>
                  <th className="py-2 pr-4 text-right">Order qty</th>
                  <th className="py-2 pr-4 text-right">Buyer value</th>
                  <th className="py-2 pr-4">Status</th>
                </tr>
              </thead>
              <tbody>
                {(pos.data ?? []).map((p) => (
                  <tr key={p.buyer_po} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="py-2.5 pr-4 font-medium">
                      <Link
                        href={poLinePath(p.buyer_po)}
                        className="text-blue-600 hover:underline"
                      >
                        {p.buyer_po}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-4">
                      {p.season ? (
                        <Badge color={p.season.confirmed ? "blue" : "yellow"}>
                          {p.season.label}
                          {p.season.confirmed ? "" : " (suggested)"}
                        </Badge>
                      ) : (
                        <Badge color="yellow">Not set</Badge>
                      )}
                    </td>
                    <td className="py-2.5 pr-4 text-slate-600 dark:text-slate-400">
                      {p.customer_name ?? "—"}
                    </td>
                    <td className="py-2.5 pr-4 text-slate-600 dark:text-slate-400">
                      {p.factories.length ? p.factories.join(", ") : "—"}
                    </td>
                    <td className="py-2.5 pr-4 text-right">{p.line_count}</td>
                    <td className="py-2.5 pr-4 text-right">{nf.format(p.order_qty)}</td>
                    <td className="py-2.5 pr-4 text-right">{moneyFmt.format(p.buyer_total_value)}</td>
                    <td className="py-2.5 pr-4 text-xs text-slate-500">
                      {Object.entries(p.statuses)
                        .map(([label, n]) => `${label} (${n})`)
                        .join(", ")}
                    </td>
                  </tr>
                ))}
                {pos.data?.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-6 text-center text-slate-400">
                      No purchase orders yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
