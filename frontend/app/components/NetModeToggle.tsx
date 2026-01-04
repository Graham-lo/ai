"use client";

export function NetModeToggle({
  value,
  onChange,
}: {
  value: "fees_only" | "fees_plus_funding";
  onChange: (value: "fees_only" | "fees_plus_funding") => void;
}) {
  return (
    <div className="inline-flex rounded-full border border-ink/10 bg-white p-1 text-sm">
      <button
        type="button"
        onClick={() => onChange("fees_only")}
        className={`rounded-full px-4 py-2 ${value === "fees_only" ? "bg-ink text-white" : "text-slate"}`}
      >
        净值（仅费用）
      </button>
      <button
        type="button"
        onClick={() => onChange("fees_plus_funding")}
        className={`rounded-full px-4 py-2 ${value === "fees_plus_funding" ? "bg-ink text-white" : "text-slate"}`}
      >
        净值（费用+资金费率）
      </button>
    </div>
  );
}
