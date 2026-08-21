import type { SeasonType } from "./types";

/** Mirror of backend app/services/seasons.py — keep the two in sync.
 *
 * March to August is Spring/Summer; the rest of the year is Autumn/Winter. An
 * Autumn/Winter season runs across the new year, so goods landing in January
 * 2027 belong to AW26, not AW27.
 */
export function seasonForDate(value: Date): { type: SeasonType; year: number } {
  const month = value.getMonth() + 1; // getMonth is 0-based
  if (month >= 3 && month <= 8) return { type: "SS", year: value.getFullYear() };
  return {
    type: "AW",
    year: month >= 9 ? value.getFullYear() : value.getFullYear() - 1,
  };
}

export const SEASON_NAMES: Record<SeasonType, string> = {
  SS: "Spring-Summer",
  AW: "Autumn-Winter",
};

export const seasonLabel = (type: SeasonType, year: number) =>
  `${SEASON_NAMES[type]} '${String(year % 100).padStart(2, "0")}`;

/** The season a date-like value falls in, or null if it isn't a usable date. */
export function seasonForValue(value: string | null | undefined) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : seasonForDate(parsed);
}
