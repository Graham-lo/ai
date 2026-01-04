"use client";

const PRESETS = [
  { value: "last_7d", label: "最近7天" },
  { value: "last_30d", label: "最近30天" },
  { value: "this_month", label: "本月" },
  { value: "last_month", label: "上月" },
  { value: "ytd", label: "年初至今" },
  { value: "all_time", label: "全部" },
];

export function PresetSelector({
  preset,
  onChange,
}: {
  preset: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-wide text-slate">预设范围</span>
      <select
        className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
        value={preset}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">自定义</option>
        {PRESETS.map((preset) => (
          <option key={preset.value} value={preset.value}>
            {preset.label}
          </option>
        ))}
      </select>
    </label>
  );
}
