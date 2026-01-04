"use client";

export function CostBreakdown({
  fees,
  funding,
}: {
  fees: number;
  funding: number;
}) {
  return (
    <div className="card-plain p-5">
      <div className="text-xs uppercase tracking-wide text-slate">成本拆解</div>
      <div className="mt-4 grid gap-3 text-sm">
        <div className="flex items-center justify-between">
          <span>撮合手续费</span>
          <span className="font-medium">{fees.toFixed(4)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>资金费率</span>
          <span className={`font-medium ${funding < 0 ? "text-ember" : "text-moss"}`}>
            {funding.toFixed(4)}
          </span>
        </div>
      </div>
    </div>
  );
}
