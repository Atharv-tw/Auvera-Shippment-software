export type Role =
  | "admin"
  | "ceo"
  | "shipping_manager"
  | "merchant"
  | "vendor"; // legacy, read-only

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
}

export interface AuditEntry {
  id: number;
  field_key: string;
  field_label: string;
  field_class: "order_detail" | "operational";
  old_value: string | null;
  new_value: string | null;
  action: "import" | "manual" | "edit";
  user_name: string | null;
  created_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface OrderLine {
  id: number;
  row_index: number | null;
  order_date: string | null;
  article: string | null;
  description: string | null;
  colour: string | null;
  style_no: string | null;
  topup: string | null;
  lot: string | null;
  garment_code: string | null;
  sizes: Record<string, number>;
  quantity: number | null;
  price: number | null;
  total_spent: number | null;
  packing_method: string | null;
  etd: string | null;
  composition: string | null;
  brand: string | null;
  factory: string | null;
  store: string | null;
}

export interface OrderHeader {
  id: number;
  order_number: string | null;
  supplier: string | null;
  code: string | null;
  country_of_payment: string | null;
  payment_terms: string | null;
  currency: string | null;
  terms_of_delivery: string | null;
  factory_town: string | null;
  port_of_loading: string | null;
  source_filename: string | null;
  created_at: string | null;
}

export interface Order extends OrderHeader {
  is_confirmation: boolean;
  lines: OrderLine[];
}

export interface VendorOrder extends OrderHeader {
  block_index: number;
  lines: OrderLine[];
}

export interface TrackerColumn {
  col: string;
  key: string;
  label: string;
  type: "text" | "number" | "date";
  source: "buyer" | "vendor" | "const" | "calc" | "operational";
  /** Money column - CEO/admin only. */
  is_price: boolean;
  /** PO#/Style/Colour - editing re-keys the row, so CEO/admin only. */
  is_identity: boolean;
  /** Computed (price difference) - read-only for everyone. */
  is_derived: boolean;
  /** For a derived column, the two labels it is calculated from. */
  derived_from?: string[];
  /** How people actually write this column ("po no", "supplier", "sailing
   * date"), from the same vocabulary that drives paste-matching. */
  aliases?: string[];
}

export interface TrackerRow {
  id: number;
  match_key: string;
  buyer_po: string | null;
  style_no: string | null;
  colour: string | null;
  article: string | null;
  data: Record<string, unknown>;
  edited_keys: string[];
  has_buyer: boolean;
  has_vendor: boolean;
  updated_at: string | null;
}

export interface UploadFileResult {
  filename: string;
  kind: string | null;
  kind_confidence: "high" | "medium" | "low" | null;
  kind_reason: string | null;
  status: "created" | "merged" | "error";
  order_ids: number[];
  tracker_rows_touched: number;
  warnings: string[];
  error: string | null;
}

export interface UploadResponse {
  results: UploadFileResult[];
  /** POs from this upload still awaiting a season. */
  seasons: SeasonSuggestion[];
}

export interface Customer {
  id: number;
  name: string;
  address: string | null;
  vat_number: string | null;
  created_at: string | null;
}

export interface Vendor {
  id: number;
  name: string;
  address: string | null;
  vat_number: string | null;
  code: string | null;
  country: string | null;
  factory_town: string | null;
  port_of_loading: string | null;
  payment_terms: string | null;
  terms_of_delivery: string | null;
  currency: string | null;
  created_at: string | null;
}

export type SeasonType = "SS" | "AW";

export interface Season {
  buyer_po: string;
  season_type: SeasonType;
  season_year: number;
  confirmed: boolean;
  code: string;
  label: string;
}

export interface SeasonSuggestion {
  buyer_po: string;
  season_type: SeasonType;
  season_year: number;
  confirmed: boolean;
  basis: string | null;
}

export interface SeasonSummary {
  code: string;
  label: string;
  season_type: SeasonType;
  season_year: number;
  po_count: number;
}

/** Which of the four per-PO sections a field belongs to. */
export type PoGroup = "buyer" | "vendor" | "product" | "shipping";

export interface PoFieldSpec {
  key: string;
  label: string;
  type: "text" | "number" | "date";
  group: PoGroup;
  /** `tracker` writes to the tracker row, `order_line` to the order sheet record. */
  origin: "tracker" | "order_line";
  is_price: boolean;
  is_identity: boolean;
  is_derived: boolean;
  /** For a derived field, the two labels it is calculated from. */
  derived_from?: string[];
}

export interface PoSchema {
  groups: { key: PoGroup; label: string }[];
  fields: PoFieldSpec[];
}

export interface SizeSpec {
  col: string;
  uk_size: string | null;
  alpha_size: string | null;
  range_label: string | null;
}

export interface PoLine {
  tracker_row_id: number;
  style_no: string | null;
  colour: string | null;
  article: string | null;
  has_buyer: boolean;
  has_vendor: boolean;
  tracker: Record<string, unknown>;
  line: Record<string, unknown>;
  sizes: Record<string, number>;
  size_header: SizeSpec[];
  editable_keys: string[];
}

export interface PoSummary {
  buyer_po: string;
  customer_name: string | null;
  factories: string[];
  line_count: number;
  order_qty: number;
  buyer_total_value: number;
  vendor_total_value: number;
  season: Season | null;
  statuses: Record<string, number>;
}

export interface PoHeader {
  side: "buyer" | "vendor";
  [key: string]: string | null;
}

export interface PoDetail {
  buyer_po: string;
  customer_name: string | null;
  season: Season | null;
  headers: PoHeader[];
  lines: PoLine[];
  totals: Record<string, number>;
}

export interface PasteColumnReport {
  excel_header: string;
  matched_field_key: string | null;
  matched_field_label: string | null;
  confidence: number;
  will_import: boolean;
  /** write = value is written · locator = used to find the row · blocked = role
   *  may not edit it · ignored = matched nothing. */
  purpose: "write" | "locator" | "blocked" | "ignored";
  blocked_reason: string | null;
}

export interface PasteRowPreview {
  row_number: number;
  buyer_po: string | null;
  tracker_row_id: number | null;
  mapped: Record<string, unknown>;
  error: string | null;
}

export interface PastePreview {
  po_column_header: string | null;
  headers: string[];
  columns: PasteColumnReport[];
  rows: PasteRowPreview[];
  matched_pos: string[];
  unmatched_pos: string[];
  matched_row_count: number;
  error_row_count: number;
}

export interface PasteResult {
  updated_rows: number;
  updated_fields: number;
  row_errors: PasteRowPreview[];
  unmatched_pos: string[];
}

export interface ReportBucket {
  key: string;
  label: string;
  po_count: number;
  line_count: number;
  order_qty: number;
  ship_qty: number;
  short_extra_qty: number;
  buyer_value: number;
  vendor_value: number;
  margin: number;
  margin_pct: number | null;
  shipped_lines: number;
  pending_lines: number;
  avg_shipment_delay: number | null;
  avg_docs_delay: number | null;
}

export interface Report {
  group_by: "season" | "customer" | "vendor";
  buckets: ReportBucket[];
  totals: ReportBucket;
  filters: Record<string, string | null>;
}

export interface ReportOptions {
  seasons: { code: string; label: string }[];
  customers: string[];
  vendors: string[];
}
