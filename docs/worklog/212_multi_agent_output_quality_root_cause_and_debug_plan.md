# 212 Multi-agent 输出质量根因排查与逐 Case 调试计划

日期：2026-05-31

## Prompt

用户要求先全面排查 multi-agent 链路上影响输出质量的问题，不只看 evidence cap、门控、prompt；需要结合 DeepSeek Pro 的真实输出边界，在安全与输出质量之间重新做 trade-off。执行顺序固定为：先排查问题，做出假设，落入文档，然后按文档规划逐 case 调试。

## Baseline Evidence

基线采用最近一次真实 Step17 sector-depth 4-case run：

- Run ID: `20260531_step17_relationship_skill_v0_2_full4_rerun_cuda_deepseek_v0_1`
- Summary: `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_relationship_skill_v0_2_full4_rerun_cuda_deepseek_v0_1/real_chain_eval_summary.json`
- 状态：`4/4` pass，真实 MCP retrieval enabled，SEC BM25/ObjectBM25/BGE rerank 有正候选数，Industry Specialist relationship citation gate 通过。
- caveat：`211` 的 relationship-pack semantic gate 是 deterministic 修复，尚未做真实 DeepSeek full-chain 复跑。

基线说明：当前 pass 主要代表链路可运行、权限合法、没有明显 unsupported leakage；不代表输出已经是高质量投研 memo。

## Case-by-case 初步诊断

| Case | 已通过部分 | 质量风险 |
| --- | --- | --- |
| AI infrastructure | 全 agent 激活、relationship lookup 24 rows、SEC search/BGE 正常、Industry relationship refs 被引用 | 输出仍说 ANET/VRT 缺少 audited financials 和 supplier-customer links；说明 company-level confirmation / claim synthesis 不够，不是单纯 route failure |
| Banking | JPM/C/WFC/GS 的 SEC、market、industry、relationship 都被调起 | Memo 表达大量缺失公司层面数据；银行专属 metric/ledger 沉淀不足，净息收入、存款、信用风险等指标没有稳定转成 claim cards |
| Healthcare | relationship/industry/SEC route 成功，Healthcare pack 被接入 | 输出说分析只覆盖部分公司和维度；产品周期、监管/需求背景和 company financial proof 没有被组织成可比较投资观点 |
| Energy / Utilities | relationship lookup 和 industry rows 足量；`211` 已修 relationship pack selection | 基线真实 run 引用了 AI-infra refs，semantic gate 已修但未真实复跑；且 SEC calls 有 source gaps，却 second-pass 为 0 |

## Root-cause Hypotheses

### H1: Research Lead / Evidence Requirement 粒度过粗

DeepSeek Pro 能正确识别 `deep_research` 并激活必要 agent，但当前 evidence requirement 仍偏“少数 compact requirements”。对 4 tickers x 多 metric families x sector-depth 问题，过粗的 requirement 会让 retrieval 和 specialist 只能拿到一组混合证据，不能形成逐公司、逐指标、逐链路的 memo-ready evidence set。

验证信号：

- 4 个 sector-depth case 的 requirement count 约 5-6。
- Tool calls 8-11，符合预算但不一定覆盖所有 company/metric slots。
- 最终 memo 常出现 “limited / missing / 缺失”。

### H2: Tool budget 与 route pruning 合法但偏保守

185/186 的权限矩阵已经落地，但 `deep_research` 当前 `max_tool_calls_total <= 12`，每个 operator 通常 `max_tool_calls=4`。这能防循环，但会让 sector-depth retrieval 在多公司、多 source-family 下倾向“能跑完”而不是“够支撑 memo”。

风险不是应该取消预算，而是 budget 应由 execution mode / case complexity / required slots 决定。

### H3: Coverage / Reflection 没有把缺口变成有效 second-pass

真实 run 中 `second_pass.attempts=0`。Energy / utilities 的 SEC tool calls 已经有 source gaps，但没有触发第二轮补证。当前 Reflection gate 更像“安全允许 bounded answer”，不是“质量上必须补证后再写”。

### H4: Specialist 输入和输出都过早压缩

当前 data view 最大 16 rows，Specialist prompt 默认 12 rows，relationship summary 默认 8 rows。这个设置能控制 hallucination，但对 sector-depth multi-company case 偏窄。

更关键的是 Specialist output 被限制为最多 3 observations。DeepSeek Pro 在这个约束下会倾向输出“证据摘要 + 缺口提示”，而不是投研 memo 需要的多个结构化 claim cards。

### H5: Specialist 没有拿到足够明确的 assigned task

Specialist request 目前主要有 `user_query`、`bounded_evidence_rows`、`relationship_summary`、`coverage_summary`、`source_boundaries`。它缺少来自 Research Lead / EvidenceRequirementPlan 的 role-specific assigned task，例如：

- 该专家必须覆盖哪些 tickers；
- 哪些 metric families 是主判断；
- 哪些 source rows 是 primary vs supporting；
- 最终应该产出哪个 memo slot。

这会导致 Fundamental / Risk / Market 输出理解上没错，但形态像“局部证据说明”，不是“投资观点构件”。

### H6: Judgment Aggregator 只安全聚合，没有做投资判断排序

当前 aggregator 保留 supported / unsupported / conflicts，安全性是对的；但它没有：

- 选择主 thesis；
- 对 claims 排 materiality；
- 合并同一公司/同一主题的证据；
- 把 specialist claim 映射到 memo outline；
- 计算哪些缺口需要阻断、哪些只需 caveat。

因此 Memo Writer 收到的是“可验证 claim 列表”，不是“高信息密度 judgment plan”。

### H7: Memo Writer 输入被压缩成 verified plan，但 plan 不是 memo-ready

Memo Writer 不读 raw rows 是正确边界。但现在它只消费 `verified_judgment_plan` / `verified_summary`，而 verified plan 缺少可直接写作的 claim cards、evidence table、section outline 和 investment stance。DeepSeek Pro 因此会花大量 token 读 payload，却输出短、保守、缺少结构的 memo。

### H8: Verifier 是安全门，不是质量提升器

Verifier 能阻止 raw rows、工具调用、unsupported claims 和 source misuse，但它不会让 memo 更深。当前 eval 里的 `claim_verification=pass` 容易掩盖“安全但浅”的问题。需要把 safety pass 和 memo quality pass 分开。

## DeepSeek Pro 能力边界判断

从 Step10-Step17 真实运行看，DeepSeek Pro 的边界大致是：

- 能稳定遵守 JSON schema、role boundary、direct tool call 禁止和修复指令。
- 能理解上游任务和 bounded evidence，不是“理解不了指令”。
- 在严格证据边界 + 短输出 cap 下，会显著保守化，倾向写缺口和 caveat。
- 当 payload 很大但输出结构不够强时，会消耗大量 token 读上下文，却不会自动产出高密度投研 memo。
- 因此下一阶段应该少靠“再嘱咐模型写深一点”，多给结构化中间产物、质量目标和分层预算。

## Safety / Quality Trade-off

继续保留的安全边界：

- Memo Writer 不直接调用工具。
- Memo Writer 不读取 raw rows / physical paths。
- Verifier 不生成新观点、不扩范围、不触发检索。
- relationship graph 只能支持 scope / hypothesis，不能当财务事实。
- market / industry 不能覆盖 SEC company-reported facts。

需要放宽或重构的地方：

- Evidence cap 不能全局固定，应按 `focused_answer` / `standard_memo` / `deep_research` 分层。
- Specialist output 不应限死 3 observations；deep research 应允许 6-8 个 claim cards。
- Judgment Aggregator 应从“安全拼接”升级为“verified claim ranking + memo outline”。
- Eval gate 应要求 quality sufficiency，不只要求 route/safety pass。

## Execution Plan

### Q0: 静态质量台账和 baseline freeze

新增只读 audit 脚本，对已保存 run 产出 case-level 质量台账：

- token by agent；
- tool rows / source gaps / BGE candidate counts；
- specialist input rows / source families；
- second-pass attempts；
- high-token / low-density / no-second-pass flags；
- run-level hypotheses。

Gate：

- 不调用 LLM；
- 不读取 API key；
- 能在现有 Step17 output dir 上直接产出 JSON + Markdown。

### Q1: Eval gate 拆成 safety pass 和 quality pass

在 full-chain eval 中新增质量层，不改变现有安全门：

- `route_success`: agent/tool 是否按预期激活；
- `real_evidence_quality`: evidence refs 是否真实、source family 是否合法；
- `claim_card_quality`: Specialist 是否产生足够 memo-ready claim cards；
- `memo_quality`: 最终 memo 是否覆盖 tickers / metrics / risk / caveat / evidence refs；
- `cost_quality`: token 是否转化为有效 claims。

Gate：

- 旧 safety gate 继续 pass/fail；
- 新 quality gate 可先 `diagnostic_only`，不能阻断主链路；
- 每个失败项必须落入 per-case audit。

### Q2: Evidence budget tier v0.2

改造 row budget：

- `focused_answer`: Specialist rows 8-12；
- `standard_memo`: 16-24；
- `deep_research` / sector-depth: 24-32；
- Industry 至少 4-8 relationship rows；
- Risk 必须 source-balanced；
- Market 维持较小，但必须保留 `as_of_date` / `snapshot_id`。

Gate：

- 不能把 raw rows 交给 Memo Writer；
- budget 提升必须只进入 Specialist / Verifier bounded data view；
- token 成本上限和 row-source quota 写入 audit。

### Q3: Specialist ClaimCard v0.2

把 SpecialistMemolet 从 1-3 observations 升级为 claim-card 输出：

- `claim`;
- `agent_id`;
- `ticker_scope`;
- `metric_scope`;
- `memo_slot`;
- `materiality`;
- `direction`;
- `claim_type`;
- `evidence_refs`;
- `source_families`;
- `confidence`;
- `missing_confirmations`;
- `caveats`。

Gate：

- focused: 2-3 cards；
- standard: 4-6 cards；
- deep: 6-8 cards；
- 所有 supported card 必须引用 known refs；
- relationship card 必须 hypothesis-only。

### Q4: Judgment Aggregator v0.2

Aggregator 不生成新事实，但要做结构化排序：

- group claim cards by memo slot；
- rank by materiality/confidence/source strength；
- preserve conflicts；
- build `memo_outline`;
- decide `memo_writer_allowed` vs `bounded_partial_memo_allowed`；
- mark second-pass-needed gaps before Memo Writer。

Gate：

- unsupported claims 不进 memo outline；
- conflict 不被平均；
- 每个 memo section 至少有 1 个 supported card 或明确缺证理由。

### Q5: Memo Writer v0.2

Memo Writer 继续不读 raw rows，但改为消费：

- verified claim cards；
- memo outline；
- compact evidence table；
- source boundary summary；
- missing evidence table。

Gate：

- sector-depth memo 必须有 thesis、company comparison、relationship/readthrough、market context、counterevidence、what-to-verify-next；
- 必须显式引用 claim card ids/evidence refs；
- 不能用 relationship/market/industry 当 company reported financial fact。

### Q6: Second-pass quality loop

当出现以下条件时，在 Memo Writer 前触发 bounded second-pass：

- source gaps > 0 且缺口对应 required metric/source；
- required ticker 没有任何 supported claim card；
- numeric metric requested 但 ledger rows = 0；
- relationship case 没有 expected pack refs；
- risk specialist 只有 generic gaps 没有 direct counterevidence 或明确 missing tests。

Gate：

- 最多一轮 quality second-pass；
- 无新增 row 或无新增 useful claim 时停止；
- loop break reason 必须进台账。

### Q7: 逐 Case 调试顺序

1. AI infrastructure：先验证 relationship + fundamental + market 能不能形成 6-8 张有效 claim cards。
2. Banking：重点验证 bank-specific ledger / metric coverage；没有 ledger 时必须把缺口阻断成 partial memo。
3. Healthcare：重点验证 product cycle / regulatory-demand context 是否被拆成可比较 cards。
4. Energy / utilities：先用 `211` semantic gate 真实复跑，确认 relationship pack refs 正确，再处理 source gaps / second-pass。

每个 case 只改一个主要变量，记录：

- changed variable；
- expected improvement；
- safety risk；
- token impact；
- pass/fail evidence；
- rollback condition。

## First Execution Slice

本次先执行 Q0：新增静态质量 audit 脚本并在现有 4-case run 上生成质量台账。随后把该 audit 挂到 Step17 full-chain eval 输出流程里，后续真实 run 会自动生成质量诊断，不再只看 hard gate pass/fail。后续再按 Q1-Q7 改主链路和真实 DeepSeek 复跑。

## Q0 Execution Result

新增：

- `scripts/audit_multi_agent_output_quality.py`
- `tests/test_multi_agent_output_quality_audit.py`

已在现有 baseline run 上生成：

- `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_relationship_skill_v0_2_full4_rerun_cuda_deepseek_v0_1/multi_agent_output_quality_audit.json`
- `eval/sec_cases/outputs/multi_agent_real_llm_chain_eval/20260531_step17_relationship_skill_v0_2_full4_rerun_cuda_deepseek_v0_1/multi_agent_output_quality_audit.md`

Audit 结果：

| Case | Risk | Tokens | Tool rows | Source gaps | Second pass | Specialist rows | 主要 flags |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| AI infra | high | 72025 | 148 | 0 | 0 | fund=16, ind=16, mkt=8, risk=16 | high token, specialist cap, unsupported claims, memo says evidence thin |
| Banking | high | 68947 | 109 | 0 | 0 | fund=16, ind=16, mkt=6, risk=16 | high token, specialist cap, unsupported claims, memo says evidence thin |
| Healthcare | high | 73106 | 109 | 0 | 0 | fund=16, ind=16, mkt=4, risk=16 | high token, specialist cap, unsupported claims, memo says evidence thin |
| Energy / utilities | high | 68396 | 164 | 5 | 0 | fund=16, ind=16, mkt=8, risk=16 | source gaps without second pass, plus the same high-token / cap / unsupported issues |

Q0 验证：

```text
python -m pytest tests/test_multi_agent_output_quality_audit.py -q
result: 2 passed

python -m compileall scripts/audit_multi_agent_output_quality.py
result: pass
```

Q0 结论：当前 Step17 hard gate 通过，但 output-quality audit 全部为 high risk。下一步应优先实现 Q1/Q2/Q3，而不是直接扩大真实 DeepSeek batch。

## Q1 Partial Execution Result

已把 Q0 audit 接入 `scripts/eval_multi_agent_real_llm_chain.py`：

- 每次 full-chain eval 聚合 summary 后自动生成：
  - `multi_agent_output_quality_audit.json`
  - `multi_agent_output_quality_audit.md`
- `real_chain_eval_summary.json` 现在会包含 `output_quality_audit` 摘要：
  - `issue_counts`
  - `run_hypotheses`
  - `case_risk_levels`

这一步只增加诊断输出，不改变 hard gate，不改变模型 prompt，不触发额外 LLM 调用。

验证：

```text
python -m pytest tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_real_llm_chain_eval.py -q
result: 7 passed

python -m compileall scripts/audit_multi_agent_output_quality.py scripts/eval_multi_agent_real_llm_chain.py
result: pass
```

Q1 剩余未做：把 `claim_card_quality`、`memo_quality`、`cost_quality` 变成正式 eval fields；当前只是 artifact-level diagnostic audit。

## Q2-Q5 Deterministic Execution Result

本轮按计划先改主链路的结构化中间产物，不直接扩大真实 DeepSeek batch。

### Q2 Evidence budget tier v0.2

已实现：

- `deep_research` agent data view 从固定 `16` rows 扩到默认 `32` rows；
- `standard_memo` 默认 `24` rows；
- Specialist prompt rows 按 execution mode 分层：
  - focused / default: `12`;
  - standard memo: `16`;
  - deep research: `24`;
- Industry / Supply-Chain 在 `deep_research` 下至少保留 `6` 条 relationship rows；
- `relationship_summary` 在 deep research 下 data-view 默认 `24` rows，prompt 默认 `12` rows；
- `input_budget` 写入 agent data view 和 Specialist request，后续 audit 可判断实际 token 是否花在有效证据上。

安全边界：

- Memo Writer 仍不读取 raw rows；
- 扩容只进入 bounded Specialist / Verifier data view；
- market snapshot 仍走 compact policy 并保留 `snapshot_id` / `as_of_date`。

### Q3 Specialist ClaimCard v0.2

已实现：

- Specialist observation 兼容 ClaimCard v0.2 字段：
  - `ticker_scope`;
  - `metric_scope`;
  - `memo_slot`;
  - `materiality`;
  - `direction`;
  - `missing_confirmations`;
  - `claim_card_version`;
  - `claim_id`。
- Fundamental / Industry / Market / Risk v0.2 skill 已更新为 execution-mode-aware claim-card 输出。
- Specialist prompt 明确要求把每条 observation 当作 ClaimCard v0.2，而不是普通证据摘要。

### Q4 Judgment Aggregator v0.2

已实现：

- Aggregator 不新增事实，只对 verified supported claim cards 排序；
- 排序依据：
  - materiality；
  - confidence；
  - source strength；
  - 原始顺序稳定 tie-break；
- 新增 `memo_outline`，按 active specialist slots 标记 supported / missing_or_partial；
- 新增 `claim_card_stats`，包含 supported claim count、high materiality count、memo slot coverage。

安全边界：

- unsupported claims 仍不进入 memo outline；
- conflicts 仍保留，不平均、不合并成乐观结论；
- missing section 会显式标记 `missing_reason`。

### Q5 Memo Writer v0.2

已实现：

- Memo Writer prompt 改为消费 `memo_outline` 和 verified ClaimCard；
- MemoDraft normalization 会保留 `memo_outline` / `claim_card_stats`；
- Memo Writer 仍只消费 verified judgment plan / verified summary，不读 raw rows、不请求工具；
- prompt 要求保留 `materiality`、`direction`、`ticker_scope`、`metric_scope`、`evidence_refs`、`caveats`、`missing_confirmations`。

### Q1 Diagnostic Extension

Audit 增加 claim-card / memo-outline 质量信号：

- `claim_card_density_low`;
- `memo_outline_under_supported`;
- Markdown table 增加 `Claim cards` 列；
- run hypotheses 会区分“路由成功”与“claim-card 密度不足 / outline 支撑不足”。

验证：

```text
python -m pytest tests/test_multi_agent_contracts.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_output_quality_audit.py -q
result: 46 passed

python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_chain_performance_eval.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_research_lead_llm.py -q
result: 42 passed

python -m compileall src/sec_agent/multi_agent_contracts.py src/sec_agent/memo_llm.py src/sec_agent/specialist_llm.py src/sec_agent/multi_agent_runtime.py scripts/audit_multi_agent_output_quality.py
result: pass
```

## Q6 Deterministic Execution Result

已实现 quality-triggered second-pass 的确定性链路：

- 在 `aggregate_judgment_plan -> memo_writer` 之间增加质量路由；
- Aggregator 生成 verified claim cards / memo outline 后，额外构建 `quality_second_pass_report`；
- 若质量报告允许补证，则把 `multi_agent_reflection_report` 切换为 `quality_second_pass` 请求，进入 `optional_second_pass`；
- `optional_second_pass` 现在在未注入自定义函数时也会用 `second_pass_retrieval_plan` 调用 `execute_evidence_operator_plan`，而不是只做 mock no-gain；
- 补证后会重新进入 Specialist subgraph 和 Aggregator；
- `quality_second_pass_attempted` 防止质量补证循环，单 case 最多一轮 quality second-pass。

触发条件当前覆盖：

- `source_gaps > 0` 且 source available；
- deep-research required ticker 没有 supported ClaimCard；
- deep-research 请求 numeric metric 但 `runtime_ledger_rows=0`；
- relationship case 缺 supported relationship evidence ref。

安全边界：

- quality second-pass 仍走 deterministic retrieval compiler；
- 仍经过 ToolCallLedger / loop budget / duplicate call checks；
- Memo Writer 仍不读 raw rows，不触发工具；
- source unavailable 不会硬搜外部数据，只进入 bounded answer / caveat。

验证：

```text
python -m pytest tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_langgraph_routing.py -q
result: 18 passed

python -m pytest tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_contracts.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_universe_relationship.py tests/test_multi_agent_output_quality_audit.py -q
result: 64 passed

python -m pytest tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_chain_performance_eval.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_research_lead_llm.py tests/test_research_skills.py -q
result: 31 passed

python -m compileall src/sec_agent/multi_agent_runtime.py src/sec_agent/langgraph_orchestrator.py
result: pass
```

## Current Remaining Work

- 已用 DeepSeek 复跑 1 个 AI infra full-chain 单 case，run id:
  `20260531_ai_infra_full_chain_real_retrieval_quality_q6_single_deepseek_v0_1`。
- 尚未逐 case 调试 AI infra / banking / healthcare / energy-utilities 的真实输出变化。
- 尚未把 memo-quality / cost-quality 从 diagnostic audit 提升成正式 blocking gate。

## Q7 Single-Case Root Cause And Fix Plan

### 真实单 case 结果

AI infra sector-depth 单 case 执行完成但 gate 失败：

- `gate_status=fail`，`diagnostic_only=true`；
- `total_tool_calls=12`；
- Research Lead / Universe / Evidence Operators / Specialist route 均成功；
- BM25/ObjectBM25/BGE rerank 实际触发，`bge_device=cuda`，`cuda_available=true`；
- `runtime_ledger_rows=0`，导致 numeric support 不足并触发 Q6 quality second-pass；
- quality second-pass 追加了 16 条 context rows，但 ledger rows 仍为 0；
- Industry Specialist 引用了 relationship evidence，但 lookup 结果混入 `energy_infrastructure_depth`，不满足 AI infra case 的 expected pack gate；
- Memo Writer 三次调用均 `finish_reason=length`，最终 JSON 解析失败并落回 deterministic fallback；
- Verifier 因 deterministic memo gate 未过而未调用 LLM。

### 根因假设

- H1: `sec_search_filings` 已能返回真实 SEC context rows，但 context rows 是 `evidence_object`，当前 runtime ledger 只从 structured object index / ledger store 构建；当 object index 没有 2026 8-K/10-Q structured rows 时，ledger 必然为 0。
- H2: AI infra query 文本包含 `infrastructure` 等词，relationship lookup 的 sector-depth query matching 会把 energy pack 一并纳入；eval gate 期望 pack 是 `technology_ai_infrastructure_depth`，所以应显式把 expected pack 传给 lookup。
- H3: Memo Writer 同时收到完整 `verified_judgment_plan` 和 data-view 内重复 judgment，prompt 过大；DeepSeek-pro 能理解任务，但输出被 `max_tokens` 截断，token 主要耗在重复 payload 与三次失败重试上。
- H4: Specialist 支持 ClaimCard 数量低，和 ledger rows 缺失、relationship pack 泄漏相关；先修上游证据结构，再判断是否需要继续调 Specialist skill/prompt。

### Q7 已执行修复

- `scripts/cloud/sec_agent_interactive.py`
  - 新增 context evidence object -> structured extraction -> runtime ledger fallback；
  - 当 SEC context row 中有 `[TABLE_START]` 或数字文本时，使用已有 `EvidenceObject` / `extract_structured_objects` 抽取 metric rows，再走现有 `_ledger_row_from_metric` / `_ledger_row_allowed`；
  - 扩展 metric family alias：`capex -> capital_expenditure_proxy`、`segment_revenue -> revenue/total_revenue/product_revenue/data_center_revenue`、`rpo_deferred_revenue -> rpo/deferred_revenue/arr_or_recurring_proxy` 等。
- `src/sec_agent/relationship_graph.py`
  - `query_relationship_graph` 增加 `expected_pack_ids`；
  - sector-depth pack lookup 在 expected pack 存在时只从指定 pack 选 relationships。
- `src/sec_agent/mcp_tool_registry.py` / `src/sec_agent/multi_agent_runtime.py` / `scripts/eval_multi_agent_real_llm_chain.py`
  - eval case 的 `expected_relationship_pack_ids` 传入 MCP relationship lookup。
- `src/sec_agent/memo_llm.py`
  - Memo Writer prompt 改用 compact judgment；
  - 去掉重复大 payload，限制 direct answer / memo claims / caveats；
  - 对 `finish_reason=length` 单独标记为 `model_output_truncated`，repair prompt 进一步缩短。
- `tests/fixtures/multi_agent_real_llm_chain_cases_v0_1.jsonl`
  - AI infra full-chain case 将 `require_runtime_ledger_rows` 提升为 `true`，使“真实 ledger rows 传给 Specialist”成为 gate。

验证：

```text
python -m pytest tests/test_sec_agent_ledger_store.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py -q
result: 33 passed

python -m compileall src/sec_agent/memo_llm.py src/sec_agent/relationship_graph.py src/sec_agent/mcp_tool_registry.py src/sec_agent/multi_agent_runtime.py scripts/cloud/sec_agent_interactive.py scripts/eval_multi_agent_real_llm_chain.py
result: pass
```

### 下一步 Gate

先复跑 AI infra 单 case，不扩大 batch。通过条件：

- `sec_search_filings` 仍触发 BM25/ObjectBM25/BGE rerank；
- `runtime_ledger_rows > 0`；
- Industry Specialist 的 relationship pack refs 只来自 `technology_ai_infrastructure_depth`；
- Memo Writer 不再 `finish_reason=length` 三连失败；
- 若最终 memo 仍 fail，必须能区分是 Specialist ClaimCard 内容不足、Verifier gate 太严，还是 Memo Writer 写作质量不足。

## Q8 Single-Case Follow-up Diagnosis

### Q7 复跑结果

AI infra 单 case 复跑 run id:
`20260531_ai_infra_full_chain_real_retrieval_quality_q7_single_deepseek_v0_1`。

结果仍为 diagnostic fail，但失败面已收窄：

- Evidence Operators 真实执行通过：
  - `sec_search_filings` 触发 BM25/ObjectBM25/BGE rerank；
  - BGE runtime 显示 `bge_device=cuda`、`cuda_available=true`；
  - `runtime_ledger_row_count` 已从 0 修复为非零，最终 state summary `ledger_row_count=70`。
- Memo Writer / Verifier 已跑通：
  - Memo Writer `call_count=1`、`finish_reason=stop`；
  - Verifier `call_count=1`、`finish_reason=stop`；
  - 上一轮 Memo Writer 三连 `length` 截断已消失。
- 仍失败的门控：
  - Universe 节点自己的 `relationship_graph_lookup` 仍返回 `energy_infrastructure_depth`，说明 expected pack 只传到了后续 evidence route，没有传到 `universe_relationship_expand` 的直接 lookup；
  - Fundamental / Risk Specialist 三次尝试后仍 `json_parse_failed`，两个 agent 分别消耗约 35k / 33k tokens，属于无效 token；
  - Industry Specialist 能产出 JSON，但因 relationship rows 混入 energy pack，被 real evidence quality gate 拦下；
  - Audit flags 仍包含 `high_total_token_cost`、`many_unsupported_specialist_claims`、`memo_surface_says_evidence_thin`。

### Q8 根因假设

- H5: relationship pack 泄漏不是 `relationship_graph.py` 的过滤逻辑无效，而是 Universe 节点直接调用 lookup 时没有传入 `expected_relationship_pack_ids`。
- H6: Fundamental / Risk 的失败更像输出截断或非 JSON 完整性问题，而不是“不理解任务”。DeepSeek 已能让 Industry / Market 输出合规 JSON；Fundamental / Risk 的输入 rows 更长、输出要求更宽，容易在 ClaimCard 生成阶段超出 `max_tokens`。
- H7: 当前 repair loop 对 parse/length 失败会重复发送同等体量 payload，导致 token 花在重复失败上；repair 应切到 compact evidence subset + minimal schema，而不是完整重跑。
- H8: 为了继续判断“prompt vs gate vs evidence”，必须把 Specialist route result 增加 `finish_reasons` / input-output tokens，否则 parse failure 仍是黑盒。

### Q8 执行计划

- 把 `expected_relationship_pack_ids` 加入 `langgraph_orchestrator._node_universe_relationship_expand` 的 `relationship_graph_lookup` 参数。
- Specialist LLM route 调整：
  - 对 `finish_reason=length` 的 parse failure 标记为 `model_output_truncated`；
  - parse/truncation repair 改用 compact repair payload：最多 8 条 evidence rows、4 条 relationship rows、minimal SpecialistMemolet shape；
  - deep-research observation budget 从泛化 `4-8` 收紧为 role-specific：
    - Fundamental: `3-5`;
    - Risk: `2-4`;
    - Industry/Market: `3-5`;
  - route summary 增加 `finish_reasons`、`input_tokens`、`output_tokens`，用于判断 token 是否花在有效输出。
- Gate 不放松：
  - relationship pack relevance 仍阻止 off-sector evidence；
  - supported observations 仍必须引用 known refs；
  - unsupported claims 仍不进入 memo claims。

### Q8 复测门控

只跑 AI infra 单 case；通过/继续条件：

- relationship refs 不再出现 `energy_infrastructure_depth`；
- Fundamental / Risk 至少不再因为 parse/truncation 三连失败；
- route_success 与 real evidence quality 能分离观察；
- Memo Writer 仍保持 `finish_reason=stop`；
- total tokens 应明显低于 Q7 的 `131893`，否则继续压缩 Specialist payload 或关闭无效 repair。

### Q8 执行结果

AI infra 单 case 复跑 run id:
`20260531_ai_infra_full_chain_real_retrieval_quality_q8_single_deepseek_v0_1`。

结果：

- `gate_status=pass`，`pass_rate=1.0`，仍是 `diagnostic_only=true`；
- `total_tool_calls=10`；
- 所有 layer checks 通过：
  - Research Lead；
  - Universe / Relationship；
  - Evidence Operators；
  - Specialists；
  - Memo Writer / Verifier；
  - payload safety。
- `sec_search_filings` 均为真实检索：
  - `candidate_sent_to_bge=16`；
  - `bge_device=cuda`、`cuda_available=true`；
  - `runtime_ledger_row_count` 在 SEC routes 上为 13 / 17；
  - state summary 的 ledger rows 已可用。
- relationship pack gate 通过：
  - available / cited pack 只剩 `technology_ai_infrastructure_depth`；
  - 不再混入 `energy_infrastructure_depth`。
- Specialist route：
  - Fundamental: `pass`，2 attempts；第一次 `finish_reason=length`，第二次 compact repair 后成功；`total_tokens=18201`；
  - Industry: `pass`，1 attempt；引用了 relationship evidence refs，且全为 AI infra pack；`total_tokens=8797`；
  - Market: `pass`，1 attempt；`total_tokens=6023`；
  - Risk: `pass`，1 attempt；`total_tokens=9785`。
- Memo Writer / Verifier：
  - Memo Writer `pass`、1 call、`finish_reason=stop`、`total_tokens=21618`；
  - Verifier `pass`、1 call、`finish_reason=stop`、`total_tokens=21948`。
- 总 token 从 Q7 的 `131893` 降至 Q8 的 `98180`，下降约 26%；主要节省来自 Specialist 解析失败重试减少。

### Q8 质量评价

这次真实链路已经从“链路不稳 / 证据未接通”进入“链路可跑通但质量效率仍需优化”的阶段。

已改善：

- evidence operators 的真实召回、BGE rerank、runtime ledger、relationship graph 都进入主链路；
- Industry Specialist 能看到并引用 relationship evidence；
- Specialist route 成功和 real evidence quality 同时通过；
- Memo Writer 不再被输出截断，Verifier 也能完整执行。

仍不足：

- Fundamental 首轮仍会 `length`，靠 compact repair 成功；说明 role-specific prompt 仍偏宽，后续应让首轮就产出 compact ClaimCards；
- Memo Writer / Verifier token 仍高，尤其 Verifier 消耗接近 Memo Writer，却只承担安全门职责；
- audit 当前仍显示 `Claim cards=0`，本轮确认这是 artifact 可观测性缺口：`multi_agent_summary.json` 没保存 `judgment_plan.claim_card_stats` / `verified_judgment_plan.claim_card_stats`，不是这次 run 已能证明真的 0 张 ClaimCard。

### Q8 后续补丁

已追加一个不调用 LLM 的可观测性补丁：

- `src/sec_agent/langgraph_orchestrator.py`
  - `multi_agent_summary.json` 现在会写入 compact `judgment_plan` / `verified_judgment_plan` 质量摘要：
    - `claim_card_stats`；
    - supported / unsupported / conflict counts；
    - memo outline 的 slot/status/count 摘要。
  - specialist route summary 保留 `input_tokens`、`output_tokens`、`finish_reasons`。
- `scripts/audit_multi_agent_output_quality.py`
  - 区分 claim-card stats 是否存在；
  - 当 stats 存在且 supported count 为 0 时，显式打 `claim_card_density_zero`；
  - 避免把“artifact 未保存 stats”误判为“模型没有产出 ClaimCard”。

验证：

```text
python -m pytest tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_specialist_llm.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_real_llm_chain_eval.py -q
result: 41 passed

python -m pytest tests/test_sec_agent_ledger_store.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_contracts.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_langgraph_routing.py -q
result: 90 passed

python -m compileall src\sec_agent\specialist_llm.py src\sec_agent\langgraph_orchestrator.py scripts\audit_multi_agent_output_quality.py
result: pass
```

### Q9 建议

下一步不建议马上扩大 4-case batch，而是先做一次低成本结构优化：

- Specialist 首轮 prompt 再压缩：
  - Fundamental deep research 首轮限制 2-4 ClaimCards；
  - rows 保持 24/32 的 evidence coverage，但 summary chars 从默认 520 降到按 source family 分层；
  - 防止 Fundamental 再靠 repair 成功。
- Memo Writer / Verifier 成本拆分：
  - Memo Writer 只读 `verified_judgment_plan` 的 `supported_claims` + `memo_outline` compact projection；
  - Verifier 不读完整 memo input payload，只读 final memo + evidence ref inventory + unsupported exclusions；
  - 将 `memo_writer_high_token_cost`、`verifier_high_token_cost` 作为 diagnostic gate 继续观察，不立即阻断。
- 再跑 AI infra 单 case 一次确认 claim-card stats artifact 正常；如果通过且 token 继续下降，再扩大到 banking / healthcare / energy-utilities。

## Q9 Quality / Cost Trade-off Debug Gate

### 当前问题判断

Q8 已经证明主链路不是“没有 full-chain”或“没有真实召回”：Research Lead、Universe、SEC/8-K/market/industry operators、BGE rerank、runtime ledger、Specialists、Memo Writer、Verifier 都被激活并通过 gate。现在影响最终 memo 质量和 token 有效性的主要问题转移到三类：

1. Specialist 首轮输出预算仍偏宽。
   - AI infra Q8 中 Fundamental 首轮 `finish_reason=length`，靠 compact repair 通过；
   - 这说明模型理解上游任务，但首轮 payload / 输出预算让它倾向于展开，而不是直接产出少量 memo-ready ClaimCards。
2. Memo Writer 输入仍存在重复视图。
   - `verified_judgment_plan` 已包含 supported claims / outline / constraints；
   - `memo_writer_data_view.verified_summary.judgment_plan` 又带一份压缩 judgment，导致模型读两份近似语义 payload；
   - Q8 Memo Writer 单次消耗 `21618` tokens，已经不是检索问题，而是综合层 payload 设计问题。
3. Verifier 成本与职责不匹配。
   - Q8 Verifier 消耗 `21948` tokens，接近 Memo Writer；
   - Verifier 只应检查 memo 是否越过 verified evidence boundary、是否夹带 unsupported claims、是否请求工具或 raw rows；
   - 让它读取完整 judgment / data_view 会把“安全门”变成昂贵二次审稿，但不会明显提升 memo 深度。

### Q9 假设

- H9: Fundamental length 不是 DeepSeek-pro 理解失败，而是首轮 evidence summary 和 role budget 过宽；把 Fundamental deep research 首轮收紧为 `2-4` ClaimCards，并按 source family 缩短 SEC row summary，可减少 repair 依赖。
- H10: Memo Writer 高 token 主要来自重复 judgment payload；只传 `supported_claims`、`memo_outline`、必要 exclusions / conflicts / source boundary 后，memo 应仍能保持质量并降低输入 tokens。
- H11: Verifier 高 token 主要来自读取完整 verified judgment plan 和 verifier data view；改为 `memo_answer` + evidence ref inventory + unsupported exclusions + compact claim texts，仍能保持安全边界。
- H12: 不应降低 relationship / sector-depth evidence gate；质量提升应来自更好的 row selector 和 compact projection，而不是放松 evidence boundary。

### Q9 执行计划

1. Specialist input / output tightening
   - Fundamental deep research observation budget：`2-4` supported ClaimCards；
   - source-family-aware summary chars：
     - SEC / 8-K rows 默认更短；
     - market / industry / relationship rows保留必要 as_of / pack / rationale；
   - 保留 deep research row count，不全局降 evidence cap，避免牺牲证据覆盖。
2. Memo Writer compact projection
   - 移除 prompt 中重复的 `memo_writer_data_view.verified_summary.judgment_plan`；
   - 只传 compact `verified_judgment_plan`：
     - supported_claims；
     - memo_outline；
     - conflicts / unsupported exclusions；
     - claim_card_stats；
     - memo_constraints / source_boundary_notes。
3. Verifier compact projection
   - 不传完整 verified judgment plan 和 verifier data_view；
   - 只传：
     - final memo；
     - deterministic verification summary；
     - supported claim ids / evidence refs inventory；
     - unsupported claim texts that must not enter memo；
     - compact conflicts and source-boundary notes。
4. Observability
   - 保留 route-level input/output tokens、finish_reasons；
   - summary artifact 保留 claim_card_stats，避免 audit 把“不可见”误判为“0 claims”。
5. 验证顺序
   - 先跑 unit/compile gate；
   - 再跑 AI infra 单 case真实 DeepSeek full-chain；
   - 若 AI infra pass 且 token 不反弹，再扩大 banking / healthcare / energy-utilities。

### Q9 通过门控

- Contract tests 全绿，compileall 通过；
- AI infra 单 case：
  - `gate_status=pass`；
  - SEC real retrieval / BM25 / ObjectBM25 / BGE rerank 仍触发；
  - `runtime_ledger_rows > 0`；
  - expected relationship pack clean；
  - Specialist expected routes valid，real evidence quality pass；
  - `judgment_plan.claim_card_stats` / `verified_judgment_plan.claim_card_stats` 在 summary artifact 可见；
  - Memo Writer / Verifier 不出现 direct tool call；
  - Fundamental 最好首轮 `finish_reason=stop`；如果仍需 repair，必须少于 Q8 token并能解释原因；
  - total token 目标低于 Q8 `98180`，优先观察 Memo Writer / Verifier 是否明显下降。

### Q9 Stop / Pivot 条件

- 如果 token 降低但 claim_card_stats 或 memo_outline 支撑下降，说明 compact projection 过度压缩，需要恢复部分 supported claim fields；
- 如果 Verifier 放过 unsupported claim text，立即回滚 compact verifier projection；
- 如果 Specialist 因 summary 缩短而 real evidence quality fail，优先恢复该 source family summary chars，而不是放松质量 gate；
- 如果 AI infra 通过但其他 sector pack 失败，逐 case 诊断 source availability / relationship pack / metric family，而不是全局调宽 prompt。

### Q9 真实复测结果

AI infra 单 case run id:
`20260531_ai_infra_full_chain_real_retrieval_quality_q9_single_deepseek_v0_1`。

结果：

- hard gate: `pass`；
- tool calls: `8`，低于 Q8 的 `10`；
- SEC real retrieval / BM25 / BGE / runtime ledger 仍通过；
- real Specialist evidence quality: `pass`；
- summary artifact 已可见 claim-card stats：
  - supported ClaimCards: `17`；
  - high materiality: `11`；
  - memo slots: `5/5 supported`；
  - unsupported claims: `12`；
  - conflicts: `5`。

Token 结果：

| Agent | Q8 tokens | Q9 tokens | 变化 |
| --- | ---: | ---: | ---: |
| Fundamental Specialist | 18,201 | 10,301 | 改善，且首轮 `stop` |
| Industry Specialist | 8,797 | 9,265 | 基本持平 |
| Market Specialist | 6,023 | 5,011 | 改善 |
| Risk Specialist | 9,785 | 19,951 | 变差，2 attempts |
| Memo Writer | 21,618 | 34,515 | 变差，3 attempts，首轮 `length` |
| Verifier | 21,948 | 8,983 | 明显改善 |
| Total | 98,180 | 99,870 | 小幅变差 |

结论：

- H9 成立：Fundamental 首轮收敛成功，说明 source-family summary chars 和 ClaimCard 数量收紧有效；
- H11 成立：Verifier compact inventory 有效，安全门仍 pass 且 token 大幅下降；
- H10 只部分成立：Memo Writer 首轮仍 length，且 repair 仍重复读取首轮 payload，导致 token 反弹；
- 新问题 H13：Risk Specialist 不应消费 relationship rows。186 的 risk source family 是 SEC / 8-K / market / industry，relationship evidence 应主要由 Industry Specialist 负责；Q9 中 Risk 引用了 relationship refs，导致输入和输出都变宽。

### Q10 小修计划

1. Memo Writer repair prompt
   - 对 `model_output_truncated` / `json_parse_failed` 使用极简 repair payload，而不是把完整首轮 prompt 再附加一次；
   - repair 输出预算降为：
     - `direct_answer <= 450 chars`；
     - `memo_claims <= 5`；
     - `caveats <= 4`；
     - `unsupported_claims_excluded <= 4`；
   - route_result 增加 failure / token diagnostics，便于下一轮解释为什么重试。
2. Memo Writer 首轮输出预算
   - 首轮 `direct_answer <= 650 chars`；
   - `memo_claims <= 6`；
   - 不要求展开每个 source row，只需要把 supported ClaimCards 转成投资主线、反证和边界。
3. Risk Specialist data view
   - risk bounded rows 不再注入 relationship_graph rows；
   - relationship evidence 仍保留给 Industry Specialist 和 judgment plan；
   - gate 不放松：Risk 仍必须引用 known SEC / market / industry evidence refs。

Q10 复测目标：

- AI infra hard gate 仍 pass；
- Fundamental 不回退到 length；
- Risk 回到 1 attempt 或 token 显著低于 Q9；
- Memo Writer 不超过 2 attempts，最好首轮 stop；
- Total tokens 低于 Q8 `98,180`，否则继续专门调 Memo Writer。

### Q10 实现与 AI Infra 真实复测结果

本轮按 Q10 计划完成三类修复：

- Memo Writer repair prompt 改为 compact-only payload：
  - truncation / parse / deterministic failure 不再重复读取完整首轮 prompt；
  - repair 输出预算压到 `direct_answer <= 450 chars`、`memo_claims <= 5`、`caveats <= 4`；
  - route result 增加 attempts / repair attempts / token / finish reason diagnostics。
- Memo Writer 首轮 prompt 改为更直接的 memo-ready contract：
  - `direct_answer <= 650 chars`；
  - `memo_claims <= 6`；
  - 不再要求逐 row 摘要。
- Risk Specialist data view 对齐 186 权限矩阵：
  - Risk 不再消费 `relationship_graph` rows；
  - relationship evidence 仍由 Industry Specialist 和 judgment plan 使用；
  - Risk 继续使用 SEC / 8-K / market / industry evidence。

验证：

```text
python -m pytest tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_real_llm_chain_eval.py -q
result: 39 passed

python -m compileall src\sec_agent\memo_llm.py src\sec_agent\specialist_llm.py src\sec_agent\multi_agent_runtime.py
result: pass

python -m pytest tests/test_sec_agent_ledger_store.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_contracts.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_langgraph_routing.py -q
result: 93 passed
```

AI infra 单 case run id:
`20260531_ai_infra_full_chain_real_retrieval_quality_q10_single_deepseek_v0_1`。

结果：

- hard gate: `pass`；
- tool calls: `9`；
- total tokens: `68,176`，低于 Q8 `98,180` 和 Q9 `99,870`；
- SEC search / BM25 / ObjectBM25 / BGE rerank / runtime ledger 均真实触发；
- relationship pack gate 通过，Industry 只引用 `technology_ai_infrastructure_depth`；
- Risk 不再看到或引用 relationship refs；
- Memo Writer 1 call、`finish_reason=stop`、`10,505` tokens；
- Verifier 1 call、`finish_reason=stop`、`9,494` tokens；
- claim-card stats 可见：
  - supported ClaimCards: `17`；
  - high materiality: `10`；
  - memo slots: `5/5 supported`；
  - unsupported claims: `12`；
  - conflicts: `5`。

Q10 结论：

- H10 修正后成立：Memo repair 不再重复读完整 payload 后，Memo Writer 从 Q9 的 `34,515` tokens 降到 `10,505`；
- H13 成立：Risk source family 边界收紧后，Risk 从 Q9 的 `19,951` tokens 降到 `10,441`，且不再误引用 relationship evidence；
- 安全 gate 未放松，token 下降来自 payload projection 和 role data-view 边界，而不是砍掉真实 evidence retrieval。

### Q11-Q13 Sector-depth 真实扩展复测

在 Q10 AI infra 通过后，继续跑 banking、healthcare、energy/utilities 三个真实 sector-depth case，用同一套 full-chain gate 检查从主 agent 到 Memo / Verifier 的链路稳定性。

| Case | Run id | Gate | Tool calls | Total tokens | Memo tokens | Verifier tokens | ClaimCards | Memo slots | 关键 flags |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| AI infra | `20260531_ai_infra_full_chain_real_retrieval_quality_q10_single_deepseek_v0_1` | pass | 9 | 68,176 | 10,505 | 9,494 | supported 17 / unsupported 12 / conflicts 5 | 5/5 | `high_total_token_cost`, `many_unsupported_specialist_claims`, `deep_research_all_specialists_active` |
| Banking | `20260531_banking_full_chain_real_retrieval_quality_q11_single_deepseek_v0_1` | pass | 10 | 66,555 | 9,124 | 7,214 | supported 17 / unsupported 12 / conflicts 4 | 4/5 | `high_total_token_cost`, `many_unsupported_specialist_claims`, `memo_surface_says_evidence_thin`, `deep_research_all_specialists_active` |
| Healthcare | `20260531_healthcare_full_chain_real_retrieval_quality_q12_single_deepseek_v0_1` | pass | 8 | 73,842 | 9,735 | 8,257 | supported 18 / unsupported 12 / conflicts 3 | 5/5 | `high_total_token_cost`, `many_unsupported_specialist_claims`, `deep_research_all_specialists_active` |
| Energy / utilities | `20260531_energy_utilities_full_chain_real_retrieval_quality_q13_single_deepseek_v0_1` | pass | 9 | 65,170 | 10,512 | 8,897 | supported 18 / unsupported 12 / conflicts 3 | 4/5 | `high_total_token_cost`, `source_gaps_without_second_pass`, `many_unsupported_specialist_claims`, `deep_research_all_specialists_active` |

Agent 层观察：

- Research Lead：
  - 能正确识别 `deep_research` 并激活必须专家；
  - 但 sector-depth case 仍倾向全量激活 4 个 specialists，成本偏高；
  - 当前更像“保守全覆盖”，不是“按任务优先级精细激活”。
- Universe / Relationship：
  - pack 语义 gate 有效；
  - AI infra / banking / healthcare / energy/utilities 均能把 expected relationship pack 传给下游；
  - 当前 relationship graph 更适合作为 sector-depth hypothesis / scope evidence，不应夸大为商业关系事实数据库。
- Evidence Operators：
  - full-chain 已确认触发真实 SEC retrieval、BM25、ObjectBM25、BGE rerank 和 runtime ledger；
  - Q10-Q13 都不是 dry-run；
  - BGE metadata 显示 CUDA 可用并有正向 rerank candidates。
- Specialists：
  - Fundamental / Industry / Market / Risk 都能理解上游任务和 bounded evidence boundary；
  - Industry 改善最大，能看到并引用 relationship evidence，且 pack 引用语义更干净；
  - Risk 在 Q10 后不再消费 relationship rows；
  - Healthcare Risk 仍出现 2 attempts / `20,604` tokens，问题更像 risk schema 输出过宽，而不是理解不了上游指令；
  - unsupported claims 每 case 仍稳定在 `12` 左右，说明 specialist 会主动列缺证，但缺证条目过多，会挤压 memo-ready 信号。
- Judgment Aggregator：
  - 能阻断 unsupported 内容，并把 supported / conflict / unsupported 组织成 verified plan；
  - 但它过于安全，最终给 Memo Writer 的更像“可验证计划 + 缺口列表”，不是高密度投资论证骨架。
- Memo Writer：
  - Q10 后成本明显改善，4 case 都能 1 call stop；
  - 输出仍偏保守，常以 `Bounded answer only` 开头；
  - banking 和 energy/utilities 缺 `thesis` slot，Memo Writer 因缺少可支持的核心 thesis ClaimCard 而保持 caveated 表述。
- Verifier：
  - 能有效守住 source boundary / unsupported claim boundary；
  - compact inventory 后 token 明显下降；
  - 但 Verifier 只负责挡错，不负责提升 memo 深度。

最终 memo 质量判断：

- 当前链路已经达到“真实 full-chain、可审计、安全边界稳定”的阶段；
- 还没有达到“高密度投研 memo”的阶段；
- 主要瓶颈不是 DeepSeek-pro 理解不了上游任务，也不是门控单独太严，而是：
  1. Specialist 产生太多 unsupported / gap-like claims，memo-ready supported ClaimCards 信噪比不够高；
  2. Aggregator 缺少 thesis synthesis 能力，无法把多个 supported ClaimCards 合成一个 evidence-backed investment thesis；
  3. Research Lead 对 sector-depth 的专家激活仍偏全量，token 花在广覆盖上，而不是花在更强的二次验证或 thesis sharpening 上；
  4. source gap second-pass 触发还不够精确，energy/utilities 出现 `source_gaps_without_second_pass`；
  5. Risk schema 在 healthcare case 下仍偏宽，导致 repair / token 放大。

### Q14 下一轮假设与执行顺序

下一轮不应继续盲目扩大 batch，而应逐 case 做质量提升：

1. Thesis synthesizer / Aggregator v0.3
   - 当 fundamentals / industry / market / risk slots 足够，但 `thesis` slot missing 时，Aggregator 允许合成一个 thesis ClaimCard；
   - 该 thesis 不得引入新事实，只能引用已有 supported ClaimCards；
   - 门控：sector-depth case 至少 `thesis` slot supported 或明确说明为什么无法形成 thesis。
2. Specialist skill v0.3 unsupported cap
   - 每个 specialist 最多输出 top 2-3 个业务重要缺证项；
   - 避免把每个缺失指标都变成 unsupported claim；
   - 门控：unsupported claims 总量下降，但 Verifier 不放过 unsupported memo text。
3. Risk compact schema
   - Risk 首轮限制为 2-3 supported risk ClaimCards、<=2 unsupported、<=2 conflicts；
   - Healthcare case 作为回归样例，目标是 1 attempt stop 且 token 接近 Q10 AI infra risk 水位。
4. Research Lead activation priority
   - 保留 sector-depth all-specialist 诊断能力；
   - 为 standard / focused / narrow case 加 strict activation gate；
   - sector-depth 也记录 priority，不再把所有 specialist 视为同等重要。
5. Source-gap second-pass trigger
   - 针对 energy/utilities 的 `source_gaps_without_second_pass` 查明触发条件；
   - 只在缺口可由现有 operator 补足时二次检索，避免无效 token。

### 本轮安全备注

- 本轮真实 DeepSeek 调用只通过运行时环境变量使用凭证；
- durable docs / model-run report 不保存明文凭证，也不保存 raw LLM response；
- Q10-Q13 run artifact 中 `memo_writer.route_result.finish_reasons` 一度为空，是聚合可观测性 bug；代码已修复 `_aggregate_model_calls`，未来 run 会在 route result 中保留 finish reasons。本轮 diagnostics 中已有正确 `finish_reason=stop`。

## Q14 Contract Implementation: Thesis Synthesis, Unsupported Cap, Risk Compact Schema

### 本轮目标

基于 Q10-Q13 的真实结果，优先修链路中 token 花费与 memo 质量转化之间的结构性问题，而不是放松 source boundary：

- banking / energy-utilities 出现 `thesis` slot missing，导致 Memo Writer 保守输出；
- 每个 sector-depth case 仍有约 `12` 条 unsupported specialist claims，缺口噪声压过 memo-ready signals；
- healthcare Risk Specialist 仍出现 2 attempts / 高 token，说明 risk 输出结构偏宽；
- `deep_research_all_specialists_active` 不能区分“全量激活但有优先级”和“无差别全量激活”；
- `source_gaps_without_second_pass` 需要区分可检索缺口和不可执行/不可得缺口。

### 实现内容

1. Aggregator thesis synthesis v0.3
   - `aggregate_specialist_judgment_plan()` 在没有 supported `thesis` slot、但至少两个业务 slot 有 supported ClaimCards 时，合成一条 `investment_thesis_synthesis` ClaimCard；
   - 合成 thesis 只拼接/引用已有 supported ClaimCards：
     - `derived_from_claim_ids` 记录来源；
     - `synthesis_policy=no_new_facts_combine_existing_supported_claim_cards_only`；
     - evidence refs / source families 来自已有 ClaimCards；
   - `memo_outline["thesis"]` 现在可被该合成 ClaimCard 支撑；
   - Verifier 允许 `investment_thesis_synthesis` 引用 `relationship_graph`，但仍保持 relationship graph 只能作为 hypothesis / context，不能作为 company-reported financial fact。

2. Unsupported claim cap
   - Aggregator 对 memo-facing unsupported claims 做 per-agent cap：
     - `UNSUPPORTED_CLAIM_CAP_PER_AGENT=2`；
     - 多余项不展开给 Memo Writer；
     - `unsupported_claim_policy` 和 `memo_constraints.unsupported_claim_overflow_count` 记录 overflow；
     - caveat 增加 `additional_unsupported_claims_summarized_not_expanded`。
   - 目的不是删除安全信息，而是防止 Specialist 把每个缺指标都变成 memo 写作 payload。

3. Risk compact schema v0.3
   - Specialist prompt 新增显式 `output_contract`；
   - Risk Specialist 在 standard/deep 下限制为：
     - `2-3` supported risk ClaimCards；
     - `unsupported_claim_cap=2`；
     - `conflict_cap=2`；
   - Risk skill 文档同步收紧：只列 top material gaps / conflicts，不生成泛化风险清单。

4. Research Lead activation priority
   - `AgentActivationPlan` 增加 `agent_priorities`；
   - deterministic router 为 active agents 写入 `primary / supporting / conditional`；
   - sector-depth 下：
     - Fundamental / Industry / Universe / core operators 为 primary；
     - Market / Risk / 8-K / market operator 为 supporting；
   - Research Lead LLM schema prompt 要求输出 active agents 的 priority；
   - 当 LLM standard plan 被 relationship/sector-depth source 升级为 deep_research 时，会覆盖成 sector-depth priority。

5. Audit / second-pass precision
   - `multi_agent_summary.json` 增加 `agent_priorities`，judgment summary 增加 `thesis_synthesis` 和 `unsupported_claim_policy`；
   - output-quality audit 如果看到 4 specialists 全激活但 priority 有区分，不再打 `deep_research_all_specialists_active`；
   - `source_gaps_without_second_pass` 只有在 sidecar 说明存在可执行 quality gaps 时才打；
   - quality reflection 跳过没有 executable routes 的 source gaps，避免为不可检索缺口触发无效 second-pass。

### 验证结果

```text
python -m pytest tests/test_multi_agent_contracts.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_activation_plan.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_output_quality_audit.py -q
result: 77 passed

python -m pytest tests/test_sec_agent_ledger_store.py tests/test_relationship_graph_lookup.py tests/test_multi_agent_evidence_requirements.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_real_llm_chain_eval.py tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_contracts.py tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_output_quality_audit.py tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_activation_plan.py tests/test_multi_agent_routing_fixtures.py tests/test_multi_agent_research_lead_llm.py -q
result: 129 passed

$files = Get-ChildItem -Path tests -Filter 'test_multi_agent*.py' | ForEach-Object { $_.FullName }; python -m pytest @files -q
result: 165 passed

python -m pytest tests/test_research_skills.py tests/test_multi_agent_agent_registry.py tests/test_sec_agent_mcp_contracts.py -q
result: 15 passed

python -m compileall src\sec_agent scripts tests
result: pass
```

### 真实 DeepSeek 回归历史状态

注：本小节记录 Q14 合同实现后的当时状态。2026-06-01 已在下方 `Q14 Real Regression: Memo v0.3 And Specialist Salvage` 小节补跑真实 DeepSeek 回归，本小节不再代表最新执行状态。

当时没有启动真实 DeepSeek Q14 回归，因为当前 shell 环境未设置 `DEEPSEEK_API_KEY`。为避免把聊天里的明文凭证写入 shell 命令、文档或历史记录，本轮只完成代码合同和确定性门控。

下一轮真实回归建议：

1. 先跑 banking 单 case：
   - 目标：`thesis_synthesis.status=synthesized`，`thesis` slot supported；
   - unsupported claims 低于 Q11 的 `12`；
   - Memo Writer 仍 1 call stop；
   - final memo 不再以纯 evidence-thin 表达为主。
2. 再跑 healthcare 单 case：
   - 目标：Risk Specialist 1 attempt stop；
   - Risk tokens 明显低于 Q12 的 `20,604`；
   - unsupported/conflict 数量下降但 Verifier 不放松。
3. 最后跑 energy/utilities 单 case：
   - 目标：source gaps 没有误打 `source_gaps_without_second_pass`；
   - 若存在 executable gap，应触发 quality second-pass；
   - `thesis` slot supported 或给出明确不可合成原因。

### Q14 预期影响

- Memo Writer 输入更像投资论证骨架，而不是“证据摘要 + 缺口清单”；
- token 继续下降不一定显著，但 token 应更集中花在 supported thesis / memo-ready claims；
- gate 仍保持 source-boundary 安全，不用牺牲证据约束换输出质量。

## Q14 Real Regression: Memo v0.3 And Specialist Salvage

### 触发问题

2026-06-01 按 Q14 合同启动真实 DeepSeek sector-depth 回归后，banking 首轮 hard gate 通过，但 Memo Writer 出现 `fallback / 3 attempts / 26,822 tokens`，且两次 `finish_reason=length`。这说明 Q14 Aggregator thesis synthesis 和 unsupported cap 已生效，但 Memo Writer 仍看到过宽的 compact judgment payload。

另外，healthcare + energy/utilities 双 case 回归中，energy/utilities 失败在 Risk Specialist：一个 supported observation 缺少 `evidence_refs`，三次 LLM 输出后仍未修好。检索、BGE、relationship、Industry relationship gate 均正常。

### 代码修复

1. Memo Writer v0.3 slot-balanced projection
   - `src/sec_agent/memo_llm.py` 只向 Memo Writer 提供：
     - thesis ClaimCard；
     - 每个 supported memo slot 的最强 ClaimCard；
     - 最多 `5` 条 supported ClaimCards；
     - 最多 `2` 条 unsupported；
     - 最多 `2` 条 conflicts；
   - prompt 明确要求：
     - 不输出 `supported_claims`；
     - 只输出 `memo_claims`；
     - 每条 memo claim 复制输入里的 `claim_id` 和 `evidence_refs`；
     - direct answer / caveats / source notes 继续收紧。

2. Specialist no-ref supported-claim safe salvage
   - `src/sec_agent/specialist_llm.py` 在 validation 失败仅由 `supported_claim_without_evidence_refs` 或 `unknown_evidence_ref` 造成时，允许安全降级；
   - 仅当至少还有一条合法 supported observation 时，才把缺 refs / unknown refs 的 observation 从 supported 移到 `unsupported_claims`；
   - 不会让无证据 supported claim 进入 Judgment Plan；
   - 如果所有 supported observations 都无有效 refs，仍 fail-closed。

3. 测试补充
   - `tests/test_multi_agent_memo_llm_repair.py`
     - 新增 Memo Writer v0.3 slot-balanced cap 测试；
     - 更新 repair prompt cap 断言。
   - `tests/test_multi_agent_specialist_llm.py`
     - 新增单条 no-ref observation salvage 测试；
     - 保留“全部 supported 都无 refs 时 fail-closed”的原有门控。

### 验证

```text
python -m pytest tests/test_multi_agent_specialist_llm.py tests/test_multi_agent_memo_llm_repair.py tests/test_multi_agent_contracts.py tests/test_multi_agent_output_quality_audit.py -q
result: 50 passed

python -m compileall src\sec_agent\specialist_llm.py src\sec_agent\memo_llm.py tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_memo_llm_repair.py
result: pass
```

### 真实 DeepSeek Q14 回归结果

Model run ledger:

- `reports/model_runs/20260601_multi_agent_output_quality_q14_memo_v0_3_deepseek_v0_1.md`

| Case | Run id | Gate | Tool calls | Total tokens | Memo tokens | Verifier tokens | ClaimCards | Memo slots | 关键 flags |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| Banking | `20260601_banking_full_chain_real_retrieval_quality_q14_memo_v0_3_single_deepseek_v0_1` | pass | 10 | 69,190 | 6,607 | 7,050 | supported 13 / unsupported 8 / synth thesis 1 | 5/5 | `high_total_token_cost`, `many_unsupported_specialist_claims`, `memo_surface_says_evidence_thin` |
| Healthcare | `20260601_healthcare_full_chain_real_retrieval_quality_q14_memo_v0_3_specialist_salvage_single_deepseek_v0_1` | pass | 9 | 59,979 | 6,468 | 7,519 | supported 17 / unsupported 8 / synth thesis 0 | 5/5 | `many_unsupported_specialist_claims`, `memo_surface_says_evidence_thin` |
| Energy / utilities | `20260601_energy_utilities_full_chain_real_retrieval_quality_q14_memo_v0_3_specialist_salvage_single_deepseek_v0_1` | pass | 11 | 65,992 | 6,822 | 7,024 | supported 14 / unsupported 8 / synth thesis 0 | 5/5 | `high_total_token_cost`, `many_unsupported_specialist_claims`, `memo_surface_says_evidence_thin` |

Runtime evidence:

| Case | SEC calls | SEC rows | Runtime ledger rows | BGE CUDA | BGE candidates |
| --- | ---: | ---: | ---: | --- | ---: |
| Banking | 5 | 72 | 0 | true | 72 |
| Healthcare | 4 | 52 | 10 | true | 52 |
| Energy / utilities | 5 | 72 | 5 | true | 72 |

Agent 层结论：

- Research Lead：3 case 均为 `deep_research`，activation validation pass；有 `agent_priorities`，旧的 `deep_research_all_specialists_active` 不再误报。
- Universe / Relationship：3 case lookup / validation 均 pass；Industry Specialist 均引用 expected relationship pack。
- Evidence Operators：真实 `sec_search_filings`、BM25/ObjectBM25、BGE rerank、market/industry/relationship tools 均被激活；BGE metadata 显示 `cuda_available=true`。
- Specialists：
  - healthcare Risk 从 Q12 的高 token / repair 问题降到 `1 attempt / 9,930 tokens`；
  - energy Risk no-ref supported claim 被安全降级后，最终 case pass；
  - Industry 在 banking/healthcare/energy 都正确引用 relationship evidence。
- Judgment Aggregator：
  - banking 成功合成 thesis；
  - 3 case memo slots 均 `5/5`；
  - unsupported claims 从 Q11-Q13 的 `12` 降到 `8`。
- Memo Writer：
  - 3 case 均 `pass / 1 attempt`；
  - memo tokens 稳定在 `6.4K-6.8K`；
  - banking 中间失败的 `26.8K` fallback 问题已修复。
- Verifier：
  - 3 case 均 pass；
  - token 低于 Q11-Q13 水位；
  - 继续作为安全门，不负责增加 memo 深度。

### 当前质量判断

Q14 之后链路比 Q10-Q13 更稳：

- route / tool / Specialist quality / Memo / Verifier 全链路通过；
- token 更有效，Memo Writer 不再反复 length repair；
- thesis slot 和 memo slots 问题基本修好；
- source-gap false flag 已消失；
- Specialist no-ref supported claim 不再污染 Judgment Plan。

但还没有达到高质量投研 memo：

- memo 仍常以 `Bounded answer only` 开头；
- `memo_surface_says_evidence_thin` 仍在 3 case 出现；
- unsupported claims 仍有 `8` 条/case，说明 Specialists 仍偏“列缺口”；
- banking `runtime_ledger_rows=0`，导致银行指标型论证仍缺硬数值支撑；
- banking / energy 总 token 仍高于理想水位。

### 下一步建议

1. 先修 banking runtime ledger row 生成 / exact metric extraction，而不是继续调 prompt。
2. 把 Memo Writer 从 bounded-summary 输出升级为 thesis-led memo shape：
   - 只要 `memo_slots=5/5` 且 evidence refs 足够，应减少 `Bounded answer only` 表面语；
   - caveat 应进入 limitations，不应压过 thesis。
3. Specialist v0.4 应从“缺口提示”转为“claim-card ranker”：
   - unsupported cap 可继续从 `2/agent` 降到 case-level top material gaps；
   - 对非核心 supporting agent 的 unsupported 输出再降权。
4. 针对 total token：
   - Industry Specialist 仍有 2-attempt case；
   - Lead/Universe token 可压缩；
   - Verifier inventory 还可进一步裁剪。
