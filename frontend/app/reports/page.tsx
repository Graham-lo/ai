"use client";

import { useEffect, useMemo, useState } from "react";

import { CostBreakdown } from "../components/CostBreakdown";
import { DateRangePicker } from "../components/DateRangePicker";
import { NetModeToggle } from "../components/NetModeToggle";
import { PresetSelector } from "../components/PresetSelector";
import { ReportViewer } from "../components/ReportViewer";
import { generateDeepseekReport, getAccounts, runReport } from "../../lib/api";
import { Account, ReportRun } from "../../lib/types";

export default function ReportsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<string>("all");
  const [preset, setPreset] = useState<string>("last_30d");
  const [dates, setDates] = useState({ start: "", end: "" });
  const [netMode, setNetMode] = useState<"fees_only" | "fees_plus_funding">("fees_only");
  const [report, setReport] = useState<ReportRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [viewMode, setViewMode] = useState<"raw" | "deepseek">("raw");
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState("");

  useEffect(() => {
    getAccounts().then(setAccounts);
  }, []);

  useEffect(() => {
    const saved = window.localStorage.getItem("deepseek_api_key");
    if (saved) {
      setLlmApiKey(saved);
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem("deepseek_api_key", llmApiKey);
  }, [llmApiKey]);

  const period = report?.summary?.period || null;
  const hasDeepseek = Boolean(report?.report_md_llm);
  const netValue = useMemo(() => {
    if (!period) return 0;
    return netMode === "fees_only" ? period.net_after_fees : period.net_after_fees_and_funding;
  }, [period, netMode]);

  async function handleRunReport() {
    setLoading(true);
    setError("");
    try {
      const payload: Record<string, unknown> = { net_mode: netMode };
      if (selectedAccount !== "all") {
        payload.account_ids = [selectedAccount];
      }
      if (preset) {
        payload.preset = preset;
      } else if (dates.start && dates.end) {
        payload.start = dates.start;
        payload.end = dates.end;
      }
      const data = await runReport(payload);
      setReport(data);
      setViewMode("raw");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateDeepseek(refresh = false) {
    if (!report) {
      setLlmError("请先生成报告。");
      return;
    }
    if (!llmApiKey) {
      setLlmError("请先输入 DeepSeek API Key。");
      return;
    }
    setLlmLoading(true);
    setLlmError("");
    try {
      const data = await generateDeepseekReport(report.id, llmApiKey, refresh);
      setReport((prev) =>
        prev
          ? {
              ...prev,
              report_md_llm: data.report_md_llm || undefined,
              llm_model: data.llm_model,
              llm_generated_at: data.llm_generated_at,
              llm_status: data.llm_status,
              llm_error: data.llm_error,
            }
          : prev,
      );
      setViewMode("deepseek");
    } catch (err) {
      setLlmError((err as Error).message);
    } finally {
      setLlmLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-6 pb-16">
      <section className="card-soft p-8">
        <h2 className="font-display text-2xl">生成报告</h2>
        <div className="mt-6 grid gap-6 md:grid-cols-3">
          <label className="block">
            <span className="text-xs uppercase tracking-wide text-slate">账户范围</span>
            <select
              className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
              value={selectedAccount}
              onChange={(event) => setSelectedAccount(event.target.value)}
            >
              <option value="all">全部账户</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.label}
                </option>
              ))}
            </select>
          </label>
          <PresetSelector preset={preset} onChange={setPreset} />
          <NetModeToggle value={netMode} onChange={setNetMode} />
        </div>
        {!preset && (
          <div className="mt-4">
            <DateRangePicker start={dates.start} end={dates.end} onChange={setDates} />
          </div>
        )}
        <div className="mt-6 flex items-center gap-4">
          <button onClick={handleRunReport} className="btn-primary">
            {loading ? "生成中..." : "生成报告"}
          </button>
          {error && <span className="text-sm text-ember">{error}</span>}
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <label className="block">
            <span className="text-xs uppercase tracking-wide text-slate">DeepSeek API Key（本地保存）</span>
            <input
              type="password"
              className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
              value={llmApiKey}
              onChange={(event) => setLlmApiKey(event.target.value)}
              placeholder="sk-..."
            />
          </label>
          <div className="md:col-span-2 flex flex-wrap items-center gap-3">
            <button onClick={() => handleGenerateDeepseek(false)} className="btn-primary" disabled={llmLoading}>
              {llmLoading ? "生成中..." : "生成 DeepSeek 深度分析"}
            </button>
            <button onClick={() => handleGenerateDeepseek(true)} className="btn-ghost" disabled={llmLoading}>
              重新生成
            </button>
            {llmError && <span className="text-sm text-ember">{llmError}</span>}
          </div>
        </div>
      </section>

      {report && (
        <section className="mt-10 grid gap-6 md:grid-cols-3">
          <div className="card-plain p-6">
            <div className="text-xs uppercase tracking-wide text-slate">净值（当前口径）</div>
            <div className="mt-2 font-display text-3xl text-dusk">{netValue.toFixed(4)}</div>
          </div>
          <CostBreakdown fees={period?.trading_fees || 0} funding={period?.funding_pnl || 0} />
          <div className="card-plain p-6">
            <div className="text-xs uppercase tracking-wide text-slate">成交次数</div>
            <div className="mt-2 font-display text-2xl">{period?.trades || 0}</div>
            <div className="mt-3 text-xs text-slate">成交额：{period?.turnover?.toFixed(2) || 0}</div>
          </div>
          <div className="md:col-span-3">
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <button
                className={`pill ${viewMode === "raw" ? "bg-ink text-white" : ""}`}
                onClick={() => setViewMode("raw")}
              >
                原始报告
              </button>
              <button
                className={`pill ${viewMode === "deepseek" ? "bg-ink text-white" : ""}`}
                onClick={() => setViewMode("deepseek")}
                disabled={!hasDeepseek}
              >
                DeepSeek 深度分析
              </button>
              {!hasDeepseek && <span className="text-xs text-slate">未生成 DeepSeek 深度分析</span>}
              {hasDeepseek && report?.llm_model && (
                <span className="text-xs text-slate">模型：{report.llm_model}</span>
              )}
            </div>
            {viewMode === "raw" && <ReportViewer content={report.report_md} />}
            {viewMode === "deepseek" && hasDeepseek && (
              <ReportViewer content={report.report_md_llm || ""} />
            )}
          </div>
        </section>
      )}
    </main>
  );
}
