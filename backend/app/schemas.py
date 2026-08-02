from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- auth ----------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    role: str = "merchant"


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

class UploadFileResult(BaseModel):
    filename: str
    kind: str | None = None  # customer | vendor
    status: str  # created | merged | error
    order_ids: list[int] = []
    tracker_rows_touched: int = 0
    warnings: list[str] = []
    error: str | None = None


class UploadResponse(BaseModel):
    results: list[UploadFileResult]
