# 420 R46 Lead Dimension Evidence Portfolio

日期：2026-06-27

## 背景

在 RD0-RD7、ProductIntelligenceGraph v0.1、ProductEvidencePack v0.2 和 AI/Semis strict follow-up 之后，数据和图谱已经不再只是散装 SEC/RAG rows。但原 agent graph 仍存在一个结构性问题：Research Lead 首轮分派后，对后续 specialist 是否真正消费了数据基座、哪些维度已有 pack 但没有 ClaimCard 承接、哪些缺口应该 targeted repair，缺少统一审计对象。

本轮目标不是重写 graph，而是把 Research Lead 升级为持续监督节点的 runtime contract 补上。

## 改动

- 新增 `src/sec_agent/dimension_evidence_portfolio.py`。
- 生成 `DimensionEvidencePortfolio`，按以下维度组织证据：
  - `fundamentals`
  - `product_and_production`
  - `capital_and_financing`
  - `competition_and_market_position`
  - `industry_supply_chain`
  - `risk_and_counterevidence`
- 每个维度记录：
  - 可用 pack refs；
  - 缺失 pack refs；
  - evidence roles；
  - lead questions；
  - repair triggers；
  - promotion boundary。
- 接入 `supervising_analyst_pack`：
  - `dimension_evidence_portfolio`
  - `dimension_evidence_portfolio_ref`
  - `ResearchLeadSynthesisPlan.dimension_evidence_portfolio_ref`
- 接入 `build_agent_data_view`：
  - Research Lead 获取全维度 compact portfolio；
  - Product / Fundamental / Market / Supply-chain / Risk specialist 只获取 role-scoped ref。
- 接入 `LeadReviewCheckpoint`：
  - checkpoint 持有 `dimension_evidence_portfolio_ref`；
  - 如果某维度已有 available pack ref 但没有 ClaimCard 承接，状态变为 `retrievable_gap`，而不是直接 `bounded_gap` 或 `not_material`。
- 接入 `MemoLogicPlan`：
  - memo plan 持有 compact portfolio ref；
  - 每个 section 可看到 dimension pack refs 和 lead questions；
  - Memo Writer 仍禁止 raw retrieval / database / web / tool rows。

## 关键边界

- `Product-KPI exact` 不放宽：只有 `value/unit/period/product/citation` 的公司披露或 source-specific parser row 能证明产品经营 exact fact。
- 产品规格、架构、客户部署、benchmark、渠道可得性、供应链和竞品关系是独立 evidence roles，可以进入 bounded thesis driver，但不能证明 SKU revenue、shipment、ASP、share、sell-through、backlog 或 order value。
- `DimensionEvidencePortfolio` 本身不提权新事实，只暴露 Research Lead 应该如何监督、追问和 repair。

## 验证

- `python -m py_compile src/sec_agent/dimension_evidence_portfolio.py src/sec_agent/supervising_analyst.py src/sec_agent/multi_agent_runtime.py src/sec_agent/lead_supervision.py src/sec_agent/memo_logic_plan.py src/sec_agent/langgraph_orchestrator.py`
- `python -m pytest tests/test_dimension_evidence_portfolio.py tests/test_supervising_analyst_pack.py -q`
  - `7 passed`
- `python -m pytest tests/test_ai_semis_product_evidence_pack.py tests/test_runtime_bridge_contracts.py tests/test_source_authority_coverage.py -q`
  - `21 passed`
- `python -m pytest tests/test_multi_agent_langgraph_routing.py tests/test_public_web_gap_repair.py -q`
  - `43 passed`

## 剩余边界

- 本轮还没有跑 full-chain LLM case；它只完成 Research Lead / specialist / LeadReview / MemoLogicPlan 的 deterministic contract 接线。
- 下一轮 full-chain 应重点观察：
  - Research Lead 是否真的针对 available-pack-but-no-claim 的维度触发 repair 或 specialist retry；
  - Product section 是否能使用 spec / architecture / deployment / relationship graph，而不是只盯 Product-KPI exact；
  - Memo Writer 是否完全按 MemoLogicPlan 写自然语言判断，不再输出内部字段或 gap-first 安全话术。
