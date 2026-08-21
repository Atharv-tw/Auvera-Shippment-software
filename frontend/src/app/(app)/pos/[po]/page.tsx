"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canAssignSeason, canPaste, canViewPos } from "@/lib/permissions";
import { Badge, Button, Card, Select, Spinner, ErrorNote } from "@/components/ui";
import { PoLineCard } from "@/components/PoLineCard";
import { PastePanel } from "@/components/PastePanel";
import type { PoDetail, PoSchema, Season } from "@/lib/types";

const nf = new Intl.NumberFormat();

const HEADER_LABELS: [string, string][] = [
  ["supplier", "Supplier"],
  ["code", "Code"],
  ["country_of_payment", "Country of Payment"],
  ["payment_terms", "Payment Terms"],
  ["currency", "Currency"],
  ["terms_of_delivery", "Terms of Delivery"],
  ["factory_town", "Factory Town"],
  ["port_of_loading", "Port of Loading"],
  ["source_filename", "Source file"],
];

export default function PurchaseOrderPage({ params }: { params: Promise<{ po: string }> }) {
  const { po } = use(params);
  const buyerPo = decodeURIComponent(po);
  const { user } = useAuth();
  const qc = useQueryClient();
  const allowed = !!user && canViewPos(user.role);

  const schema = useQuery({
    queryKey: ["po-schema"],
    queryFn: () => api<PoSchema>("/api/pos/schema"),
    staleTime: Infinity,
    enabled: allowed,
  });
  const detail = useQuery({
    queryKey: ["po", buyerPo],
    queryFn: () => api<PoDetail>(`/api/pos/${encodeURIComponent(buyerPo)}`),
    enabled: allowed,
  });

  if (user && !allowed)
    return <ErrorNote message="Your role does not have access to purchase orders." />;
  if (schema.isLoading || detail.isLoading) return <Spinner />;
  if (detail.error) return <ErrorNote message={(detail.error as Error).message} />;

  const d = detail.data!;
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["po", buyerPo] });
    qc.invalidateQueries({ queryKey: ["pos"] });
    qc.invalidateQueries({ queryKey: ["tracker"] });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link href="/pos" className="text-sm text-blue-600 hover:underline">
          ← Purchase Orders
        </Link>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">
          PO {d.buyer_po}
        </h1>
        {d.customer_name && <Badge color="blue">{d.customer_name}</Badge>}
      </div>

      <Card title="Order summary">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Lines" value={d.lines.length} />
          <Stat label="Order qty" value={nf.format(d.totals.order_qty ?? 0)} />
          <Stat label="Buyer value" value={nf.format(d.totals.buyer_total_value ?? 0)} />
          <Stat label="Vendor value" value={nf.format(d.totals.vendor_total_value ?? 0)} />
        </div>

        <div className="mt-4">
          <SeasonControl
            buyerPo={d.buyer_po}
            season={d.season}
            canEdit={!!user && canAssignSeason(user.role)}
            onSaved={refresh}
          />
        </div>

        {d.headers.length > 0 && (
          <div className="mt-4 space-y-3">
            {d.headers.map((h, i) => (
              <div key={i}>
                <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  {h.side === "buyer" ? "From the buyer sheet" : "From the vendor sheet"}
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                  {HEADER_LABELS.map(([key, label]) => (
                    <div
                      key={key}
                      className="rounded-md border border-slate-100 p-2 dark:border-slate-800"
                    >
                      <div className="text-[11px] text-slate-400">{label}</div>
                      <div className="mt-0.5 truncate text-sm text-slate-800 dark:text-slate-200">
                        {h[key] || "—"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {user && canPaste(user.role) && (
        <Card title="Paste details for this PO">
          <p className="mb-3 text-xs text-slate-500">
            Paste a table straight from an e-mail — booking details, container and vessel,
            BL numbers. Columns are matched to tracker fields automatically and previewed
            before anything is written.
          </p>
          <PastePanel buyerPo={d.buyer_po} onApplied={refresh} />
        </Card>
      )}

      <div className="space-y-4">
        {d.lines.map((line) => (
          <PoLineCard
            key={line.tracker_row_id}
            buyerPo={d.buyer_po}
            line={line}
            groups={schema.data?.groups ?? []}
            fields={schema.data?.fields ?? []}
            role={user!.role}
            onSaved={refresh}
          />
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-slate-100 p-2 dark:border-slate-800">
      <div className="text-lg font-bold text-slate-900 dark:text-slate-100">{value}</div>
      <div className="text-[11px] text-slate-400">{label}</div>
    </div>
  );
}

const THIS_YEAR = new Date().getFullYear();
const YEARS = [THIS_YEAR - 2, THIS_YEAR - 1, THIS_YEAR, THIS_YEAR + 1, THIS_YEAR + 2];

function SeasonControl({
  buyerPo,
  season,
  canEdit,
  onSaved,
}: {
  buyerPo: string;
  season: Season | null;
  canEdit: boolean;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [type, setType] = useState(season?.season_type ?? "SS");
  const [year, setYear] = useState(season?.season_year ?? THIS_YEAR);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api("/api/seasons/assign", {
        method: "POST",
        body: JSON.stringify({
          assignments: [{ buyer_po: buyerPo, season_type: type, season_year: year }],
        }),
      });
      setEditing(false);
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save the season");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        Season
      </span>
      {editing ? (
        <>
          <div className="w-40">
            <Select value={type} onChange={(e) => setType(e.target.value as "SS" | "AW")}>
              <option value="SS">Spring-Summer</option>
              <option value="AW">Autumn-Winter</option>
            </Select>
          </div>
          <div className="w-28">
            <Select value={year} onChange={(e) => setYear(Number(e.target.value))}>
              {YEARS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </Select>
          </div>
          <Button disabled={saving} onClick={save}>
            {saving ? "Saving…" : "Save"}
          </Button>
          <Button variant="ghost" disabled={saving} onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </>
      ) : (
        <>
          {season ? (
            <Badge color={season.confirmed ? "blue" : "yellow"}>
              {season.label}
              {season.confirmed ? "" : " (suggested)"}
            </Badge>
          ) : (
            <Badge color="yellow">Not set</Badge>
          )}
          {canEdit && (
            <Button variant="ghost" onClick={() => setEditing(true)}>
              {season ? "Change" : "Set season"}
            </Button>
          )}
        </>
      )}
      {error && <ErrorNote message={error} />}
    </div>
  );
}
