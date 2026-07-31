"""Value cleaning helpers for parsing Excel cells into typed values.

Handles the messy real-world variety in these sheets: dates written as
``06 - Feb - 2026`` or ``27-Jul-26`` or native Excel datetimes, numbers with
stray commas/currency symbols, and Excel error tokens.
"""

from __future__ import annotations

from datetime import date, datetime

_EXCEL_ERROR_TOKENS = {"#VALUE!", "#REF!", "#DIV/0!", "#N/A", "#NAME?", "#NULL!", "NA", "N/A"}

_DATE_FORMATS = [
    "%d - %b - %Y",   # 06 - Feb - 2026
    "%d-%b-%Y",       # 06-Feb-2026
    "%d-%b-%y",       # 27-Jul-26
    "%d - %b - %y",
    "%d/%m/%Y",
    "%d/%m/%y",
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d.%m.%y",
    "%d %b %Y",
    "%d %B %Y",
]


def clean_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if s == "" or s.upper() in _EXCEL_ERROR_TOKENS:
            return None
        return s
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value).strip()


def clean_number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if s == "" or s.upper() in _EXCEL_ERROR_TOKENS:
            return None
        s = s.replace(",", "").replace("£", "").replace("$", "").replace("%", "").strip()
        try:
            return float(s)
        except ValueError:
            return None
    return None


def clean_int(value) -> int | None:
    n = clean_number(value)
    return int(round(n)) if n is not None else None


def clean_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s == "" or s.upper() in _EXCEL_ERROR_TOKENS:
            return None
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    return None
