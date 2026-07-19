# P34 AI/Semis Quality Artifacts v0.1

日期：2026-07-07

状态：`no_paid_quality_audit_blocked_live_route_attempt_and_quality_gaps_pending`

## 1. 本文档说明

本文档记录 P34 当前已经落下的机器可读合同、route plan、adapter fixture 和 no-paid quality audit：

1. AI/Semis LaneResearchQualityRubric v0.1。
2. AI/Semis RequiredJudgmentChainRegistry v0.1。
3. AI/Semis EvidenceSlotContractMapping v0.1。
4. AI/Semis SourceRoutePlan v0.1。
5. AI/Semis AdapterFixtureReport v0.1。
6. AI/Semis No-paid Quality Audit v0.1。

这些 artifacts 不是 live source readiness，也不是 full-chain pass。它们的作用是把“研究质量”放在 source route/parser 之前，防止后续只追求 row 数和 parser pass。当前 P34-6 结果为 blocked，说明 paid Memo Writer / full-chain 仍不得运行。

## 2. Artifacts

### 2.1 LaneResearchQualityRubric

路径：

```text
docs/project_os/p34_ai_semis_lane_research_quality_rubric_v0_1.json
```

核心要求：

- AI capex 只能先证明 demand pool，不能直接证明 supplier allocation。
- 产品层即使没有 SKU revenue，也要从架构、规格、benchmark、deployment、OEM config、供应瓶颈和竞品替代形成 bounded judgment。
- DELL AI server 必须分开写 revenue visibility 和 margin quality。
- Semicap read-through 必须拆 ASML / AMAT / LRCX / KLAC 的不同机制。
- Market price-in 必须有 capital-feedback pack。

### 2.2 RequiredJudgmentChainRegistry

路径：

```text
docs/project_os/p34_ai_semis_judgment_chain_registry_v0_1.json
```

首批 7 条 judgment chains：

1. `jc_ai_capex_demand_pool`
2. `jc_accelerator_architecture_competition`
3. `jc_customer_deployment_oem_adoption`
4. `jc_dell_ai_server_financial_quality`
5. `jc_foundry_semicap_readthrough`
6. `jc_market_price_in_capital_feedback`
7. `jc_counter_thesis_what_would_change`

这些 chain 后续必须进入 Research Lead / Specialist / JudgmentCard / MemoLogicPlan 的 runtime 消费点。当前状态只是 contract documented。

### 2.3 EvidenceSlotContractMapping

路径：

```text
docs/project_os/p34_ai_semis_evidence_slot_contract_mapping_v0_1.json
```

覆盖 P33 live source backfill 里的 AI/Semis 20 条 rows。当前状态：

- `20/20` 已映射到 judgment chain。
- `4` 条仍为 strict `live_runtime_ready`。
- `1` 条为 parser lineage pending。
- `13` 条为 weak candidate。
- `2` 条需要 basket / issuer binding。

关键变化：每条 row 不再只记录 parser status，而是记录：

- quality role；
- strong / medium / proxy evidence；
- forbidden substitutes；
- required fields；
- source route family；
- promotion rule；
- cannot infer；
- next action。

### 2.4 SourceRoutePlan

路径：

```text
docs/project_os/p34_ai_semis_source_route_plan_v0_1.json
docs/internal/vnext_20260610/p34_ai_semis_source_route_plan_v0_1.zh-CN.md
```

当前结果：

- `20` 个 evidence slots。
- `47` 条 source routes。
- `20` 条 primary routes。
- `27` 条 fallback routes。
- `20/20` slots 有 primary route。
- `20/20` slots 有 fallback route。
- `0` 个 route gap。
- `15` 类 adapter family。

边界：

- SourceRoutePlan 只证明 slot 到 route / adapter family 的规划完整。
- 它不证明 source 已抓取、网页/PDF 已解析、parser lineage 已存在、runtime row 可提权、Research Lead / specialist 已消费，也不证明 paid memo 或 full-chain 质量。

### 2.5 AdapterFixtureReport

路径：

```text
docs/project_os/p34_ai_semis_adapter_fixture_report_v0_1.json
docs/internal/vnext_20260610/p34_ai_semis_adapter_fixture_report_v0_1.zh-CN.md
```

当前结果：

- adapter family：`3`
- fixture：`9`
- runtime rows：`9`
- rejected candidates：`9`
- typed gaps：`0`
- rows with parser lineage：`9`
- rows with authority scope：`9`

首批 adapter family：

1. `sec_8k_earnings_release_table_adapter`
2. `official_product_spec_page_adapter`
3. `semicap_bookings_backlog_adapter`

边界：

- 这是 parser contract fixture pass，不是 live fetch / crawler / parser 全量验收。
- 当前 runtime rows 只能证明字段合同、parser lineage 和 cannot-infer boundary 可以生成。
- 这些 rows 不能直接进入 live evidence bundle；下一步必须接真实 source route attempts，或生成 attempt-backed typed gaps。

### 2.6 No-paid Quality Audit

路径：

```text
docs/project_os/p34_ai_semis_no_paid_quality_audit_v0_1.json
docs/internal/vnext_20260610/p34_ai_semis_no_paid_quality_audit_v0_1.zh-CN.md
```

当前结果：

- status：`blocked_live_route_attempt_and_quality_gaps_pending`
- judgment_chain_count：`7`
- chain_pass_count：`0`
- chain_partial_count：`4`
- chain_fail_count：`3`
- source_route_gap_count：`0`
- adapter_fixture_runtime_row_count：`9`
- allow_paid_memo_writer：`false`
- allow_full_chain：`false`

质量结论：

- route plan 完整不等于研究质量通过。
- adapter fixture contract 通过不等于 live source/parser readiness。
- 当前缺的不是更多模型调用，而是 live route attempts、attempt-backed typed gap、cloud capex、market price-in、counter-thesis 和 customer deployment/OEM configuration 的 source-runtime 闭合。

## 3. 当前边界

未做：

- 未做 live source fetch / crawl / rendered-page parsing。
- 未把 fixture rows 接入真实 source route attempts。
- 未把 unresolved rows 关闭为 attempt-backed typed gaps。
- 未运行 paid LLM。
- 未运行 full-chain。
- 未运行模型对比。
- 未将 P34 artifacts 注入 Research Lead / Specialist / JudgmentCard runtime。
- 未获得 P34 no-paid quality audit pass。

下一步：

1. 把首批 3 个 adapter fixture 接到真实 source route attempts，或记录 attempt-backed typed gaps。
2. 补 cloud capex demand-pool、customer deployment/OEM config、market price-in/capital feedback、counter-thesis route rows。
3. 重新运行 P34 no-paid quality audit；通过前继续禁止 paid writer / full-chain / model comparison / case expansion。
