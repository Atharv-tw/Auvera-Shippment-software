"""Role capabilities for the four user types.

Roles
-----
- ``admin``            - full access (edit everything, upload, delete, view audit).
- ``ceo``              - edits everything including prices, sees the audit trail,
                         may upload order sheets.
- ``shipping_manager`` - owns the Shipment Tracker and edits it freely, except
                         the price columns and the row's PO/Style/Colour identity.
- ``merchant``         - uploads order sheets, assigns each PO its season, and
                         works purchase orders in the per-PO view (same price and
                         identity limits). No Shipment Tracker: it is the shipping
                         team's table and irrelevant to them.

``vendor`` is a legacy role kept as a read-only viewer (orders only).

The editing model is deliberately flat: everyone who can edit, edits everything,
*except* the money columns, which are the CEO's and admin's alone. Uploads are
not affected - a sheet that carries prices still writes them for whoever uploads
it, because that is the sheet's own figure and not a hand edit.
"""

from __future__ import annotations

from app.services import field_groups as fg
from app.services import tracker_map as tm

ADMIN = "admin"
CEO = "ceo"
SHIPPING_MANAGER = "shipping_manager"
MERCHANT = "merchant"

# roles that may be chosen at self-registration (admin is bootstrap/seed only)
SELF_REGISTER_ROLES = (CEO, SHIPPING_MANAGER, MERCHANT)
ALL_ROLES = (ADMIN, CEO, SHIPPING_MANAGER, MERCHANT)


def can_view_tracker(role: str) -> bool:
    """The Shipment Tracker page itself, and every write to it."""
    return role in (ADMIN, CEO, SHIPPING_MANAGER)


def can_read_tracker_rows(role: str) -> bool:
    """Read-only tracker rows, for the dashboard's Shipment Tracker panel.

    Deliberately wider than ``can_view_tracker``: merchants see the panel, but
    the tracker page, the export and every tracker write stay shut to them,
    because those all hang off ``can_view_tracker``.
    """
    return can_view_tracker(role) or role == MERCHANT


def can_view_pos(role: str) -> bool:
    """The per-PO view: everyone who works orders, merchants included."""
    return role in (ADMIN, CEO, SHIPPING_MANAGER, MERCHANT)


def can_edit_prices(role: str) -> bool:
    """Money columns: buyer/factory price, both totals, price difference."""
    return role in (ADMIN, CEO)


def can_edit_identity(role: str) -> bool:
    """Buyer PO# / Style / Colour - changing these re-keys the row."""
    return role in (ADMIN, CEO)


def can_edit_tracker(role: str) -> bool:
    return role in (ADMIN, CEO, SHIPPING_MANAGER)


def can_paste(role: str) -> bool:
    """Pasting a table of PO details straight from an e-mail."""
    return role in (ADMIN, SHIPPING_MANAGER)


def can_assign_season(role: str) -> bool:
    return role in (ADMIN, CEO, MERCHANT)


def can_upload(role: str) -> bool:
    return role in (ADMIN, MERCHANT, CEO)


def can_view_audit(role: str) -> bool:
    return role in (ADMIN, CEO)


def can_view_reports(role: str) -> bool:
    return role in (ADMIN, CEO)


def can_view_customers(role: str) -> bool:
    return role in (ADMIN, CEO)


def can_manage_customers(role: str) -> bool:
    return role == ADMIN


def can_view_vendors(role: str) -> bool:
    return role in (ADMIN, CEO)


def can_manage_vendors(role: str) -> bool:
    return role == ADMIN


def can_delete(role: str) -> bool:
    return role == ADMIN


def editable_tracker_keys(role: str) -> frozenset[str]:
    """The set of tracker column keys this role is allowed to write."""
    if role not in (ADMIN, CEO, SHIPPING_MANAGER, MERCHANT):
        return frozenset()
    # price_difference is computed from the two prices - nobody hand-edits it
    keys = set(tm.TRACKER_KEYS) - set(tm.DERIVED_KEYS)
    if not can_edit_prices(role):
        keys -= tm.PRICE_KEYS
    if not can_edit_identity(role):
        keys -= tm.IDENTITY_KEYS
    return frozenset(keys)


def editable_line_keys(role: str) -> frozenset[str]:
    """Order-sheet line fields (article, garment spec...) this role may write."""
    if role not in (ADMIN, CEO, SHIPPING_MANAGER, MERCHANT):
        return frozenset()
    keys = set(fg.LINE_KEYS)
    if not can_edit_prices(role):
        keys -= fg.LINE_PRICE_KEYS
    return frozenset(keys)
