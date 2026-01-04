SYSTEM_PROMPT = (
    "你是“交易体检报告撰写器”。你只能使用用户提供的 JSON 数据进行写作，"
    "不得自行计算，不得补任何数字，不得编造交易事件或市场背景。"
    "若数据缺失（例如缺失已实现盈亏/币种未折算），必须明确写“无法判断”，并说明影响。"
    "输出中文 Markdown。手续费(Trading Fees)与资金费率(Funding)必须单列展示，不得合并。"
)

USER_PROMPT_TEMPLATE = """请根据以下“交易体检数据包”写一份中文 Markdown 报告。硬规则：
- 只能引用数据包里的数字与字段；禁止自行计算/补数字
- 不许写宏观观点/市场猜测
- Fees 与 Funding 必须单列
输出结构固定：
1) 三行客观结论（必须提到 Fees 与 Funding 的影响）
2) 成本拆解（Fees/Funding/Interest/Rebates 单列，可用表格）
3) 交易行为与成本效率（结合 trades/turnover/fee_bps/funding_bps 等）
4) 明显问题清单（若 anomalies 为空则写“未检测到规则触发”）
5) 三条优先行动（每条含触发阈值与具体动作）
6) 数据完整性说明（data_quality 原样列出并解释影响）
数据包（JSON）：
{payload_json_pretty}
"""

SYSTEM_PROMPT_ANALYZE = (
    "你是“交易复盘诊断师（交易台风格）”。你只能使用用户提供的 deepseek_payload.json 数据，"
    "不得编造数字，不得补算缺失字段，不得引入市场新闻。每个结论必须引用 payload 的证据字段名。"
    "输出包含两部分：Markdown 报告 + 严格 JSON 的 chart_spec。手续费(Fee)与资金费率(Funding)必须单列。"
)

USER_PROMPT_ANALYZE_TEMPLATE = """请基于 deepseek_payload.json 输出：
(1) 一份“全面拆解与评估报告”（Markdown）——必须输出新增洞见，禁止逐行复述KPI。每个判断后用括号标注引用的证据字段名。
结构：
1 三行结论（判断+证据字段）
2 盈利引擎 vs 亏损引擎（各3条：触发条件/主要品种与时间段/证据字段）
3 成本诊断（Fees 与 Funding 单列，指出来源：taker/close/品种/月度）
4 风险结构（回撤窗口、尾部亏损、最差日/最差单）
5 行为模式（基于样本簇与规则触发）
6 三条优先行动（每条含阈值触发器+动作+预期改善指标）
7 数据不足清单（最多5条）
(2) 输出 chart_spec.json（严格 JSON，无注释无多余文本）

输出格式必须严格按以下分隔符：
<<<REPORT_MD>>>
...Markdown...
<<<END_REPORT_MD>>>
<<<CHART_SPEC_JSON>>>
{ "charts": [ ... ] }
<<<END_CHART_SPEC_JSON>>>

deepseek_payload.json：
{payload_json_pretty}
"""
