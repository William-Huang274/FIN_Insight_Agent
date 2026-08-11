# 222 Fin Agent S1-S8 比较型 Evidence Gate 与分层测试矩阵

日期：2026-06-01

分支：`codex/api-model-call-architecture`

状态：本轮分层 gate 已完成；未启动 full-chain

关联文档：

- `docs/worklog/185_multi_agent_investment_research_framework_draft.md`
- `docs/worklog/186_multi_agent_tool_data_access_matrix_draft.md`
- `docs/eval/fin_agent_investment_research_quality_framework_v0_1.md`
- `docs/eval/fin_agent_layered_quality_execution_plan_v0_1.md`
- `docs/eval/fin_agent_s1_s8_agent_quality_case_matrix_v0_2.md`

## 问题

用户指出 NVDA primary filing rows 在 S5/S7 表现为“不完整”，并要求先修：

1. 比较型 case 的 focus ticker balanced row selector。
2. Specialist prompt row 分布持久化。
3. Comparative / sector-depth quality gate。
4. context rows 存在但 exact-value ledger rows 缺失时的显式 source gap。

随后再设计不同维度、不同行业、不同难度的 S1-S8 分层用例，逐层确认 agent 激活、工具调用、上游解析、输出质量和 token 成本，不急于 full-chain。

## 根因判断

当前 S3 并不是完全没有 NVDA primary rows；已查到 `ma_nvda_amd_market_standard` S3 有 NVDA primary context rows。但问题发生在 S5 可见和消费层：

- Fundamental data view 先拼 runtime ledger rows，再拼 context rows；如果某一 ticker exact-value rows 数量明显更多，会挤占 prompt row budget。
- Specialist prompt row selector 按 required slot terms 排序后直接截断，没有比较型 ticker coverage 约束。
- S5 gate 只检查有 primary rows 和 refs 合法，没有检查每个 focus ticker 是否有可见 primary evidence 或 source gap。
- S3 artifact 没有把 “context 有 filing，但 ledger 没 exact rows” 写成显式缺口，导致 S4/S5 无法区分 “filing 不存在” 与 “exact-value 抽取不足”。

## 文档更新

新增 `docs/eval/fin_agent_s1_s8_agent_quality_case_matrix_v0_2.md`，定义：

- exact / focused / standard / sector-depth / cross-sector / run-inspect 多层用例。
- AI infra、banking、healthcare、energy、utilities 等行业覆盖。
- S1-S8 每层 gate。
- comparative ticker primary visibility gate。
- source-gap / knowledge-base limitation 记录规则。

## 计划实现

P0 修复：

- 在 `build_agent_data_view()` 后增加 bounded row distribution。
- Fundamental / Risk data view 和 prompt selector 加 focus-ticker balanced selection。
- Specialist route result 增加 `prompt_row_distribution`。
- S5 gate 增加 comparative focus ticker primary rows 或 source gap 检查。
- S3 `execute_evidence_operator_plan()` 对 `ledger_missing_despite_context` 进行记录，并在 S3 result summary 中输出 row distribution。

P1 测试：

- 增加 unit tests 验证比较型 rows 不被单一 ticker 挤占。
- 增加 S5 scoring tests 验证 ticker coverage gate。
- 复用已通过 S1-S4 artifacts 跑 `ma_nvda_amd_market_standard` S5 targeted real DeepSeek。
- 再扩展 S1-S8 fixture，分层跑，不直接 full-chain。

## Stop / Proceed

Proceed：

- targeted unit tests 通过。
- S5 targeted `ma_nvda_amd_market_standard` 中 Fundamental/Risk prompt row distribution 同时覆盖 NVDA/AMD primary rows。
- Specialist real-evidence gate 区分 route pass 与 ticker evidence pass。

Stop：

- S5 gate 仍允许某 focus ticker 无 primary rows 且无 source gap。
- prompt route artifact 仍无法判断模型是否看到 NVDA rows。
- 失败来自本地知识库缺外源确认时，必须记录 source gap，不做 prompt 硬修。

## 本轮实现与修复结果

代码层已落地：

- S3 result summary 增加 row distribution，并在有 primary filing context 但缺 exact-value ledger 时记录 `ledger_missing_despite_context`。
- Fundamental / Risk data view 从“最小保留 focus ticker”升级为 ticker soft quota + metric/source diversity，避免某一个 ticker 或某一类 ledger rows 挤占 prompt。
- Risk data view / prompt selector 增加 market snapshot 与 untickered industry snapshot floor，避免风险专家看不到行业/市场上下文。
- Specialist route result 持久化 `prompt_row_distribution` 与 `input_coverage_summary`。
- S5 real-evidence gate 增加 comparative primary visibility、relationship evidence 引用、prompt distribution、temporal claim ref-depth 检查。
- temporal gate 修正为：单条 evidence row 若自身包含明确同比/比较文本，可支撑 trend claim；否则趋势/同比/环比/trajectory claim 至少需要两个 relevant period refs。
- S6-S8 `judgment_memo_diagnostic` schema 已接入 `audit_fin_agent_layer_quality.py`，不再被审计器标为 unknown。

新增/更新测试：

- `tests/test_multi_agent_evidence_requirements.py`
- `tests/test_multi_agent_specialist_llm.py`
- `tests/test_multi_agent_operator_permissions.py`
- `tests/test_multi_agent_real_llm_chain_eval.py`
- `tests/test_fin_agent_layer_quality_audit.py`

本地 targeted regression：`pytest -q tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_real_llm_chain_eval.py` 通过，`tests/test_fin_agent_layer_quality_audit.py` 通过。

## 分层真实 DeepSeek 运行结果

- S1 `20260601_fin_agent_s1_agent_quality_matrix_v0_2_deepseek_v0_2`：9/9 pass，total tokens 64,497。
- S2 `20260601_fin_agent_s2_agent_quality_matrix_v0_2_deepseek_v0_1`：2/2 pass，total tokens 22,620。
- S3 `20260601_fin_agent_s3_agent_quality_matrix_v0_2_real_retrieval_v0_1`：8/8 pass，真实 retrieval，725 context rows、1108 runtime ledger rows、14 market rows、34 industry rows。
- S4 `20260601_fin_agent_s4_agent_quality_matrix_v0_2_v0_1`：8/8 pass，3 个 case second pass allowed/ran，但新增 rows 为 0。
- S5 NVDA/AMD `20260601_fin_agent_s5_temporal_gate_nvda_amd_deepseek_v0_5`：1/1 pass，无 repair，total tokens 21,815。
- S5 energy final `20260601_fin_agent_s5_energy_risk_industry_prompt_floor_deepseek_v0_5`：1/1 pass，Risk prompt 包含 `industry_snapshot=2`、`market_snapshot=2`。
- S5 selected `20260601_fin_agent_s5_agent_quality_matrix_selected_deepseek_v0_2`：banking/utilities pass；energy 初始失败来自 temporal gate 过严，后续 targeted rerun 已修复。
- S6-S8 NVDA/AMD `20260601_fin_agent_s6_s8_nvda_amd_deepseek_v0_1`：1/1 pass，无 memo repair，total tokens 14,360。
- S6-S8 energy `20260601_fin_agent_s6_s8_energy_deepseek_v0_1`：1/1 pass，memo repair 1 次，total tokens 17,865。
- S6-S8 banking/utilities `20260601_fin_agent_s6_s8_selected_banking_utilities_deepseek_v0_1`：2/2 pass，memo repair 2 次，total tokens 43,103。

## 当前质量判断

- S1-S4：链路稳定，agent activation、工具归属、真实 retrieval、coverage/second-pass 边界可审计。
- S5：Specialist 已能理解上游任务和 bounded evidence，能生成合法 ClaimCards；比较型和行业上下文消费明显改善。
- S6：Aggregator 能把 ClaimCards 转成可写 memo 的 thesis pack，unsupported/conflict 不进入 memo slot。
- S7：Memo Writer 能稳定产出 thesis-led bounded memo，但输出仍偏短，尚未达到完整深度投研报告形态。
- S8：Verifier 能守住边界和引用合法性，但不提升 memo 深度。

## 已知限制

- Relationship graph 仍多为 sector-depth hypothesis，不是 confirmed commercial relationship。
- Healthcare fixture 是 focused answer，不触发 Specialist；需要新增 healthcare standard/deep case 才能测医疗专家能力。
- Energy 本地数据支持 commodity price context，但缺管理层 commodity outlook、外部供需/监管等细粒度外源数据。
- S6-S8 仍有 memo repair token 成本，后续应优化 Memo Writer schema/prompt，降低 repair。
