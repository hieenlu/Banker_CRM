export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type MeResponse = {
  username: string;
  authenticated: boolean;
};

export type Client = {
  id: number;
  name: string;
  birthday: string | null;
  address: string | null;
  phone_number: string | null;
  email: string | null;
  notes: string | null;
  home_insurance_amount_covered: number | null;
  home_insurance_expiry_date: string | null;
  home_insurance_insured_premium: number | null;
  salary_amount: number | null;
  salary_concurrent: boolean;
  salary_note: string | null;
  dividends_amount: number | null;
  dividends_concurrent: boolean;
  dividends_note: string | null;
  others_income_amount: number | null;
  others_income_concurrent: boolean;
  others_income_note: string | null;
};

export type ClientCreate = Omit<Client, "id">;

export type Investment = {
  id: number;
  client_id: number;
  asset_type: string;
  ticker_name: string | null;
  ticker_identifier: string | null;
  quantity: number;
  unit: number | null;
  principal: number | null;
  purchase_price: number;
  currency: string;
  purchase_date: string | null;
  tenor: string | null;
  interest_rate: number | null;
  principal_payment: number | null;
  ytm: number | null;
  current_price: number | null;
  received_coupon: number | null;
  expected_coupon: number | null;
  maturity_date: string | null;
  is_done: boolean;
  notes: string | null;
};

export type Income = {
  id: number;
  client_id: number;
  income_type: string;
  income_mode: string;
  amount: number;
  concurrent: boolean;
  is_done: boolean;
  note: string | null;
};

export type Reminder = {
  id: number;
  title: string;
  reminder_date: string;
  reminder_type: string;
  client_id: number | null;
  investment_id: number | null;
  notes: string | null;
  created_at: string | null;
  sent_at: string | null;
};

export type Article = {
  id: number;
  url: string;
  title: string;
  source: string;
  published_at: string | null;
  fetched_at: string;
  category: string;
  relevance_score: number;
  region: string;
  language: string | null;
  is_paywalled: boolean;
  mention_count: number;
  vietnam_macro_score: number;
  vietnam_banking_score: number;
  vietnam_wealth_score: number;
  bookmarked: boolean;
};

export type ArticleDetail = Article & {
  body_text: string | null;
  body_fetch_status: string;
  canonical_url: string | null;
  url_hash: string;
  dedup_cluster_id: string | null;
};

export type Newspaper = {
  id: number;
  report_date: string;
  market_regime: string;
  content: Record<string, unknown>;
  provider: string;
  model: string;
  created_at: string;
};

export type StoredFile = {
  id: number;
  kind: string;
  backend: string;
  status: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  client_id: number | null;
  original_filename: string | null;
  label: string | null;
  period_yyyymm: string | null;
  source_url: string | null;
  created_at: string;
  synced_at: string | null;
  download_url: string | null;
  download_expires_at: string | null;
};

export const NEWS_CATEGORIES = [
  "Global Macro",
  "Central Banks",
  "Inflation",
  "Fixed Income",
  "Equities",
  "Commodities",
  "FX",
  "Crypto",
  "China",
  "Vietnam",
  "Geopolitics",
  "Uncategorized",
] as const;

export type PortfolioTotals = {
  principal: number;
  current_value: number;
  pnl: number;
  pnl_pct: number | null;
};

export type PortfolioSubgroup = {
  name: string;
  columns: string[];
  rows: Record<string, unknown>[];
  unrealized_pnl: number;
  native_currency: string;
};

export type PortfolioGroup = {
  name: string;
  subgroups: PortfolioSubgroup[];
};

export type PortfolioView = {
  display_currency: string;
  usd_vnd_rate: number;
  totals: PortfolioTotals;
  groups: PortfolioGroup[];
};

export type PriceRefreshResult = {
  requested: number;
  resolved: number;
  updated: number;
  prices: Record<string, number>;
  missing: string[];
};

export type NewsRefreshResult = {
  status: string;
  fetched: number;
  new_count: number;
  deduped: number;
  classified: number;
  errors: string[];
};
