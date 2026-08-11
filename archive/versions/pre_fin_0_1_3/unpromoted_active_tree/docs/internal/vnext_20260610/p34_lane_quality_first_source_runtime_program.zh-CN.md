# P34 Lane Quality-First Source Runtime Program

日期：2026-07-07

状态：`p34_fact_table_projection_and_goldcase_availability_alignment_done_full_chain_blocked_user_approval_pending`

## 1. 文档定位

P34 是 P33 之后的 source-runtime 修复主线。它不是继续堆 parser，也不是继续跑 full-chain，而是把每个 vertical lane 先定义成“什么叫研究质量合格”，再倒推出 evidence slot、source route、parser 和 runtime consumption。

当前 P33 事实：

- Humanmade Gold Set 已覆盖 `15` 个 case、`68` 条 source-runtime rows。
- `p33_goldset_live_source_backfill_v0_1` 严格回填结果只有 `4/68` 条 `live_runtime_ready`。
- `1` 条为 `route_candidate_only_parser_lineage_pending`。
- `13` 条为 AI/Semis weak candidates，不能提权。
- `44` 条 rubric rows 仍需要 issuer / lane / source route binding。
- `6` 条 negative rows 是 failure fixtures，不是 evidence。
- `RC-P33-019-humanmade-gold-set-runtime-depth-gap` 仍 open，禁止 broad full-chain、模型对比、case expansion、release eval。

P34 的核心口径：

```text
先定义研究质量
-> 再定义 judgment chain
-> 再定义 evidence slot
-> 再找 source route / parser
-> 再做 runtime promotion
-> 最后才允许 scoped paid node / workbench dogfood
```

## 2. 为什么要做 P34

P33 暴露的问题不是“项目没有数据”，而是：

1. 数据没有按投研判断所需的 exact slot 组织。
2. false positive 风险很高，宽松匹配会把 consolidated revenue、generic product row、relationship graph、ordinary source authority row 误提权。
3. AI/Semis 缺的是 source-specific parser / locator，而不是又一个通用 SEC ledger。
4. rubric cases 仍只是行业问题和证据槽位，没有 issuer / lane / source route binding。
5. 如果不先做 slot-level 数据工程，继续换模型或调 writer 会掩盖上游证据不稳。

P34 增加一条更硬的约束：工程 row pass 不等于研究质量 pass。一个 lane 必须同时满足：

```text
Research Quality Pass
+ Engineering Evidence Pass
```

## 3. P34 执行顺序

### P34-0 Baseline And Governance

目标：冻结 P33 事实和 P34 禁跑边界。

交付物：

- `docs/internal/vnext_20260610/p34_lane_quality_first_source_runtime_program.zh-CN.md`
- `docs/project_os/p34_ai_semis_lane_research_quality_rubric_v0_1.json`
- `docs/project_os/p34_ai_semis_judgment_chain_registry_v0_1.json`
- `docs/project_os/p34_ai_semis_evidence_slot_contract_mapping_v0_1.json`

通过条件：

- 文档明确 P34 不能以 parser row 数量替代研究质量。
- 所有后续 tasks 都能追溯到 Research Quality Rubric。
- 禁止事项继承 P33：不得用 full-chain / paid model 发现 deterministic/source-runtime 问题。

### P34-1 Lane Research Quality Rubric

目标：先定义一个 lane 的“好研究是什么”。首个 lane 固定为 `AI/Semis`。

AI/Semis 必答问题：

1. AI capex 是真实需求、提前拉货，还是市场叙事？
2. GPU / TPU / ASIC / server OEM / ODM / HBM / CoWoS / semicap 谁受益，传导链怎么走？
3. 产品架构、性能、功耗、成本、软件生态、供应瓶颈如何影响竞争？
4. 客户部署是官方确认、渠道 proxy，还是需求池推断？
5. DELL AI server 是收入能见度改善，还是利润质量改善？
6. ASML / LRCX / AMAT / KLAC 如何从 foundry / memory / logic capex 周期 read-through？
7. 市场是否已经 price in？
8. 什么证据会推翻当前判断？

通过条件：

- Rubric 能让 reviewer 判断 memo 是否像 analyst workpaper。
- Rubric 不只列规则，还包含 good / bad answer pattern。
- Rubric 明确“没有 SKU revenue 不等于产品层无法判断”。

### P34-2 Humanmade Answer To Judgment Chain

目标：把 AI/Semis humanmade gold answer v0.2 编译为可执行 `RequiredJudgmentChain`。

首批 judgment chains：

1. `jc_ai_capex_demand_pool`
2. `jc_accelerator_architecture_competition`
3. `jc_customer_deployment_oem_adoption`
4. `jc_dell_ai_server_financial_quality`
5. `jc_foundry_semicap_readthrough`
6. `jc_market_price_in_capital_feedback`
7. `jc_counter_thesis_what_would_change`

每条 chain 必须包含：

- `question_answered`
- `business_mechanism`
- `required_evidence_roles`
- `counter_evidence_roles`
- `minimum_quality_bar`
- `failure_conditions`
- `writer_must_say`

通过条件：

- Research Lead 能用 chain 生成 thesis path / required-item plan。
- Specialist 能用 chain 判断自己应该回答什么。
- Writer 能从 chain 组织 workpaper，而不是把 evidence dump 重排。

### P34-3 Evidence Slot Contract

目标：把 judgment chain 拆成可执行 evidence slots。

首批 AI/Semis slots：

- `dell_ai_server_orders_shipments_backlog`
- `dell_isg_revenue_margin_baseline`
- `dell_nvidia_poweredge_ai_factory_product_path`
- `dell_xe9712_gb200_oem_system_config`
- `nvda_gb200_nvl72_rack_architecture`
- `nvda_data_center_revenue_demand_confirmation`
- `amd_mi300x_memory_bandwidth_competition`
- `amd_mlperf_mi355x_performance_proxy`
- `google_tpu_v6e_trillium_architecture`
- `google_a4x_gb200_cloud_deployment_surface`
- `msft_cloud_ai_capex_supply_shortfall`
- `amzn_aws_demand_pool_context`
- `alphabet_capex_server_chain_context`
- `meta_capex_component_pricing_risk`
- `tsmc_advanced_node_hpc_ai_readthrough`
- `asml_lithography_installed_base_readthrough`
- `amat_semiconductor_systems_mix`
- `lrcx_memory_hbm_process_intensity`
- `market_price_in_valuation_positioning_gap`
- `counter_thesis_pack_ai_semis`

每个 slot 必须定义：

- strong / medium / proxy evidence；
- forbidden substitutes；
- required fields；
- source route family；
- parser family；
- promotion rule；
- cannot infer；
- current P33 backfill status；
- next repair action。

通过条件：

- AI/Semis 20 条 rows 全部映射到 judgment chain。
- 每条 row 都有 quality role，而不是只有 parser status。
- weak candidates 不得因为 row 相似而自动提权。

### P34-4 Source Route Plan

目标：把 evidence slot 绑定到 source route / adapter family。

首批 adapter family：

1. `sec_8k_earnings_release_table_adapter`
2. `investor_deck_pdf_table_adapter`
3. `official_product_spec_page_adapter`
4. `benchmark_result_adapter`
5. `customer_deployment_news_adapter`
6. `cloud_capex_filing_adapter`
7. `semicap_bookings_backlog_adapter`
8. `oem_configuration_adapter`

通过条件：

- 每个 slot 至少有一个 primary route 和一个 fallback route。
- route 无法绑定时要写 `route_gap`，不能写 public source absent。

第一轮执行结果（2026-07-07）：

- 已生成机器可读 SourceRoutePlan：`docs/project_os/p34_ai_semis_source_route_plan_v0_1.json`。
- 已生成可读报告：`docs/internal/vnext_20260610/p34_ai_semis_source_route_plan_v0_1.zh-CN.md`。
- `20/20` AI/Semis evidence slots 已绑定 primary route。
- `20/20` AI/Semis evidence slots 已绑定 fallback route。
- route 总数 `47`，primary route `20`，fallback route `27`。
- adapter family `15` 类。
- `route_gap_count=0`。
- P34-4 未运行 paid LLM、未运行 full-chain、未实现新 crawler/parser、未证明 live source/parser readiness。

下一步固定为 P34-5 adapter-family fixtures，优先做：

1. `sec_8k_earnings_release_table_adapter`
2. `official_product_spec_page_adapter`
3. `semicap_bookings_backlog_adapter`

### P34-5 Adapter Family Implementation

目标：按 source family 写 parser / locator，不按 600 家公司逐个硬写。

通过条件：

- 每个 adapter 至少有 2-3 个真实 fixture。
- 输出统一 runtime row：

```text
issuer
product_or_family
metric_or_attribute
value
unit
period_or_version
source_url
citation
parser_lineage
authority_scope
cannot_infer
```

- parser 失败必须 typed：`locator_gap`、`parser_gap`、`source_absent`、`credential_gap`、`commercial_gap`。

当前执行结果（2026-07-07）：

- 已生成 adapter fixture 报告：`docs/project_os/p34_ai_semis_adapter_fixture_report_v0_1.json`。
- 已生成可读报告：`docs/internal/vnext_20260610/p34_ai_semis_adapter_fixture_report_v0_1.zh-CN.md`。
- 首批 3 个 adapter family 均已通过 parser contract fixture：
  - `sec_8k_earnings_release_table_adapter`
  - `official_product_spec_page_adapter`
  - `semicap_bookings_backlog_adapter`
- fixture_count：`9`。
- runtime_row_count：`9`。
- rejected_candidate_count：`9`。
- typed_gap_count：`0`。
- rows_with_parser_lineage_count：`9`。
- rows_with_authority_scope_count：`9`。

边界：

- 本阶段使用本地 artifact-backed fixture snippets，不做 live fetch / crawler。
- `source_url` 使用 `source-ledger://p34/...`，表示 parser contract fixture，不表示真实 URL snapshot。
- fixture rows 的 `promotion_status=fixture_parser_contract_pass_live_fetch_pending`，不能直接进入 live evidence bundle。
- 下一步必须把 adapter 接到真实 source route attempts，或记录 attempt-backed typed gap。

### P34-6 Promotion Gate + Research Quality Gate

目标：区分工程可提权和研究质量可用。

工程 gate：

- issuer 一致；
- product / metric 具体；
- source authority 匹配；
- parser lineage 完整；
- 没有 forbidden substitute。

研究质量 gate：

- judgment chain 是否被回答；
- 是否形成 product / customer / supply-chain / financial bridge；
- 是否区分 strong / medium / proxy；
- 是否有 counter-thesis；
- 是否有 price-in / capital feedback；
- 是否能形成 bounded analyst view。

通过条件：

- row coverage 高但不能回答 judgment chain，不得 pass。
- gap 必须 attempt-backed。

当前执行结果（2026-07-07）：

- 已生成 no-paid quality audit：`docs/project_os/p34_ai_semis_no_paid_quality_audit_v0_1.json`。
- 已生成可读报告：`docs/internal/vnext_20260610/p34_ai_semis_no_paid_quality_audit_v0_1.zh-CN.md`。
- audit status：`blocked_live_route_attempt_and_quality_gaps_pending`。
- judgment_chain_count：`7`。
- chain_pass_count：`0`。
- chain_partial_count：`4`。
- chain_fail_count：`3`。
- source_route_gap_count：`0`。
- adapter_fixture_runtime_row_count：`9`。
- allow_paid_memo_writer：`false`。
- allow_full_chain：`false`。

主要 blocked lane：

- `jc_ai_capex_demand_pool`：缺 hyperscaler capex route rows。
- `jc_market_price_in_capital_feedback`：缺 market price-in / capital feedback route rows。
- `jc_counter_thesis_what_would_change`：缺独立 counter-thesis route rows。
- `jc_dell_ai_server_financial_quality`：orders/backlog 和 ISG baseline 有 fixture，但 AI server mix、GPU pass-through 和 margin bridge 未闭合。
- `jc_customer_deployment_oem_adoption`：orders/product context 有，但 official deployment / OEM configuration live route 未闭合。

结论：P34-6 已执行并正确 blocked。当前不得运行 paid Memo Writer、full-chain、模型对比、case expansion 或 release eval。

第二轮执行结果（2026-07-07）：

- 已生成 live route attempt 报告：`docs/project_os/p34_ai_semis_live_route_attempt_report_v0_1.json`。
- 已生成可读报告：`docs/internal/vnext_20260610/p34_ai_semis_live_route_attempt_report_v0_1.zh-CN.md`。
- live route status：`live_route_attempts_recorded_with_remaining_typed_gaps`。
- slot_count：`20`。
- attempted_slot_count：`20`。
- attempt_count：`21`。
- accepted_live_runtime_row_count：`21`。
- accepted_slot_count：`20`。
- network_attempt_count：`15`。
- network_ok_count：`15`。
- unattempted_slot_count：`0`。
- typed_gap_count：`2`，且均为 attempt-backed typed gap。
- 重新生成 no-paid quality audit：`docs/project_os/p34_ai_semis_no_paid_quality_audit_v0_1.json`。
- audit status：`bounded_quality_audit_pass_scoped_writer_allowed_full_chain_blocked`。
- judgment_chain_count：`7`。
- chain_pass_count：`5`。
- chain_partial_count：`2`。
- chain_fail_count：`0`。
- source_route_gap_count：`0`。
- allow_scoped_paid_memo_writer：`true`。
- allow_paid_memo_writer：`true`。
- allow_full_chain：`false`。

第二轮修复点：

- 修复 `_fetch_url_text()` 的 owned source-fetch 问题：先走 `requests` + browser-like headers，PDF 使用 `pypdf` 解析前 5 页，再回退 urllib，避免 AMD 官方 HTML/PDF 可达却被误判为 `locator_gap`。
- 修正 AMD MI300X 官方规格页 keyword：`192GB` -> `192 GB`。
- 替换 LRCX route 到 Lam 官方 advanced packaging 技术页，使 `HBM/TSV/etch/deposition` 进入 semicap read-through，而不是用泛 quarterly-result 新闻稿硬凑。
- 把 P34 no-paid audit 从单一 blocked 语义改成两级语义：所有 slot 已真实尝试、无 route gap、remaining gaps 均 attempt-backed 时，允许 scoped paid Memo Writer node；但 full-chain / 模型对比 / case expansion / release eval 仍保持 blocked。

剩余 bounded typed gaps：

1. `dell_ai_server_margin_bridge_quality_gap`
   - 类型：`source_absent_after_attempt`。
   - 含义：公开 Dell rows 能支持 AI server revenue / order visibility 和 ISG baseline，但没有披露 AI server mix、GPU pass-through cost、AI server gross margin 或 backlog conversion。
   - writer 可写：AI server 对 revenue visibility 有支持，但利润质量只能 bounded 判断，不能写成已证明 margin 改善。
2. `market_price_in_exact_positioning_gap`
   - 类型：`commercial_gap`。
   - 含义：公开 delayed/context rows 能支持 price-in 讨论，但 exact crowding、实时资金流、完整 options positioning、borrow cost、institutional flow 需要商业数据或更深 adapter。
   - writer 可写：可以讨论估值/市场预期/价格反应 context，不能写成精确拥挤度或资金流结论。

结论：P34-6 已从 fail-closed blocked 推进到 bounded source-runtime pass。下一步只允许 P34-9 scoped paid Memo Writer node，并且必须带上述两个 typed boundary；仍禁止 broad full-chain、模型对比、case expansion、release eval。

### P34-7 Runtime Integration

目标：把 P34 artifacts 接入 agent runtime。

接入点：

- Research Lead：读取 rubric + judgment chain。
- Specialist：读取 evidence slot contract + promoted rows。
- ProductIntelligenceGraph：输出 investment-role edge。
- MemoLogicPlan：只接 JudgmentCard / typed gap / evidence refs。
- Writer：负责表达，不重新研究。
- Workbench：显示 chain -> slot -> source -> parser -> JudgmentCard -> memo section。

通过条件：

- Research Lead plan 覆盖 judgment chains。
- Specialist 输出 JudgmentCard 而非 evidence summary。
- Writer 输出 workpaper 而非搜索结果总结。

### P34-8 No-paid Audit

目标：在任何 paid/full-chain 前，用 deterministic audit 检查：

- slot coverage；
- source route coverage；
- promoted row quality；
- judgment chain answerability；
- specialist input readiness；
- writer payload readiness；
- negative case failure。

通过条件：

每条 chain 状态必须是：

- `answered`
- `partially_answered_with_boundary`
- `parser_gap`
- `source_absent_after_attempt`
- `commercial_gap`

不得存在 `unknown` 或 generic gap。

### P34-9 Scoped Paid Node Test

目标：只有 no-paid audit 过了，才允许少量 paid node。

顺序：

1. Research Lead paid node。
2. Selected Specialist paid node。
3. Aggregate / JudgmentCard deterministic replay。
4. Memo Writer node。
5. Renderer / verifier / Workbench projection。

通过条件：

- 输出接近 humanmade gold answer。
- 若失败，能归因到数据源、parser、Research Lead、specialist、writer、renderer 或模型能力。

### P34-10 Rubric Lane Replication

目标：AI/Semis 通过后复制方法，不复制 slot。

后续 lanes：

- Semicap。
- Cloud/SaaS。
- Financials。
- Healthcare/Medtech。
- Energy/Utilities。
- Retail/Consumer。
- Auto/Industrial。
- Secondary-market price-in。

每个 lane 必须重复：

```text
Research Quality Rubric
-> Humanmade Answer Exemplar
-> Judgment Chain
-> Evidence Slot Contract
-> Source Route Plan
-> Adapter / Parser
-> Promotion + Quality Gate
-> Runtime Integration
```

## 4. 当前已执行阶段

截至 2026-07-07，本轮已完成或执行到：

1. `AI/Semis LaneResearchQualityRubric v0.1`。
2. `AI/Semis RequiredJudgmentChainRegistry v0.1`。
3. `AI/Semis EvidenceSlotContractMapping v0.1`，覆盖 P33 当前 20 条 AI/Semis rows。
4. `AI/Semis SourceRoutePlan v0.1`，覆盖 `20` 个 evidence slots、`47` 条 routes、`15` 类 adapter family，`route_gap_count=0`。
5. `AI/Semis AdapterFixtureReport v0.1`，首批 3 类 adapter fixture 生成 `9` 条 normalized rows 和 `9` 条 rejected false substitutes。
6. `AI/Semis No-paid Quality Audit v0.1` 第一轮已执行，结果为 `blocked_live_route_attempt_and_quality_gaps_pending`，不是 pass。
7. `AI/Semis Live Route Attempt Report v0.1` 已执行真实 source route attempts：`20/20` slots attempted、`21` accepted live runtime rows、`2` attempt-backed typed gaps、`0` unattempted slots。
8. `AI/Semis No-paid Quality Audit v0.1` 第二轮已执行，结果为 `bounded_quality_audit_pass_scoped_writer_allowed_full_chain_blocked`：`5/7` chains pass、`2/7` chains bounded partial、`0` fail，允许 scoped paid Memo Writer node，但不允许 full-chain。
9. `AI/Semis Scoped Memo Writer Node + Projection Replay v0.1` 已执行：P34 writer payload preflight `pass`，scoped DeepSeek Memo Writer node `pass`，`1` 次调用、`0` repair、`16,441` tokens、no salvage；renderer projection / final verifier projection / Workbench projection 均 `pass`。本轮修复了两个 owned projection bug：final verifier 在 claim_id 已匹配时仍只保留 memo 明文交集 refs，导致 known evidence refs 被剪少；Workbench projection 只显示维度 section，未把必答问题、投资含义、what-would-change 和 actionable gap 作为 reviewer surface 展开。
10. `AI/Semis Fact-table Projection + Goldcase Availability Alignment v0.1` 已执行：不跑 paid LLM、不跑 true full-chain，只用 P34 accepted runtime rows 做 deterministic projection preview，并把 AI/Semis goldcase 要求对齐当前 RAG/SQL/Milvus/source-route 可得性。该步骤修复 writer payload 只拿 claim / required-item answer、没有拿财务表 / 产品规格表 / 部署表 / 市场边界表的问题；新增 `analyst_fact_table_blocks`，并要求 true full-chain eval 前必须区分每条证据来自 SQL/Milvus/RAG、source-route live attempt、existing manifest row 还是 deterministic fixture。

对应机器可读 artifacts：

- `docs/project_os/p34_ai_semis_lane_research_quality_rubric_v0_1.json`
- `docs/project_os/p34_ai_semis_judgment_chain_registry_v0_1.json`
- `docs/project_os/p34_ai_semis_evidence_slot_contract_mapping_v0_1.json`
- `docs/project_os/p34_ai_semis_source_route_plan_v0_1.json`
- `docs/project_os/p34_ai_semis_adapter_fixture_report_v0_1.json`
- `docs/project_os/p34_ai_semis_live_route_attempt_report_v0_1.json`
- `docs/project_os/p34_ai_semis_no_paid_quality_audit_v0_1.json`
- `docs/project_os/p34_single_case_projection_replay_v0_1.json`
- `docs/project_os/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.json`
- `docs/internal/vnext_20260610/p34_fact_table_projection_preview_v0_1.zh-CN.md`
- `docs/internal/vnext_20260610/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.zh-CN.md`
- `eval/sec_cases/outputs/p34_ai_semis_scoped_writer_runs/p34_scoped_memo_writer_node_deepseek_20260707_120609/p34_ai_semis_scoped_writer_case_v0_1/memo_writer_node_summary.json`

### P34-11 Fact-table Projection + Goldcase Availability Alignment

触发原因：

- 人工 review 发现 scoped writer rendered memo 虽然有 evidence refs，但没有先把财务数据、产品规格、部署路径、市场边界以表格方式投影出来。
- 必答问题段落把判断、边界和 what-would-change 混在同一段，读起来像“刚说一句就开始免责”，没有形成 analyst workpaper 的信息层级。
- goldcase 不能脱离当前 RAG/SQL/Milvus/source-route 可得性，否则会要求 agent 输出当前 runtime row 里并不存在的 exact 数字。

本轮修复：

- `src/sec_agent/p34_lane_quality_runtime.py`：P34 scoped writer payload 新增 `analyst_fact_table_blocks`，按 `financial_bridge_table`、`product_spec_architecture_table`、`customer_deployment_oem_table`、`capex_demand_pool_table`、`semicap_readthrough_table`、`market_counter_boundary_table`、`attempt_backed_gap_table` 七类组织。
- `src/sec_agent/langgraph_orchestrator.py`：renderer 在 `核心判断` 后优先渲染 `关键数据表`；必答问题改为 judgment / boundary / what-would-change 分层输出，避免把边界塞进同一句。
- `src/sec_agent/memo_llm.py`：Memo Writer 不再被要求保留 raw metric id；正文应把内部字段翻译成 analyst-readable label。
- `scripts/eval_multi_agent/run_p34_fact_table_projection_and_goldcase_alignment.py`：新增 no-paid deterministic runner，生成 fact-table preview 和 goldcase/RAG availability alignment。

当前可得性对齐结果：

- Indexed rows：`154,484`；tickers：`603`。
- P34 slots：`20/20` attempted；accepted runtime rows：`21`；typed gaps：`2`。
- Analyst fact tables：`7` blocks / `23` rows。
- Value quality：`structured_metric_context=6`、`specific_technical_or_deployment_fact=8`、`context_summary=7`、`attempt_backed_gap=2`。

关键边界：

- 本轮 P34 scoped writer case 是 source-route/runtime-row replay，不是 Milvus/rerank-driven full-chain retrieval run。Milvus/RAG 仍是 broader discovery/retrieval substrate，但本轮专门验证“已接受 source-route rows 能否变成 analyst-ready fact tables”。
- 这不是 SEC/XBRL/13F 等标准化材料全局解析失效。标准化 SEC / XBRL / structured ledger rows 仍按既有物化结果可用；本轮暴露的是 AI/Semis source-route rows 中，很多来自官方 press/product/IR 页面，当前 adapter 只稳定抽到了 context/spec/deployment fact，没有把所有页面表格单元都抽成 `value/unit/period/product/citation`。
- true full-chain eval 前，goldcase required item 必须先映射为 `available/runtime`、`context_summary`、`attempt_backed_gap`、`commercial_gap` 或 `not_in_current_rag_scope`，不能要求 writer 编造当前 runtime row 没有的 exact 数字。

当前结论：

- writer payload / renderer surface 的 owned defect 已修：输出现在可以先展示事实表，再进入判断和边界。
- 投研深度仍不能被表面 pass 掩盖：DELL AI server margin bridge、market price-in exact positioning、部分 semicap bookings/backlog/customer allocation 仍是更深 parser/source/commercial boundary 问题。
- 下一步只有在用户认可本轮 deterministic preview 后，才允许进入 scoped node 或 true full-chain eval；未经认可不得继续 paid full-chain、模型对比或 case expansion。

## 5. 当前禁止事项

- 禁止把 P34 文档当作 runtime pass。
- 禁止把 slot contract 当作 live source row。
- 禁止把 `4/68` live-ready 误记为 source sufficiency。
- 禁止 broad full-chain、模型对比、case expansion、release eval。
- 禁止让 weak candidates 进入正式 evidence bundle。
- 禁止因 parser/locator 未做而写 public source absent。
- 禁止把 P34-6 bounded no-paid audit 误记为 full-chain 放行；当前只允许 `allow_scoped_paid_memo_writer=true`，`allow_full_chain=false`。
- 禁止 scoped Memo Writer 隐去 `dell_ai_server_margin_bridge_quality_gap` 和 `market_price_in_exact_positioning_gap` 两个 attempt-backed typed boundaries。
- 禁止把 P34 scoped Memo Writer node + projection replay 误记为 full-chain、模型对比、case expansion、release eval 或 human-accepted gold workpaper；它只证明单 case writer/projection 节点级闭环。

## 6. 下一步

P34 下一步从 scoped writer 转入人工审阅 / closeout 判断，而不是 broad full-chain：

1. 人工审阅 `docs/project_os/p34_single_case_projection_replay_v0_1.json` 和 rendered workpaper，判断是否接近 humanmade gold answer。
2. 若审阅发现 writer 仍过度边界化、判断不够像 analyst、或没有把 product / deployment / financial bridge / semicap / market price-in 串成故事线，必须回到 writer payload / JudgmentCard / ProductIntelligenceGraph projection / MemoLogicPlan 修复，不得用 full-chain 重跑掩盖。
3. 若人工审阅通过，才能把 P34 AI/Semis 单 case 标为 scoped writer/projection accepted，并规划下一步是否进入 limited Workbench dogfood。
4. 仍禁止 broad full-chain、模型对比、case expansion、release eval，直到 scoped writer + projection + human review 证明 gold-set workpaper 质量。
