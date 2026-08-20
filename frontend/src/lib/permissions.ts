import type { Role } from "./types";

/** Mirror of backend app/permissions.py — keep the two in sync. */

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

export const canViewTracker = (r: Role) =>
  r === "admin" || r === "ceo" || r === "shipping_manager";

export const canEditOperational = (r: Role) =>
  r === "admin" || r === "shipping_manager";

export const canEditOrderDetails = (r: Role) => r === "admin" || r === "ceo";

export const canUpload = (r: Role) => r === "admin" || r === "merchant" || r === "ceo";

export const canViewAudit = (r: Role) => r === "admin" || r === "ceo";

export const canViewCustomers = (r: Role) => r === "admin" || r === "ceo";

export const canManageCustomers = (r: Role) => r === "admin";

/** Bulk/inline editing in the spreadsheet-style tracker grid ("Excel view") is
 * restricted to admin + shipping_manager. CEO still edits order-detail fields,
 * but only through the per-row field view (each change is audited the same way). */
export const canUseExcelView = (r: Role) => r === "admin" || r === "shipping_manager";

export const canDelete = (r: Role) => r === "admin";

const ORDER_DETAIL_SOURCES = ["buyer", "vendor", "const", "calc"];

export const isOrderDetailSource = (source: string) =>
  ORDER_DETAIL_SOURCES.includes(source);

/** Whether a role may edit a tracker column given its `source`.
 * `calc` columns are derived (e.g. price difference) and never hand-edited. */
export const canEditSource = (r: Role, source: string) => {
  if (source === "calc") return false;
  return isOrderDetailSource(source)
    ? canEditOrderDetails(r)
    : canEditOperational(r);
};

/** Any editing at all is possible for this role? */
export const canEditAnyTracker = (r: Role) =>
  canEditOrderDetails(r) || canEditOperational(r);
