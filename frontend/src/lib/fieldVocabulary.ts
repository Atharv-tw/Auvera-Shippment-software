import type { PoFieldSpec, TrackerColumn } from "@/lib/types";

/** One searchable entry per field: its label, its key, and the words people
 * actually use for it. The aliases come from the backend's paste-matching
 * vocabulary rather than a second list invented here, so "supplier",
 * "factory" and "Factory's Name" all resolve to the same column. */
export type FieldEntry = {
  key: string;
  label: string;
  type: "text" | "number" | "date";
  /** everything this field can be matched on, lower-cased */
  terms: string[];
};

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

function entry(key: string, label: string, type: FieldEntry["type"], aliases?: string[]): FieldEntry {
  const terms = new Set<string>([norm(label), norm(key)]);
  for (const a of aliases ?? []) terms.add(norm(a));
  return { key, label, type, terms: [...terms].filter(Boolean) };
}

export function vocabularyFromColumns(columns: TrackerColumn[]): FieldEntry[] {
  return columns.map((c) => entry(c.key, c.label.trim(), c.type, c.aliases));
}

export function vocabularyFromFields(fields: PoFieldSpec[]): FieldEntry[] {
  return fields.map((f) => entry(f.key, f.label.trim(), f.type));
}

/** Ranked matches. Prefix hits beat substring hits, so typing "col" offers
 * Colour before "Container No." even though both contain the letters. */
export function searchVocabulary(vocab: FieldEntry[], query: string, limit = 8): FieldEntry[] {
  const q = norm(query);
  if (!q) return [];
  const scored: { entry: FieldEntry; score: number }[] = [];
  for (const e of vocab) {
    let best = Infinity;
    for (const t of e.terms) {
      if (t === q) best = Math.min(best, 0);
      else if (t.startsWith(q)) best = Math.min(best, 1);
      else if (t.includes(q)) best = Math.min(best, 2);
    }
    if (best < Infinity) scored.push({ entry: e, score: best });
  }
  scored.sort((a, b) => a.score - b.score || a.entry.label.localeCompare(b.entry.label));
  return scored.slice(0, limit).map((s) => s.entry);
}

// --- chips ------------------------------------------------------------------

export type Chip =
  /** show this field / column */
  | { kind: "field"; key: string; label: string }
  /** narrow rows to those matching */
  | { kind: "filter"; key: string; label: string; op: FilterOp; value: string; type: FieldEntry["type"] }
  /** free text, matched against everything */
  | { kind: "text"; value: string };

export type FilterOp = "=" | "!=" | "<" | "<=" | ">" | ">=" | "~";

const OPERATORS: FilterOp[] = [">=", "<=", "!=", "=", "<", ">", "~"];

/** Turn typed text into a chip.
 *
 * `vendor total value`      -> show that column
 * `factory = CRIMSON`       -> filter rows
 * `price difference < 0`    -> filter rows
 * `CRIMSON`                 -> free-text search
 *
 * Note what this does NOT do: split on commas. Column AV is literally named
 * "Approval, Carting, DO date" and remarks contain commas, so a comma
 * delimiter would corrupt real values. The comma is only a key that commits
 * the chip; once committed a chip is atomic and never re-parsed.
 */
export function parseChip(raw: string, vocab: FieldEntry[]): Chip | null {
  const text = raw.trim();
  if (!text) return null;

  for (const op of OPERATORS) {
    const at = text.indexOf(op);
    if (at <= 0) continue;
    const lhs = text.slice(0, at).trim();
    const rhs = text.slice(at + op.length).trim();
    if (!lhs || !rhs) continue;
    const field = searchVocabulary(vocab, lhs, 1)[0];
    if (!field) continue;
    return { kind: "filter", key: field.key, label: field.label, op, value: rhs, type: field.type };
  }

  const exact = searchVocabulary(vocab, text, 1)[0];
  if (exact) return { kind: "field", key: exact.key, label: exact.label };
  return { kind: "text", value: text };
}

export function chipId(chip: Chip): string {
  return chip.kind === "text"
    ? `text:${chip.value}`
    : chip.kind === "field"
      ? `field:${chip.key}`
      : `filter:${chip.key}:${chip.op}:${chip.value}`;
}

export function chipLabel(chip: Chip): string {
  if (chip.kind === "text") return `"${chip.value}"`;
  if (chip.kind === "field") return chip.label;
  return `${chip.label} ${chip.op} ${chip.value}`;
}

// --- chips -> AG Grid ---------------------------------------------------------

const TEXT_OPS: Record<FilterOp, string> = {
  "=": "equals", "!=": "notEqual", "~": "contains",
  "<": "lessThan", "<=": "lessThan", ">": "greaterThan", ">=": "greaterThan",
};
const NUM_OPS: Record<FilterOp, string> = {
  "=": "equals", "!=": "notEqual", "~": "equals",
  "<": "lessThan", "<=": "lessThanOrEqual",
  ">": "greaterThan", ">=": "greaterThanOrEqual",
};

/** Filter chips -> an AG Grid filter model, so chips and the floating filter
 * row drive the same state rather than two competing ones. */
export function chipsToFilterModel(chips: Chip[]): Record<string, unknown> {
  const model: Record<string, unknown> = {};
  for (const chip of chips) {
    if (chip.kind !== "filter") continue;
    if (chip.type === "number") {
      const n = Number(chip.value);
      if (!Number.isFinite(n)) continue;
      model[chip.key] = { filterType: "number", type: NUM_OPS[chip.op], filter: n };
    } else if (chip.type === "date") {
      model[chip.key] = {
        filterType: "date",
        type: chip.op === "=" ? "equals" : NUM_OPS[chip.op],
        dateFrom: chip.value,
      };
    } else {
      model[chip.key] = { filterType: "text", type: TEXT_OPS[chip.op], filter: chip.value };
    }
  }
  return model;
}

/** Field chips -> the columns to show. Empty means "show everything". */
export function visibleKeysFromChips(chips: Chip[]): string[] | null {
  const keys = chips.filter((c) => c.kind === "field").map((c) => (c as { key: string }).key);
  return keys.length ? keys : null;
}

/** Free-text chips collapse into AG Grid's quick filter. */
export function quickFilterFromChips(chips: Chip[]): string {
  return chips
    .filter((c) => c.kind === "text")
    .map((c) => (c as { value: string }).value)
    .join(" ");
}
