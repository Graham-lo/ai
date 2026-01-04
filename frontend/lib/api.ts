import { Account, MonthlyAttributionResult, PluginManifest, ReportRun, TransactionLogEntry } from "./types";

function resolveApiBase(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE;
  if (base && base !== "http://localhost:8000") {
    return base;
  }
  if (typeof window === "undefined") {
    return base || "http://localhost:18000";
  }
  const origin = window.location.origin;
  if (origin.includes(":13000")) {
    return origin.replace(":13000", ":18000");
  }
  if (origin.includes(":3000")) {
    return origin.replace(":3000", ":8000");
  }
  return base || "http://localhost:18000";
}

const API_BASE = resolveApiBase();
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "devtoken";

async function request<T>(path: string, options: RequestInit = {}, timeoutMs = 30000): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Token": API_TOKEN,
      ...(options.headers || {}),
    },
    cache: "no-store",
    signal: controller.signal,
  }).finally(() => clearTimeout(timeoutId));
  if (!res.ok) {
    const rawText = await res.text();
    const contentType = res.headers.get("content-type") || "";
    let message = rawText || res.statusText;
    if (contentType.includes("application/json") || rawText.trim().startsWith("{")) {
      try {
        const parsed = JSON.parse(rawText);
        message = parsed.detail || parsed.message || message;
      } catch {
        // Keep rawText fallback.
      }
    }
    throw new Error(message);
  }
  return res.json();
}

export function getPlugins(): Promise<PluginManifest[]> {
  return request<PluginManifest[]>("/plugins");
}

export function getAccounts(): Promise<Account[]> {
  return request<Account[]>("/accounts");
}

export function createAccount(payload: {
  exchange_id: string;
  label: string;
  account_types: string[];
  credentials: Record<string, string>;
  options?: Record<string, unknown>;
}): Promise<Account> {
  return request<Account>("/accounts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateAccount(id: string, payload: Partial<Account>): Promise<Account> {
  return request<Account>(`/accounts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function rotateCredentials(id: string, credentials: Record<string, string>): Promise<void> {
  return request<void>(`/accounts/${id}/rotate-credentials`, {
    method: "POST",
    body: JSON.stringify({ credentials }),
  });
}

export function deleteAccount(id: string): Promise<void> {
  return request<void>(`/accounts/${id}`, {
    method: "DELETE",
  });
}

export function runReport(payload: Record<string, unknown>): Promise<ReportRun> {
  return request<ReportRun>("/reports/run", {
    method: "POST",
    body: JSON.stringify(payload),
  }, 180000);
}

export function runReportAsync(payload: Record<string, unknown>): Promise<{
  report_id: string;
  status: string;
  stage: string;
  percent: number;
  message: string;
  error?: string | null;
  updated_at: string;
}> {
  return request("/reports/run-async", {
    method: "POST",
    body: JSON.stringify(payload),
  }, 10000);
}

export function getReportStatus(reportId: string): Promise<{
  report_id: string;
  status: string;
  stage: string;
  percent: number;
  message: string;
  error?: string | null;
  updated_at: string;
}> {
  return request(`/reports/${reportId}/status`, {}, 10000);
}

export function getReport(reportId: string): Promise<ReportRun> {
  return request<ReportRun>(`/reports/${reportId}`);
}

export function getMarketCoverage(payload: {
  account_ids?: string[];
  exchange_id?: string;
  preset?: string;
  start?: string;
  end?: string;
  symbols?: string[];
}): Promise<{
  start?: string | null;
  end?: string | null;
  symbols: string[];
  has_market: boolean;
  coverage: Record<string, any>;
  missing: Record<string, any>;
  notes: string[];
}> {
  return request("/market/coverage", {
    method: "POST",
    body: JSON.stringify(payload),
  }, 10000);
}

export function generateDeepseekReport(
  reportId: string,
  apiKey: string,
  refresh = false,
): Promise<{
  report_id: string;
  report_md_llm: string | null;
  llm_model: string | null;
  llm_generated_at: string | null;
  llm_status: string | null;
  llm_error: string | null;
}> {
  const search = refresh ? "?refresh=1" : "";
  return request(`/reports/${reportId}/deepseek${search}`, {
    method: "POST",
    headers: apiKey ? { "X-DeepSeek-Api-Key": apiKey } : undefined,
  });
}

export function generateDeepseekReportAsync(
  reportId: string,
  apiKey: string,
  refresh = false,
): Promise<{
  report_id: string;
  report_md_llm: string | null;
  llm_model: string | null;
  llm_generated_at: string | null;
  llm_status: string | null;
  llm_error: string | null;
}> {
  const search = refresh ? "?refresh=1" : "";
  return request(`/reports/${reportId}/deepseek-async${search}`, {
    method: "POST",
    headers: apiKey ? { "X-DeepSeek-Api-Key": apiKey } : undefined,
  }, 10000);
}

export function getDeepseekPayload(reportId: string): Promise<Record<string, any>> {
  return request(`/reports/${reportId}/deepseek-payload`);
}

export function generateDeepseekAnalysis(
  reportId: string,
  apiKey: string,
  refresh = false,
): Promise<{
  report_id: string;
  report_md_llm: string | null;
  chart_spec_json: string | null;
  llm_model: string | null;
  llm_generated_at: string | null;
  llm_status: string | null;
  llm_error: string | null;
}> {
  const search = refresh ? "?refresh=1" : "";
  return request(`/reports/${reportId}/deepseek-analyze${search}`, {
    method: "POST",
    headers: apiKey ? { "X-DeepSeek-Api-Key": apiKey } : undefined,
  });
}

export function getDeepseekStatus(reportId: string): Promise<{
  report_id: string;
  report_md_llm: string | null;
  llm_model: string | null;
  llm_generated_at: string | null;
  llm_status: string | null;
  llm_error: string | null;
}> {
  return request(`/reports/${reportId}/deepseek-status`, {}, 10000);
}

export function runSync(payload: Record<string, unknown>): Promise<{ status: string; fills: number; cashflows: number }> {
  return request("/sync/run", {
    method: "POST",
    body: JSON.stringify(payload),
  }, 180000);
}

export function getSyncRuns(): Promise<Array<Record<string, any>>> {
  return request("/sync/runs");
}

export async function importBybitTransactionLog(accountId: string, file: File): Promise<any> {
  const form = new FormData();
  form.append("account_id", accountId);
  form.append("file", file);
  const res = await fetch(`${API_BASE}/imports/bybit/transaction-log`, {
    method: "POST",
    headers: {
      "X-API-Token": API_TOKEN,
    },
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export async function runMonthlyAttribution(params: {
  file: File;
  start?: string;
  end?: string;
  preset?: string;
  symbols?: string;
}): Promise<MonthlyAttributionResult> {
  const form = new FormData();
  form.append("file", params.file);
  if (params.start) form.append("start", params.start);
  if (params.end) form.append("end", params.end);
  if (params.preset) form.append("preset", params.preset);
  if (params.symbols) form.append("symbols", params.symbols);
  const res = await fetch(`${API_BASE}/reports/monthly-attribution`, {
    method: "POST",
    headers: {
      "X-API-Token": API_TOKEN,
    },
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export function runMonthlyAttributionDb(payload: {
  account_ids?: string[];
  exchange_id?: string;
  start?: string;
  end?: string;
  preset?: string;
  symbols?: string;
}): Promise<MonthlyAttributionResult> {
  return request("/reports/monthly-attribution-db", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTransactionLog(params: {
  account_id: string;
  start?: string;
  end?: string;
  symbol?: string;
  type?: string;
}): Promise<TransactionLogEntry[]> {
  const search = new URLSearchParams({ account_id: params.account_id });
  if (params.start) search.set("start", params.start);
  if (params.end) search.set("end", params.end);
  if (params.symbol) search.set("symbol", params.symbol);
  if (params.type) search.set("type", params.type);
  return request<TransactionLogEntry[]>(`/exports/bybit_transaction_log.json?${search.toString()}`);
}

export function getTransactionLogExportUrl(params: {
  account_id: string;
  start?: string;
  end?: string;
  symbol?: string;
  type?: string;
}): string {
  const search = new URLSearchParams({ account_id: params.account_id });
  if (params.start) search.set("start", params.start);
  if (params.end) search.set("end", params.end);
  if (params.symbol) search.set("symbol", params.symbol);
  if (params.type) search.set("type", params.type);
  return `${API_BASE}/exports/bybit_transaction_log.csv?${search.toString()}`;
}
