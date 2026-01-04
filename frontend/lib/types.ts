export type AuthField = {
  name: string;
  label: string;
  type: string;
  required: boolean;
  secret: boolean;
};

export type PluginManifest = {
  exchange_id: string;
  display_name: string;
  auth_fields: AuthField[];
  account_types: string[];
  capabilities: Record<string, unknown>;
  notes: string[];
};

export type Account = {
  id: string;
  exchange_id: string;
  label: string;
  account_types: string[];
  options: Record<string, unknown>;
  is_enabled: boolean;
};

export type ReportRun = {
  id: string;
  summary: Record<string, any>;
  anomalies: Array<Record<string, any>>;
  report_md: string;
  report_md_llm?: string | null;
  chart_spec_json?: string | null;
  facts_path?: string | null;
  evidence_path?: string | null;
  evidence_json?: Record<string, any> | null;
  schema_version?: string | null;
  llm_model?: string | null;
  llm_generated_at?: string | null;
  llm_status?: string | null;
  llm_error?: string | null;
  created_at: string;
};

export type TransactionLogEntry = {
  Currency: string;
  Contract: string;
  Type: string;
  Direction: string;
  Quantity: string;
  Position: string;
  "Filled Price": string;
  Funding: string;
  "Fee Paid": string;
  "Cash Flow": string;
  Change: string;
  "Wallet Balance": string;
  Action: string;
  OrderId: string;
  TradeId: string;
  Time: string;
};

export type MonthlyAttributionResult = {
  report_md: string;
  months: string[];
};
