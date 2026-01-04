"use client";

import dynamic from "next/dynamic";

const ReactECharts = dynamic(() => import("echarts-for-react"), { ssr: false });

type ChartSpec = {
  charts?: Array<{
    id?: string;
    type?: string;
    title?: string;
    option?: Record<string, unknown>;
  }>;
};

export function DeepseekCharts({ chartSpec }: { chartSpec: ChartSpec | null }) {
  if (!chartSpec?.charts?.length) {
    return <div className="text-sm text-slate">暂无图表数据。</div>;
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {chartSpec.charts.map((chart, index) => (
        <div key={chart.id || index} className="card-plain p-4">
          {chart.title && <div className="mb-2 text-sm font-semibold text-ink">{chart.title}</div>}
          {chart.option ? (
            <ReactECharts option={chart.option} style={{ height: 300 }} />
          ) : (
            <div className="text-sm text-slate">图表配置缺失。</div>
          )}
        </div>
      ))}
    </div>
  );
}
