"""Keep the Customer and Vendor masters in step with what the uploads reveal.

Every order sheet names its customer (the D1 block) and every vendor block
names its factory, so both master lists populate themselves from imports and
are then corrected by hand in the UI. Existing records are only ever enriched -
a blank on a later sheet never wipes a value someone typed in.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Customer, Vendor
from app.services.parties import parse_buyer_block

# vendor block header key -> Vendor column
_VENDOR_FIELDS = {
    "code": "code",
    "country_of_payment": "country",
    "factory_town": "factory_town",
    "port_of_loading": "port_of_loading",
    "payment_terms": "payment_terms",
    "terms_of_delivery": "terms_of_delivery",
    "currency": "currency",
}


def _by_name(db: Session, model, name: str):
    return db.query(model).filter(func.lower(model.name) == name.lower()).first()


def _enrich(record, values: dict) -> None:
    """Fill blanks only - never overwrite something already there."""
    for attr, value in values.items():
        if value and not getattr(record, attr, None):
            setattr(record, attr, value)


def upsert_customer_from_buyer_block(db: Session, buyer_block: str | None) -> Customer | None:
    """Create/enrich the Customer named by a sheet's D1 block."""
    parsed = parse_buyer_block(buyer_block)
    name = parsed["name"]
    if not name:
        return None
    customer = _by_name(db, Customer, name)
    if customer is None:
        customer = Customer(name=name)
        db.add(customer)
    _enrich(customer, {"address": parsed["address"], "vat_number": parsed["vat_number"]})
    db.flush()
    return customer


def upsert_vendor_from_header(db: Session, header: dict) -> Vendor | None:
    """Create/enrich the Vendor named as Supplier on a vendor block."""
    name = header.get("supplier")
    if not name:
        return None
    vendor = _by_name(db, Vendor, name)
    if vendor is None:
        vendor = Vendor(name=name)
        db.add(vendor)
    _enrich(vendor, {col: header.get(key) for key, col in _VENDOR_FIELDS.items()})
    db.flush()
    return vendor
