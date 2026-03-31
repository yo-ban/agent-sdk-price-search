export interface IdentifiedProduct {
  name: string;
  model_number: string;
  manufacturer: string;
  product_url: string;
  release_date: string;
  is_substitute: boolean;
  substitution_reason: string;
}

export interface Offer {
  merchant_name: string;
  merchant_product_name: string;
  merchant_product_url: string;
  currency: string;
  item_price: string;
  availability: "in_stock" | "limited_stock" | "out_of_stock" | "unknown";
  evidence: string;
}

export interface PriceResearchResult {
  product_name: string;
  identified_product: IdentifiedProduct;
  summary: string;
  offers: Offer[];
}

export type RunStatus =
  | "researching"
  | "finished"
  | "failed"
  | "interrupted";

export type TimelineKind =
  | "system"
  | "thinking"
  | "tool"
  | "text"
  | "result"
  | "error";

export interface TimelineItem {
  t: number;
  kind: TimelineKind;
  label: string;
  detail: string;
}

export interface RunData {
  run_id: string;
  product_name: string;
  market: string;
  currency: string;
  max_offers: number;
  model: string;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  duration_ms: number;
  total_cost_usd: number | null;
  num_turns: number | null;
  result: PriceResearchResult | null;
  timeline: TimelineItem[];
}

export interface SearchFormValues {
  productNameAndModelNumber: string;
  color: string;
  manufacturer: string;
  market: string;
  currency: string;
  maxOffers: number;
}
