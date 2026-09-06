"""Turn a table pasted out of an e-mail into tracker updates.

The shipping team lives in their inbox: a forwarder sends a booking table, a
factory sends invoice numbers, and today that gets retyped column by column.
This maps a pasted block onto tracker columns instead.

The approach is the one already proven in the sibling app: split the paste on
tabs, take the first row as headers, and fuzzy-match each header onto a tracker
column - never by position, because two pastes never have the same column
order. One tracker column can be claimed by at most one pasted column.

Matching is deliberately conservative. A column that matches nothing is left
alone rather than guessed at, and the caller can override any mapping before
anything is written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

from rapidfuzz import fuzz

from app.services import tracker_map as tm

MAPPED_THRESHOLD = 88
LOW_CONFIDENCE_THRESHOLD = 70
TIE_BREAK_WINDOW = 3

# dots glue abbreviations ("B.L." -> "bl"), other punctuation splits words
_DOT_RE = re.compile(r"\.")
_PUNCT_RE = re.compile(r"[#_/()\[\]{}:;,!?'\"&*+=|\\<>@$%^~`-]")
_DEDUPE_SUFFIX_RE = re.compile(r"\.\d+$")
_WS_RE = re.compile(r"\s+")

# How the shipping team's correspondents actually write these columns. The
# tracker's own labels are matched too, so this only needs the wordings that
# would otherwise miss.
ALIASES: dict[str, list[str]] = {
    "buyer_po": ["po", "po no", "po number", "po#", "buyer po", "order no", "order number",
                 "purchase order"],
    "style_no": ["style", "style no", "style number", "article no", "art no"],
    "colour": ["color", "colour", "shade"],
    "factory_name": ["factory", "supplier", "vendor", "manufacturer"],
    "customer_name": ["customer", "buyer", "client"],
    "order_qty": ["qty", "quantity", "order quantity", "ordered qty"],
    "ship_qty": ["shipped qty", "ship qty", "shipped quantity", "despatch qty"],
    "pkgs_ctns": ["cartons", "ctns", "ctn", "packages", "pkgs", "no of cartons"],
    "mode": ["mode", "shipment mode", "transport mode"],
    "etd": ["etd", "sailing date", "vessel sailing date", "sailed on", "departure"],
    "eta": ["eta", "arrival", "arrival date", "expected arrival"],
    "bl_no": ["bl", "bl no", "b l no", "awb", "awb no", "fcr", "fcr no", "bill of lading"],
    "bl_date": ["bl date", "awb date", "fcr date", "bill of lading date"],
    "container_no": ["container", "container no", "cntr", "cntr no", "container number"],
    "container_size": ["container size", "size", "box size", "equipment"],
    "lcl_fcl": ["lcl fcl", "lcl or fcl", "load type"],
    "vessel": ["vessel", "vessel name", "ship", "ship name"],
    "voyage": ["voyage", "voyage no", "voy"],
    "booking_no": ["booking", "booking no", "booking number", "booking ref"],
    "booking_date": ["booking date"],
    "forwarder": ["forwarder", "freight forwarder", "agent", "shipping line"],
    "pod": ["pod", "port of discharge", "destination port"],
    "factory_inv_no": ["factory invoice", "factory inv", "invoice no", "inv no"],
    "factory_inv_date": ["factory invoice date", "invoice date", "inv date"],
    "auvera_inv_no": ["auvera invoice", "auvera inv", "our invoice"],
    "shipment_status": ["status", "shipment status"],
    "remarks": ["remarks", "remark", "notes", "comment", "comments"],
    "final_inspection_date": ["inspection date", "final inspection"],
    "docs_received": ["docs received", "documents received"],
    "docs_due_date": ["docs due", "documents due"],
    "actual_ho_date": ["handover date", "ho date", "handover"],
}

PO_ALIAS_HINTS = ALIASES["buyer_po"]


def normalize_header(header: str) -> str:
    text = str(header).strip()
    text = _DEDUPE_SUFFIX_RE.sub("", text)
    text = text.lower()
    text = _DOT_RE.sub("", text)
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


# A header cell in a space-aligned table: a run of text with no two spaces in
# it, so "PO No." stays one column while "Colour   Mode" is two.
_HEADER_CELL_RE = re.compile(r"[^ ]+(?: [^ ]+)*")


def _column_bounds(header_line: str) -> list[tuple[int, int]]:
    """Character span of each column, taken from the header line."""
    starts = [m.start() for m in _HEADER_CELL_RE.finditer(header_line)]
    if len(starts) < 2:
        return []
    ends = starts[1:] + [len(header_line)]
    return list(zip(starts, ends))


def _cut(line: str, at: int, floor: int) -> int:
    """Move a column boundary off the middle of a word.

    Data rarely lines up with its header to the character: a right-aligned
    number reaches back before its header starts, a long value runs past where
    the next one begins. Whichever column a word *starts* in is the column it
    belongs to, so the boundary moves to that word's far edge rather than
    slicing it in half.
    """
    if at <= 0 or at >= len(line) or line[at] == " " or line[at - 1] == " ":
        return at
    start = at
    while start > 0 and line[start - 1] != " ":
        start -= 1
    if start <= floor:  # the word began in the left column - keep it there
        end = at
        while end < len(line) and line[end] != " ":
            end += 1
        return end
    return start


def _split_fixed_width(lines: list[str]) -> list[list[str]]:
    """Slice a space-aligned table at its header's column positions.

    Splitting each line on runs of two-or-more spaces cannot work here: an
    empty cell has nothing to split on, so the row comes back short and every
    value after the gap silently shifts a column left - a BL number landing in
    Mode. Cutting at fixed positions keeps an empty cell empty and every other
    value under its own header.
    """
    header_index = next((i for i, line in enumerate(lines) if line.strip()), None)
    if header_index is None:
        return [[line.strip()] for line in lines]
    bounds = _column_bounds(lines[header_index])
    if not bounds:  # single-column paste; nothing to align
        return [re.split(r" {2,}", line.strip()) for line in lines]

    rows: list[list[str]] = []
    for i, line in enumerate(lines):
        if i < header_index:
            rows.append(re.split(r" {2,}", line.strip()))
            continue
        cells: list[str] = []
        left = 0
        for n, (_start, end) in enumerate(bounds):
            right = len(line) if n == len(bounds) - 1 else _cut(line, end, left)
            cells.append(line[left:right].strip())
            left = right
        rows.append(cells)
    return rows


def parse_tsv(text: str) -> list[list[str]]:
    """Split a paste into rows of cells.

    Tab-separated is what Excel and Outlook tables put on the clipboard, and it
    marks the empty cells for us. A paste with no tabs at all is a plain-text
    table held together by alignment, so it is sliced at the header's own
    column positions instead of on runs of spaces.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    if any("\t" in line for line in lines):
        return [line.split("\t") for line in lines]
    return _split_fixed_width(lines)


def extract_table(rows: list[list[str]]) -> tuple[list[str], list[tuple[int, dict]]]:
    """First non-empty row is the header; the rest are data.

    Row numbers are 1-based over the paste so errors can point at a line the
    user can actually find.
    """
    header_index = next(
        (i for i, row in enumerate(rows) if any(str(c).strip() for c in row)), None
    )
    if header_index is None:
        return [], []

    headers: list[str] = []
    indexes: list[int] = []
    seen: dict[str, int] = {}
    for idx, cell in enumerate(rows[header_index]):
        name = str(cell).strip()
        if not name:
            continue
        if name in seen:
            seen[name] += 1
            name = f"{name}.{seen[name]}"
        else:
            seen[name] = 0
        headers.append(name)
        indexes.append(idx)

    data: list[tuple[int, dict]] = []
    for offset, row in enumerate(rows[header_index + 1:], start=header_index + 2):
        record = {
            header: (str(row[idx]).strip() if idx < len(row) else "")
            for header, idx in zip(headers, indexes)
        }
        if all(v == "" for v in record.values()):
            continue
        data.append((offset, record))
    return headers, data


def _candidates(key: str) -> list[str]:
    return [
        normalize_header(c)
        for c in [key, tm.LABEL_BY_KEY.get(key, ""), *ALIASES.get(key, [])]
        if c
    ]


def _score(normalized: str, key: str) -> tuple[float, bool]:
    """(best fuzzy score 0..100, exact alias hit)."""
    best = 0.0
    for candidate in _candidates(key):
        if candidate == normalized:
            return 100.0, True
        best = max(
            best,
            fuzz.token_sort_ratio(normalized, candidate),
            fuzz.WRatio(normalized, candidate),
        )
    return best, False


def detect_po_column(headers: list[str]) -> str | None:
    """Which pasted column holds the Buyer PO."""
    best, best_score = None, 0.0
    for header in headers:
        normalized = normalize_header(header)
        if normalized in PO_ALIAS_HINTS:
            return header
        score = max(fuzz.token_sort_ratio(normalized, a) for a in PO_ALIAS_HINTS)
        if score > best_score:
            best, best_score = header, score
    return best if best_score >= 80 else None


@dataclass
class MappingReport:
    columns: list[dict] = dc_field(default_factory=list)

    def mapping(self) -> dict[str, str]:
        """pasted header -> tracker column key, for the columns we will write."""
        return {
            c["excel_header"]: c["matched_field_key"]
            for c in self.columns
            if c["will_import"] and c["matched_field_key"]
        }


def map_columns(headers: list[str], allowed_keys: set[str] | None = None) -> MappingReport:
    """Fuzzy-match pasted headers onto tracker columns.

    ``allowed_keys`` is the caller's role permission set. Columns matching a
    key outside it are still reported - so the user can see the paste contained
    a price and that we refused it - but are not imported.
    """
    keys = [c["key"] for c in tm.TRACKER_COLUMNS if c["key"] not in tm.DERIVED_KEYS]

    columns: list[dict] = []
    scored: list[list[tuple[float, bool, str]]] = []
    for index, header in enumerate(headers):
        normalized = normalize_header(header)
        columns.append({
            "excel_header": str(header),
            "excel_index": index,
            "matched_field_key": None,
            "matched_field_label": None,
            "confidence": 0.0,
            "will_import": False,
            "purpose": "ignored",
            "blocked_reason": None,
        })
        scored.append(sorted(
            ((*_score(normalized, key), key) for key in keys),
            key=lambda t: t[0],
            reverse=True,
        ))

    claimed: set[str] = set()

    def claim(idx: int, key: str, confidence: float) -> None:
        blocked = allowed_keys is not None and key not in allowed_keys
        claimed.add(key)
        columns[idx].update(
            matched_field_key=key,
            matched_field_label=tm.LABEL_BY_KEY.get(key, key),
            confidence=round(confidence / 100.0, 4),
            will_import=not blocked,
            blocked_reason=(
                "your role cannot edit this column" if blocked else None
            ),
        )

    # strongest columns claim first, so on a clash the better match wins
    ranked: list[tuple[float, int, list[tuple[float, bool, str]]]] = []
    for idx in range(len(headers)):
        eligible = [c for c in scored[idx] if c[0] >= LOW_CONFIDENCE_THRESHOLD]
        if not eligible:
            continue
        top = eligible[0][0]
        window = [c for c in eligible if c[0] >= top - TIE_BREAK_WINDOW]
        window.sort(key=lambda c: not c[1])  # exact alias hits first
        ranked.append((top, idx, window))

    ranked.sort(key=lambda t: (-t[0], t[1]))
    for _top, idx, window in ranked:
        unclaimed = [c for c in window if c[2] not in claimed]
        if not unclaimed:
            continue
        score, _exact, key = unclaimed[0]
        claim(idx, key, score)

    return MappingReport(columns=columns)


def apply_overrides(report: MappingReport, overrides: dict[str, str | None],
                    allowed_keys: set[str] | None = None) -> dict[str, str]:
    """The final header -> key mapping after the user's manual corrections."""
    mapping = report.mapping()
    for header, key in overrides.items():
        mapping.pop(header, None)
        if key and key in tm.TRACKER_KEYS and key not in tm.DERIVED_KEYS:
            if allowed_keys is None or key in allowed_keys:
                mapping[header] = key
    return mapping
