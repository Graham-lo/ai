"use client";

import { useEffect, useMemo, useState } from "react";

import { getAccounts, getSyncRuns, importBybitTransactionLog, runSync } from "../../lib/api";
import { Account } from "../../lib/types";

const PRESETS = [
  { value: "last_7d", label: "最近7天" },
  { value: "last_30d", label: "最近30天" },
  { value: "last_month", label: "上月" },
  { value: "ytd", label: "年初至今" },
  { value: "all_time", label: "最近两年（Bybit限制）" },
  { value: "", label: "自定义" },
];

export default function SyncPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountId, setAccountId] = useState("");
  const [preset, setPreset] = useState("last_30d");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [syncRuns, setSyncRuns] = useState<Array<Record<string, any>>>([]);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState("");
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    getAccounts().then((data) => {
      setAccounts(data);
      if (data.length) {
        setAccountId(data[0].id);
      }
    });
    refreshRuns();
  }, []);

  useEffect(() => {
    const hasRunning = syncRuns.some((run) => run.status === "running");
    if (!hasRunning) {
      return undefined;
    }
    const timer = setInterval(() => {
      refreshRuns();
    }, 5000);
    return () => clearInterval(timer);
  }, [syncRuns]);

  async function refreshRuns() {
    const runs = await getSyncRuns();
    setSyncRuns(runs);
  }

  async function handleSync() {
    setLoading(true);
    setMessage("");
    try {
      const payload: Record<string, unknown> = {};
      if (accountId) payload.account_ids = [accountId];
      if (preset) {
        payload.preset = preset;
      } else if (start && end) {
        payload.start = start;
        payload.end = end;
      }
      const result = await runSync(payload);
      setMessage(`同步完成：成交 ${result.fills} 条，流水 ${result.cashflows} 条`);
      await refreshRuns();
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleImport() {
    if (!file || !accountId) {
      setMessage("请选择账户并上传 CSV 文件");
      return;
    }
    setImporting(true);
    setMessage("");
    try {
      const result = await importBybitTransactionLog(accountId, file);
      setMessage(`导入完成：成交 ${result.fills} 条，流水 ${result.cashflows} 条`);
      await refreshRuns();
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setImporting(false);
    }
  }

  const filteredRuns = useMemo(() => syncRuns, [syncRuns]);

  function renderStatus(status: string) {
    if (status === "completed") return "完成";
    if (status === "running") return "进行中";
    if (status === "failed") return "失败";
    return status;
  }

  function statusClass(status: string) {
    if (status === "completed") return "bg-moss/10 text-moss";
    if (status === "running") return "bg-amber-100 text-amber-700";
    if (status === "failed") return "bg-ember/10 text-ember";
    return "bg-ink/5 text-slate";
  }

  return (
    <main className="mx-auto max-w-6xl px-6 pb-16">
      <section className="card-soft p-8">
        <h2 className="font-display text-2xl">同步与导入</h2>
        <p className="mt-2 text-sm text-slate">支持手动同步、定时同步与 CSV 导入。</p>
        <div className="mt-6 grid gap-4 md:grid-cols-4">
          <label className="block">
            <span className="text-xs uppercase tracking-wide text-slate">账户</span>
            <select
              className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
              value={accountId}
              onChange={(event) => setAccountId(event.target.value)}
            >
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-wide text-slate">预设范围</span>
            <select
              className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
              value={preset}
              onChange={(event) => setPreset(event.target.value)}
            >
              {PRESETS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-wide text-slate">开始日期</span>
            <input
              type="date"
              className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
              value={start}
              onChange={(event) => setStart(event.target.value)}
              disabled={Boolean(preset)}
            />
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-wide text-slate">结束日期</span>
            <input
              type="date"
              className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
              disabled={Boolean(preset)}
            />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button className="btn-primary" onClick={handleSync} type="button">
            {loading ? "同步中..." : "手动同步"}
          </button>
          <button
            className="btn-ghost"
            onClick={refreshRuns}
            type="button"
          >
            刷新记录
          </button>
          {message && <span className="text-sm text-ember">{message}</span>}
        </div>
      </section>

      <section className="mt-8 card-soft p-8">
        <h3 className="font-display text-xl">导入交易所 CSV</h3>
        <p className="mt-2 text-sm text-slate">当前支持 Bybit UM TransactionLog 导入。</p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept=".csv"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          <button className="btn-primary" onClick={handleImport} type="button">
            {importing ? "导入中..." : "导入 CSV"}
          </button>
        </div>
      </section>

      <section className="mt-8 card-soft p-6">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-xl">同步记录</h3>
          <span className="text-sm text-slate">最近 {filteredRuns.length} 条</span>
        </div>
        <div className="mt-4 overflow-auto">
          <table className="min-w-[900px] text-sm">
            <thead className="border-b border-ink/10 text-left text-xs uppercase tracking-wide text-slate">
              <tr>
                <th className="py-2">时间</th>
                <th>状态</th>
                <th>范围</th>
                <th>fills</th>
                <th>cashflows</th>
                <th>错误</th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.map((run) => (
                <tr key={run.id} className="border-b border-ink/5">
                  <td className="py-2 text-xs">{run.created_at}</td>
                  <td>
                    <span className={`rounded-full px-2 py-1 text-xs ${statusClass(run.status)}`}>
                      {renderStatus(run.status)}
                    </span>
                  </td>
                  <td className="text-xs">{run.preset || `${run.start || ""} ~ ${run.end || ""}`}</td>
                  <td>{run.counts?.fills ?? 0}</td>
                  <td>{run.counts?.cashflows ?? 0}</td>
                  <td className="text-xs text-ember">{run.error || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filteredRuns.length && <div className="py-6 text-sm text-slate">暂无记录</div>}
        </div>
      </section>
    </main>
  );
}
