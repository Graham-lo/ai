"use client";

import { AuthField, PluginManifest } from "../../lib/types";

export function PluginForm({
  manifest,
  values,
  onChange,
  onSubmit,
}: {
  manifest: PluginManifest | null;
  values: Record<string, string>;
  onChange: (name: string, value: string) => void;
  onSubmit: () => void;
}) {
  if (!manifest) {
    return <div className="text-sm text-slate">请选择交易所以显示鉴权字段。</div>;
  }

  return (
    <div className="space-y-4">
      {manifest.auth_fields.map((field: AuthField) => (
        <label key={field.name} className="block">
          <span className="text-xs uppercase tracking-wide text-slate">{field.label}</span>
          <input
            className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
            type={field.secret ? "password" : "text"}
            value={values[field.name] || ""}
            required={field.required}
            onChange={(event) => onChange(field.name, event.target.value)}
          />
        </label>
      ))}
      <button onClick={onSubmit} className="btn-primary" type="button">
        保存账户
      </button>
    </div>
  );
}
