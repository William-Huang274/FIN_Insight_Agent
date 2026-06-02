# Fin Agent 分层质量门控执行文档 v0.1

日期：2026-06-01

关联框架：`docs/eval/fin_agent_investment_research_quality_framework_v0_1.md`

机器可读配置：`configs/fin_agent_quality_rubric_v0_1.json`

辅助审计脚本：`scripts/audit_fin_agent_layer_quality.py`

S1-S8 v0.2 case matrix：`docs/eval/fin_agent_s1_s8_agent_quality_case_matrix_v0_2.md`

## 1. 执行原则

本阶段不再直接从 full chain 看最终 memo 好不好，而是按 LangGraph 控制边界逐层验收。

原则：

1. 每一层只消费上一层已经通过 gate 的 artifact。
2. 某层失败时，冻结并复用已通过的上游产物，只修当前层。
3. 每个 agent 既看 route / schema 是否通过，也看真实 evidence / output quality 是否通过。
4. Full chain 只在 S1-S9 单层门控通过后运行。
5. 多轮测试放在 full chain 之后，专门测试 scope revision、artifact reuse 和上下文边界。

## 2. Artifact 固化规则

每个阶段输出必须写入 run 目录，后续阶段通过路径读取：

| Artifact | 用途 |
| --- | --- |
| `activation_diagnostic.json` | Research Lead S1 gate |
| `relationship_plan.json` 或 `multi_agent_summary.json` 中的 relationship section | Universe / Relationship S2 gate |
| `tool_call_ledger` / `tool_observations` | Evidence Operator S3 gate |
| `quality_second_pass_report` / `evidence_sufficiency_report` | Coverage / Reflection S4 gate |
| `specialist_route_results` / `specialist_outputs` | Specialist S5 gate |
| `judgment_plan` / `verified_judgment_plan` / `memo_thesis_pack` | Aggregator S6 gate |
| `memo_answer` / `memo_route_result` | Memo Writer S7 gate |
| `claim_verification` / `verifier_projection` | Verifier S8 gate |
| `rendered_answer` | Renderer S9 gate |
| `real_chain_eval_summary.json` | Full-chain S10 gate |

如果某一层重跑，run id 必须体现阶段、case、目的和版本，不能覆盖上一次结果。

## 3. 阶段 S1：Research Lead

目标：验证主 agent 能理解 query、选择正确 execution mode、agent activation、source family 和业务 evidence needs。

输入：

- 用户 query。
- focus/search-scope ticker。
- source inventory。
- 上轮 session summary（多轮 case）。

执行：

```powershell
$env:DEEPSEEK_API_KEY='<use shell env only>'
python scripts\eval_multi_agent_research_lead_activation.py `
  --run-id 20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1 `
  --require-evidence-requirements `
  --strict
```

通过门控：

- `gate_status=pass`。
- 每个 case `mode_match=true`。
- required agents 全部激活。
- forbidden agents 全部未激活。
- `evidence_requirement_validation_pass=true`。
- scope 没有无授权扩大。
- 支持 deep_research 时要区分 primary / supporting / conditional agent，不再粗暴全量同优先级。

失败处理：

- 不进入 Universe / Relationship。
- 复用失败 case 的 request，调 Research Lead prompt / schema / validator。

## 4. 阶段 S2：Universe / Relationship

目标：验证关系图不是“公司列表扩展器”，而是形成经济关系、证据边界和缺证项。

输入：

- S1 通过的 activation plan。
- relationship graph lookup rows。
- sector-depth pack metadata。

执行：

```powershell
$env:DEEPSEEK_API_KEY='<use shell env only>'
python scripts\eval_multi_agent_universe_relationship_gate.py `
  --activation-summary eval\sec_cases\outputs\multi_agent_activation_diagnostic\<s1_run_id>\activation_diagnostic.json `
  --run-id 20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2 `
  --input-max-relationships 48 `
  --max-relationships 48 `
  --max-expanded-tickers 32 `
  --max-tokens 4200 `
  --strict
```

审计：

```powershell
python scripts\audit_fin_agent_layer_quality.py `
  --summary eval\sec_cases\outputs\multi_agent_universe_relationship_diagnostic\<s2_run_id>\universe_relationship_diagnostic.json `
  --strict
```

通过门控：

- relationship lookup 被合理触发。
- included / excluded tickers 有 rationale。
- 每条 relationship 有 `relationship_type`、`direction`、`financial_link_type`、`confidence`、`evidence_refs`。
- 没有 direct edge 时，明确 `no_confirmed_direct_edge` 与 `possible_indirect_economic_link` 的区别。
- relationship evidence 只支持 scope / hypothesis，不支持财务事实。
- Relationship lookup 的 source inventory 必须包含 bounded lookup 返回的 related tickers，不能因为 S1 初始 search scope 较窄而把已召回关系行过滤成空输入。
- Pack relevance gate 必须防止 `capex` 这类通用词把 AI infrastructure case 误扩到 energy pack；跨 sector 只在用户显式提到 AI/data-center power/load/electricity 传导时放行。
- `economic_link_map` 必须存在，并至少包含 bounded entities、economic links、transmission mechanisms、investment implications。
- `economic_link_map` 的 `claim_scope` 必须维持为 `economic_mechanism_hypothesis_only` / relationship-hypothesis 边界，不得写成确认商业供应链事实。
- relationship plan 必须覆盖 bounded lookup rows；如果模型只输出经济图谱，runtime 必须用 deterministic completion 补回 lookup relationships。
- `sector_inferred` / `category_inferred` 关系必须标记为 `no_confirmed_direct_edge`，并保留 direct customer/supplier、contract/order、revenue exposure 等 missing confirmations。

当前接受结果：

| Run ID | Gate | Case | Key metrics |
| --- | --- | --- | --- |
| `20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2` | pass | `ma_ai_capex_supply_chain_deep` | lookup relationships `42`，plan relationships `42`，deterministic completed `42`，economic links `4`，mechanisms `2`，investment implications `2`，tokens `36,646`，artifact audit `pass` |

失败处理：

- 复用 S1 artifact 和 relationship lookup rows。
- 只修 Universe prompt / schema / validator / relationship pack selector。

## 5. 阶段 S3：Evidence Operators / RAG

目标：验证工具实际执行、召回/重排/ledger 能给下游可用 rows，而不只是 route 成功。

输入：

- S1/S2 通过 artifact。
- compiled EvidenceRequirementPlan。
- MCP tool registry。

执行：

```powershell
python scripts\eval_multi_agent_evidence_operator_gate.py `
  --run-id 20260601_fin_agent_s3_evidence_operator_gate_v0_4 `
  --strict
```

审计：

```powershell
python scripts\audit_fin_agent_layer_quality.py `
  --summary eval\sec_cases\outputs\multi_agent_evidence_operator_diagnostic\20260601_fin_agent_s3_evidence_operator_gate_v0_4\evidence_operator_diagnostic.json `
  --strict
```

通过门控：

- expected operator agents 被调用。
- expected tool names 被调用。
- `sec_search_filings` 实际触发 BM25 / ObjectBM25 / BGE rerank。
- BGE 在配置为 `auto` 且 CUDA 可用时走 CUDA。
- exact-value metric case 有 runtime ledger rows。
- sector-depth case 有 context rows、relationship rows、industry/market rows。
- tool_call_ledger 无重复调用、预算超限、权限越界。
- row selector 记录 row counts、source families、rerank candidates、ledger rows。

当前接受结果：

| Run ID | Gate | Cases | Key metrics |
| --- | --- | --- | --- |
| `20260601_fin_agent_s3_evidence_operator_gate_v0_4` | pass | `4/4` | tool calls `14`，context rows `300`，runtime ledger rows `349`，market rows `7`，industry rows `10`，SEC pre-rerank candidates `360`，BGE candidates `300`，CUDA auto gate `4/4`，artifact audit `pass` |

S3 默认覆盖集：

| Case | Mode | Rows |
| --- | --- | --- |
| `ma_msft_capex_lookup` | deterministic lookup | ledger `37` |
| `ma_amzn_margin_focused` | focused answer | SEC context `20`，ledger `6`，BGE `cuda` |
| `ma_nvda_amd_market_standard` | standard memo | SEC context `40`，ledger `136`，market `2`，BGE `cuda` |
| `ma_ai_capex_supply_chain_deep` | deep research | SEC context `240`，ledger `170`，market `5`，industry `10`，relationship lookup `24`，relationship plan `4`，BGE `cuda` |

失败处理：

- 复用 S1/S2 artifact。
- 不运行 Specialist。
- 先查 retrieval policy、chunk 切片、manifest/source inventory、ledger selection、reranker device。

## 6. 阶段 S4：Coverage / Reflection

目标：验证系统能判断证据缺口，并在可查时触发有增益的 second pass。

输入：

- S3 通过的 tool observations / ledger / context rows。
- EvidenceRequirementPlan。

执行：

```powershell
python scripts\eval_multi_agent_coverage_reflection_gate.py `
  --relationship-summary eval\sec_cases\outputs\multi_agent_universe_relationship_diagnostic\20260601_fin_agent_s2_relationship_inference_coverage_gate_deepseek_v0_2\universe_relationship_diagnostic.json `
  --evidence-summary eval\sec_cases\outputs\multi_agent_evidence_operator_diagnostic\20260601_fin_agent_s3_after_s2_relationship_inference_v0_2\evidence_operator_diagnostic.json `
  --run-id 20260601_fin_agent_s4_coverage_reflection_gate_after_s3_v0_1 `
  --strict
```

审计：

```powershell
python scripts\audit_fin_agent_layer_quality.py `
  --summary eval\sec_cases\outputs\multi_agent_coverage_reflection_diagnostic\20260601_fin_agent_s4_coverage_reflection_gate_after_s3_v0_1\coverage_reflection_diagnostic.json `
  --strict
```

通过门控：

- source gap 分为 searchable / unsearchable / product-boundary。
- searchable gap 能产生 second-pass request。
- second pass 之后 rows / ledger / coverage 至少一项有增益。
- 无增益或重复调用时中止，并给 bounded answer boundary。
- 不把缺证都压成最终 memo 的“证据很薄”。

当前接受结果：

| Run ID | Gate | Cases | Key metrics |
| --- | --- | --- | --- |
| `20260601_fin_agent_s4_coverage_reflection_gate_after_s3_v0_1` | pass | `4/4` | second-pass allowed `3`，ran `3`，added rows `0`，missing requirements `3`，audit score `2.844` |
| `20260601_fin_agent_s4_after_8k_second_pass_routefix_v0_1` | pass | `4/4` | missing requirements `0`，second-pass allowed `0`，S3 rows available `4/4`，说明 8-K 缺口已由 S3 routefix 上游解决 |

解释：

- S4 已能识别无缺口 case、searchable gap 和二次检索无增益 case。
- 这轮三个 second-pass 都是 `8k_commentary:no_rows`，并以 `no_incremental_evidence` bounded 中止；这说明 loop control 有效，但还没证明 second pass 能提升 evidence quality。
- 后续 routefix 运行显示该 8-K 缺口不是 S4 必须 retry 的真实缺口，而是 S3 route/source-scope 编译问题；`20260601_fin_agent_s4_after_8k_second_pass_routefix_v0_1` 已作为当前 S4 artifact。

失败处理：

- 复用 S3 rows。
- 只修 reflection gap classifier / second-pass compiler。

## 7. 阶段 S5：Specialists

目标：验证每个专家能消费 bounded rows 和上游任务，输出 memo-ready ClaimCards，而不是行摘要。

输入：

- S3/S4 通过的 bounded evidence rows。
- relationship_summary。
- task cards / agent priority。

通过门控：

- 每个 required specialist route `status=pass`。
- 每个 supported ClaimCard 至少有一个 known evidence_ref。
- ClaimCard 必须有 `claim`、`so_what`、`evidence_refs`、`confidence`、`investment_use`。
- Fundamental 不用 market/industry 替代公司披露。
- Market 保留 snapshot/as_of_date。
- Risk 输出风险严重度，不污染 supported claims。
- Industry 在 sector-depth / relationship case 下必须看到并引用 relationship evidence。
- supporting specialists 产出 1-3 个高价值 claims，不消耗 primary 等量预算。
- 比较型 fundamental / risk case 下，每个 focus ticker 必须有可见 primary filing rows，或有 ticker-level source gap；不能只因总体存在 primary rows 就通过。
- Specialist route artifact 必须持久化 prompt row distribution：`by_ticker`、`by_source_family`、`by_ticker_source_family`、`by_form_type`、`by_metric`。
- 如果上游 S3 记录 `ledger_missing_despite_context`，Specialist 必须把它当 exact-value coverage gap，而不是说 filing evidence 完全不存在。

失败处理：

- 复用 S3/S4 rows。
- 针对失败 agent 单独重跑，不重跑 Research Lead / retrieval。

当前接受结果：

| Run ID | Gate | Cases | Key metrics |
| --- | --- | --- | --- |
| `20260601_fin_agent_s5_specialist_layer_gate_after_s4_v0_1` | pass | `2/2` | specialist routes `7`，real-evidence quality `2/2`，repair `0`，tokens `65,251`，AI capex Industry Specialist cited relationship refs `14` |

## 8. 阶段 S6：Judgment Aggregator

目标：验证 Aggregator 能把专家 ClaimCards 组织成投资判断计划，而不是安全地压扁为证据清单。

输入：

- S5 通过 Specialist outputs。
- source-boundary constraints。
- coverage / gap summary。

通过门控：

- 生成 `memo_thesis_pack` 或后续 `InvestmentThesisPlan`。
- 包含 stance、core thesis、key debate、entity ranking、risk hierarchy、watch items。
- 不引入新事实。
- 不让 unsupported claims 进入 memo slots。
- 不把 blocking caveat 和 watch item 混为一类。

失败处理：

- 复用 S5 outputs。
- 修 Aggregator schema / ranker / claim selection。

## 9. 阶段 S7：Memo Writer

目标：验证 Memo Writer 能写出自然语言投研 memo，而不是 schema 填空或证据摘要。

输入：

- S6 通过的 thesis plan / memo thesis pack。
- 精选 ClaimCards。
- allowed evidence refs。
- source-boundary notes。

通过门控：

- `memo_route_result.status=pass`。
- 第一次输出尽量收敛，repair attempt 不超过 1。
- memo profile 必须与 case 深度和证据密度匹配：`compact | standard | expanded | deep_research`。
- `standard / expanded / deep_research` 必须输出自然语言投研段落，而不是 internal ClaimCard label、schema recap、row summary 或 pipe-joined claims。
- `expanded / deep_research` 必须有非空的 `investment_implications`、`what_would_change_view`、`monitoring_items`；有 source gaps 时应填 `evidence_gaps_but_actionable`。
- memo 先给 thesis-led stance，再解释机制、证据、反证和观察项。
- 不新增 facts、tickers、refs。
- 不把 indirect / hypothesis 写成 confirmed direct relationship。
- 不因普通 caveat 过度弱化 thesis。
- `memo_claim_count` 达到 profile / case 要求；sector-depth deep-research 至少 6 条有 refs 的 memo claims。
- direct answer 长度使用 profile 上下限和容忍区间做质量门，不做机械字数优化；重点检查是否有重复句、内部标签和缺失 action fields。

失败处理：

- 复用 S6 thesis plan。
- 优先修 profile selector、输入 projection、memo schema、writing skill；不要只提高 max tokens。

## 10. 阶段 S8：Verifier / Repair

目标：验证 Verifier 是安全门，不是第二个 writer，也不是深度补偿器。

输入：

- S7 memo。
- minimal verifier projection。
- allowed refs。

通过门控：

- deterministic verifier pass。
- LLM verifier pass 或给出定点 repair instruction。
- repair 后 failures 减少。
- Verifier 不生成新投资观点、不扩大范围、不触发检索。
- projection row/claim counts 合理，不回退到 broad inventory。

失败处理：

- 复用 S7 memo。
- 修 verifier projection / specific repair instruction。

## 11. 阶段 S9：Renderer / Product Answer

目标：验证用户看到的是成熟回答，而不是内部 trace。

输入：

- S8 通过 memo。
- boundary summary。
- citations / refs。

通过门控：

- 有直接回答、关键 memo claims、evidence refs、source boundary。
- 不展示裸 ledger、raw rows、内部 prompt、私有路径。
- 多轮 follow-up 中能说明继承和更新了哪些 scope。

失败处理：

- 复用 S8 memo。
- 修 renderer format / citation projection。

## 12. 阶段 S10：Full Chain 和多轮回归

只有 S1-S9 单层通过后运行。

执行：

```powershell
$env:DEEPSEEK_API_KEY='<use shell env only>'
python scripts\eval_multi_agent_real_llm_chain.py `
  --run-id 20260601_fin_agent_s10_full_chain_quality_gate_deepseek_v0_1 `
  --real-evidence-operators `
  --strict
```

通过门控：

- all cases `gate_status=pass`。
- route 成功和真实 evidence quality 都通过。
- sector-depth cases 覆盖 AI infra、banking、healthcare、energy/utilities。
- multi-turn 不发生 stale ticker carryover。
- `audit_fin_agent_layer_quality.py` 输出总 gate pass。
- 高成本 flags 需要进入诊断队列，不能直接宣称成熟质量通过。

## 13. 自动审计命令

Research Lead artifact：

```powershell
python scripts\audit_fin_agent_layer_quality.py `
  --summary eval\sec_cases\outputs\multi_agent_activation_diagnostic\<run_id>\activation_diagnostic.json `
  --json-out eval\sec_cases\outputs\multi_agent_activation_diagnostic\<run_id>\fin_agent_layer_quality_audit.json `
  --md-out eval\sec_cases\outputs\multi_agent_activation_diagnostic\<run_id>\fin_agent_layer_quality_audit.md `
  --strict
```

Full-chain artifact：

```powershell
python scripts\audit_fin_agent_layer_quality.py `
  --summary eval\sec_cases\outputs\multi_agent_real_llm_chain_eval\<run_id>\real_chain_eval_summary.json `
  --artifact-root eval\sec_cases\outputs\multi_agent_real_llm_chain_eval\<run_id> `
  --json-out eval\sec_cases\outputs\multi_agent_real_llm_chain_eval\<run_id>\fin_agent_layer_quality_audit.json `
  --md-out eval\sec_cases\outputs\multi_agent_real_llm_chain_eval\<run_id>\fin_agent_layer_quality_audit.md `
  --strict
```

## 14. 当前优化顺序

基于 216/P7 之后的问题，后续优化顺序为：

1. [x] 建立并固定 S1-S10 分层质量门控。
2. [x] S1：重测 Research Lead，确认 cost-aware activation 和 primary/supporting/conditional 区分。
3. [x] S2：把 Universe / Relationship 输出升级为 `EconomicLinkMap` / relationship mechanism frame。
4. [x] S3：修 exact-value ledger alias/relaxed fallback，并验证 real SEC retrieval、BM25/ObjectBM25/BGE rerank、market/industry/relationship rows。
5. [x] S4：Coverage / Reflection second-pass gate。
6. [x] S5：新增 artifact-reuse Specialist layer gate，复用 S1-S4 outputs，真实 DeepSeek 跑过 `2/2` specialist cases、`7` specialist routes、real-evidence quality `2/2`、`0` repair。
7. [ ] S6：把 Aggregator 从 `memo_thesis_pack` 升级为 `InvestmentThesisPlan`。
8. [ ] S7：Memo Writer 改为 thesis-plan-driven natural-language writer，减少 retry 和 evidence-summary 风格。
9. [ ] S10：扩展 full-chain + multi-turn eval，再考虑 LLM judge。

## 14.1 v0.2 分层测试补充

本补充用于 2026-06-01 后续 S1-S8 agent 能力测试，执行前先阅读 `fin_agent_s1_s8_agent_quality_case_matrix_v0_2.md`。

新增测试维度：

- 行业：AI infra、banking、healthcare、energy、utilities。
- 难度：exact lookup、focused answer、standard memo、sector-depth、run artifact inspect。
- 能力：精准激活、工具调用准确性、上游输出解析、role-specific ClaimCard 输出、下游可消费性、token 成本。

新增硬门控：

- S1 不允许 focused / exact case 激活所有 Specialist。
- S3 comparative case 必须输出 row distribution；context 有 primary filing 但 ledger 无 exact rows 时写 `ledger_missing_despite_context`。
- S5 comparative fundamental/risk case 必须通过 `comparative_focus_ticker_primary_visible_or_gap`。
- S5 route artifact 缺 `prompt_row_distribution` 时 fail。
- S6-S8 只能复用已通过 S5 artifact，不能因为 memo 质量差重新从 S1 开始跑。
- S7/S8 中文 query 必须传递 `response_language=zh-CN`；Memo Writer user-facing prose、Verifier gate、Renderer section titles 都必须按中文输出，tickers / metric ids / evidence refs / 数字单位保持原样。
- S7/S8 中文 numeric fidelity 必须识别 `亿美元`、`百万美元`、`倍`、`个百分点` 和区间单位继承，不能因为中英文单位表达不同而删除或改写有效数值。

知识库限制：

- 如果本地 SEC/market/industry/relationship 数据无法证明真实客户/供应商、consensus、实时新闻、转录稿、监管/临床/商品价格事实，必须记录为 source/data limitation。
- 数据缺口不算 prompt 失败；但未记录缺口而让下游 hallucinate，算 hard fail。

## 15. Stop / Proceed 规则

Proceed：

- 当前层 hard gate 全 pass。
- 当前层质量分不低于 3.0，或该层是 diagnostic-only 且文档明确不阻塞。
- 上游 artifact 已保存，可复用。

Stop：

- 任一 hard gate fail。
- 任一 agent 越权。
- source-boundary fail。
- 真实 evidence quality fail。
- token 成本异常且 claim density / memo density 低。

Pivot：

- 本地知识库无法支持目标 claim。
- 证据缺口属于缺数据，不是 prompt 或 schema 问题。
- 检索 ceiling 无法支持下游质量目标。
