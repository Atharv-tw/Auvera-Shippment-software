"""A browsable view of the database at /admin.

SQLAlchemy is the ORM; this is the GUI for it - every table, its rows and its
relationships, without pointing an external client at the database. Admins sign
in with their normal app credentials.

Read the data here, but change it in the app: edits made here bypass the role
checks and the audit trail, which is why nothing is editable and only the admin
role gets in.
"""

from __future__ import annotations

import logging

from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.orm import Session
from starlette.requests import Request

from app import email_policy
from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import (
    AuditLog,
    AuthEvent,
    Customer,
    Order,
    OrderLine,
    POSeason,
    TrackerRow,
    User,
    UserSession,
    Vendor,
    VendorOrder,
    VendorOrderLine,
)
from app.security import hash_password, verify_password  # noqa: F401  (hash re-exported for parity)

settings = get_settings()
log = logging.getLogger("app")


class AdminAuth(AuthenticationBackend):
    """Session-cookie login, admin role only."""

    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = str(form.get("username", "")).lower()
        password = str(form.get("password", ""))
        db: Session = SessionLocal()
        try:
            if not email_policy.is_allowed_login_email(email):
                return False
            user = db.query(User).filter(User.email == email).first()
            if user is None or not user.is_active or user.role != "admin":
                return False
            if not verify_password(password, user.password_hash):
                return False
            request.session.update({"admin_user": user.email})
            return True
        finally:
            db.close()

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("admin_user"))


class _Base(ModelView):
    can_create = False
    can_edit = False
    can_delete = False
    can_export = True
    page_size = 50


class UserAdmin(_Base, model=User):
    name_plural = "Users"
    icon = "fa-solid fa-user"
    column_list = [User.id, User.email, User.name, User.role, User.is_active, User.created_at]
    column_searchable_list = [User.email, User.name]
    column_sortable_list = [User.id, User.email, User.role]


class CustomerAdmin(_Base, model=Customer):
    name_plural = "Customers"
    icon = "fa-solid fa-building"
    column_list = [Customer.id, Customer.name, Customer.address, Customer.vat_number]
    column_searchable_list = [Customer.name]


class VendorAdmin(_Base, model=Vendor):
    name_plural = "Vendors"
    icon = "fa-solid fa-industry"
    column_list = [
        Vendor.id, Vendor.name, Vendor.country, Vendor.factory_town,
        Vendor.port_of_loading, Vendor.payment_terms, Vendor.terms_of_delivery,
    ]
    column_searchable_list = [Vendor.name]


class OrderAdmin(_Base, model=Order):
    name_plural = "Customer orders"
    icon = "fa-solid fa-file-invoice"
    column_list = [
        Order.id, Order.order_number, Order.supplier, Order.currency,
        Order.payment_terms, Order.customer_id, Order.source_filename, Order.created_at,
    ]
    column_searchable_list = [Order.order_number, Order.source_filename]


class OrderLineAdmin(_Base, model=OrderLine):
    name_plural = "Customer order lines"
    icon = "fa-solid fa-list"
    column_list = [
        OrderLine.id, OrderLine.order_id, OrderLine.article, OrderLine.description,
        OrderLine.style_no, OrderLine.colour, OrderLine.topup, OrderLine.quantity,
        OrderLine.price, OrderLine.total_spent, OrderLine.sizes, OrderLine.etd,
    ]
    column_searchable_list = [OrderLine.style_no, OrderLine.article]


class VendorOrderAdmin(_Base, model=VendorOrder):
    name_plural = "Vendor orders"
    icon = "fa-solid fa-file-contract"
    column_list = [
        VendorOrder.id, VendorOrder.order_number, VendorOrder.supplier,
        VendorOrder.block_index, VendorOrder.payment_terms, VendorOrder.vendor_id,
        VendorOrder.source_filename,
    ]
    column_searchable_list = [VendorOrder.order_number, VendorOrder.supplier]


class VendorOrderLineAdmin(_Base, model=VendorOrderLine):
    name_plural = "Vendor order lines"
    icon = "fa-solid fa-list-check"
    column_list = [
        VendorOrderLine.id, VendorOrderLine.vendor_order_id, VendorOrderLine.article,
        VendorOrderLine.style_no, VendorOrderLine.colour, VendorOrderLine.quantity,
        VendorOrderLine.price, VendorOrderLine.sizes, VendorOrderLine.etd,
    ]
    column_searchable_list = [VendorOrderLine.style_no]


class TrackerRowAdmin(_Base, model=TrackerRow):
    name_plural = "Tracker rows"
    icon = "fa-solid fa-table"
    column_list = [
        TrackerRow.id, TrackerRow.buyer_po, TrackerRow.style_no, TrackerRow.colour,
        TrackerRow.article, TrackerRow.has_buyer, TrackerRow.has_vendor,
        TrackerRow.edited_keys, TrackerRow.updated_at,
    ]
    column_searchable_list = [TrackerRow.buyer_po, TrackerRow.style_no]


class POSeasonAdmin(_Base, model=POSeason):
    name_plural = "PO seasons"
    icon = "fa-solid fa-leaf"
    column_list = [
        POSeason.id, POSeason.buyer_po, POSeason.season_type, POSeason.season_year,
        POSeason.confirmed, POSeason.assigned_by, POSeason.updated_at,
    ]
    column_searchable_list = [POSeason.buyer_po]


class AuditLogAdmin(_Base, model=AuditLog):
    name_plural = "Audit trail"
    icon = "fa-solid fa-clock-rotate-left"
    column_list = [
        AuditLog.id, AuditLog.entity_type, AuditLog.entity_id, AuditLog.field_label,
        AuditLog.old_value, AuditLog.new_value, AuditLog.action, AuditLog.user_name,
        AuditLog.created_at,
    ]
    column_searchable_list = [AuditLog.field_key, AuditLog.user_name]
    column_default_sort = ("id", True)


class UserSessionAdmin(_Base, model=UserSession):
    name_plural = "Sessions"
    icon = "fa-solid fa-key"
    column_list = [
        UserSession.id, UserSession.user_id, UserSession.created_at,
        UserSession.last_used_at, UserSession.expires_at,
        UserSession.revoked_at, UserSession.revoked_reason,
    ]
    column_default_sort = ("id", True)


class AuthEventAdmin(_Base, model=AuthEvent):
    name_plural = "Sign-in activity"
    icon = "fa-solid fa-right-to-bracket"
    column_list = [
        AuthEvent.id, AuthEvent.created_at, AuthEvent.event,
        AuthEvent.user_name, AuthEvent.user_email, AuthEvent.session_id,
    ]
    column_searchable_list = [AuthEvent.user_email, AuthEvent.user_name]
    column_default_sort = ("id", True)


_VIEWS = (
    UserAdmin, UserSessionAdmin, AuthEventAdmin, CustomerAdmin, VendorAdmin,
    OrderAdmin, OrderLineAdmin, VendorOrderAdmin, VendorOrderLineAdmin,
    TrackerRowAdmin, POSeasonAdmin, AuditLogAdmin,
)


def _admin_secret() -> str:
    """The cookie key for this GUI.

    Sharing ``jwt_secret`` means one leaked value opens both the API and this
    database browser. Falling back keeps an existing deployment working the day
    this ships; the warning says what to set.
    """
    if settings.admin_session_secret:
        return settings.admin_session_secret
    log.warning(
        "ADMIN_SESSION_SECRET is unset - the /admin browser is signing its "
        "cookie with JWT_SECRET. Set a separate value so one leak does not "
        "open both."
    )
    return settings.jwt_secret


def mount_admin(app) -> Admin:
    admin = Admin(
        app,
        engine,
        title="Shipping Z data",
        authentication_backend=AdminAuth(secret_key=_admin_secret()),
    )
    for view in _VIEWS:
        admin.add_view(view)
    return admin
