import type { CellClassParams, RowClassParams } from "ag-grid-community";

/** Conditional formatting for the tracker, the Excel feature people actually
 * scan for. These are deliberately a fixed set of domain rules rather than a
 * rule builder: they answer "what needs attention" without anyone configuring
 * anything, which is the whole point for someone who just opens the sheet.
 */

/** ISO date -> comparable YYYYMMDD number. Parsed by hand rather than via
 * `new Date(...)`: `new Date("2026-08-12")` is UTC midnight, and reading it
 * back with local getters shifts the day in negative offsets. */
export function isoToNumber(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!m) return null;
  const year = Number(m[1]);
  // Excel turns an empty date cell into serial 0, which reads back as
  // 1900-01-0x. The real tracker is full of them - four of its seven rows carry
  // 1900-01-07 in Docs Due Date - and treating those as genuinely overdue would
  // light up most of the sheet amber for a value that means "blank".
  if (year < 2000) return null;
  return year * 10000 + Number(m[2]) * 100 + Number(m[3]);
}

function today(): number {
  const d = new Date();
  return d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
}

const num = (v: unknown): number | null => {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

const blank = (v: unknown) => v === null || v === undefined || v === "";

type Rule = (value: unknown, row: Record<string, unknown>) => boolean;

/** key -> { bad, warn }. A cell gets at most one class; bad wins. */
export const HIGHLIGHT_RULES: Record<string, { bad?: Rule; warn?: Rule }> = {
  // late is late
  docs_delay_days: { bad: (v) => (num(v) ?? 0) > 0 },
  delay_shipment: { bad: (v) => (num(v) ?? 0) > 0 },
  // we are paying the factory more than the buyer pays us
  price_difference: { bad: (v) => (num(v) ?? 0) < 0 },
  // due to leave, nothing sailed
  buyer_po_delivery_date: {
    warn: (v, row) => {
      const due = isoToNumber(v);
      return due !== null && due < today() && blank(row.etd);
    },
  },
  // docs were due and have not arrived
  docs_due_date: {
    warn: (v, row) => {
      const due = isoToNumber(v);
      return due !== null && due < today() && blank(row.docs_received);
    },
  },
  // shipped quantity does not match what was ordered
  short_extra_qty: { warn: (v) => (num(v) ?? 0) !== 0 },
};

export function cellClassRulesFor(key: string) {
  const rule = HIGHLIGHT_RULES[key];
  if (!rule) return undefined;
  return {
    "tg-bad": (p: CellClassParams) =>
      !!rule.bad?.(p.value, (p.data ?? {}) as Record<string, unknown>),
    "tg-warn": (p: CellClassParams) =>
      !rule.bad?.(p.value, (p.data ?? {}) as Record<string, unknown>) &&
      !!rule.warn?.(p.value, (p.data ?? {}) as Record<string, unknown>),
  };
}

/** A row with no factory side yet is incomplete, not wrong.
 *
 * Marked with an edge rule rather than dimmed: greying reads as "disabled" in
 * almost every interface, and these rows are perfectly editable. */
export function trackerRowClass(p: RowClassParams) {
  const row = p.data as { __hasVendorData?: boolean } | undefined;
  return row && row.__hasVendorData === false ? "tg-row-novendor" : undefined;
}

/** The same rules, for a single field outside the grid (the per-PO view).
 * Returns "bad" | "warn" | null so a caller can pick its own styling. */
export function fieldFlag(
  key: string,
  value: unknown,
  row: Record<string, unknown>,
): "bad" | "warn" | null {
  const rule = HIGHLIGHT_RULES[key];
  if (!rule) return null;
  if (rule.bad?.(value, row)) return "bad";
  if (rule.warn?.(value, row)) return "warn";
  return null;
}
