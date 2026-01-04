"use client";

import { useEffect, useMemo, useState } from "react";

import { getAccounts, getTransactionLog, getTransactionLogExportUrl } from "../../lib/api";
import { Account, TransactionLogEntry } from "../../lib/types";

const TYPE_OPTIONS = [
  { value: "", label: "全部" },
  { value: "TRADE", label: "成交" },
  { value: "SETTLEMENT", label: "资金费率" },
];

export default function TransactionsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountId, setAccountId] = useState("");
  const [symbol, setSymbol] = useState("");
  const [type, setType] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [rows, setRows] = useState<TransactionLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getAccounts().then((data) => {
      setAccounts(data);
      if (data.length && !accountId) {
        setAccountId(data[0].id);
      }
    });
  }, [accountId]);

  const exportUrl = useMemo(() => {
    if (!accountId) return "";
    return getTransactionLogExportUrl({
      account_id: accountId,
      start: start || undefined,
      end: end || undefined,
      symbol: symbol || undefined,
      type: type || undefined,
    });
  }, [accountId, end, start, symbol, type]);

  async function handleSearch() {
    if (!accountId) {
      setError("请先选择账户");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await getTransactionLog({
        account_id: accountId,
        start: start || undefined,
        end: end || undefined,
        symbol: symbol || undefined,
        type: type || undefined,
      });
      setRows(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function displayType(value: string) {
    if (value === "TRADE") return "成交";
    if (value === "SETTLEMENT") return "资金费率";
    return value;
  }

  function displayDirection(value: string) {
    if (value === "BUY") return "买";
    if (value === "SELL") return "卖";
    return value || "--";
  }

  return (
    <main className="mx-auto max-w-6xl px-6 pb-16">
      <section className="card-soft p-8">
        <h2 className="font-display text-2xl">交易日志</h2>
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
            <span className="text-xs uppercase tracking-wide text-slate">合约</span>
            <input
              className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
              value={symbol}
              onChange={(event) => setSymbol(event.target.value.toUpperCase())}
              placeholder="BTCUSDT"
            />
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-wide text-slate">类型</span>
            <select
              className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
              value={type}
              onChange={(event) => setType(event.target.value)}
            >
              {TYPE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-end gap-3">
            <button type="button" onClick={handleSearch} className="btn-primary">
              {loading ? "查询中..." : "查询"}
            </button>
            {exportUrl && (
              <a className="btn-ghost" href={exportUrl}>
                导出
              </a>
            )}
          </div>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block">
            <span className="text-xs uppercase tracking-wide text-slate">开始日期</span>
            <input
              type="date"
              className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-wide text-slate">结束日期</span>
            <input
              type="date"
              className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
            />
          </label>
        </div>
        {error && <div className="mt-3 text-sm text-ember">{error}</div>}
      </section>

      <section className="mt-8 card-soft p-6">
        <div className="text-sm text-slate">共 {rows.length} 条记录</div>
        <div className="mt-4 overflow-auto">
          <table className="min-w-[1200px] text-sm">
            <thead className="border-b border-ink/10 text-left text-xs uppercase tracking-wide text-slate">
              <tr>
                <th className="py-2">时间</th>
                <th>币种</th>
                <th>合约</th>
                <th>类型</th>
                <th>方向</th>
                <th>数量</th>
                <th>成交价</th>
                <th>资金费率</th>
                <th>手续费</th>
                <th>OrderId</th>
                <th>TradeId</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={`${row.TradeId}-${idx}`} className="border-b border-ink/5">
                  <td className="py-2">{row.Time}</td>
                  <td>{row.Currency}</td>
                  <td>{row.Contract}</td>
                  <td>{displayType(row.Type)}</td>
                  <td>{displayDirection(row.Direction)}</td>
                  <td>{row.Quantity}</td>
                  <td>{row["Filled Price"]}</td>
                  <td className={row.Funding.startsWith("-") ? "text-ember" : "text-moss"}>
                    {row.Funding}
                  </td>
                  <td className={row["Fee Paid"].startsWith("-") ? "text-ember" : "text-slate"}>
                    {row["Fee Paid"]}
                  </td>
                  <td className="text-xs">{row.OrderId}</td>
                  <td className="text-xs">{row.TradeId}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && <div className="py-6 text-sm text-slate">暂无数据</div>}
        </div>
      </section>
    </main>
  );
}
