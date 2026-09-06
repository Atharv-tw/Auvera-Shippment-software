import type { PoFieldSpec, Role, TrackerColumn } from "./types";

/** Which pages and actions a role gets. Page-level only.
 *
 * Per-*field* editability is deliberately not here: the API decides it and
 * sends `editable` on every column and field spec (see `lockReason`). The
 * backend refuses the write either way, so there is nothing left for the UI
 * to work out for itself.
 *
 * What remains below mirrors app/permissions.py, and every route it guards is
 * enforced server-side by a dependency — a role that slips past one of these
 * gets a 403 from the endpoint.
 */

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  ceo: "CEO",
  shipping_manager: "Shipping Manager",
  merchant: "Merchant",
  vendor: "Vendor",
  pending: "Awaiting approval",
};

/** Roles an admin may assign in the user-management panel (not `pending`, which
 * is the absence of a role, nor the legacy `vendor`). Mirrors ALL_ROLES on the
 * backend. */
export const ASSIGNABLE_ROLES: { value: Role; label: string }[] = [
  { value: "merchant", label: "Merchant" },
  { value: "shipping_manager", label: "Shipping Manager" },
  { value: "ceo", label: "CEO" },
  { value: "admin", label: "Admin" },
];

/** Approve waitlisted accounts and assign roles - the admin panel. */
export const canManageUsers = (r: Role) => r === "admin";

/** The Shipment Tracker page itself, and every write to it. */
export const canViewTracker = (r: Role) =>
  r === "admin" || r === "ceo" || r === "shipping_manager";

/** Read-only tracker rows, for the dashboard's Shipment Tracker panel.
 *
 * Wider than `canViewTracker` on purpose: the panel's columns are all order
 * facts a merchant already sees per-PO. The tracker page, its export and its
 * edits are the shipping team's, and stay on `canViewTracker`.
 */
export const canReadTrackerRows = (r: Role) => canViewTracker(r) || r === "merchant";

/** The per-PO view: everyone who works orders, merchants included. */
export const canViewPos = (r: Role) =>
  r === "admin" || r === "ceo" || r === "shipping_manager" || r === "merchant";

export const canEditTracker = (r: Role) =>
  r === "admin" || r === "ceo" || r === "shipping_manager";

/** Buyer PO# / Style / Colour — changing these re-keys the row. Also the gate
 * on the Manual PO Line page, which creates a row and so sets its identity. */
export const canEditIdentity = (r: Role) => r === "admin" || r === "ceo";

export const canPaste = (r: Role) => r === "admin" || r === "shipping_manager";

export const canAssignSeason = (r: Role) =>
  r === "admin" || r === "ceo" || r === "merchant";

export const canUpload = (r: Role) =>
  r === "admin" || r === "merchant" || r === "ceo";

export const canViewAudit = (r: Role) => r === "admin" || r === "ceo";

export const canViewReports = (r: Role) => r === "admin" || r === "ceo";

export const canViewCustomers = (r: Role) => r === "admin" || r === "ceo";

export const canManageCustomers = (r: Role) => r === "admin";

export const canViewVendors = (r: Role) => r === "admin" || r === "ceo";

export const canManageVendors = (r: Role) => r === "admin";

export const canDelete = (r: Role) => r === "admin";

/** The spreadsheet-style grid, on the tracker page only. */
export const canUseExcelView = (r: Role) =>
  r === "admin" || r === "shipping_manager";

type Gated = Pick<
  TrackerColumn | PoFieldSpec,
  "editable" | "is_price" | "is_identity" | "is_payment_terms" | "is_derived"
> & { derived_from?: string[] };

/** Why a field is locked, for the tooltip on a disabled input — `null` when it
 * is not locked at all.
 *
 * `editable` settles *whether*; the flags only explain *why*, so a rule change
 * in permissions.py needs nothing here. The fallback covers a field locked for
 * a reason this UI has no wording for yet: still locked, just less helpfully.
 */
export const lockReason = (field: Gated): string | null => {
  if (field.editable) return null;
  if (field.is_derived) {
    // name the actual inputs: "change the price" is unhelpful advice on a
    // shipment-delay field. Two inputs (a subtraction or a total), or one (a
    // date offset). Wording stays operator-neutral so it fits all of them.
    const from = field.derived_from ?? [];
    if (from.length === 2)
      return `Calculated from ${from[0]} and ${from[1]}. Change those instead.`;
    if (from.length === 1)
      return `Calculated from ${from[0]}. Change that instead.`;
    return "Calculated automatically from other columns";
  }
  if (field.is_price)
    return "Price fields can only be changed by the CEO or an admin";
  if (field.is_identity)
    return "PO, style and colour identify the row — CEO or admin only";
  if (field.is_payment_terms)
    return "Payment terms are commercial — merchant, CEO or admin only";
  return "Read-only for your role";
};

const ORDER_DETAIL_SOURCES = ["buyer", "vendor", "const", "calc"];

export const isOrderDetailSource = (source: string) =>
  ORDER_DETAIL_SOURCES.includes(source);
