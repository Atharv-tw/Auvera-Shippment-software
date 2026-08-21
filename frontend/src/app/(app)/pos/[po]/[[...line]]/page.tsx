"use client";

import { use, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canAssignSeason, canPaste, canViewPos } from "@/lib/permissions";
import { poLinePath, safeDecode, segmentMatches } from "@/lib/routes";
import { Badge, Button, Card, Select, Spinner, ErrorNote } from "@/components/ui";
import { PoLineCard } from "@/components/PoLineCard";
import { PastePanel } from "@/components/PastePanel";
import { FieldChipBar } from "@/components/FieldChipBar";
import { usePersistentState } from "@/lib/usePersistentState";
import {
  visibleKeysFromChips,
  vocabularyFromFields,
  type Chip,
} from "@/lib/fieldVocabulary";
import { clsx } from "@/components/clsx";
import type { PoDetail, PoLine, PoSchema, Season } from "@/lib/types";

const nf = new Intl.NumberFormat();

/** `/pos/D579` opens the first line; `/pos/D579/20271108-T1/Black` opens that one. */
export default function PurchaseOrderPage({
  params,
}: {
  params: Promise<{ po: string; line?: string[] }>;
}) {
  const { po, line } = use(params);
  const buyerPo = safeDecode(po);
  const [wantStyle, wantColour] = line ?? [];
  const { user } = useAuth();
  const qc = useQueryClient();
  const router = useRouter();
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

  // All three live here, not in PoLineCard: the card is keyed on
  // tracker_row_id, so every line-tab switch remounts it and anything kept
  // inside would be lost. Persisted, so it also survives a reload.
  // Keyed per user, like the tracker's saved views: two people on one browser
  // profile should not inherit each other's layout.
  const prefKey = (name: string) => `po-${name}:${user?.id ?? "anon"}`;
  const [quickViewChips, setQuickViewChips] = usePersistentState<Chip[]>(
    prefKey("quick-view"),
    [],
  );
  const [openSections, setOpenSections] = usePersistentState<Record<string, boolean>>(
    prefKey("open-sections"),
    {},
  );
  const [hideEmpty, setHideEmpty] = usePersistentState(prefKey("hide-empty"), false);

  const poVocabulary = useMemo(
    () => vocabularyFromFields(schema.data?.fields ?? []),
    [schema.data],
  );
  const quickViewKeys = useMemo(
    () => visibleKeysFromChips(quickViewChips) ?? [],
    [quickViewChips],
  );
  const poPresets = useMemo(() => {
    const fields = schema.data?.fields ?? [];
    const of = (group: string) => fields.filter((f) => f.group === group).map((f) => f.key);
    return [
      ...(schema.data?.groups ?? []).map((g) => ({ label: g.label, keys: of(g.key) })),
      { label: "Money", keys: fields.filter((f) => f.is_price).map((f) => f.key) },
    ].filter((preset) => preset.keys.length > 0);
  }, [schema.data]);

  // The URL is the source of truth for which tab is open. An unknown or missing
  // style/colour falls back to the first line rather than showing nothing.
  const lines = detail.data?.lines ?? [];
  const active: PoLine | undefined =
    lines.find(
      (l) =>
        segmentMatches(l.style_no, wantStyle) && segmentMatches(l.colour, wantColour),
    ) ?? lines[0];

  // keep the open tab visible — a deep link can land on one that's scrolled off
  const activeTab = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    activeTab.current?.scrollIntoView({
      block: "nearest",
      inline: "center",
      behavior: "smooth",
    });
  }, [active?.tracker_row_id]);

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
          <Stat label="Style / colour lines" value={d.lines.length} />
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
      </Card>

      {active && (
        <div>
          {d.lines.length > 1 && (
            <div
              role="tablist"
              aria-label="Order lines"
              className="thin-scroll mb-3 flex gap-2 overflow-x-auto pb-2"
            >
              {d.lines.map((line) => {
                const isActive = line.tracker_row_id === active.tracker_row_id;
                return (
                  <button
                    key={line.tracker_row_id}
                    ref={isActive ? activeTab : undefined}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    onClick={() =>
                      router.replace(
                        poLinePath(d.buyer_po, line.style_no, line.colour),
                        { scroll: false },
                      )
                    }
                    className={clsx(
                      "shrink-0 whitespace-nowrap rounded-lg border px-3 py-2 text-sm transition-colors",
                      isActive
                        ? "border-blue-500 bg-blue-50 font-semibold text-blue-700 dark:bg-blue-500/15 dark:text-blue-300"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 dark:hover:text-slate-200",
                    )}
                  >
                    {line.style_no ?? "—"} · {line.colour ?? "—"}
                  </button>
                );
              })}
            </div>
          )}

          <div className="space-y-2">
            <FieldChipBar
              vocabulary={poVocabulary}
              chips={quickViewChips}
              onChange={setQuickViewChips}
              presets={poPresets}
              placeholder="Pin a field to Quick view — type a name, or pick a set below…"
            />
            <label className="flex w-fit cursor-pointer items-center gap-1.5 text-xs text-slate-600 dark:text-slate-300">
              <input
                type="checkbox"
                checked={hideEmpty}
                onChange={(e) => setHideEmpty(e.target.checked)}
                className="h-3.5 w-3.5 accent-blue-600"
              />
              Hide empty fields
            </label>
          </div>

          <PoLineCard
            key={active.tracker_row_id}
            buyerPo={d.buyer_po}
            line={active}
            groups={schema.data?.groups ?? []}
            fields={schema.data?.fields ?? []}
            role={user!.role}
            showTitle={d.lines.length === 1}
            onSaved={refresh}
            openSections={openSections}
            onToggleSection={(key, open) =>
              setOpenSections((current) => ({ ...current, [key]: open }))
            }
            quickViewKeys={quickViewKeys}
            hideEmpty={hideEmpty}
          />
        </div>
      )}

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
