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
  return Number(m[1]) * 10000 + Number(m[2]) * 100 + Number(m[3]);
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

/** Rows with no factory side yet are context, not problems - muted, not coloured. */
export function trackerRowClass(p: RowClassParams) {
  const row = p.data as { __hasVendor?: boolean } | undefined;
  return row && row.__hasVendor === false ? "tg-row-novendor" : undefined;
}
