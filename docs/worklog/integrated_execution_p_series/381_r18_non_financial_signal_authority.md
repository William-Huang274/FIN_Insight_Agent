# 381 R18 Non-Financial Signal Authority

日期：2026-06-22

## 问题

R15-R17 把 exact-slot、source-role、Product-KPI、ProductFamilyEvidence 和 R17 canary 做实后，新的质量瓶颈变成了 authority 口径过窄：系统几乎只把“能否作为财务 exact fact”当成提权标准，导致产品规格、客户部署、供应链、行业经营、监管、宏观和市场预期等强信号被压成 context/gap。

用户要求先把数据基座问题做清楚：除财务事实外的信息源渠道也要有专门提权机制，不能让产品、宏微观基本面、行业数据和供应链证据都被财务事实 gate 压制。

## 决策

不降低财务 exact gate，新增独立的 `NonFinancialSignalAuthority`：

- `ExactFactAuthority`：仍只支持财务 exact、产品收入、销量、ASP、份额、sell-through、backlog、订单金额等强事实。
- `NonFinancialSignalAuthority`：标记技术规格、代际、benchmark、客户部署、生态、供应链、监管、行业经营、宏观和市场预期信号。
- `ThesisDriverAuthority`：可信源 + 实体绑定 + citation + claim boundary 通过时，非财务信号可以支撑 bounded thesis driver，但不能冒充 exact KPI。

## 已完成

新增代码：

- `src/sec_agent/non_financial_signal_authority.py`
  - `classify_non_financial_signal_authority`
  - `attach_non_financial_signal_authority`
  - `validate_signal_claim_authority`

更新 runtime：

- `src/sec_agent/runtime_source_context_store.py`
  - selected product/public rows 自动补 `non_financial_signal_authority`
  - summary 增加 `by_signal_authority_type`、`by_signal_promotion_level`、`thesis_driver_authority_row_count`

更新 R17 rows：

- `scripts/data_expansion/build_r17_product_family_evidence_rows.py`
  - R17 product/spec/deployment/operating metric rows 物化时直接带 signal authority 字段
  - strict 重建后 `runtime_row_count=24`，`thesis_driver_authority_row_count=24`

更新 graph/prompt：

- `src/sec_agent/specialist_llm.py`
  - Specialist prompt 明确 `thesis_driver_authority=true` rows 可以支撑 bounded non-financial thesis driver
  - bounded rows 透传 signal 字段
  - Product/Technology requirement 从“public proxy rows stay context/gap”改为“不能 exact，但强信号必须转成产品/技术/需求 proxy insight”
- `src/sec_agent/multi_agent_contracts.py`
  - ClaimCard / ThesisDriverPack 保留 `signal_authority_type`、`signal_promotion_level`、`thesis_driver_authority`、`allowed_non_financial_claims` 和 `claim_boundary`

更新文档：

- `docs/architecture/agent_graph_vnext/23_non_financial_signal_authority_and_multidimensional_research_basis.zh-CN.md`
- `docs/architecture/agent_graph_vnext/README.zh-CN.md`
- `docs/internal/vnext_20260610/vertical_lanes/r17_product_family_evidence.zh-CN.md`

新增/更新测试：

- `tests/test_non_financial_signal_authority.py`
- `tests/test_runtime_source_context_store.py`
- `tests/test_r17_product_family_evidence_rows.py`
- `tests/test_multi_agent_contracts.py`

## 验证

已运行：

```powershell
python -m pytest tests\test_non_financial_signal_authority.py tests\test_runtime_source_context_store.py tests\test_r17_product_family_evidence_rows.py tests\test_multi_agent_contracts.py -q
python scripts\data_expansion\build_r17_product_family_evidence_rows.py --strict
```

结果：

- targeted pytest：`46 passed`
- R17 strict：`status=pass`
- R17 signal authority 分布：
  - `technical_fact=10`
  - `technical_benchmark_signal=2`
  - `technical_generation_signal=1`
  - `customer_deployment_signal=2`
  - `ecosystem_deployment_signal=1`
  - `industry_operating_signal=7`
  - `business_mix_signal=1`
  - `thesis_driver_allowed=24`

## 2026-06-22 数据源基座讨论补充

本轮继续收敛了数据源层问题：`NonFinancialSignalAuthority` 只是第一步，下一阶段需要扩展 source route 本身，而不是只沿用现有 SEC/官网/监管/公开 API。

新增数据源吸收框架已写入 `docs/architecture/agent_graph_vnext/23_non_financial_signal_authority_and_multidimensional_research_basis.zh-CN.md`：

- 事实锚点层：SEC/XBRL、公司 IR、local exchange、年报、earnings release、transcript。
- 公司经营层：产品页、datasheet、pricing、status page、developer docs、App Store、GitHub/npm/PyPI/HuggingFace、ATS、公开采购、渠道 SKU。
- Leading signal 层：新架构、benchmark、良率/产能、客户部署、供应链 ramp、云实例/OEM 配置、数据中心建设、产业会议和可信财经/产业媒体。
- 行业/宏观/周期层：FRED/BLS/BEA/Census/EIA/FDIC、行业协会、监管统计。
- 垂直行业专用层：半导体、SaaS、医药、汽车、金融、零售、工业/能源等不同 source pack。
- 技术/IP/论文层：PatentsView/USPTO、OpenAlex、论文、标准组织、benchmark、开源生态。
- 资本/融资/持仓/市场流动性层：debt footnote、credit agreement、offering、working capital、13F/13D/13G/Form 4、DEF 14A、N-PORT、buyback、short interest、rates、credit spread、ETF/factor flows。
- 商业 tracker 缺口层：IDC/Gartner/Omdia、IQVIA、S&P Mobility、Circana/NielsenIQ、Sensor Tower/data.ai、consensus/revision。

当前进度复盘：

- 已完成：R15-R17 的 exact-slot/source-role/Product-KPI/R17 canary 和 R18 `NonFinancialSignalAuthority` 最小 runtime 合同。
- 未完成：SourceRouteRegistry v2、LeadingSignalSourceLayer、Capital/Funding/Ownership/MarketLiquidityLayer、全量 L2/L3 signal authority mapping、Research Lead signal coverage consumption、full-chain signal-aware eval。

本轮没有跑新增代码测试；这是文档和规划收敛。

## 2026-06-23 专业研报范式补充

用户要求回到投研流程，思考顶级投行/成熟买方研报中值得吸收的结构、关系图谱和信息源。已将新增内容写入 23 文档：

- 报告组织对象：`InvestmentDebate`、`VariantPerception`、`DriverTree`、`CatalystPath`、`ScenarioAndSensitivity`、`RiskRewardMap`、`ValuationBridge`、`SourceConfidenceLedger`。
- 研报工作流源：consensus/estimate/revision、company access / management read、channel checks / primary research、industry KPI model、peer/comp set source、ownership/flow/positioning、alternative / leading data。
- 成熟关系图谱：issuer/security/entity、industry taxonomy、segment revenue exposure、product/technology、customer/supplier/partner、capital structure/instrument、ownership/flow、estimate/expectation、catalyst/event、macro factor exposure、risk/regulatory/legal、governance/incentive。
- Agent 输出标准：Research Lead 先产出 `InvestmentDebateContract`；specialists 输出 dimension model；Memo Writer 按“核心判断 -> 为什么现在重要 -> 驱动证据 -> 预期差 -> 估值情景桥 -> 反证/缺口/触发”组织。

参考的公开框架和商业数据形态包括 CFA report essentials / independence-objectivity practice、GICS、SASB industry metrics、FactSet RBICS/Revere、LSEG I/B/E/S、S&P Global / Visible Alpha KPI guides。商业源只进入 source taxonomy 和 commercial gap 设计，不代表当前公开源策略会直接接入。

## 2026-06-23 公开成熟机构研报抽样复盘与下一阶段规划

用户进一步要求不要只参考 CFA 教材式框架，而要看成熟机构真实报告能教给本项目什么。本轮抽样了可公开访问的成熟机构材料，并把结论补入 23 文档：

- Goldman Sachs `Top of Mind`：有效点是 debate-first / question-led，而不是先堆资料。对应新增 `TopOfMindQuestionSet` 和 Research Lead 的 `InvestmentDebateContract`。
- Morgan Stanley `Bridging a $1.5tr Data Center Financing Gap`：有效点是把 AI demand、hyperscaler capex、operating cash flow、credit/private credit/ABS/CMBS 和 ROI risk 连接成资金桥。对应新增 `CapexFundingBridge` 和 `CustomerSpendingCapacityGraph`。
- Morgan Stanley `The Humanoid 100`：有效点是主题 -> 价值链 -> public equities paths to expression，并区分当前参与、潜在参与、受益层级和流动性。对应新增 `ThemeToExpressionGraph`、`BeneficiaryAndEnablerMap`、`ExposureConfidence`。
- UBS `House View March 2026`：有效点是 bull/base/risk case、capex / operating cash flow、外部融资、资产类别波动和 sector risk-reward。对应强化 `ScenarioAndSensitivity`、`RiskRewardMap`、`ValueChainLayerMap`。
- Morgan Stanley Asia Research / AlphaWise：有效点是 primary research、survey、web intelligence、quant/data visualization 补宏观统计看不到的分布压力。公开源策略下只能用合法公共 proxy 模拟这种形态，并进入 `SourceConfidenceLedger`。

23 文档同时新增了下一阶段实施规划，顺序为：

1. Phase 0：冻结当前可用事实基线，生成 R18 capability snapshot，防止后续实现偏离当前已验证事实。
2. Phase 1：把 R17 canary 的 `NonFinancialSignalAuthority` 扩展到全量 L2/L3 runtime rows。
3. Phase 2：建设 `SourceRouteRegistry v2`，统一 8 层数据源、source role、claim scope、parser/verifier 和 authority boundary。
4. Phase 3：先落 AI infra / semis `LeadingSignalSourceLayer`，覆盖产品架构、benchmark、良率/产能、客户部署、供应链 ramp、capex buildout、市场预期和技术生态。
5. Phase 4：落 `Capital / Funding / Ownership / Market Liquidity Layer`，补资金桥、营运资本、负债结构、持仓/资金流和市场流动性。
6. Phase 5：扩展主题到投资表达的 KG：`ThemeToExpressionGraph`、`ValueChainLayerMap`、`BeneficiaryAndEnablerMap`、`ExposureConfidence`、`EstimateExpectationGraph`、`CatalystEventGraph`、`BusinessRevenueExposureGraph`。
7. Phase 6：升级 Research Lead / Specialist / Memo 合同，让 Research Lead 像 supervising analyst 一样监督 debate、source coverage、targeted repair 和 MemoLogicPlan。
8. Phase 7：补 signal-aware full-chain eval gate，重点检查 judgment density、caveat overuse、signal-to-thesis、dimension balance、source boundary 和 valuation/funding bridge。

这次是文档和规划更新，没有把上述 Phase 0-7 误标为已实现。

## 2026-06-23 数据源 / Adapter / Parser 准入硬化

用户指出 23 文档如果只写需要的数据源和下一阶段方向，仍可能把公开源下的半成品数据拉进 runtime，尤其是 AI 行业 first tranche。已把这一点补入 23：

- 新增 `Data Source / Adapter / Parser 准入矩阵`，把已有和待接 source roles 映射到 adapter/parser/verifier/authority mapper 要求。
- 明确 `runtime_ready`、`planning_only`、`lead_only`、`final_boundary` 四类状态。
- 明确 URL、snippet、search result、blocked page、seed、attempt-only rows 不能进入 ClaimCard 或 specialist evidence bundle。
- 明确当前已有基础：SEC/FSD/company-reported Product-KPI、non-US L1/local disclosure、official product surface、R17 product-family evidence、USAspending、ATS/hiring、developer ecosystem、CDW/channel、official API context、regulated product context、trusted news smoke 等。
- 明确当前仍需要做细的 source routes：cloud instance / OEM configuration、Digi-Key/Mouser/Arrow/Amazon/JD/official store、supplier/customer official news、benchmark allowlist、PatentsView/assignee resolver、hyperscaler capex / customer spending bridge、local exchange / IR PDF table parser。
- 新增 AI / Semis 首批 source-route 接入门槛：GPU/accelerator、foundry/advanced packaging、memory/HBM、semicap、networking/server OEM/power-cooling、EDA/IP 每个子领域必须有 required source roles、最低 parser-backed runtime rows 和失败状态。
- CG-18-11/12/15 已同步到 master checklist，要求 `accepted_row_without_route_contract_count=0`、`accepted_row_without_parser_or_verifier_count=0`、`unbound_row_count=0`、`url_or_snippet_promoted_count=0`、`forbidden_claim_violation_count=0`。

这次仍是文档和规划硬化，没有运行数据接入脚本或 full-chain。下一步真正实现时，应先做 Phase 0 capability snapshot，再做 SourceRouteRegistry v2 / readiness matrix，最后进入 AI/Semis first tranche。

## 2026-06-23 R18 Data Source Admission Ledger v0.1

按用户建议，本轮把数据源处理阶段升级为正式台账，而不是只依赖 coverage summary。新增脚本和产物：

- 脚本：`scripts/data_expansion/build_r18_data_source_admission_ledger.py`
- 明细：`data/manifests/r18_data_source_admission_ledger_v0_1.jsonl`
- 摘要：`data/manifests/r18_data_source_admission_ledger_summary_v0_1.json`
- 报告：`docs/internal/vnext_20260610/r18_data_source_admission_ledger.zh-CN.md`
- 测试：`tests/test_r18_data_source_admission_ledger.py`

台账来源：

- `company_public_source_coverage_matrix_v0_1`
- `exact_slot_coverage_matrix_v0_1`
- `source_route_attempt_ledger_v0_1`
- `vertical_source_lane_registry_v0_1`

台账粒度为 `company x source_role x source_id`，字段覆盖支撑面、是否公司特定、公司名称、行业 lane、数据来源、数据概括、是否可得、adapter/parser/verifier 状态、binding 状态、claim boundary、是否可进 evidence bundle 和 next action。

运行结果：

```powershell
python -m pytest tests\test_r18_data_source_admission_ledger.py -q
python -m py_compile scripts\data_expansion\build_r18_data_source_admission_ledger.py
python scripts\data_expansion\build_r18_data_source_admission_ledger.py --strict
```

结果：

- targeted pytest：`3 passed`
- py_compile：通过
- strict ledger：`status=pass`
- `company_count=603`
- `row_count=7884`
- `source_role_count=16`
- `source_id_count=29`
- `can_enter_evidence_bundle_count=7750`
- `not_evidence_ready_count=134`
- availability split：
  - `runtime_ready_exact_or_bounded_slot=7750`
  - `route_or_parser_debt=52`
  - `attempt_backed_public_boundary=82`
- hard gate 全为 0：
  - `accepted_row_without_route_contract_count=0`
  - `accepted_row_without_parser_or_verifier_count=0`
  - `unbound_company_specific_accepted_row_count=0`
  - `url_or_snippet_promoted_count=0`
  - `forbidden_claim_violation_count=0`

解释：

- 这不是说所有 source gap 都解决了，而是说明“已经允许进 evidence bundle 的行”都有 route/parser/verifier/authority 边界。
- 未准入的 134 行继续留在 planning / targeted repair / gap ledger，不会被 ClaimCard 或 Memo 使用。
- AI/Semis 后续是第一批全链路验收对象；23 的大框架和台账已经覆盖 600+ 公司，不是只做 AI 行业。

## 2026-06-23 SourceRouteRegistry v2 / SignalAuthorityMapper v0.2

在 R18 Data Source Admission Ledger 之后，本轮继续把台账变成可执行 source-role 合同和 authority coverage matrix：

- 新增 `src/sec_agent/source_route_registry_v2.py`
  - `SourceRouteContract`
  - `SOURCE_ROUTE_CONTRACTS`
  - `map_signal_authority_from_admission_row`
- 新增 `scripts/data_expansion/build_r18_source_route_registry_v2.py`
  - 输出 `data/manifests/r18_source_route_registry_v2.json`
  - 输出 `data/manifests/r18_signal_authority_coverage_matrix_v0_2.jsonl`
  - 输出 `data/manifests/r18_source_route_registry_v2_summary.json`
  - 输出 `docs/internal/vnext_20260610/r18_source_route_registry_v2.zh-CN.md`
- 新增 `tests/test_source_route_registry_v2.py`
- 更新 `src/sec_agent/non_financial_signal_authority.py`
  - 让 `official_product_surface`、`macro_official_context`、`energy_utility_context`、`financial_regulatory_context`、`auto_product_identity_context`、`app_rank_store_proxy`、`platform_review_proxy` 等 source roles 不再落成 generic context。
  - `sample_urls` / `sample_evidence_refs` 也可作为 citation presence。
- 修复 `build_r18_data_source_admission_ledger.py`
  - 从 exact-slot coverage 回填 sample URLs / exact slot refs，避免 registry required-field gate 把已准入 rows 误降级。

运行：

```powershell
python -m pytest tests\test_non_financial_signal_authority.py tests\test_source_route_registry_v2.py tests\test_runtime_source_context_store.py tests\test_r18_data_source_admission_ledger.py -q
python scripts\data_expansion\build_r18_data_source_admission_ledger.py --strict
python scripts\data_expansion\build_r18_source_route_registry_v2.py --strict
```

结果：

- targeted pytest：`18 passed`
- R18 admission ledger strict：`status=pass`，`603` companies，`7,884` rows，`7,750` evidence-admissible rows。
- R18 registry strict：`status=pass`
  - `registry_source_role_count=16`
  - `signal_matrix_row_count=7,884`
  - `evidence_bundle_allowed_count=7,750`
  - `planning_or_gap_only_count=134`
  - authority split：`exact_company_fact_authority=2,412`，`bounded_thesis_driver_authority=5,472`
  - hard gate 全 0：`unregistered_source_role_count=0`、`evidence_row_without_registry_count=0`、`evidence_row_missing_required_fields_count=0`、`non_evidence_row_marked_allowed_count=0`

这轮完成了 CG-18-11。当时仍未完成的是让 Research Lead / LeadReviewCheckpoint 默认消费该 matrix，以及 AI/Semis first tranche 的 product-family-level source-route admission gate 和 full-chain 验收；下一节继续补上前两项的 runtime / gate 骨架。

## 2026-06-23 Research Lead SourceAuthorityCoverage 与 AI/Semis Gate

本轮把 R18 matrix 从“离线台账/registry”接到 Research Lead / LeadReviewCheckpoint，并建立 AI/Semis first-tranche deterministic source-route gate：

- 新增 `src/sec_agent/source_authority_coverage.py`
  - 读取 `r18_signal_authority_coverage_matrix_v0_2.jsonl`
  - 按 ticker / search scope / dimension 选择 source authority candidates
  - 输出 dimension coverage、repairability、source roles、source ids、signal authority types、forbidden claim types 和 probe order
- 更新 `src/sec_agent/lead_supervision.py`
  - `build_lead_review_checkpoint` 新增 `source_authority_coverage` 输入
  - 如果某个维度没有 ClaimCard 但 matrix 显示有 parser-backed 或可修 source authority，Lead 会标为 `retrievable_gap`，而不是直接写成 generic gap
  - targeted repair plan 继承 source authority fields
  - memo directive 新增 `source_authority_write_policy`，要求 writer 把 exact fact、thesis driver、repair-first 和 boundary-only 维度分开写
- 更新 `src/sec_agent/langgraph_orchestrator.py`
  - 默认加载 SourceAuthorityCoverage
  - checkpoint / artifact summary / governance ledger 增加 `source_authority_coverage`
- 新增 `scripts/data_expansion/build_r18_ai_semis_source_route_gate.py`
  - 对 V1 Semiconductors / AI Infrastructure product-family assignments 做 source-route gate
  - gate 要求每个 product family 的关键 source-role group 都有 parser-backed runtime rows 或明确 route/parser debt
  - seed、URL、attempt-only、blocked page 不能算 coverage pass
- 新增 targeted tests：
  - `tests/test_source_authority_coverage.py`
  - `tests/test_r18_ai_semis_source_route_gate.py`
- 新增报告：
  - `data/manifests/r18_ai_semis_source_route_gate_rows_v0_1.jsonl`
  - `data/manifests/r18_ai_semis_source_route_gate_summary_v0_1.json`
  - `docs/internal/vnext_20260610/r18_ai_semis_source_route_gate.zh-CN.md`

运行：

```powershell
python -m pytest tests\test_source_authority_coverage.py tests\test_r18_ai_semis_source_route_gate.py tests\test_source_layer_capability_audit.py tests\test_runtime_bridge_contracts.py tests\test_source_route_registry_v2.py -q
python -m py_compile src\sec_agent\source_authority_coverage.py src\sec_agent\lead_supervision.py src\sec_agent\langgraph_orchestrator.py scripts\data_expansion\build_r18_ai_semis_source_route_gate.py
python scripts\data_expansion\build_r18_data_source_admission_ledger.py --strict
python scripts\data_expansion\build_r18_source_route_registry_v2.py --strict
python scripts\data_expansion\build_r18_ai_semis_source_route_gate.py
```

结果：

- targeted pytest：`25 passed`
- py_compile：通过
- R18 admission ledger strict：`status=pass`，`603` companies，`7,884` rows，`7,750` evidence-admissible rows
- R18 registry strict：`status=pass`
- AI/Semis gate：
  - `assignment_count=56`
  - `pass_assignment_count=44`
  - `action_required_assignment_count=12`
  - `family_count=11`
  - `ticker_count=53`
  - hard gate：`unregistered_required_source_role_count=0`、`url_or_snippet_promoted_count=0`、`forbidden_claim_violation_count=0`

Action-required rows：

- `2308.TW` / power_cooling：company disclosure、official product surface、public order / hiring / macro / industry signal 仍是 route/parser debt 或无 parser-backed row。
- `ADI` / analog embedded semiconductors：company disclosure、official product surface、industry/technology signal 未达 parser-backed coverage。
- `AEHR` / semicap equipment：customer order / capex bridge 仍是 route/parser debt。
- `CDNS` / EDA/IP：company disclosure、official product surface、developer / research / customer signal 未达 parser-backed coverage。
- `ETN` / power cooling：company disclosure、official product surface、public order / hiring / macro / industry signal 仍是 route/parser debt。
- `JBL` / electronics manufacturing services：company disclosure、official product surface、industry/technology signal 未达 parser-backed coverage。
- `MU` / memory：company disclosure、official product surface、industry/technology signal 未达 parser-backed coverage。
- `PWR` / power cooling：company disclosure、official product surface、public order / hiring / macro / industry signal 未达 parser-backed coverage。
- `SNPS` / EDA/IP：company disclosure、official product surface、developer / research / customer signal 未达 parser-backed coverage。
- `TER` / semicap equipment：company disclosure、official product surface、technology/industry signal、customer order / capex bridge 未达 parser-backed coverage。
- `TXN` / analog embedded semiconductors：company disclosure、official product surface、industry/technology signal 未达 parser-backed coverage。
- `VRT` / power cooling：company disclosure、official product surface、public order / hiring / macro / industry signal 未达 parser-backed coverage。

解释：

- CG-18-02/03/04 的核心 runtime 能力已经完成：R18 全量 row 已有 authority matrix，SourceRouteRegistry v2 已 strict pass，Research Lead 已消费 matrix。
- 当时 CG-18-12/15 还不能标为完成：AI/Semis source-route gate 已存在，但 `12/56` assignment 仍 action_required。
- 当时没有跑 DeepSeek/full-chain，因为 first-tranche source-route gate 还没全绿；继续跑 full-chain 会把明确的 parser/source-route debt 压给 memo writer。

## 2026-06-23 AI/Semis Gate Closeout Repair

本轮继续修上一节暴露的 `12/56` action_required，目标是把公开可修的 parser/source-route debt 修到 strict gate pass，而不是把 source-route requirement 放松。

Root cause：

1. `build_r18_ai_semis_source_route_gate.py` 错误地按 company `primary_lane_id == V1` 过滤 R18 matrix rows。很多 AI infrastructure 相关公司本身 primary lane 是工业/能源/服务等，例如 VRT、PWR、ETN、JBL，但它们在 V1 product-family assignment 下应当可以使用自身 parser-backed L1/L2/L3 rows。修复后 gate scope 改为由 `company_product_family_assignments_v0_1` 的 V1 assignment 决定。
2. 剩余 AEHR / semicap equipment 缺 `customer_order_or_capex_bridge`。通过 AEHR 官网官方新闻 materialize 一条 `supply_chain_official_relationship` bounded row：`Aehr official production-order relationship with lead hyperscale AI customer`，source URL 为 `https://www.aehr.com/2026/04/aehr-receives-record-41-million-production-order-from-lead-hyperscale-ai-customer-second-half-bookings-exceed-92-million/`。该 row 只能支持官方客户/订单关系上下文，不支持收入、backlog、order value、shipment volume 或 share 推断。

完成的改动：

- 更新 `scripts/data_expansion/build_r18_ai_semis_source_route_gate.py`
  - matrix row scope 从 `primary_lane_id == V1` 改为 V1 assignment tickers。
  - 保持 source-role registry / parser-backed row / forbidden-claim hard gate 不变。
- 更新 `scripts/data_expansion/build_targeted_supply_chain_official_relationship_rows.py`
  - 新增 AEHR 官方 relationship seed。
  - live fetch 成功，`targeted_supply_chain_official_relationship_context_rows_v0_1` materialize AEHR row。
- 更新 tests：
  - `tests/test_r18_ai_semis_source_route_gate.py` 增加跨 lane assignment scope 回归。
  - `tests/test_targeted_supply_chain_official_relationship_rows.py` 增加 AEHR 官方客户/订单关系绑定回归。

重建顺序：

```powershell
python scripts\data_expansion\build_targeted_supply_chain_official_relationship_rows.py --tickers AEHR --timeout-s 20 --sleep-s 0
python scripts\data_expansion\build_company_public_source_coverage_matrix.py
python scripts\data_expansion\build_r18_data_source_admission_ledger.py --strict
python scripts\data_expansion\build_r18_source_route_registry_v2.py --strict
python scripts\data_expansion\build_r18_ai_semis_source_route_gate.py --strict
```

结果：

- targeted supply-chain parser：`10/10` materialized，新增 `AEHR`；remaining targeted gap tickers `0`。
- company public source coverage matrix：`603` companies，仍为全局 `gap`，这是 603 公司全 lane coverage 状态，不影响 AI/Semis gate。
- R18 admission ledger strict：`status=pass`，`can_enter_evidence_bundle_count=7,752`。
- R18 registry strict：`status=pass`，`evidence_bundle_allowed_count=7,752`，hard gate 全 0。
- AI/Semis gate strict：`status=pass`，`assignment_count=56`，`pass_assignment_count=56`，`action_required_assignment_count=0`，hard gate 全 0。

解释：

- CG-18-15 可以关闭：AI/Semis first-tranche hard source admission gate 已全绿。
- CG-18-12 不能完全关闭：first-tranche source-route readiness 已通过，但完整 LeadingSignalSourceLayer 仍需要把 ProductArchitectureSignal、BenchmarkSignal、YieldCapacitySignal、CustomerDeploymentSignal、SupplyChainRampSignal、CapexBuildoutSignal、MarketExpectationSignal、TechnologyEcosystemSignal 作为更细 runtime objects / eval gates 做完。
- 本轮仍未跑 DeepSeek/full-chain；下一步可在 gate 已全绿的前提下进入 AI/Semis full-chain smoke 或继续补 LeadingSignalSourceLayer objects。

## 后续

1. Product-family / relationship graph 应增加 signal-to-thesis 推理路径：产品规格 -> 竞品比较 -> 客户部署 -> 供应链验证 -> 财务/预期桥接。
2. full-chain eval 后续要检查强信号是否进入有用判断，而不是被写成 generic gap。
3. 继续落 LeadingSignalSourceLayer 的细 runtime objects 和 Capital/Funding/Ownership/MarketLiquidityLayer。
4. 继续落 InvestmentDebateContract、DimensionModel、ValuationBridge 和 SourceConfidenceLedger 的 runtime / eval 合同。

## 安全边界

- 本轮未跑 DeepSeek / full-chain；只做 deterministic contract、runtime row、prompt contract 和 targeted tests。
- 非财务信号不能支持产品收入、销量、ASP、份额、sell-through、channel inventory、backlog、订单金额或 reported financial fact。
- L4 / 未绑定 / 无 citation / 低可信来源仍只能做 lead，不得进入 core thesis。
