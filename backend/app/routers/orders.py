from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user, require_upload
from app.models import Order, User, VendorOrder
from app.schemas import (
    OrderOut,
    UploadFileResult,
    UploadResponse,
    VendorOrderOut,
)
from app.services import reconcile
from app.services.order_parser import detect_kind, parse_customer_order, parse_vendor_order
from app.services.storage import save_upload

router = APIRouter(prefix="/api", tags=["orders"])
settings = get_settings()


@router.post("/orders/upload", response_model=UploadResponse)
def upload_orders(
    files: list[UploadFile],
    db: Session = Depends(get_db),
    user: User = Depends(require_upload),
):
    """Upload one or more Customer-Order / Vendor-Order .xlsx workbooks.

    Kind is auto-detected (filename hint, then layout). Each file becomes its own
    Order/VendorOrder record and its lines are reconciled into the tracker.
    """
    results: list[UploadFileResult] = []
    for f in files:
        name = f.filename or "upload.xlsx"
        if not name.lower().endswith(".xlsx"):
            results.append(UploadFileResult(filename=name, status="error",
                                            error="Only .xlsx files are supported"))
            continue
        content = f.file.read()
        if len(content) > settings.max_upload_bytes:
            results.append(UploadFileResult(filename=name, status="error",
                                            error="File exceeds size limit"))
            continue
        try:
            path = save_upload(content)
            kind = detect_kind(path, name_hint=name)
            if kind == "vendor":
                parsed = parse_vendor_order(path)
                orders, touched, warnings = reconcile.import_vendor_order(db, parsed, name, user.id, user.name)
                results.append(UploadFileResult(
                    filename=name, kind="vendor", status="created",
                    order_ids=[o.id for o in orders], tracker_rows_touched=touched,
                    warnings=warnings,
                ))
            else:
                parsed = parse_customer_order(path)
                order, touched, warnings = reconcile.import_customer_order(db, parsed, name, user.id, user.name)
                results.append(UploadFileResult(
                    filename=name, kind="customer", status="created",
                    order_ids=[order.id], tracker_rows_touched=touched,
                    warnings=warnings,
                ))
        except Exception as exc:  # noqa: BLE001 - surface parse failures per file
            db.rollback()
            results.append(UploadFileResult(filename=name, status="error", error=str(exc)))
    return UploadResponse(results=results)


@router.get("/orders", response_model=list[OrderOut])
def list_orders(
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Order).options(joinedload(Order.lines)).order_by(Order.created_at.desc())
    if search:
        q = q.filter(Order.order_number.ilike(f"%{search}%"))
    return q.all()


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = db.query(Order).options(joinedload(Order.lines)).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order


@router.get("/vendor-orders", response_model=list[VendorOrderOut])
def list_vendor_orders(
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (
        db.query(VendorOrder)
        .options(joinedload(VendorOrder.lines))
        .order_by(VendorOrder.created_at.desc())
    )
    if search:
        q = q.filter(VendorOrder.order_number.ilike(f"%{search}%"))
    return q.all()


@router.get("/vendor-orders/{vo_id}", response_model=VendorOrderOut)
def get_vendor_order(vo_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    vo = db.query(VendorOrder).options(joinedload(VendorOrder.lines)).filter(VendorOrder.id == vo_id).first()
    if vo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor order not found")
    return vo
