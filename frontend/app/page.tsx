export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-6 pb-16">
      <section className="card-soft p-10">
        <h1 className="font-display text-4xl text-dusk">交易体检，直给事实。</h1>
        <p className="mt-4 max-w-2xl text-slate">
          接入交易所 API，同步成交与资金流水，输出费用与资金费率分离的报告，并自动给出进步检测和异常标注。
        </p>
        <div className="mt-8 flex flex-wrap gap-4">
          <a className="btn-primary" href="/accounts">
            接入账户
          </a>
          <a className="btn-ghost" href="/reports">
            生成报告
          </a>
        </div>
      </section>
      <section className="mt-10 grid gap-6 md:grid-cols-3">
        <div className="card-plain p-6">
          <div className="text-sm uppercase tracking-widest text-moss">成本</div>
          <h3 className="mt-2 font-display text-xl">手续费与资金费率拆分</h3>
          <p className="mt-2 text-sm text-slate">资金费率始终单列，并支持两种净口径。</p>
        </div>
        <div className="card-plain p-6">
          <div className="text-sm uppercase tracking-widest text-ember">进步检测</div>
          <h3 className="mt-2 font-display text-xl">月度与滚动对比</h3>
          <p className="mt-2 text-sm text-slate">用客观规则识别改进与退步。</p>
        </div>
        <div className="card-plain p-6">
          <div className="text-sm uppercase tracking-widest text-dusk">安全</div>
          <h3 className="mt-2 font-display text-xl">只读设计</h3>
          <p className="mt-2 text-sm text-slate">不提供下单、转账或提币功能。</p>
        </div>
      </section>
    </main>
  );
}
