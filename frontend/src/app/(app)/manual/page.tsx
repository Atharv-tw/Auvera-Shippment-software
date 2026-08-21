"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canEditIdentity, canEditField } from "@/lib/permissions";
import { seasonForValue, seasonLabel } from "@/lib/seasons";
import { poLinePath } from "@/lib/routes";
import { Badge, Button, Card, Select, Spinner, ErrorNote } from "@/components/ui";
import type { Season, SeasonType, TrackerColumn, TrackerRow } from "@/lib/types";

// Same three sections the per-PO view uses, minus Product: a hand-made row has
// only tracker columns behind it, and the garment spec comes off an order sheet.
const GROUPS: { title: string; sources: string[] }[] = [
  { title: "Buyer details", sources: ["buyer", "const"] },
  { title: "Vendor details", sources: ["vendor", "calc"] },
  { title: "Shipping details", sources: ["operational"] },
];

const THIS_YEAR = new Date().getFullYear();
const YEARS = [THIS_YEAR - 2, THIS_YEAR - 1, THIS_YEAR, THIS_YEAR + 1, THIS_YEAR + 2];

export default function ManualEntryPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [fields, setFields] = useState<Record<string, string>>({});
  const [seasonOverride, setSeasonOverride] = useState<{
    type: SeasonType;
    year: number;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const allowed = !!user && canEditIdentity(user.role);

  const buyerPo = (fields.buyer_po ?? "").trim();

  const columns = useQuery({
    queryKey: ["tracker-columns"],
    queryFn: () => api<TrackerColumn[]>("/api/tracker/columns"),
    staleTime: Infinity,
    enabled: allowed,
  });

  // If this PO already exists it already has a season, and creating another
  // line on it must not silently re-file the whole PO somewhere else.
  const existingSeason = useQuery({
    queryKey: ["season", buyerPo],
    queryFn: async () => {
      try {
        return await api<Season>(`/api/seasons/${encodeURIComponent(buyerPo)}`);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }
    },
    enabled: allowed && buyerPo.length > 0,
    retry: false,
  });

  if (user && !allowed)
    return (
      <ErrorNote message="Only CEO / admin can create a tracker row (it sets the order identity)." />
    );

  // Suggested from the delivery date being typed, exactly as an upload would.
  const suggested = seasonForValue(fields.buyer_po_delivery_date) ?? {
    type: "AW" as SeasonType,
    year: THIS_YEAR,
  };
  const chosen = seasonOverride ?? suggested;
  const alreadyFiled = existingSeason.data ?? null;

  const submit = async () => {
    if (!fields.buyer_po || !fields.style_no) {
      setError("Buyer PO# and Style No. are required (they form the row identity).");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const cleaned = Object.fromEntries(Object.entries(fields).filter(([, v]) => v !== ""));
      await api<TrackerRow>("/api/tracker", {
        method: "POST",
        body: JSON.stringify({ fields: cleaned }),
      });

      // A row with no season falls into "Season not set" in every report, so
      // file it now. An existing PO keeps the season it already has.
      if (!alreadyFiled) {
        await api("/api/seasons/assign", {
          method: "POST",
          body: JSON.stringify({
            assignments: [
              { buyer_po: buyerPo, season_type: chosen.type, season_year: chosen.year },
            ],
          }),
        });
      }

      qc.invalidateQueries({ queryKey: ["tracker"] });
      qc.invalidateQueries({ queryKey: ["pos"] });
      qc.invalidateQueries({ queryKey: ["seasons"] });
      router.push(poLinePath(buyerPo, fields.style_no, fields.colour));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create row");
    } finally {
      setBusy(false);
    }
  };

  if (columns.isLoading) return <Spinner />;
  const cols = columns.data ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">
          New purchase order line
        </h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
          For an order with no sheet to upload. Buyer PO# + Style No. + Colour identify the
          line; the same PO number adds a line to an existing purchase order.
        </p>
      </div>

      {error && <ErrorNote message={error} />}

      <Card title="Season">
        {alreadyFiled ? (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400">
              PO {alreadyFiled.buyer_po} is already filed under
            </span>
            <Badge color="blue">{alreadyFiled.label}</Badge>
            <span className="text-xs text-slate-400">
              — this line joins it. Change the season on the purchase order itself.
            </span>
          </div>
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[11px] text-slate-400">Season</span>
              <div className="w-44">
                <Select
                  value={chosen.type}
                  onChange={(e) =>
                    setSeasonOverride({ ...chosen, type: e.target.value as SeasonType })
                  }
                >
                  <option value="SS">Spring-Summer</option>
                  <option value="AW">Autumn-Winter</option>
                </Select>
              </div>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[11px] text-slate-400">Year</span>
              <div className="w-28">
                <Select
                  value={chosen.year}
                  onChange={(e) =>
                    setSeasonOverride({ ...chosen, year: Number(e.target.value) })
                  }
                >
                  {YEARS.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </Select>
              </div>
            </label>
            <p className="pb-2 text-xs text-slate-400">
              {seasonOverride
                ? `Filed as ${seasonLabel(chosen.type, chosen.year)}.`
                : fields.buyer_po_delivery_date
                  ? `Suggested from the buyer delivery date. Change it if that is wrong.`
                  : `Set a Buyer PO Delivery date below and this follows it.`}
            </p>
          </div>
        )}
      </Card>

      {GROUPS.map((g) => {
        const groupCols = cols.filter(
          (c) => g.sources.includes(c.source) && canEditField(user!.role, c),
        );
        if (groupCols.length === 0) return null;
        return (
          <Card key={g.title} title={g.title}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {groupCols.map((c) => (
                <div key={c.key}>
                  <label className="text-[11px] text-slate-400 dark:text-slate-500">
                    {c.label}
                  </label>
                  <input
                    className="mt-0.5 w-full rounded border border-slate-200 px-2 py-1 text-sm outline-none focus:border-blue-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                    type={c.type === "number" ? "number" : c.type === "date" ? "date" : "text"}
                    value={fields[c.key] ?? ""}
                    onChange={(e) => setFields((f) => ({ ...f, [c.key]: e.target.value }))}
                  />
                </div>
              ))}
            </div>
          </Card>
        );
      })}

      <div className="flex gap-2">
        <Button onClick={submit} disabled={busy}>
          {busy ? "Creating…" : "Create line"}
        </Button>
        <Button
          variant="ghost"
          onClick={() => {
            setFields({});
            setSeasonOverride(null);
          }}
          disabled={busy}
        >
          Clear
        </Button>
      </div>
    </div>
  );
}
