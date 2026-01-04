"use client";

import { useEffect, useMemo, useState } from "react";

import { PluginForm } from "../components/PluginForm";
import { createAccount, deleteAccount, getAccounts, getPlugins, rotateCredentials, updateAccount } from "../../lib/api";
import { Account, PluginManifest } from "../../lib/types";

export default function AccountsPage() {
  const [plugins, setPlugins] = useState<PluginManifest[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedExchange, setSelectedExchange] = useState<string>("");
  const [label, setLabel] = useState<string>("");
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [accountTypes, setAccountTypes] = useState<string[]>([]);
  const [optionsText, setOptionsText] = useState<string>("{}");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    Promise.all([getPlugins(), getAccounts()]).then(([pluginData, accountData]) => {
      setPlugins(pluginData);
      setAccounts(accountData);
    });
  }, []);

  const manifest = useMemo(
    () => plugins.find((plugin) => plugin.exchange_id === selectedExchange) || null,
    [plugins, selectedExchange]
  );

  function toggleAccountType(type: string) {
    setAccountTypes((prev) =>
      prev.includes(type) ? prev.filter((item) => item !== type) : [...prev, type]
    );
  }

  function handleFieldChange(name: string, value: string) {
    setCredentials((prev) => ({ ...prev, [name]: value }));
  }

  async function handleCreateAccount() {
    setError("");
    if (!manifest) return;
    try {
      const parsedOptions = optionsText ? JSON.parse(optionsText) : {};
      const next = await createAccount({
        exchange_id: manifest.exchange_id,
        label: label || `${manifest.display_name} Account`,
        account_types: accountTypes.length ? accountTypes : manifest.account_types.slice(0, 1),
        credentials,
        options: parsedOptions,
      });
      setAccounts((prev) => [...prev, next]);
      setCredentials({});
      setLabel("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function toggleEnabled(account: Account) {
    const updated = await updateAccount(account.id, { is_enabled: !account.is_enabled });
    setAccounts((prev) => prev.map((item) => (item.id === account.id ? updated : item)));
  }

  async function handleRotate(account: Account) {
    const apiKey = window.prompt("新的 API Key");
    const apiSecret = window.prompt("新的 API Secret");
    if (!apiKey || !apiSecret) return;
    await rotateCredentials(account.id, { api_key: apiKey, api_secret: apiSecret });
    alert("密钥已更新");
  }

  async function handleDelete(account: Account) {
    const ok = window.confirm(`确认删除账户：${account.label}？该操作不可恢复。`);
    if (!ok) return;
    await deleteAccount(account.id);
    setAccounts((prev) => prev.filter((item) => item.id !== account.id));
  }

  return (
    <main className="mx-auto max-w-6xl px-6 pb-16">
      <section className="card-soft p-8">
        <h2 className="font-display text-2xl">接入交易所账户</h2>
        <p className="mt-2 text-sm text-slate">仅使用只读权限密钥，建议启用 IP 白名单。</p>
        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <div className="space-y-4">
            <label className="block">
              <span className="text-xs uppercase tracking-wide text-slate">交易所</span>
              <select
                className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
                value={selectedExchange}
                onChange={(event) => {
                  const value = event.target.value;
                  setSelectedExchange(value);
                  const nextManifest = plugins.find((plugin) => plugin.exchange_id === value);
                  setAccountTypes(nextManifest ? nextManifest.account_types.slice(0, 1) : []);
                }}
              >
                <option value="">选择交易所</option>
                {plugins.map((plugin) => (
                  <option key={plugin.exchange_id} value={plugin.exchange_id}>
                    {plugin.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs uppercase tracking-wide text-slate">标签</span>
              <input
                className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                placeholder="主账户"
              />
            </label>
            {manifest && (
              <div>
                <div className="text-xs uppercase tracking-wide text-slate">账户类型</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {manifest.account_types.map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => toggleAccountType(type)}
                      className={`rounded-full px-3 py-1 text-xs ${
                        accountTypes.includes(type)
                          ? "bg-ink text-white"
                          : "border border-ink/10 bg-white text-slate"
                      }`}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <label className="block">
              <span className="text-xs uppercase tracking-wide text-slate">选项（JSON）</span>
              <textarea
                className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
                value={optionsText}
                onChange={(event) => setOptionsText(event.target.value)}
              />
            </label>
          </div>
          <div>
            <PluginForm
              manifest={manifest}
              values={credentials}
              onChange={handleFieldChange}
              onSubmit={handleCreateAccount}
            />
            {error && <div className="mt-3 text-sm text-ember">{error}</div>}
          </div>
        </div>
      </section>

      <section className="mt-10">
        <h3 className="font-display text-xl">账户列表</h3>
        <div className="mt-4 grid gap-4">
          {accounts.map((account) => (
            <div key={account.id} className="card-plain p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="font-medium">{account.label}</div>
                  <div className="text-xs text-slate">{account.exchange_id}</div>
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={() => toggleEnabled(account)} className="pill bg-ink/5 text-ink">
                    {account.is_enabled ? "禁用" : "启用"}
                  </button>
                  <button onClick={() => handleRotate(account)} className="pill bg-ink/5 text-ink">
                    更换密钥
                  </button>
                  <button onClick={() => handleDelete(account)} className="pill bg-ember/10 text-ember">
                    删除
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
