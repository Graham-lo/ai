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
  const isDateValue = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value);
  return (
    <div className="flex flex-col gap-3 md:flex-row">
      <label className="flex-1">
        <span className="text-xs uppercase tracking-wide text-slate">开始日期</span>
        <input
          type="date"
          className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
          value={isDateValue(start) ? start : ""}
          onChange={(event) => onChange({ start: event.target.value, end })}
        />
        <input
          type="text"
          className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
          placeholder="YYYY-MM-DD"
          value={start}
          onChange={(event) => onChange({ start: event.target.value.trim(), end })}
        />
      </label>
      <label className="flex-1">
        <span className="text-xs uppercase tracking-wide text-slate">结束日期</span>
        <input
          type="date"
          className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
          value={isDateValue(end) ? end : ""}
          onChange={(event) => onChange({ start, end: event.target.value })}
        />
        <input
          type="text"
          className="mt-2 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm shadow-sm"
          placeholder="YYYY-MM-DD"
          value={end}
          onChange={(event) => onChange({ start, end: event.target.value.trim() })}
        />
      </label>
    </div>
  );
}
