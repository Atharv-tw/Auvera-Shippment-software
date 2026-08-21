"""Parsers for the Roman Originals "Order" template.

Two variants share the same header block and A..X line columns but differ after
column X:

* **Customer Order / Order Confirmation** (buyer): ``Y`` Quantity, ``Z`` Price,
  ``AA`` Total Spent, ``AB`` Packing method, ...
* **Vendor Order** (factory): no "Total Spent" column, so everything from ``AA``
  shifts left by one. A vendor workbook may also stack **several order blocks**
  (one per factory), each with its own header + Total row.

Both parsers return plain dicts so they are easy to test and decoupled from the
ORM.
"""

from __future__ import annotations

from datetime import date, datetime

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter

from app.services.cleaners import clean_date, clean_int, clean_number, clean_text

# --- column maps (1-based indices via column letters) --------------------------

_PRE_SIZE = {
    "A": ("order_date", "text"),
    "B": ("article", "text"),
    "C": ("description", "text"),
    "D": ("colour", "text"),
    "E": ("style_no", "text"),
    "F": ("topup", "text"),
    "G": ("lot", "text"),
    "H": ("garment_code", "text"),
}

# I..X hold the size ratio. The real bucket names are read off the sheet's own
# header row (see _parse_size_header); these are the fallback when that row is
# unreadable, and they also fix the column span.
_SIZE_BUCKETS = ["6", "8", "10", "12", "14", "16", "18", "20", "22", "24", "26", "28", "30", "32", "34", "36"]
_SIZE_COLS = {get_column_letter(column_index_from_string("I") + i): bucket for i, bucket in enumerate(_SIZE_BUCKETS)}
_SIZE_FIRST_COL = "I"
_SIZE_LAST_COL = "X"

# the buyer sheets always name us as the supplier; the vendor sheets name the factory
_OUR_COMPANY = "auvera studio limited"

_CUSTOMER_TAIL = {
    "Y": ("quantity", "int"),
    "Z": ("price", "number"),
    "AA": ("total_spent", "number"),
    "AB": ("packing_method", "text"),
    "AC": ("etd", "date"),
    "AD": ("sleeve_length", "text"),
    "AE": ("shoulder_pad", "text"),
    "AF": ("hanger_foam", "text"),
    "AG": ("composition", "text"),
    "AH": ("lining", "text"),
    "AJ": ("brand", "text"),
    "AK": ("swing_ticket_type", "text"),
    "AL": ("label_extra", "text"),
    "AM": ("factory", "text"),
    "AN": ("store", "text"),
}

_VENDOR_TAIL = {
    "Y": ("quantity", "int"),
    "Z": ("price", "number"),
    "AA": ("packing_method", "text"),
    "AB": ("etd", "date"),
    "AC": ("sleeve_length", "text"),
    "AD": ("shoulder_pad", "text"),
    "AE": ("hanger_foam", "text"),
    "AF": ("composition", "text"),
    "AG": ("lining", "text"),
    "AI": ("brand", "text"),
    "AJ": ("swing_ticket_type", "text"),
    "AK": ("label_extra", "text"),
    "AL": ("factory", "text"),
    "AM": ("store", "text"),
}

_HEADER_LABELS = {
    "order number": "order_number",
    "supplier": "supplier",
    "code": "code",
    "country of payment": "country_of_payment",
    "payment terms": "payment_terms",
    "currency": "currency",
    "terms of delivery": "terms_of_delivery",
    "factory town": "factory_town",
    "port of loading": "port_of_loading",
}


def _norm(text) -> str:
    return " ".join(str(text).strip().lower().split()) if text is not None else ""


def _coerce(value, kind: str):
    if kind == "int":
        return clean_int(value)
    if kind == "number":
        return clean_number(value)
    if kind == "date":
        return clean_date(value)
    return clean_text(value)


def _json_safe(value):
    """Excel cells land in JSON columns, so dates have to become strings."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _parse_size_header(ws, line_header_row: int) -> list[dict]:
    """Read the size-ratio grid spec off the sheet.

    Each I..X header is a three-line cell holding the UK size, the alpha size
    and the size range - "24 / XL / 22-24" - though most carry only the UK
    size. Returns one entry per size column so per-size reporting can group by
    whichever of the three the client asks for.
    """
    spec: list[dict] = []
    first = column_index_from_string(_SIZE_FIRST_COL)
    last = column_index_from_string(_SIZE_LAST_COL)
    for idx in range(first, last + 1):
        col = get_column_letter(idx)
        raw = ws.cell(row=line_header_row, column=idx).value
        parts = [p.strip() for p in str(raw).splitlines()] if raw is not None else []
        parts += [""] * (3 - len(parts))
        uk = parts[0] or None
        if uk is None:
            continue
        spec.append({
            "col": col,
            "uk_size": uk,
            "alpha_size": parts[1] or None,
            "range_label": parts[2] or None,
        })
    return spec


def _header_texts(ws, line_header_row: int) -> dict[str, str]:
    """Column letter -> the header text above it on the line-header row."""
    out: dict[str, str] = {}
    for idx in range(1, ws.max_column + 1):
        text = clean_text(ws.cell(row=line_header_row, column=idx).value)
        if text:
            out[get_column_letter(idx)] = " ".join(text.split())
    return out


def _raw_row(ws, row: int, header_texts: dict[str, str]) -> dict:
    """Every non-empty cell of a line, keyed by Excel column letter.

    Columns we have no modelled field for still end up here, so a template that
    grows a column later loses nothing on import.
    """
    out: dict = {}
    for idx in range(1, ws.max_column + 1):
        value = ws.cell(row=row, column=idx).value
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        col = get_column_letter(idx)
        out[col] = {"header": header_texts.get(col), "value": _json_safe(value)}
    return out


def _get_sheet(wb):
    return wb["Order"] if "Order" in wb.sheetnames else wb.active


def _cell(ws, row: int, col_letter: str):
    return ws.cell(row=row, column=column_index_from_string(col_letter)).value


# --- block / header detection --------------------------------------------------

def _header_label_rows(ws) -> list[int]:
    """Rows whose column A reads 'Order number' — the top of each order block."""
    rows = []
    for r in range(1, ws.max_row + 1):
        if _norm(_cell(ws, r, "A")) == "order number":
            rows.append(r)
    return rows


def _parse_header(ws, label_row: int) -> dict:
    """Read a block header by scanning the label row and reading the row below.

    Robust to the one-column shift between customer and vendor layouts, since we
    locate each label by text rather than by fixed column.
    """
    header: dict = {}
    raw_header: dict = {}
    value_row = label_row + 1
    for c in range(1, ws.max_column + 1):
        label_cell = ws.cell(row=label_row, column=c).value
        value = clean_text(ws.cell(row=value_row, column=c).value)
        label = clean_text(label_cell)
        if label:
            # keep every label the block carries, modelled or not
            raw_header[" ".join(label.split())] = value
        key = _HEADER_LABELS.get(_norm(label_cell))
        if key and key not in header:
            header[key] = value
    # buyer block (company/address/VAT) lives in the merged D1 cell
    header["buyer_block"] = clean_text(_cell(ws, 1, "D"))
    header["raw_header"] = raw_header
    return header


def _line_header_row(ws, start: int, end: int) -> int | None:
    """Within [start, end), find the row whose column B reads 'Article'."""
    for r in range(start, end):
        if _norm(_cell(ws, r, "B")) == "article":
            return r
    return None


def _detect_kind_from_line_header(ws, line_header_row: int) -> str:
    """Customer sheets label AA 'Total Spent'; vendor sheets label AA 'Packing method'."""
    aa = _norm(_cell(ws, line_header_row, "AA"))
    if "total spent" in aa:
        return "customer"
    if "packing" in aa:
        return "vendor"
    return "customer"


def _parse_lines(
    ws,
    data_start: int,
    end: int,
    tail: dict,
    size_cols: dict[str, str] | None = None,
    header_texts: dict[str, str] | None = None,
) -> list[dict]:
    size_cols = size_cols or _SIZE_COLS
    header_texts = header_texts or {}
    lines: list[dict] = []
    for r in range(data_start, end):
        # stop at the block's Total row
        if _norm(_cell(ws, r, "C")) == "total":
            break
        row: dict = {}
        for col, (key, kind) in _PRE_SIZE.items():
            row[key] = _coerce(_cell(ws, r, col), kind)
        sizes: dict[str, int] = {}
        for col, bucket in size_cols.items():
            v = clean_int(_cell(ws, r, col))
            if v:
                sizes[bucket] = v
        row["sizes"] = sizes
        for col, (key, kind) in tail.items():
            row[key] = _coerce(_cell(ws, r, col), kind)
        # skip fully-empty rows (no article and no description and no sizes)
        if not row.get("article") and not row.get("description") and not sizes:
            continue
        # quantity falls back to the sum of size buckets
        if row.get("quantity") is None and sizes:
            row["quantity"] = sum(sizes.values())
        # the sheet writes the order date as text ("13 - Apr - 2026"); keep that
        # verbatim and carry a real date alongside it for grouping / seasons
        row["order_date_d"] = clean_date(row.get("order_date"))
        row["raw"] = _raw_row(ws, r, header_texts)
        row["row_index"] = r
        lines.append(row)
    return lines


def detect_kind_detail(path: str, name_hint: str | None = None) -> dict:
    """Work out whether a workbook is a buyer or a vendor sheet.

    The layout decides it, not the filename: the vendor template has no "Total
    Spent" column, so everything from AA shifts left by one and cell AA on the
    line-header row reads "Packing method" instead. Getting this backwards
    would read prices out of the wrong columns, so the filename is only ever a
    last-resort tiebreak.

    Returns ``{kind, confidence, reason}`` so the upload screen can show what
    was detected and let the user override before anything is written.
    """
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = _get_sheet(wb)
        heads = _header_label_rows(ws)
        if heads:
            line_header = _line_header_row(ws, heads[0], ws.max_row + 1)
            if line_header is not None:
                aa = _norm(_cell(ws, line_header, "AA"))
                if "total spent" in aa:
                    return {"kind": "customer", "confidence": "high",
                            "reason": "column AA is 'Total Spent'"}
                if "packing" in aa:
                    return {"kind": "vendor", "confidence": "high",
                            "reason": "column AA is 'Packing method'"}
            # AA was unreadable - fall back on who the sheet names as supplier
            supplier = _norm(_parse_header(ws, heads[0]).get("supplier"))
            if supplier:
                if supplier == _OUR_COMPANY:
                    return {"kind": "customer", "confidence": "medium",
                            "reason": f"supplier is us ({supplier})"}
                return {"kind": "vendor", "confidence": "medium",
                        "reason": f"supplier is a factory ({supplier})"}
            if len(heads) > 1:
                return {"kind": "vendor", "confidence": "medium",
                        "reason": f"{len(heads)} stacked order blocks"}
        name = f"{name_hint or ''}".lower()
        if "vendor" in name:
            return {"kind": "vendor", "confidence": "low", "reason": "filename says vendor"}
        return {"kind": "customer", "confidence": "low", "reason": "no layout signal, defaulted"}
    finally:
        wb.close()


def detect_kind(path: str, name_hint: str | None = None) -> str:
    """Return 'customer' or 'vendor' for a workbook."""
    return detect_kind_detail(path, name_hint)["kind"]


def parse_customer_order(path: str) -> dict:
    """Parse a Customer-Order / Order-Confirmation workbook (single block)."""
    wb = load_workbook(path, data_only=True)
    ws = _get_sheet(wb)
    heads = _header_label_rows(ws)
    if not heads:
        raise ValueError("No 'Order number' header found — not a recognised order sheet")
    label_row = heads[0]
    header = _parse_header(ws, label_row)
    line_hdr = _line_header_row(ws, label_row, ws.max_row + 1)
    if line_hdr is None:
        raise ValueError("No 'Article' line-header row found")
    size_header = _parse_size_header(ws, line_hdr)
    header["size_header"] = size_header
    lines = _parse_lines(
        ws, line_hdr + 1, ws.max_row + 1, _CUSTOMER_TAIL,
        size_cols={e["col"]: e["uk_size"] for e in size_header},
        header_texts=_header_texts(ws, line_hdr),
    )
    return {"kind": "customer", "header": header, "lines": lines}


def parse_vendor_order(path: str) -> dict:
    """Parse a Vendor-Order workbook — one or more stacked factory blocks."""
    wb = load_workbook(path, data_only=True)
    ws = _get_sheet(wb)
    heads = _header_label_rows(ws)
    if not heads:
        raise ValueError("No 'Order number' header found — not a recognised order sheet")
    bounds = heads + [ws.max_row + 1]
    blocks: list[dict] = []
    for i, label_row in enumerate(heads):
        end = bounds[i + 1]
        header = _parse_header(ws, label_row)
        line_hdr = _line_header_row(ws, label_row, end)
        if line_hdr is None:
            continue
        size_header = _parse_size_header(ws, line_hdr)
        header["size_header"] = size_header
        lines = _parse_lines(
            ws, line_hdr + 1, end, _VENDOR_TAIL,
            size_cols={e["col"]: e["uk_size"] for e in size_header},
            header_texts=_header_texts(ws, line_hdr),
        )
        blocks.append({"header": header, "lines": lines})
    return {"kind": "vendor", "blocks": blocks}


def parse_workbook(path: str, name_hint: str | None = None) -> dict:
    """Auto-detect and parse; returns {'kind': 'customer'|'vendor', ...}."""
    kind = detect_kind(path, name_hint)
    return parse_vendor_order(path) if kind == "vendor" else parse_customer_order(path)
