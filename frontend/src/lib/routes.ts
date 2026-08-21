/** Links into the per-PO view.
 *
 * A line's identity is Buyer PO# + Style No. (+TopUp) + Colour — the same three
 * parts as the tracker's `match_key` — so a deep link carries style *and*
 * colour. Style alone would be ambiguous the moment one style ships in two
 * colours.
 */
export function poLinePath(
  buyerPo: string,
  style?: string | null,
  colour?: string | null,
) {
  const base = `/pos/${encodeURIComponent(buyerPo)}`;
  if (!style) return base;
  if (!colour) return `${base}/${encodeURIComponent(style)}`;
  return `${base}/${encodeURIComponent(style)}/${encodeURIComponent(colour)}`;
}

/** Route segments arrive decoded, but never trust a hand-typed URL. */
export function safeDecode(segment: string) {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

/** Case- and whitespace-insensitive compare for style / colour segments. */
export function segmentMatches(value: string | null, segment: string | undefined) {
  if (segment === undefined) return true;
  return (value ?? "").trim().toLowerCase() === safeDecode(segment).trim().toLowerCase();
}
