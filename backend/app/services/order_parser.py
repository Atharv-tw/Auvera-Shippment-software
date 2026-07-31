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

# I..X -> size buckets
_SIZE_BUCKETS = ["6", "8", "10", "12", "14", "16", "18", "20", "22", "24", "26", "28", "30", "32", "34", "36"]
_SIZE_COLS = {get_column_letter(column_index_from_string("I") + i): bucket for i, bucket in enumerate(_SIZE_BUCKETS)}

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
    value_row = label_row + 1
    for c in range(1, ws.max_column + 1):
        key = _HEADER_LABELS.get(_norm(ws.cell(row=label_row, column=c).value))
        if key and key not in header:
            header[key] = clean_text(ws.cell(row=value_row, column=c).value)
    # buyer block (company/address/VAT) lives in the merged D1 cell
    header["buyer_block"] = clean_text(_cell(ws, 1, "D"))
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


def _parse_lines(ws, data_start: int, end: int, tail: dict) -> list[dict]:
    lines: list[dict] = []
    for r in range(data_start, end):
        # stop at the block's Total row
        if _norm(_cell(ws, r, "C")) == "total":
            break
        row: dict = {}
        for col, (key, kind) in _PRE_SIZE.items():
            row[key] = _coerce(_cell(ws, r, col), kind)
        sizes: dict[str, int] = {}
        for col, bucket in _SIZE_COLS.items():
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
        row["row_index"] = r
        lines.append(row)
    return lines


def detect_kind(path: str, name_hint: str | None = None) -> str:
    """Return 'customer' or 'vendor' for a workbook (filename hint, then layout)."""
    name = f"{name_hint or ''} {path}".lower()
    if "vendor" in name:
        return "vendor"
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = _get_sheet(wb)
        heads = _header_label_rows(ws)
        if not heads:
            return "customer"
        lh = _line_header_row(ws, heads[0], ws.max_row + 1)
        if lh is None:
            return "customer"
        return _detect_kind_from_line_header(ws, lh)
    finally:
        wb.close()


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
    lines = _parse_lines(ws, line_hdr + 1, ws.max_row + 1, _CUSTOMER_TAIL)
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
        lines = _parse_lines(ws, line_hdr + 1, end, _VENDOR_TAIL)
        blocks.append({"header": header, "lines": lines})
    return {"kind": "vendor", "blocks": blocks}


def parse_workbook(path: str, name_hint: str | None = None) -> dict:
    """Auto-detect and parse; returns {'kind': 'customer'|'vendor', ...}."""
    kind = detect_kind(path, name_hint)
    return parse_vendor_order(path) if kind == "vendor" else parse_customer_order(path)
