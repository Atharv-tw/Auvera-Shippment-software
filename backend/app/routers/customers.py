from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_customer_manage, require_customer_view
from app.models import Customer, User
from app.schemas import CustomerCreate, CustomerOut

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
def list_customers(
    search: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_customer_view),
):
    q = db.query(Customer).order_by(Customer.name.asc())
    if search:
        q = q.filter(Customer.name.ilike(f"%{search}%"))
    return q.all()


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_customer_view),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    return customer


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    body: CustomerCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_customer_manage),
):
    customer = Customer(name=body.name, address=body.address, vat_number=body.vat_number)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    body: CustomerCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_customer_manage),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    customer.name = body.name
    customer.address = body.address
    customer.vat_number = body.vat_number
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_customer_manage),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    db.delete(customer)
    db.commit()
