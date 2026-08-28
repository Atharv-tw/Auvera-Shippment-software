from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- auth ----------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- admin: user management ----------------------------------------------------

class UserAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime


class UserRoleUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


# --- orders / vendor orders ----------------------------------------------------

class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    row_index: int | None = None
    order_date: str | None = None
    article: str | None = None
    description: str | None = None
    colour: str | None = None
    style_no: str | None = None
    topup: str | None = None
    lot: str | None = None
    garment_code: str | None = None
    sizes: dict[str, Any] = {}
    quantity: float | None = None
    price: float | None = None
    total_spent: float | None = None
    packing_method: str | None = None
    etd: date | None = None
    sleeve_length: str | None = None
    shoulder_pad: str | None = None
    hanger_foam: str | None = None
    composition: str | None = None
    lining: str | None = None
    brand: str | None = None
    swing_ticket_type: str | None = None
    label_extra: str | None = None
    factory: str | None = None
    store: str | None = None
    order_date_d: date | None = None


class OrderHeaderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_number: str | None = None
    supplier: str | None = None
    code: str | None = None
    country_of_payment: str | None = None
    payment_terms: str | None = None
    currency: str | None = None
    terms_of_delivery: str | None = None
    factory_town: str | None = None
    port_of_loading: str | None = None
    source_filename: str | None = None
    size_header: list[dict[str, Any]] = []
    created_at: datetime | None = None


class OrderOut(OrderHeaderOut):
    is_confirmation: bool = False
    lines: list[LineOut] = []


class VendorOrderOut(OrderHeaderOut):
    block_index: int = 0
    lines: list[LineOut] = []


# --- tracker -------------------------------------------------------------------

class TrackerColumnOut(BaseModel):
    col: str
    key: str
    label: str
    type: str
    source: str
    # May the caller write this column? The one answer, decided by
    # app/permissions.py - the UI reads it rather than re-deriving the rule.
    editable: bool = False
    # why it is locked, for the message on a disabled field. Descriptive only:
    # nothing infers editability from these.
    is_price: bool = False
    is_identity: bool = False
    is_derived: bool = False
    # for a derived column, the labels it is calculated from - so the UI can say
    # which fields to change instead of just refusing the edit
    derived_from: list[str] = []
    # how people actually write this column ("po no", "supplier", "sailing
    # date"). Already maintained for paste-matching; the UI's field search uses
    # the same vocabulary so both understand the same words.
    aliases: list[str] = []


class TrackerExportRequest(BaseModel):
    """Export what is on screen rather than the whole table.

    ``row_ids`` is the filtered set in the order the grid shows them; ``keys``
    the visible columns. Either omitted means "all of them", so the plain
    Download button still produces the full 56-column sheet.
    """
    row_ids: list[int] | None = None
    keys: list[str] | None = None


class TrackerRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    match_key: str
    buyer_po: str | None = None
    style_no: str | None = None
    colour: str | None = None
    article: str | None = None
    data: dict[str, Any] = {}
    edited_keys: list[str] = []
    has_buyer: bool = False
    has_vendor: bool = False
    updated_at: datetime | None = None


class TrackerRowUpdate(BaseModel):
    """Partial edit of one tracker row: {tracker_key: value}."""
    fields: dict[str, Any]


class TrackerRowBulkUpdate(BaseModel):
    updates: dict[int, dict[str, Any]]  # {tracker_row_id: {key: value}}


class TrackerRowCreate(BaseModel):
    fields: dict[str, Any]


# --- audit trail ---------------------------------------------------------------

class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    field_key: str
    field_label: str
    field_class: str
    old_value: str | None = None
    new_value: str | None = None
    action: str
    user_name: str | None = None
    created_at: datetime | None = None


# --- upload results ------------------------------------------------------------

# --- customers ----------------------------------------------------------------

class CustomerCreate(BaseModel):
    name: str
    address: str | None = None
    vat_number: str | None = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    address: str | None = None
    vat_number: str | None = None
    created_at: datetime | None = None


# --- upload results ------------------------------------------------------------

class UploadFileResult(BaseModel):
    filename: str
    kind: str | None = None  # customer | vendor
    kind_confidence: str | None = None  # high | medium | low
    kind_reason: str | None = None
    status: str  # created | merged | error
    order_ids: list[int] = []
    tracker_rows_touched: int = 0
    warnings: list[str] = []
    error: str | None = None


class SeasonSuggestion(BaseModel):
    """A PO this upload touched, with the season we think it belongs to."""
    buyer_po: str
    season_type: str  # SS | AW
    season_year: int
    confirmed: bool = False
    basis: str | None = None  # which date the suggestion came from


class UploadResponse(BaseModel):
    results: list[UploadFileResult]
    # POs from this upload awaiting a season decision by the merchant
    seasons: list[SeasonSuggestion] = []


# --- vendors ------------------------------------------------------------------

class VendorCreate(BaseModel):
    name: str
    address: str | None = None
    vat_number: str | None = None
    code: str | None = None
    country: str | None = None
    factory_town: str | None = None
    port_of_loading: str | None = None
    payment_terms: str | None = None
    terms_of_delivery: str | None = None
    currency: str | None = None


class VendorOut(VendorCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime | None = None


# --- seasons ------------------------------------------------------------------

class SeasonAssignment(BaseModel):
    buyer_po: str
    season_type: str = Field(pattern="^(SS|AW)$")
    season_year: int = Field(ge=2000, le=2100)


class SeasonAssignRequest(BaseModel):
    assignments: list[SeasonAssignment]


class SeasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    buyer_po: str
    season_type: str
    season_year: int
    confirmed: bool
    code: str
    label: str


class SeasonSummary(BaseModel):
    code: str
    label: str
    season_type: str
    season_year: int
    po_count: int


# --- per-PO view --------------------------------------------------------------

class PoFieldSpec(BaseModel):
    key: str
    label: str
    type: str
    group: str      # buyer | vendor | product | shipping
    origin: str     # tracker | order_line
    # as on TrackerColumnOut: `editable` is the answer, the flags are the reason
    editable: bool = False
    is_price: bool = False
    is_identity: bool = False
    is_derived: bool = False
    derived_from: list[str] = []


class PoSchemaOut(BaseModel):
    groups: list[dict[str, str]]
    fields: list[PoFieldSpec]


class PoLineOut(BaseModel):
    """One tracker row of a PO, plus the order-sheet detail behind it."""
    tracker_row_id: int
    style_no: str | None = None
    colour: str | None = None
    article: str | None = None
    has_buyer: bool = False
    has_vendor: bool = False
    tracker: dict[str, Any] = {}
    line: dict[str, Any] = {}
    sizes: dict[str, Any] = {}
    size_header: list[dict[str, Any]] = []


class PoSummaryOut(BaseModel):
    buyer_po: str
    customer_name: str | None = None
    factories: list[str] = []
    line_count: int = 0
    order_qty: float = 0
    buyer_total_value: float = 0
    vendor_total_value: float = 0
    season: SeasonOut | None = None
    statuses: dict[str, int] = {}


class PoDetailOut(BaseModel):
    buyer_po: str
    customer_name: str | None = None
    season: SeasonOut | None = None
    headers: list[dict[str, Any]] = []
    lines: list[PoLineOut] = []
    totals: dict[str, float] = {}


class PoRowUpdate(BaseModel):
    """Partial edit of one PO line: tracker columns and/or order-sheet fields."""
    tracker_fields: dict[str, Any] = {}
    line_fields: dict[str, Any] = {}


# --- paste ingest -------------------------------------------------------------

class PasteRequest(BaseModel):
    text: str
    buyer_po: str | None = None  # pin every row to this PO
    column_overrides: dict[str, str | None] = {}  # excel header -> field key / None


class PasteColumnReport(BaseModel):
    excel_header: str
    matched_field_key: str | None = None
    matched_field_label: str | None = None
    confidence: float = 0.0
    will_import: bool = False
    # write   - the value is written to this tracker column
    # locator - read to find the right row (PO / Style / Colour), never written
    # blocked - matched a column this role may not edit
    # ignored - matched nothing
    purpose: str = "ignored"
    blocked_reason: str | None = None


class PasteRowPreview(BaseModel):
    row_number: int
    buyer_po: str | None = None
    tracker_row_id: int | None = None
    mapped: dict[str, Any] = {}
    error: str | None = None


class PastePreviewOut(BaseModel):
    po_column_header: str | None = None
    headers: list[str] = []
    columns: list[PasteColumnReport] = []
    rows: list[PasteRowPreview] = []
    matched_pos: list[str] = []
    unmatched_pos: list[str] = []
    matched_row_count: int = 0
    error_row_count: int = 0


class PasteApplyOut(BaseModel):
    updated_rows: int = 0
    updated_fields: int = 0
    row_errors: list[PasteRowPreview] = []
    unmatched_pos: list[str] = []


# --- reports ------------------------------------------------------------------

class ReportBucket(BaseModel):
    key: str
    label: str
    po_count: int = 0
    line_count: int = 0
    order_qty: float = 0
    ship_qty: float = 0
    short_extra_qty: float = 0
    buyer_value: float = 0
    vendor_value: float = 0
    margin: float = 0
    margin_pct: float | None = None
    shipped_lines: int = 0
    pending_lines: int = 0
    avg_shipment_delay: float | None = None
    avg_docs_delay: float | None = None


class ReportOut(BaseModel):
    group_by: str
    buckets: list[ReportBucket] = []
    totals: ReportBucket
    filters: dict[str, Any] = {}
