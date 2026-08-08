/** Dates are stored/transmitted as ISO "yyyy-mm-dd" strings; these convert
 * to/from the "dd-mm-yyyy" format used everywhere in the UI. */

const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const DISPLAY_RE = /^(\d{2})-(\d{2})-(\d{4})$/;

export function toDisplayDate(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  const s = String(value);
  const m = ISO_RE.exec(s);
  if (!m) return s;
  const [, y, mo, d] = m;
  return `${d}-${mo}-${y}`;
}

export function toIsoDate(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  const s = String(value).trim();
  const m = DISPLAY_RE.exec(s);
  if (!m) return s;
  const [, d, mo, y] = m;
  return `${y}-${mo}-${d}`;
}
