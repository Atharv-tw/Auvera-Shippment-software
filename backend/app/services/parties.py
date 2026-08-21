"""Pull customer / vendor identities out of the order paperwork.

The buyer sheets never name the customer in a labelled field - the customer is
the merged block in cell D1, three lines of free text::

    Roman Originals PLC
    Unit 1, Vantage Point, 5 Wingfoot Close, Birmingham. B24 9JH
    VAT Number: GB 111 3607 23

(The sheets' own "Supplier" field is *us*, Auvera Studio Limited.) Vendors are
simpler: the factory is the Supplier of each vendor block.

Pure parsing, no database - see ``masters.py`` for the upserts.
"""

from __future__ import annotations

_VAT_PREFIXES = ("vat number", "vat no", "vat")


def parse_buyer_block(text: str | None) -> dict:
    """Split the D1 customer block into ``{name, address, vat_number}``."""
    if not text:
        return {"name": None, "address": None, "vat_number": None}
    lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
    if not lines:
        return {"name": None, "address": None, "vat_number": None}

    name = lines[0]
    vat: str | None = None
    address_lines: list[str] = []
    for line in lines[1:]:
        lowered = line.lower()
        if vat is None and any(lowered.startswith(p) for p in _VAT_PREFIXES):
            # "VAT Number: GB 111 3607 23" -> "GB 111 3607 23"
            vat = line.split(":", 1)[1].strip() if ":" in line else line
            continue
        address_lines.append(line)
    return {
        "name": name,
        "address": ", ".join(address_lines) or None,
        "vat_number": vat,
    }
