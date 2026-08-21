from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    # admin | ceo | shipping_manager | merchant  (legacy: vendor -> read-only)
    role: Mapped[str] = mapped_column(String(20), default="merchant")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# --- shared line-item columns --------------------------------------------------

class _LineColumns:
    row_index: Mapped[int | None] = mapped_column(Integer)
    order_date: Mapped[str | None] = mapped_column(String(64))
    # the same order date parsed to a real date, for grouping / season defaults
    order_date_d: Mapped[date | None] = mapped_column(Date)
    article: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(String(255))
    colour: Mapped[str | None] = mapped_column(String(64))
    style_no: Mapped[str | None] = mapped_column(String(64), index=True)
    topup: Mapped[str | None] = mapped_column(String(32))
    lot: Mapped[str | None] = mapped_column(String(32))
    garment_code: Mapped[str | None] = mapped_column(String(32))
    sizes: Mapped[dict] = mapped_column(JSON, default=dict)
    quantity: Mapped[float | None] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float)
    packing_method: Mapped[str | None] = mapped_column(String(64))
    etd: Mapped[date | None] = mapped_column(Date)
    sleeve_length: Mapped[str | None] = mapped_column(String(64))
    shoulder_pad: Mapped[str | None] = mapped_column(String(64))
    hanger_foam: Mapped[str | None] = mapped_column(String(64))
    composition: Mapped[str | None] = mapped_column(String(255))
    lining: Mapped[str | None] = mapped_column(String(64))
    brand: Mapped[str | None] = mapped_column(String(64))
    swing_ticket_type: Mapped[str | None] = mapped_column(String(64))
    label_extra: Mapped[str | None] = mapped_column(String(64))
    factory: Mapped[str | None] = mapped_column(String(128))
    store: Mapped[str | None] = mapped_column(String(32))
    # every non-empty cell of the source row, keyed by Excel column letter, with
    # the header text it sat under. Nothing the sheet carries is thrown away —
    # columns we have no field for are still recoverable from here.
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class _OrderHeaderColumns:
    order_number: Mapped[str | None] = mapped_column(String(64), index=True)
    supplier: Mapped[str | None] = mapped_column(String(128))
    code: Mapped[str | None] = mapped_column(String(32))
    country_of_payment: Mapped[str | None] = mapped_column(String(64))
    payment_terms: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(16))
    terms_of_delivery: Mapped[str | None] = mapped_column(String(64))
    factory_town: Mapped[str | None] = mapped_column(String(64))
    port_of_loading: Mapped[str | None] = mapped_column(String(64))
    buyer_block: Mapped[str | None] = mapped_column(Text)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    # full label -> value map of the block header, including labels we do not model
    raw_header: Mapped[dict] = mapped_column(JSON, default=dict)
    # the size-ratio grid spec read off the sheet: one entry per size column,
    # {col, uk_size, alpha_size, range_label} — e.g. 24 / XL / 22-24
    size_header: Mapped[list] = mapped_column(JSON, default=list)


# --- buyer side ----------------------------------------------------------------

class Order(Base, TimestampMixin, _OrderHeaderColumns):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    is_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    lines: Mapped[list["OrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderLine(Base, TimestampMixin, _LineColumns):
    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    total_spent: Mapped[float | None] = mapped_column(Float)

    order: Mapped[Order] = relationship(back_populates="lines")


# --- factory side --------------------------------------------------------------

class VendorOrder(Base, TimestampMixin, _OrderHeaderColumns):
    __tablename__ = "vendor_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    block_index: Mapped[int] = mapped_column(Integer, default=0)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    lines: Mapped[list["VendorOrderLine"]] = relationship(
        back_populates="vendor_order", cascade="all, delete-orphan"
    )


class VendorOrderLine(Base, TimestampMixin, _LineColumns):
    __tablename__ = "vendor_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_order_id: Mapped[int] = mapped_column(ForeignKey("vendor_orders.id"), index=True)

    vendor_order: Mapped[VendorOrder] = relationship(back_populates="lines")


# --- reconciled tracker row ----------------------------------------------------

class TrackerRow(Base, TimestampMixin):
    __tablename__ = "tracker_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # denormalised for listing / search
    buyer_po: Mapped[str | None] = mapped_column(String(64), index=True)
    style_no: Mapped[str | None] = mapped_column(String(64), index=True)
    colour: Mapped[str | None] = mapped_column(String(64))
    article: Mapped[str | None] = mapped_column(String(64))

    # --- the 56 tracker columns -------------------------------------------------
    # Real columns, not a JSON blob: the tracker is listed, searched, sorted,
    # paginated and reported on by these, and all of that needs SQL. Declared
    # explicitly rather than generated from TRACKER_COLUMNS - the parity test in
    # tests/test_tracker_columns.py is the guard, and it fails loudly where
    # metaprogramming would fail silently. buyer_po / style_no / colour are
    # tracker columns too; they are declared above as the row identity.
    # A few operational columns are Text rather than String(255): they hold
    # accumulated lists or free notes (BL/AWB/FCR No. already carries three
    # numbers and a carrier in one cell). SQLite ignores column lengths, so an
    # overflow here would pass every dev test and fail only on Postgres.
    # A  Company code
    company_code: Mapped[str | None] = mapped_column(String(255))
    # B  Customer Name
    customer_name: Mapped[str | None] = mapped_column(String(255))
    # C  Factory's Name
    factory_name: Mapped[str | None] = mapped_column(String(255), index=True)
    # D  Division
    division: Mapped[str | None] = mapped_column(String(255))
    # H  Buyer PO Delivery dtd
    buyer_po_delivery_date: Mapped[date | None] = mapped_column(Date, index=True)
    # I  Factory Delivery dtd
    factory_delivery_date: Mapped[date | None] = mapped_column(Date)
    # J  Mode
    mode: Mapped[str | None] = mapped_column(String(255))
    # K  FOB or C&F
    fob_or_cf: Mapped[str | None] = mapped_column(String(255))
    # L  Order qty
    order_qty: Mapped[float | None] = mapped_column(Float)
    # M  Ship Qty ( pcs )
    ship_qty: Mapped[float | None] = mapped_column(Float)
    # N  Pkgs / Ctns
    pkgs_ctns: Mapped[float | None] = mapped_column(Float)
    # O  Buyer Currency
    buyer_currency: Mapped[str | None] = mapped_column(String(255))
    # P  Buyer Net Price
    buyer_net_price: Mapped[float | None] = mapped_column(Float)
    # Q  Buyer Total Value
    buyer_total_value: Mapped[float | None] = mapped_column(Float)
    # R  Vendor Terms
    vendor_terms: Mapped[str | None] = mapped_column(String(255))
    # S  Factory Unit Price
    factory_price: Mapped[float | None] = mapped_column(Float)
    # T  Vendor Total Value
    vendor_total_value: Mapped[float | None] = mapped_column(Float)
    # U  Price Difference
    price_difference: Mapped[float | None] = mapped_column(Float)
    # V  Factory Inv No.
    factory_inv_no: Mapped[str | None] = mapped_column(String(255))
    # W  Factory Inv/ Date
    factory_inv_date: Mapped[date | None] = mapped_column(Date)
    # X  Auvera Inv No.
    auvera_inv_no: Mapped[str | None] = mapped_column(String(255))
    # Y  Actual Vessel Sailing date (ETD)
    etd: Mapped[date | None] = mapped_column(Date, index=True)
    # Z  Shipment ETA (Confirm by forwarder)
    eta: Mapped[date | None] = mapped_column(Date)
    # AA  BL/AWB/FCR No.
    bl_no: Mapped[str | None] = mapped_column(Text)
    # AB  BL/AWB/FCR Date
    bl_date: Mapped[date | None] = mapped_column(Date)
    # AC  Post shipping / Docs received from  vendor
    docs_received: Mapped[date | None] = mapped_column(Date)
    # AD  Docs Due Date
    docs_due_date: Mapped[date | None] = mapped_column(Date)
    # AE  Day of Delayed Received docs
    docs_delay_days: Mapped[float | None] = mapped_column(Float)
    # AF  FORWARDER
    forwarder: Mapped[str | None] = mapped_column(String(255))
    # AG  Item
    item: Mapped[str | None] = mapped_column(String(255))
    # AH  Short / Extra Ship Qnty (+/-)
    short_extra_qty: Mapped[float | None] = mapped_column(Float)
    # AI  Factory Pyament Due Date
    factory_payment_due_date: Mapped[date | None] = mapped_column(Date)
    # AJ  Shipment Status
    shipment_status: Mapped[str | None] = mapped_column(String(255), index=True)
    # AK  Delay Shipment
    delay_shipment: Mapped[float | None] = mapped_column(Float)
    # AL  Buyer Payment Due Date
    buyer_payment_due_date: Mapped[date | None] = mapped_column(Date)
    # AM  Remarks
    remarks: Mapped[str | None] = mapped_column(Text)
    # AN  Factory Payment Terms (LC/TT/DA/DP) Status
    factory_payment_terms_status: Mapped[str | None] = mapped_column(String(255))
    # AO  Buyer Payment Terms (LC/TT/DA/DP) Status
    buyer_payment_terms_status: Mapped[str | None] = mapped_column(String(255))
    # AP  Final inspection date
    final_inspection_date: Mapped[date | None] = mapped_column(Date)
    # AQ  POD
    pod: Mapped[str | None] = mapped_column(String(255))
    # AR  Pre-shipping docs sending to buyer for approval
    preship_docs_sent: Mapped[date | None] = mapped_column(Date)
    # AS  Buyer Approved
    buyer_approved: Mapped[date | None] = mapped_column(Date)
    # AT  Booking No.
    booking_no: Mapped[str | None] = mapped_column(String(255))
    # AU  Booking date
    booking_date: Mapped[date | None] = mapped_column(Date)
    # AV  Approval, Carting, DO date
    approval_carting_do_date: Mapped[date | None] = mapped_column(Date)
    # AW  Actual H/o date/FCR date
    actual_ho_date: Mapped[date | None] = mapped_column(Date)
    # AX  Container No.
    container_no: Mapped[str | None] = mapped_column(Text)
    # AY  Container Size
    container_size: Mapped[str | None] = mapped_column(String(255))
    # AZ  LCL/FCL
    lcl_fcl: Mapped[str | None] = mapped_column(String(255))
    # BA  Vessel
    vessel: Mapped[str | None] = mapped_column(String(255))
    # BB  Voyage
    voyage: Mapped[str | None] = mapped_column(String(255))
    # BC  Post shipping Docs share to the customer via mail
    docs_shared_customer: Mapped[str | None] = mapped_column(Text)
    # BD  date
    docs_shared_date: Mapped[date | None] = mapped_column(Date)

    # Anything the tracker gains that is not modelled above, exactly like
    # _LineColumns.raw. Normally empty - it exists so a 57th tracker column can
    # ship as a TRACKER_COLUMNS entry alone, with no migration, and be promoted
    # to a real column later.
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    # tracker keys a user has manually edited — never clobbered on re-import
    edited_keys: Mapped[list] = mapped_column(JSON, default=list)
    has_buyer: Mapped[bool] = mapped_column(Boolean, default=False)
    has_vendor: Mapped[bool] = mapped_column(Boolean, default=False)
    order_line_id: Mapped[int | None] = mapped_column(ForeignKey("order_lines.id"))
    vendor_order_line_id: Mapped[int | None] = mapped_column(ForeignKey("vendor_order_lines.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    # --- the wire shape ---------------------------------------------------------
    # The API has always exposed the tracker as a single ``data`` dict and the
    # whole frontend reads it that way, so it stays - assembled from the columns
    # rather than stored. Two properties of the old blob are preserved
    # deliberately, because changing either would be a visible regression:
    #   * it is **sparse** - only keys that actually have a value appear;
    #   * **dates are ISO strings**, which is what the sheets, the grid and
    #     seasons._as_date all already expect.
    # (Ints becoming floats is not a regression: JSON numbers are IEEE doubles,
    # so 300 and 300.0 parse to the same JavaScript value.)

    @property
    def data(self) -> dict:
        from app.services import tracker_map as tm

        out: dict = {}
        for key in tm.TRACKER_KEYS:
            value = getattr(self, key, None)
            if value is None:
                continue
            out[key] = value.isoformat() if isinstance(value, date) else value
        # unmodelled keys last; they never collide with a real column
        out.update(self.raw or {})
        return out

    def set_tracker_values(self, values: dict) -> None:
        """Write tracker keys onto the row: modelled -> column, rest -> ``raw``.

        The single write path for the 56 columns. Values are coerced to the
        column's type, so callers may pass the sheets' strings or the API's JSON
        without each having to know which is which.
        """
        from app.services import cleaners
        from app.services import tracker_map as tm

        leftovers = dict(self.raw or {})
        for key, value in values.items():
            if key not in tm.TRACKER_KEYS:
                leftovers[key] = value
                continue
            kind = tm.TYPE_BY_KEY.get(key)
            if kind == "date":
                value = cleaners.clean_date(value)
            elif kind == "number":
                value = cleaners.clean_number(value)
            else:
                value = cleaners.clean_text(value)
            setattr(self, key, value)
        self.raw = leftovers


# --- field-level change trail --------------------------------------------------

class AuditLog(Base):
    """One row per field change on a tracker row.

    Captures who set/changed a value and when — for the order-detail columns this
    answers "who entered these details" across uploads and manual edits. The CEO
    (and admin) read this back per field via the info button in the field view.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), default="tracker")
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    field_key: Mapped[str] = mapped_column(String(64), index=True)
    field_label: Mapped[str] = mapped_column(String(128))
    field_class: Mapped[str] = mapped_column(String(20))  # order_detail | operational
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String(20))  # import | manual | edit
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    user_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# --- customers ----------------------------------------------------------------

class Customer(Base, TimestampMixin):
    """Customer master record: name, address and VAT number."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    vat_number: Mapped[str | None] = mapped_column(String(64))


# --- vendors (factory master) --------------------------------------------------

class Vendor(Base, TimestampMixin):
    """Factory master record.

    Mirrors ``Customer`` but carries the sourcing detail the vendor workbooks
    supply per factory block, so the list self-populates from uploads and is
    then corrected by hand.
    """

    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    vat_number: Mapped[str | None] = mapped_column(String(64))
    code: Mapped[str | None] = mapped_column(String(32))
    country: Mapped[str | None] = mapped_column(String(64))
    factory_town: Mapped[str | None] = mapped_column(String(64))
    port_of_loading: Mapped[str | None] = mapped_column(String(64))
    payment_terms: Mapped[str | None] = mapped_column(String(128))
    terms_of_delivery: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(16))


# --- season of a purchase order ------------------------------------------------

class POSeason(Base, TimestampMixin):
    """Which selling season a Buyer PO belongs to.

    The order paperwork never states this, so it comes from the merchant: on
    upload we suggest a season from the PO's delivery date (Mar-Aug =
    Spring/Summer, otherwise Autumn/Winter) and they confirm or change it.
    ``confirmed`` stays False until a human has actually looked at it.
    """

    __tablename__ = "po_seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_po: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    season_type: Mapped[str] = mapped_column(String(2))  # SS | AW
    season_year: Mapped[int] = mapped_column(Integer)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    @property
    def label(self) -> str:
        """e.g. ``Spring-Summer '26``."""
        name = "Spring-Summer" if self.season_type == "SS" else "Autumn-Winter"
        return f"{name} '{self.season_year % 100:02d}"

    @property
    def code(self) -> str:
        """e.g. ``SS26``."""
        return f"{self.season_type}{self.season_year % 100:02d}"
