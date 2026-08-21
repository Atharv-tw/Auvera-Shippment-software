"""Vendor (factory) master - the mirror of the customer master.

The list seeds itself from vendor-order uploads (each block names its factory
and carries its town, port, payment terms and delivery terms), then gets
corrected and completed by hand here.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_vendor_manage, require_vendor_view
from app.models import User, Vendor
from app.schemas import VendorCreate, VendorOut

router = APIRouter(prefix="/api/vendors", tags=["vendors"])

_EDITABLE = (
    "name", "address", "vat_number", "code", "country", "factory_town",
    "port_of_loading", "payment_terms", "terms_of_delivery", "currency",
)


@router.get("", response_model=list[VendorOut])
def list_vendors(
    search: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_vendor_view),
):
    q = db.query(Vendor).order_by(Vendor.name.asc())
    if search:
        q = q.filter(Vendor.name.ilike(f"%{search}%"))
    return q.all()


@router.get("/{vendor_id}", response_model=VendorOut)
def get_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_vendor_view),
):
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")
    return vendor


@router.post("", response_model=VendorOut, status_code=status.HTTP_201_CREATED)
def create_vendor(
    body: VendorCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_vendor_manage),
):
    vendor = Vendor(**body.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.put("/{vendor_id}", response_model=VendorOut)
def update_vendor(
    vendor_id: int,
    body: VendorCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_vendor_manage),
):
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")
    for field in _EDITABLE:
        setattr(vendor, field, getattr(body, field))
    db.commit()
    db.refresh(vendor)
    return vendor


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_vendor_manage),
):
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")
    db.delete(vendor)
    db.commit()
