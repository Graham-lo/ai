import { Account, PluginManifest, ReportRun, TransactionLogEntry } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "devtoken";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Token": API_TOKEN,
      ...(options.headers || {}),
    },
    cache: "no-store",
  });
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
  });
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

export function runSync(payload: Record<string, unknown>): Promise<{ status: string; fills: number; cashflows: number }> {
  return request("/sync/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
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
