"use client";

export function DateRangePicker({
  start,
  end,
  onChange,
}: {
  start: string;
  end: string;
  onChange: (next: { start: string; end: string }) => void;
}) {
  return (
    <div className="flex flex-col gap-3 md:flex-row">
      <label className="flex-1">
        <span className="text-xs uppercase tracking-wide text-slate">开始日期</span>
        <input
          type="date"
          className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
          value={start}
          onChange={(event) => onChange({ start: event.target.value, end })}
        />
      </label>
      <label className="flex-1">
        <span className="text-xs uppercase tracking-wide text-slate">结束日期</span>
        <input
          type="date"
          className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
          value={end}
          onChange={(event) => onChange({ start, end: event.target.value })}
        />
      </label>
    </div>
  );
}
