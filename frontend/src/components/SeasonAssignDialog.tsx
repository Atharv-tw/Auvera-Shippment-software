"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Badge, Button, Card, ErrorNote, Select } from "@/components/ui";
import type { SeasonSuggestion, SeasonType } from "@/lib/types";

const THIS_YEAR = new Date().getFullYear();
const YEARS = [THIS_YEAR - 2, THIS_YEAR - 1, THIS_YEAR, THIS_YEAR + 1, THIS_YEAR + 2];

/** Confirm which season each PO from an upload belongs to.
 *
 * The paperwork never says, so the merchant decides. We pre-fill from the PO's
 * delivery date — March to August is Spring/Summer — and they adjust anything
 * that is wrong. The import has already happened; this only records the season.
 */
export function SeasonAssignDialog({
  suggestions,
  onDone,
}: {
  suggestions: SeasonSuggestion[];
  onDone: () => void;
}) {
  const [choices, setChoices] = useState<Record<string, { type: SeasonType; year: number }>>(
    Object.fromEntries(
      suggestions.map((s) => [s.buyer_po, { type: s.season_type, year: s.season_year }]),
    ),
  );
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pending = suggestions.filter((s) => !s.confirmed);
  if (suggestions.length === 0) return null;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api("/api/seasons/assign", {
        method: "POST",
        body: JSON.stringify({
          assignments: suggestions.map((s) => ({
            buyer_po: s.buyer_po,
            season_type: choices[s.buyer_po].type,
            season_year: choices[s.buyer_po].year,
          })),
        }),
      });
      setSaved(true);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save the seasons");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title="Which season do these orders belong to?">
      <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">
        The order sheets do not say, so please confirm. We have guessed from each PO&rsquo;s
        delivery date — March to August is Spring-Summer, the rest of the year
        Autumn-Winter.
      </p>

      {error && <ErrorNote message={error} />}

      <div className="space-y-2">
        {suggestions.map((s) => {
          const choice = choices[s.buyer_po];
          return (
            <div
              key={s.buyer_po}
              className="flex flex-wrap items-center gap-2 rounded-md border border-slate-100 p-2 dark:border-slate-800"
            >
              <span className="font-medium text-slate-900 dark:text-slate-100">
                {s.buyer_po}
              </span>
              {s.confirmed ? (
                <Badge color="green">already set</Badge>
              ) : (
                s.basis && <span className="text-xs text-slate-400">from {s.basis}</span>
              )}
              <div className="ml-auto flex gap-2">
                <div className="w-40">
                  <Select
                    disabled={saving || saved}
                    value={choice.type}
                    onChange={(e) =>
                      setChoices((c) => ({
                        ...c,
                        [s.buyer_po]: { ...choice, type: e.target.value as SeasonType },
                      }))
                    }
                  >
                    <option value="SS">Spring-Summer</option>
                    <option value="AW">Autumn-Winter</option>
                  </Select>
                </div>
                <div className="w-28">
                  <Select
                    disabled={saving || saved}
                    value={choice.year}
                    onChange={(e) =>
                      setChoices((c) => ({
                        ...c,
                        [s.buyer_po]: { ...choice, year: Number(e.target.value) },
                      }))
                    }
                  >
                    {YEARS.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex items-center gap-2">
        <Button disabled={saving || saved} onClick={save}>
          {saved ? "Seasons saved" : saving ? "Saving…" : "Confirm seasons"}
        </Button>
        {!saved && pending.length > 0 && (
          <span className="text-xs text-slate-400">
            {pending.length} PO(s) still need confirming — you can also set this later on
            the purchase order.
          </span>
        )}
      </div>
    </Card>
  );
}
