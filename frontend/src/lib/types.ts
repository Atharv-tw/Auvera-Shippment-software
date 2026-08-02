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
  status: "created" | "merged" | "error";
  order_ids: number[];
  tracker_rows_touched: number;
  warnings: string[];
  error: string | null;
}

export interface UploadResponse {
  results: UploadFileResult[];
}
