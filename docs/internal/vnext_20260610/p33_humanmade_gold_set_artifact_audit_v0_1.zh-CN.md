# P33 Humanmade Gold Set Artifact Audit v0.1

日期：2026-07-06

状态：`no_paid_artifact_audit_completed_findings_open`

## 1. 审计定位

本轮不是继续跑 full-chain，也不是再比较 DeepSeek / GPT。目标是拿已经落好的 Humanmade Gold Set v0.2 回头审计当前 AI/Semis 历史 full-chain artifact 和 P33 stepwise 节点流转，确认：

1. 当前输出离 humanmade gold workpaper 差在哪里；
2. 哪些问题是最终 memo 写作层问题；
3. 哪些问题更早发生在 Research Lead、evidence fusion、coverage reflection、specialist、aggregate、MemoLogicPlan 或 writer payload；
4. 哪些更深层原因来自 agent 编排、prompt/skill、ProductIntelligenceGraph、数据源和 parser/locator；
5. 后续修复应先修哪个最早 faulty artifact。

本轮没有运行 paid LLM、full-chain、模型对比、crawler 或新检索。

## 2. 审计输入

### 2.1 Gold Set / Ruler

- `docs/internal/vnext_20260610/p33_ai_semis_research_judgment_ruler.zh-CN.md`
- `docs/internal/vnext_20260610/p33_ai_semis_humanmade_gold_case.zh-CN.md`
- `docs/internal/vnext_20260610/p33_humanmade_gold_set_spec_v0_1.zh-CN.md`
- `docs/project_os/humanmade_gold_set_spec_v0_1.json`
- `docs/internal/vnext_20260610/p33_humanmade_gold_set_answer_exemplars_v0_2.zh-CN.md`
- `docs/project_os/humanmade_gold_set_answer_exemplars_v0_2.json`

### 2.2 历史 full-chain / memo artifact

- P30 DeepSeek full-chain:
  - `reports/r53_r60_p30_full_chain_ai_semis/p30_ai_infra_deepseek_fullchain_after_graph_program_split_20260704_r1/p30_ai_infra_deepseek_fullchain_after_graph_program_split_20260704_r1/ma_real_sector_ai_infra_full_chain_real_retrieval/qwen/rendered_answer.md`
  - `reports/r53_r60_p30_full_chain_ai_semis/p30_ai_infra_deepseek_fullchain_after_graph_program_split_20260704_r1/p30_ai_infra_deepseek_fullchain_after_graph_program_split_20260704_r1/multi_agent_output_quality_audit.json`
  - `reports/r53_r60_p30_full_chain_ai_semis/p30_ai_infra_deepseek_fullchain_after_graph_program_split_20260704_r1/p30_ai_infra_deepseek_fullchain_after_graph_program_split_20260704_r1/agent_information_economy_audit.json`
- P33 DeepSeek full-chain failed artifact:
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_gold_case_deepseek_full_chain_after_milvus_available_semantics_fix_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/qwen/rendered_answer.md`
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_gold_case_deepseek_full_chain_after_milvus_available_semantics_fix_20260705_r1/multi_agent_output_quality_audit.json`
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_gold_case_deepseek_full_chain_after_milvus_available_semantics_fix_20260705_r1/agent_information_economy_audit.json`
- P33 old paid Memo Writer node from aggregate r7:
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_memo_writer_node_from_aggregate_r7_deepseek_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/memo_answer.json`
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_memo_writer_node_from_aggregate_r7_deepseek_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/memo_writer_node_result.json`

### 2.3 P33 stepwise accepted artifacts

- Research Lead:
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_research_lead_after_route_scope_fix_deepseek_20260705_r5/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/stepwise_node_result.json`
- Evidence fusion:
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_evidence_fusion_selector_after_requirement_trace_fix_20260705_r4/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/evidence_fusion_selector_node_result.json`
- Coverage reflection:
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_coverage_reflection_enriched_state_after_fusion_fix_20260705_r3/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/coverage_reflection_node_result.json`
- Specialist composite:
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_optional_specialist_composite_after_targeted_repairs_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/optional_specialist_subgraph_node_result.json`
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_optional_specialist_composite_after_targeted_repairs_20260705_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/optional_specialist_subgraph_summary.json`
- Aggregate r7:
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_node_result.json`
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/aggregate_judgment_plan_summary.json`
- Memo Writer payload preflight:
  - `eval/sec_cases/outputs/p33_gold_case_runs/p33_stepwise_memo_writer_payload_preflight_source_coverage_hardening_20260706_r1/p33_3_ai_semis_accelerator_dell_gold_case_v0_1/memo_writer_payload_preflight_summary.json`

## 3. Gold Set 对比结论

### 3.1 总体判断

当前项目不是没有证据，也不是 agent graph 完全没工作。Research Lead、Evidence Fusion、Coverage、Specialist、Aggregate 已经能把 case 组织成 required items、JudgmentCandidates、MemoLogicPlan 和 writer payload。

但按 Humanmade Gold Set v0.2 的标准，当前 artifact 仍没有达到可接受的 analyst workpaper。核心原因是：

```text
上游有结构，但缺 gold-depth source rows；
specialist 有 judgment candidate，但仍以 context/proxy + cannot infer 为主；
aggregate 有 required-item plan，但没有足够强的 answer-level material；
writer payload shape 通过，但旧 paid memo 仍像证据摘要和边界声明。
```

### 3.2 逐项差距表

| Gold item | 当前 artifact 状态 | 判断 | 最早问题层 |
| --- | --- | --- | --- |
| Opening bounded thesis | Research Lead / Aggregate 有 thesis path；旧 paid memo 只有泛化“capex/产品收入/毛利锚点分层看” | `partial` | Memo Writer / writer payload semantic selection |
| Demand pool vs supplier allocation | MSFT/AMZN capex rows 已进入；P33 能防止直接写成 supplier allocation | `partial_pass` | 还缺 GOOGL/META capex 和更清晰 AI/non-AI capex bridge |
| Product / Architecture | `evidence_fusion.product_runtime_fact_count=0`；GOOGL TPU 仍 unsupported；NVDA/AMD 多为 taxonomy/product slot | `fail_for_gold_depth` | Product source route / ProductIntelligenceGraph runtime projection |
| Customer deployment / adoption | relationship_graph 有 DELL/NVDA/AMD/AMZN 关系；但多为 scope/hypothesis/context | `partial` | CustomerDeployment exact/source role rows 未进入本 case runtime |
| DELL financial quality / margin bridge | DELL operating income / gross margin rows 有；AI server mix、GPU pass-through、backlog conversion 缺 | `partial_fail` | Financial bridge source depth + specialist answer contract |
| Supply chain / semicap read-through | ASML/AMAT/LRCX/TSM 机制有关系图谱，但 ASML/TSM SEC manifest gaps 仍是 retrievable route gap | `partial` | FPI/company IR/local disclosure parser route + semicap playbook depth |
| Market expectation / price-in | market analyst 明确 valuation/positioning/crowding rows 缺失 | `fail` | CapitalMarketFeedback pack 未提供本 case 所需 valuation/positioning rows |
| Risk / counter-thesis | capex digestion、DELL margin dilution 进入；customer concentration、export control、substitution 仍 unsupported | `partial` | Risk source routes + product/deployment/source deepening |
| Evidence authority boundary | relationship_graph / market / industry proxy 边界基本写清楚 | `pass_as_boundary` | 后续要防止边界说明压倒判断 |
| Final memo surface | P30 / P33 old memo 均不满足 answer exemplar；旧 P33 memo 已被新 verifier 判 invalid | `fail` | Writer prompt/projection + upstream material quality |

## 4. 历史 full-chain 输出审计

### 4.1 P30 DeepSeek full-chain

P30 case 的 `real_chain_case_score` 是 pass，但用 Humanmade Gold Set 回看，不能作为 gold workpaper。

主要问题：

1. 开头判断仍是“DELL 毛利率、产品收入、资本开支、ANET 资本开支”等锚点罗列，缺少 `demand pool -> product capability -> customer deployment -> financial quality -> semicap -> price-in -> counter-thesis` 的主链条。
2. 它提到 DELL ISG revenue 和 product margin decline，但没有真正回答 AI server 对 DELL 是高质量收入还是低毛利 pass-through。
3. 产品层仍主要围绕收入/毛利，不足以回答 NVDA GB200、AMD MI300/MI35x、GOOGL TPU 的架构、benchmark、deployment 和替代边界。
4. `agent_information_economy_audit` 仍有 `prompt_pack_overlap_proxy`，说明输入传输和上下文选择在当时仍存在低效重读。

结论：P30 的 pass 是旧 gate 标准下的 pass，不是 Humanmade Gold Set 下的 pass。

### 4.2 P33 DeepSeek full-chain after Milvus available semantics fix

P33 该 full-chain run 的 `real_chain_case_score.gate_status=fail`，质量审计是 diagnostic-only。`multi_agent_output_quality_audit` 记录：

- `high_total_token_cost`
- `low_memo_chars_per_token`
- `memo_payload_not_dense_enough`
- `memo_writer_high_token_cost`
- `memo_writer_retry_cost_present`

`agent_information_economy_audit` 进一步记录：

- `memo_writer_raw_gate_or_salvage_failure`
- `prompt_pack_overlap_proxy`
- `repair_loop_agent_failure_proxy`

最终 rendered answer 开头仍然是：

```text
DELL 的资本开支是发行人自身再投资...
DELL 的产品收入提供分部收入锚点...
AMD 的收入提供基本面锚点...
MSFT 的资本开支只能说明客户/需求侧资本开支...
```

这说明它仍没有形成 humanmade gold 所要求的判断链条。它把一些正确边界写出来了，但没有先形成足够有价值的投资判断。

### 4.3 P33 old paid Memo Writer from aggregate r7

该 old paid memo 现在必须视为 invalid。旧 direct answer 仍是：

```text
MSFT/AMZN 的 capital expenditure proxy 说明需求端投入...
DELL 的 operating income/毛利率说明产品线、技术能力或经营锚点存在...
AMZN 的 issuer official context/issuer identity 提供基本面锚点...
```

这类输出的问题不是只有“写得不好”，而是：

1. 没回答 Dell AI server orders / shipments / backlog 与 ISG revenue / margin 的桥；
2. 没回答 NVDA GB200 / Blackwell、AMD MI300、GOOGL TPU 的产品竞争力；
3. 没回答 customer deployment、cloud instance、OEM configuration 这些 humanmade source ledger 中的关键证据；
4. 没回答 semicap read-through 的机制差异；
5. 没回答 market price-in，只保留了宽泛边界；
6. 新 verifier 已返回 `analyst_depth_generic_template_language` 和 `analyst_depth_direct_answer_too_thin_for_profile`。

结论：旧 paid memo 是缺陷样本，不可作为通过样本。

## 5. 逐节点流转审计

### 5.1 Research Lead

Research Lead 当前比 P30 明显进步：已经能产出 thesis path、required items 和 writer order。它能提出：

- `product_architecture_competition`
- `customer_deployment_adoption`
- `supply_chain_readthrough`
- `fundamental_financial_bridge`
- `capital_market_price_in`
- `risk_and_counterevidence`

问题在于：它仍主要定义“应该问什么”，还没有足够硬地定义“每个问题需要什么级别的证据才算 briefing-pack 合格”。例如：

- Product / Architecture 不能只需要 product slot，应要求 official spec / benchmark / cloud/OEM config；
- DELL margin bridge 不能只需要 operating income / gross margin，应要求 AI server orders/backlog -> ISG revenue/margin -> GPU pass-through / attach / cash conversion；
- Semicap 不能只要 peer/supply-chain relation，应要求 bookings/backlog/systems sold/EUV/DUV/process control/memory/foundry/logic exposure；
- price-in 不能只要 market snapshot，应要求 valuation/positioning/crowding/event reaction 或明确 typed gap。

结论：Research Lead 结构合格，但还缺 `gold_depth_evidence_contract`。

### 5.2 Evidence Fusion

Accepted artifact 显示：

- `row_count=375`
- `exact_authority_row_count=232`
- `context_only_row_count=139`
- `gap_only_row_count=4`
- `bounded_gap_count=4`
- `required_like_counts` 覆盖 `req_hyperscaler_capex=42`、`req_dell_margin_quality=99`、`req_supply_chain=75`、`req_customer_deployment=60`、`req_accelerator_architecture=10`
- `product_runtime_fact_count=0`

这就是质量问题的最早硬信号之一：required items 有 rows，但 Product / Architecture 的核心事实没有进入 runtime exact/product graph facts。`req_accelerator_architecture` 只有 context/proxy，不能支撑 gold memo 里对 GB200、MI300、TPU、benchmark、OEM config 的产品判断。

结论：Evidence Fusion 的“覆盖”不是 gold-depth 覆盖；需要从 source route / ProductIntelligenceGraph runtime facts 修。

### 5.3 Coverage Reflection

Coverage Reflection 显示：

- `sufficiency_level=partial`
- `missing_requirement_count=0`
- `quality_gap_count=1`
- `product_runtime_fact_count=0`
- `bounded_answer_allowed=true`

这个 gate 现在会放行到 specialist。它在工程上是合理的：没有 missing requirement，允许 bounded answer。但按 humanmade gold 标准，它不应该让这个 case 直接进入 writer closeout，因为 `req_accelerator_architecture` 的质量缺口会影响核心判断。

结论：Coverage Reflection 缺少 `briefing_pack_quality_gate`。它现在能判断“有没有材料”，但不能判断“这些材料够不够写一个有洞察的 analyst briefing”。

### 5.4 Specialist

Specialist composite 已经能产出 judgment candidates，且 gate 显示：

- `verification_status=pass`
- `writer_allowed=true`
- `supported_claim_count=16`
- `unsupported_claim_count=7`
- `conflict_count=1`

但按 gold set 审计，问题仍明显：

1. Product specialist 能写 NVDA Blackwell / AMD Accelerators 是 competing product generations，但证据主要是 product slots / taxonomy，缺 official specs / benchmark / deployment。
2. Product specialist 明确 GOOGL TPU architecture unsupported，说明 Google TPU source ledger 没进入 runtime。
3. Fundamental specialist 只做到 “capex demand signal + DELL operating income/gross margin”，不能闭合 AI server mix / margin bridge。
4. Industry specialist 能写 supplier-OEM-cloud 结构，但 evidence 是 relationship_graph context-only，不能证明 orders / revenue / margin。
5. Market specialist 明确 valuation/price-in/positioning/crowding rows 缺失。
6. Risk specialist 有 capex digestion 和 DELL margin dilution，但 customer concentration / export control 仍 unsupported。

这说明 specialist prompt/skill 已经不再是纯搜索摘要，但还没达到 human analyst briefing pack 的证据深度和答案风格。

结论：Specialist 的根因不只是 prompt，还包括 role-specific source packs 缺深度；但 prompt/contract 也需要从“产出 judgment candidate”升级为“产出 answer exemplar style briefing”。

### 5.5 Aggregate r7 / MemoLogicPlan

Aggregate r7 的优点：

- `supported_claim_count=26`
- `unsupported_claim_count=7`
- `conflict_count=1`
- `memo_outline_count=7`
- `judgment_card_count=14`
- `required_question_item_count=10`
- `required_item_answer_plan_count=10`

但审计发现两个问题：

1. `required_item_answer_plan` 虽然有 10 条，但部分 answer contract 仍不够语义化，不能直接指导 writer 产出 humanmade answer exemplar。
2. Aggregate 保留了 unsupported / conflict，但没有在进入 writer 前强制判断：“如果 DELL margin bridge、GOOGL TPU architecture、market price-in 仍 unsupported，这份 memo 应如何组织成有价值判断，而不是变成缺口说明？”

结论：Aggregate r7 是结构性进步，但不是 gold workpaper proof。它还需要 GoldSetAudit / BriefingPackQualityGate。

### 5.6 Memo Writer payload preflight

Writer payload preflight 通过：

- `compact_required_item_count=10`
- `compact_section_count=7`
- `compact_supported_claim_count=8`
- `known_evidence_ref_count=5`
- `approx_total_prompt_chars_with_scaffold=56016`
- `raw_rows_excluded=true`

这证明 writer input shape 已经比 evidence dump 好。但它仍只证明 payload shape，不证明 semantic quality。

风险：

1. 26 条 supported claims 被压到 8 条，可能丢掉 gold answer 所需的产品/客户/财务/风险桥；
2. 只有 5 个 known evidence refs，对 AI/Semis gold case 来说偏少；
3. prompt 大约 56k chars，仍可能产生高 token 成本；
4. payload 没有显式证明覆盖 humanmade gold answer exemplar 的关键句式和证据角色。

结论：writer payload 需要进入 HumanmadeGoldSetAudit，而不能只做 shape preflight。

## 6. 工程问题清单

1. **历史 pass 标准不一致**
   - P30 full-chain gate pass，但按 Humanmade Gold Set v0.2 明显不合格。
   - 需要把历史 artifact 标记为 `legacy_pass_not_gold_quality_pass`。

2. **artifact 命名和 source-of-truth 不够稳定**
   - Research Lead 最新 artifact 文件名是 `stepwise_node_result.json`，不是直观的 `research_lead_node_result.json`。
   - P33 program doc 路径和此前口头简称存在漂移，后续 audit runner 应读 ledger 而不是猜路径。

3. **coverage gate 粒度过粗**
   - `missing_requirement_count=0` 不代表 gold-depth sufficient。
   - `product_runtime_fact_count=0` 仍能下游，这是当前核心质量问题之一。

4. **specialist pass 不代表 briefing quality**
   - `all_outputs_have_judgment_candidates=true` 只能证明结构，不证明答案像 analyst briefing。
   - 需要新增 specialist-level gold-answer rubric。

5. **writer payload preflight 缺 semantic coverage**
   - 当前检查 raw rows excluded、sections complete、budget under max，但没有检查每个 gold answer item 是否有足够 material。

6. **available evidence / missing evidence 仍可能错位**
   - Aggregate 有 DELL gross margin / operating income，但旧 memo 仍写成泛化锚点。
   - 需要从 writer consumption 和 selected claim bridge 查原因，而不是只 fail。

7. **source routes 与 human source ledger 未打通**
   - Humanmade source ledger 里列出的 Dell FY26 Q4 8-K、Dell Q1 release、NVIDIA GB200、AMD MI300/MLPerf、Google TPU/A4X、TSMC/ASML/AMAT/LRCX official results 没有稳定进入当前 runtime exact/product/deployment/benchmark slots。

## 7. 更深层 root cause

### 7.1 数据源 / parser / source route

当前最硬的缺口不是“没有任何数据”，而是 humanmade gold case 所需的数据没有被同等深度接进 runtime：

- Dell AI-optimized server orders / shipments / backlog 没有成为本 case 中的高权重 exact operating row；
- Dell ISG revenue / margin 与 AI server orders 的桥没有被解析成 financial-quality bridge；
- NVIDIA GB200 / Blackwell、AMD MI300/MI35x、GOOGL TPU v6e/Trillium/A4X 没有进入 product spec / architecture / deployment slots；
- MLPerf / benchmark 没有进入 Product Performance Proxy；
- TSMC / ASML / AMAT / LRCX official release tables 没有进入 semicap read-through 的 exact evidence；
- market price-in 所需 valuation / positioning / holder / event reaction rows 没进入本 case。

因此不能把这些都归因于模型。模型拿到的 briefing material 本身不够 gold-depth。

### 7.2 ProductIntelligenceGraph

ProductIntelligenceGraph 已有关系边和 product slots，但当前 case 中 `product_runtime_fact_count=0`。这意味着图谱没有把产品规格、架构、benchmark、cloud/OEM config、customer deployment 映射成 writer-ready product facts。

图谱现在更像 research scope map，而不是 product intelligence proof pack。

### 7.3 Prompt / Skill

当前 specialist skill 已经比旧版好，但仍存在“回答边界多于回答判断”的问题。原因是 prompt/contract 让 specialist 产出 judgment candidate，却没有强制：

- 按 answer exemplar 风格写一个可直接进入 memo 的段落；
- 对每个 required item 给出 “judgment + mechanism + evidence role + cannot infer + what would change”；
- 在 evidence 不足时触发 source repair，而不是只写 unsupported；
- 区分 “数据源没接入 / parser 没吃到 / 公开源没有 / 商业 tracker gap”。

### 7.4 Agent 编排

Research Lead 已经会拆题，但仍缺两个关键动作：

1. 在 specialist 前，定义每个 lane 的 gold-depth evidence contract；
2. 在 specialist 后，像 supervising analyst 一样拦住 “结构完整但洞察不够” 的 briefing pack。

现在的 LeadReview 还不够硬，不能强制判断“这份材料能不能写出一个真正有价值的 workpaper”。

### 7.5 Eval

以前 eval 更偏工程结构：

- required items 是否覆盖；
- claim refs 是否存在；
- section 是否齐；
- writer payload 是否在 budget 内；
- verifier 是否识别 obvious bad output。

但 Humanmade Gold Set 需要 eval 到答案质量：

- 是否先给判断；
- 是否解释商业机制；
- 是否把产品、客户、财务、供应链、市场预期打通；
- 是否把 proxy 和 exact 边界写清楚；
- 是否把缺口归因到 source/parser/runtime/commercial boundary；
- 是否避免泛化拒答和证据清单化。

## 8. 修复顺序

当前不建议直接 paid Memo Writer 或 full-chain。下一步应按以下顺序：

1. **实现 no-paid HumanmadeGoldSetAudit runner**
   - 输入 aggregate r7、writer payload preflight、humanmade gold set JSON。
   - 输出每个 gold item 的 `pass / partial / fail`、最早 faulty layer 和 required repair。

2. **新增 BriefingPackQualityGate**
   - 在 Memo Writer 前检查每个 gold required item 的 evidence depth。
   - 如果只有 context/proxy，必须标记为 `research_quality_gap`，并要求 Lead 指定 source repair 或 typed boundary。

3. **补 AI/Semis gold source runtime ingestion**
   - Dell FY26 Q4 AI server orders / shipments / backlog；
   - Dell FY26 Q1 ISG revenue / operating income / margin；
   - NVIDIA GB200 / H100 / H200 / B200 / Blackwell architecture；
   - AMD MI300 / MI35x / MLPerf；
   - Google TPU v6e/Trillium and A4X GB200；
   - TSMC / ASML / AMAT / LRCX official release tables and semicap mechanism slots。

4. **升级 ProductIntelligenceGraph projection**
   - 增加 `technical_fact`、`architecture_generation`、`benchmark_proxy`、`cloud_instance_deployment`、`oem_configuration`、`customer_deployment_signal`、`semicap_cycle_readthrough` 等 edge/product fact roles。

5. **升级 specialist skill / contract**
   - 每个 specialist 输出不仅是 JudgmentCandidate，还要包含 `answer_exemplar_paragraph` 或等价 writer-ready briefing。
   - 缺口必须归因为 `source_not_ingested / parser_gap / runtime_projection_gap / public_boundary / commercial_gap`。

6. **升级 Research Lead post-specialist review**
   - 如果材料不能形成 humanmade gold chain，Lead 必须拦截并发起 targeted repair，不允许直接进 writer。

7. **最后才跑单节点 paid Memo Writer**
   - 只在 no-paid audit 和 quality gate 通过后，从 aggregate r7 或更新后的 accepted aggregate checkpoint 跑一个 Memo Writer node。
   - 不跑 broad full-chain，不跑 20-50 case。

## 9. 本轮没有做的事

- 没有 paid LLM 调用。
- 没有 full-chain。
- 没有模型对比。
- 没有新 crawler/parser/source ingestion。
- 没有修改 runtime 代码。
- 没有把本审计结论当成修复完成。

## 10. 当前结论

P33 当前已完成的是工程链路和方法注入的 node-level 基础，但 Humanmade Gold Set 审计显示：要形成真正高质量 AI/Semis analyst workpaper，最关键的地基仍是 `gold-depth source rows + product graph projection + specialist answer exemplar + Lead quality veto + semantic audit`。

在这些修好前，继续跑 paid full-chain 只会把已知问题重新暴露一遍，并继续烧 token。
