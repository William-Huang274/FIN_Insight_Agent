# KG / Sub-agent / Graph Upgrade Checkpoint

日期：2026-06-13

## 触发

用户要求按 `08_legacy_planning_docs_absorption_and_data_governance_plan.zh-CN.md` 的下一阶段建议顺序继续推进，并要求过程中及时落 checkpoint 文档、持续对照 07 / 08 文档规划和门控，避免偏离方向。

## 不偏离的主线

本轮不是继续横向堆公开源，也不是放宽 source gate 来提高覆盖。执行顺序固定为：

1. Full P/K：把 minimal P0/K1/K2/K3 扩成完整 KG Matrix Registry、ProductModel / ProductSpec / ProductGenerationEdge / CompetitiveComparableEdge / ChannelOffer / FieldInquiryNote。
2. Product / Technology sub-agent：把专家 agent 升级为次级 agent，输出 `ProductSpecPack` + gated `ClaimCards`。
3. Capital / Ownership 和 Macro Exposure：补 debt / offering / ownership / macro driver edges，但继续保持公开源 / 商业源 / gap 边界。
4. Agent graph / skill：回到反思插入点、联网工具权限、Research Lead planning skill、专家 skill、共享上下文和 async/sync 协作机制。
5. D-series DB hardening：在 full P/K 结构稳定后，补 D3 true SQL-backed resolver、D4 object-store provenance / before-after diff、D5 real vintage stores、D11 vector / graph memory parity。

## 阶段门控

### K1-K3 Full P/K Registry

通过条件：

- KG registry 明确 Operating KG、Capital / Ownership Graph、Macro / Industry Driver Graph、Evidence / Claim / Gap Layer 的 node / edge schema。
- Product spec ontology 明确 ProductFamily、ProductModel、ProductSpec、ProductGenerationEdge、CompetitiveComparableEdge、ChannelOffer、FieldInquiryNote。
- ChannelOffer 只能支持 price / availability / configuration / lead-time context，不能支持 sales、sell-through、market share、company ASP 或 channel inventory。
- FieldInquiryNote 只能作为 analyst / user provided lead，不能作为权威事实。
- `public_buyer_observer` policy 明确 allowed source classes 和 forbidden actions。

### K4 Product / Technology Sub-agent

通过条件：

- Product / Technology sub-agent 输出 `ProductSpecPack`，且 spec / generation / comparable / channel / inquiry 都带 source、time、region、claim boundary。
- 只允许 parser/gate 后对象进入 ClaimCard；raw web / Milvus chunk / search snippet 不得直接进入 ClaimCard。
- 没有 comparable dimension 时不能输出竞品判断。

### K5-K6 Capital / Ownership / Macro

通过条件：

- CapitalStructure / DebtInstrument / CreditFacility / EquityOffering / OwnershipPosition / InsiderTransaction 带 period、source、lag / maturity / coupon / rate type。
- MacroDriver 必须经 CompanyExposureToDriver 才能进入公司 thesis，禁止 macro -> company conclusion 直连。
- 13F 必须标注 report_period、filing_date、lag_days、not_realtime_flag。

### K7-K8 Gates And E2E

通过条件：

- Verifier / reflection gates 覆盖 product page != sales、channel offer != sell-through、13F != realtime flow、macro != company fact、patent != commercial success、FieldInquiryNote != authority fact。
- 10-20 case KG sub-agent eval 覆盖产品规格、代际比较、竞品比较、资本结构、持仓、宏观 exposure、公开采购视角。

### D Hardening

通过条件：

- DB hardening 不在 KG schema 未稳定前抢跑。
- D3/D4/D5/D11 hardening 必须保留 D-series closeout 既有 gates，不允许用 DB fallback 绕过 evidence governance。

## 当前 checkpoint

- 基线提交：`04894f7 Close D-series runtime governance loop`。
- 当前工作树进入本阶段前干净。
- 第一段执行对象：K1-K3 Full P/K registry，优先扩展现有 `kg_minimal_registry` 而不是另起孤立配置，以保持 D7/D8 source boundary 兼容。

## 2026-06-13 K1-K4 执行 checkpoint

### 已完成

- 新增 full `KG Matrix Registry v0.1`：
  - 覆盖 Operating KG、Capital / Ownership Graph、Macro / Industry Driver Graph、Evidence / Claim / Gap Layer 和 workflow runtime layer。
  - 把 ProductFamily、ProductModel、ProductSpec、ProductGenerationEdge、CompetitiveComparableEdge、ChannelOffer、FieldInquiryNote 纳入机器可读 node / edge schema。
  - 保留 minimal P0/K1/K2/K3 derived view，继续兼容 D7 Metric / Product Ontology 与 D8 Source Capability Router。
- 新增 `ProductSpecPack v0.1`：
  - 从 product evidence / public source context / live web context rows 生成 ProductFamily、ProductModel、ProductSpec、ProductKPI refs、ProductGenerationEdge、CompetitiveComparableEdge、ChannelOffer、FieldInquiryNote、commercial gaps 和 rejected objects。
  - ChannelOffer 固定为 price / availability / configuration / lead-time context；任何 exact authority、sell-through、market share、company ASP、channel inventory 提权尝试都会被拒绝。
  - FieldInquiryNote 固定为 qualitative lead / verification lead；禁止 authority fact。
  - CompetitiveComparableEdge 没有 comparable dimensions 时拒绝生成。
- Product / Technology Specialist 升级为 sub-agent contract：
  - `AgentDataView` 给 `product_technology_analyst` 注入 `product_spec_pack` 和 compact ref。
  - Specialist request / prompt 透传 ProductSpecPack，并把 pack 内 evidence refs 纳入可引用集合。
  - Product skill 明确 ProductSpecPack、ChannelOffer、FieldInquiryNote 和 commercial gap 使用边界。
  - 修复 product-only activation 未触发 specialist subgraph 的路由遗漏。
- 新增 `CapitalMacroExposurePack v0.1`：
  - 从 capital / ownership / macro / public vertical rows 生成 CapitalStructure、DebtInstrument、CreditFacility、EquityOffering、OwnershipPosition、InsiderTransaction、MacroDriver、TradeDriver、IndustryDriver、CompanyExposureToDriver 和 VerticalOfficialObject。
  - OwnershipPosition / 13F 必须带 report period、filing date、lag days、`not_realtime_flag`；realtime flow 提权直接拒绝。
  - MacroDriver / TradeDriver / IndustryDriver 默认 context-only；公司 thesis 只能通过 CompanyExposureToDriver bridge 连接。
  - VerticalOfficialObject 只能作为 official object context，不能直接证明 product sales、company revenue、commercial success。
- Fundamental / Industry / Risk Specialist 接入 `capital_macro_pack`：
  - `AgentDataView` 只在有相关输入行时注入 pack 和 compact ref。
  - Specialist request / prompt 把 pack refs 纳入 known evidence refs。
  - Shared evidence skill 明确 13F lag、macro exposure bridge 和 vertical official object 边界。
- K7 verifier / repair boundary 已接入：
  - product page / public proxy 不能支持 product sales 或 product KPI fact。
  - ChannelOffer 不能支持 sell-through、market share、channel inventory。
  - FieldInquiryNote 不能写成 authority fact。
  - ownership filing 不能写成 realtime flow。
  - macro / public / Milvus context 不能写成 company revenue / sales / margin / commercial success。

### 当前通过测试

- `python -m py_compile src\sec_agent\product_spec_pack.py src\sec_agent\multi_agent_runtime.py src\sec_agent\specialist_llm.py src\sec_agent\langgraph_orchestrator.py`
- `pytest -q tests\test_product_spec_pack.py tests\test_kg_matrix_registry.py tests\test_kg_minimal_registry.py`：`10 passed`
- `pytest -q tests\test_metric_product_ontology_reconciliation.py tests\test_entity_master_source_capability_router.py`：`11 passed`
- `pytest -q tests\test_multi_agent_evidence_requirements.py tests\test_multi_agent_specialist_llm.py`：`70 passed`
- `pytest -q tests\test_multi_agent_langgraph_routing.py tests\test_multi_agent_agent_registry.py tests\test_research_skills.py`：`38 passed`
- `pytest -q tests\test_multi_agent_activation_plan.py tests\test_multi_agent_research_lead_llm.py tests\test_multi_agent_routing_fixtures.py`：`44 passed`
- `python -m py_compile src\sec_agent\capital_macro_pack.py src\sec_agent\multi_agent_runtime.py src\sec_agent\specialist_llm.py src\sec_agent\multi_agent_contracts.py`
- `pytest -q tests\test_capital_macro_pack.py tests\test_product_spec_pack.py`：`7 passed`
- `pytest -q tests\test_multi_agent_contracts.py tests\test_multi_agent_judgment_memo_verifier.py`：`33 passed`
- `pytest -q tests\test_multi_agent_evidence_requirements.py tests\test_multi_agent_specialist_llm.py tests\test_multi_agent_langgraph_routing.py`：`94 passed`
- `pytest -q tests\test_multi_agent_agent_registry.py tests\test_multi_agent_activation_plan.py tests\test_multi_agent_research_lead_llm.py tests\test_multi_agent_routing_fixtures.py tests\test_research_skills.py`：`58 passed`
- `pytest -q tests\test_kg_matrix_registry.py tests\test_kg_minimal_registry.py tests\test_metric_product_ontology_reconciliation.py tests\test_entity_master_source_capability_router.py tests\test_gate_registry_eval_matrix.py tests\test_capital_macro_pack.py tests\test_product_spec_pack.py`：`27 passed`
- `git diff --check`：pass
- `pytest -q`：`880 passed`

### 未完成，不得提前兜底

- K5 已完成 runtime edge-pack gate，但 source-specific parser/backfill 仍未补：SEC debt footnote、offering、13F、13D/G、Form 3/4/5、proxy parser 需要在后续把真实 row 映射到 pack 输入。
- K6 已完成 runtime edge-pack gate，但 source-specific parser/backfill 仍未补：FRED/EIA/Census/FDIC/ClinicalTrials/openFDA/NHTSA/PatentsView/OpenAlex 等需要按行业 adapter 映射，不得直接给公司结论。
- K8 10-20 case KG sub-agent E2E gate 尚未跑。
- D3/D4/D5/D11 DB hardening 继续等待 full P/K + K5/K6 parser/backfill 稳定后再补；当前不得用 DB fallback 绕过 pack/verifier gates。

## 回滚与安全

- 不写 `.env`、raw data、Milvus index 或大体量运行输出。
- 所有新增 source policy 都必须保留 commercial gap，不得把公开 proxy 提权。
- 每个阶段至少跑 targeted tests；跨 graph 变更后跑 multi-agent / D-series 相关回归。
