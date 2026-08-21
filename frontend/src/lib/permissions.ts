import type { PoFieldSpec, Role, TrackerColumn } from "./types";

/** Mirror of backend app/permissions.py — keep the two in sync.
 *
 * The model is flat: everyone who can edit, edits everything, *except* the
 * money columns, which belong to the CEO and admin alone. The one other
 * exception is a row's PO/Style/Colour identity, which re-keys the row.
 */

export const SELF_REGISTER_ROLES: { value: Role; label: string }[] = [
  { value: "merchant", label: "Merchant" },
  { value: "shipping_manager", label: "Shipping Manager" },
  { value: "ceo", label: "CEO" },
];

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  ceo: "CEO",
  shipping_manager: "Shipping Manager",
  merchant: "Merchant",
  vendor: "Vendor",
};

/** The Shipment Tracker itself — merchants have no business here. */
export const canViewTracker = (r: Role) =>
  r === "admin" || r === "ceo" || r === "shipping_manager";

/** The per-PO view: everyone who works orders, merchants included. */
export const canViewPos = (r: Role) =>
  r === "admin" || r === "ceo" || r === "shipping_manager" || r === "merchant";

export const canEditTracker = (r: Role) =>
  r === "admin" || r === "ceo" || r === "shipping_manager";

/** Money columns: buyer/factory price, both totals, price difference. */
export const canEditPrices = (r: Role) => r === "admin" || r === "ceo";

/** Buyer PO# / Style / Colour — changing these re-keys the row. */
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
  "is_price" | "is_identity" | "is_derived"
>;

/** Whether a role may edit a given column/field, from the flags the API sends. */
export const canEditField = (r: Role, field: Gated) => {
  if (field.is_derived) return false;
  if (field.is_price) return canEditPrices(r);
  if (field.is_identity) return canEditIdentity(r);
  return canEditTracker(r) || canViewPos(r);
};

/** Why a field is locked, for the tooltip on a disabled input. */
export const lockReason = (r: Role, field: Gated): string | null => {
  if (field.is_derived) return "Calculated from the buyer and factory prices";
  if (field.is_price && !canEditPrices(r))
    return "Price fields can only be changed by the CEO or an admin";
  if (field.is_identity && !canEditIdentity(r))
    return "PO, style and colour identify the row — CEO or admin only";
  return null;
};

const ORDER_DETAIL_SOURCES = ["buyer", "vendor", "const", "calc"];

export const isOrderDetailSource = (source: string) =>
  ORDER_DETAIL_SOURCES.includes(source);
