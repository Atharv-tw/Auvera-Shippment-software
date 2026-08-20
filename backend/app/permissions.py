"""Role capabilities for the four user types.

Roles
-----
- ``admin``            – full access (edit everything, upload, delete, view audit).
- ``ceo``              – edits order details (via the per-row field view only, never
                         the bulk tracker grid), views (not edits) operational data,
                         sees the field-level audit trail, and may upload order sheets.
- ``shipping_manager`` – edits the tracker's operational data, views (not edits)
                         order details.
- ``merchant``         – uploads order sheets and views order details; no tracker.

``vendor`` is a legacy role kept as a read-only viewer (orders only).
"""

from __future__ import annotations

from app.services import tracker_map as tm

ADMIN = "admin"
CEO = "ceo"
SHIPPING_MANAGER = "shipping_manager"
MERCHANT = "merchant"

# roles that may be chosen at self-registration (admin is bootstrap/seed only)
SELF_REGISTER_ROLES = (CEO, SHIPPING_MANAGER, MERCHANT)
ALL_ROLES = (ADMIN, CEO, SHIPPING_MANAGER, MERCHANT)


def can_view_tracker(role: str) -> bool:
    return role in (ADMIN, CEO, SHIPPING_MANAGER)


def can_edit_operational(role: str) -> bool:
    return role in (ADMIN, SHIPPING_MANAGER)


def can_edit_order_details(role: str) -> bool:
    return role in (ADMIN, CEO)


def can_upload(role: str) -> bool:
    return role in (ADMIN, MERCHANT, CEO)


def can_view_audit(role: str) -> bool:
    return role in (ADMIN, CEO)


def can_view_customers(role: str) -> bool:
    return role in (ADMIN, CEO)


def can_manage_customers(role: str) -> bool:
    return role == ADMIN


def can_delete(role: str) -> bool:
    return role == ADMIN


def editable_tracker_keys(role: str) -> frozenset[str]:
    """The set of tracker column keys this role is allowed to write."""
    keys: set[str] = set()
    if can_edit_order_details(role):
        keys |= tm.ORDER_DETAIL_KEYS
    if can_edit_operational(role):
        keys |= tm.OPERATIONAL_KEYS
    return frozenset(keys)
