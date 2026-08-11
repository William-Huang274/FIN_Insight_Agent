# 109 P34 Lane Quality-First Source Runtime Program

日期：2026-07-07

## 背景

P33 gold-set source-runtime backfill 证明了一个关键问题：项目不是没有数据，而是很多数据没有按投研判断所需的 exact slot 和 judgment chain 组织。严格回填后只有 `4/68` 条 rows 可以安全作为 live runtime ready；其余要么是 AI/Semis weak candidate，要么是 rubric case 尚未 issuer/lane binding，要么只是 failure fixture。

因此 P34 不继续先堆 parser 或跑模型，而是先定义每个 lane 的 research quality rubric，再倒推 judgment chain、evidence slot、source route/parser 和 runtime promotion。

## 本轮完成

1. 新增 P34 source-of-truth 文档：
   - `docs/internal/vnext_20260610/p34_lane_quality_first_source_runtime_program.zh-CN.md`
   - `docs/internal/vnext_20260610/p34_ai_semis_quality_artifacts_v0_1.zh-CN.md`

2. 新增 AI/Semis LaneResearchQualityRubric v0.1：
   - `docs/project_os/p34_ai_semis_lane_research_quality_rubric_v0_1.json`
   - 覆盖 demand pool、product architecture、customer deployment、DELL financial quality、supply-chain read-through、market price-in、counter-thesis 七类问题。

3. 新增 AI/Semis RequiredJudgmentChainRegistry v0.1：
   - `docs/project_os/p34_ai_semis_judgment_chain_registry_v0_1.json`
   - 覆盖 `jc_ai_capex_demand_pool`、`jc_accelerator_architecture_competition`、`jc_customer_deployment_oem_adoption`、`jc_dell_ai_server_financial_quality`、`jc_foundry_semicap_readthrough`、`jc_market_price_in_capital_feedback`、`jc_counter_thesis_what_would_change`。

4. 新增 AI/Semis EvidenceSlotContractMapping v0.1：
   - `docs/project_os/p34_ai_semis_evidence_slot_contract_mapping_v0_1.json`
   - 将 P33 live-source backfill 的 20 条 AI/Semis rows 全部映射到 judgment chain、quality role、required fields、source route family、promotion rule 和 cannot-infer boundary。

5. 新增 focused contract test：
   - `tests/test_p34_lane_quality_first_program.py`
   - 当前结果：`4 passed`。

## 当前边界

这些产物只是 quality contract documented，不是：

- live source readiness；
- adapter/parser pass；
- Research Lead runtime injection；
- specialist pass；
- Memo Writer pass；
- full-chain pass；
- 模型对比。

P34 下一步必须先做 AI/Semis SourceRoutePlan，再做前三个 adapter-family fixture，最后跑 P34 no-paid quality audit。
