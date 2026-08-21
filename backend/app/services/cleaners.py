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


# Excel stores an empty date cell as serial 0, which reads back as a date in
# early 1900 (1900-01-07, 1900-01-30, 1900-02-02 all appear in the real tracker,
# 736 times across its tabs). Those mean "blank", not "1900". Letting them
# through would store, display, sort, filter and re-export a garbage date, and
# make every "is this overdue?" rule fire. This is a 2026 shipping operation, so
# nothing before 2000 is a real date.
_MIN_PLAUSIBLE_YEAR = 2000


def _reject_excel_zero_date(value: date | None) -> date | None:
    return None if value is not None and value.year < _MIN_PLAUSIBLE_YEAR else value


def clean_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _reject_excel_zero_date(value.date())
    if isinstance(value, date):
        return _reject_excel_zero_date(value)
    if isinstance(value, str):
        s = value.strip()
        if s == "" or s.upper() in _EXCEL_ERROR_TOKENS:
            return None
        for fmt in _DATE_FORMATS:
            try:
                return _reject_excel_zero_date(datetime.strptime(s, fmt).date())
            except ValueError:
                continue
    return None
