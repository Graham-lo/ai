"use client";

import { useEffect, useMemo, useState } from "react";

import { CostBreakdown } from "../components/CostBreakdown";
import { DateRangePicker } from "../components/DateRangePicker";
import { NetModeToggle } from "../components/NetModeToggle";
import { PresetSelector } from "../components/PresetSelector";
import { ReportViewer } from "../components/ReportViewer";
import {
  generateDeepseekReportAsync,
  getAccounts,
  getDeepseekStatus,
  getMarketCoverage,
  getReport,
  getReportStatus,
  runReportAsync,
} from "../../lib/api";
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
  const [viewMode, setViewMode] = useState<"deepseek">("deepseek");
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState("");
  const [progress, setProgress] = useState<{
    status: string;
    stage: string;
    percent: number;
    message: string;
    error?: string | null;
  } | null>(null);
  const [marketWarning, setMarketWarning] = useState<string>("");

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
    setProgress(null);
    setMarketWarning("");
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
      let includeMarket = true;
      try {
        const coverage = await getMarketCoverage(payload);
        if (!coverage.has_market) {
          includeMarket = false;
          const missingKeys = Object.keys(coverage.missing || {}).join(", ");
          setMarketWarning(
            missingKeys
              ? `行情数据缺口：${missingKeys}，将仅生成成本报告。`
              : "行情数据不足，将仅生成成本报告。"
          );
        }
      } catch (coverageErr) {
        includeMarket = false;
        setMarketWarning(`行情覆盖检查失败，已降级为成本报告：${(coverageErr as Error).message}`);
      }
      payload.include_market = includeMarket;
      const startRes = await runReportAsync(payload);
      setProgress({
        status: startRes.status,
        stage: startRes.stage,
        percent: startRes.percent,
        message: startRes.message,
        error: startRes.error,
      });
      const reportId = startRes.report_id;
      const timer = window.setInterval(async () => {
        try {
          const next = await getReportStatus(reportId);
          setProgress({
            status: next.status,
            stage: next.stage,
            percent: next.percent,
            message: next.message,
            error: next.error,
          });
          if (next.status === "completed") {
            const data = await getReport(reportId);
            setReport(data);
            window.clearInterval(timer);
            setLoading(false);
          }
          if (next.status === "failed") {
            setError(next.error || "报告生成失败。");
            window.clearInterval(timer);
            setLoading(false);
          }
        } catch (pollErr) {
          setError((pollErr as Error).message);
          window.clearInterval(timer);
          setLoading(false);
        }
      }, 2000);
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    } finally {
      // Loading will be cleared by polling loop.
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
      await generateDeepseekReportAsync(report.id, llmApiKey, refresh);
      const timer = window.setInterval(async () => {
        try {
          const status = await getDeepseekStatus(report.id);
          if (status.llm_status === "success") {
            const data = await getReport(report.id);
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
            window.clearInterval(timer);
            setLlmLoading(false);
          } else if (status.llm_status === "failed") {
            setLlmError(status.llm_error || "DeepSeek 生成失败。");
            window.clearInterval(timer);
            setLlmLoading(false);
          }
        } catch (pollErr) {
          setLlmError((pollErr as Error).message);
          window.clearInterval(timer);
          setLlmLoading(false);
        }
      }, 2000);
    } catch (err) {
      setLlmError((err as Error).message);
      setLlmLoading(false);
    } finally {
      // Loading will be cleared by polling loop.
    }
  }

  function stripEvidenceMarkers(content: string): string {
    const withoutBrackets = content.replace(/\[[^\]]+\]/g, "");
    return withoutBrackets.replace(
      /\(([^)]*(account_summary|market_|behavior_flags|performance_by_regime|anomalies|counterfactual|notes|schema_version)[^)]*)\)/g,
      ""
    );
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
          {marketWarning && <span className="text-xs text-amber-700">{marketWarning}</span>}
          {progress && (
            <span className="text-xs text-slate">
              {progress.percent}% · {progress.stage} · {progress.message}
            </span>
          )}
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
        {report?.schema_version && (
          <div className="mt-3 text-xs text-slate">证据版本：{report.schema_version}</div>
        )}
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
            {viewMode === "deepseek" && hasDeepseek && (
              <ReportViewer content={stripEvidenceMarkers(report.report_md_llm || "")} />
            )}
          </div>
        </section>
      )}
    </main>
  );
}
