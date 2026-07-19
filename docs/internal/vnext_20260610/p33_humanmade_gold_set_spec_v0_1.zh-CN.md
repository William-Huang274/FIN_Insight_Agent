# P33 Humanmade Gold Set Spec v0.1

日期：2026-07-06

状态：`gold_set_catalog_schema_documented_pending_user_review`

边界：

- 本文档只落 `HumanmadeGoldSetSpec v0.1` 的 catalog、schema 和通过标准。
- 本轮不审计 accepted aggregate r7 / Memo Writer payload。
- 本轮不跑 paid LLM、Memo Writer、full-chain、模型对比或 broad case expansion。
- 第五步 `HumanmadeGoldCaseAudit` / audit runner 等用户审完本文档后再做。

## 1. 为什么要从 gold case 升级成 gold set

单个 AI/Semis humanmade gold case 能解决当前 P33 的第一问题：让 agent 不再只围绕工程节点跑通，而是先对齐“人类 analyst 会怎么研究、怎么写、怎么判断”。但一个 case 不能保证泛化。

因此 P33 需要三种粒度：

1. `Deep Gold Case`：完整人工 memo + source ledger + audit spec，用于倒推一个深度链路。
2. `Rubric Gold Case`：不写长 memo，只定义必答项、证据角色、可提权边界、失败标准，用于防止过拟合单 case。
3. `Negative Gold Case`：专门测试不能外推、缺口归因、parser/data boundary、available-but-not-used 这类高风险错误。

这三类 gold case 的目的不是把所有研究都人工写完，而是给 Research Lead、specialist、JudgmentCard、ProductIntelligenceGraph、MemoLogicPlan、Memo Writer 和 verifier 提供明确的研究质量尺子。

## 2. 通用研究方法 Rubric

所有 gold case 都必须围绕研究链条，而不是证据清单：

```text
问题定义
 -> 业务机制 / 产品机制
 -> 证据角色
 -> 财务或经营传导
 -> 市场预期 / price-in / 资金面
 -> 反证和什么会改变判断
 -> 明确边界
```

最低合格回答必须包含：

- `judgment`：不是“找到了什么”，而是“基于这些材料怎么看”。
- `business_mechanism`：说明产品、客户、供应链、财务、资本市场之间的传导。
- `evidence_roles`：区分 strong fact、medium corroboration、proxy、scope hypothesis、gap。
- `cannot_infer`：明确哪些结论不能从当前公开源外推。
- `what_would_change_view`：说明哪些数据或事件会改变判断。
- `typed_gap`：找不到时必须说明是 source absence、parser gap、runtime projection gap、commercial tracker gap，不能笼统写“缺数据”。

## 3. Case Schema

后续 machine-readable spec 必须至少保留这些字段：

```text
case_id
case_type
status
vertical
companies
user_question
research_chain
must_answer_items
evidence_roles
promotable_boundaries
forbidden_inferences
pass_criteria
fail_criteria
expected_artifacts
next_use
```

### 3.1 Case Type

`deep_gold_case`：

- 必须有 source ledger、human workflow、human workpaper 或 polished memo。
- 用于审计现有 aggregate / writer payload 与人类样板之间的缺口。

`rubric_gold_case`：

- 不要求长 memo。
- 必须定义研究问题、必答项、证据角色、通过/失败标准。
- 用于后续 deterministic 和 paid artifact 的横向质量检查。

`negative_gold_case`：

- 不要求长 memo。
- 必须定义“什么不能写”“为什么不能写”“正确缺口归因是什么”。
- 用于防止模型或 renderer 把 proxy、图谱边、source coverage、parser gap 提权为强判断。

## 4. Deep Gold Case Catalog

### DGC-001: AI/Semis Accelerator -> Server OEM -> Semicap Gold Case

- `case_id`：`ai_semis_dell_nvda_anchor_v0_1`
- `case_type`：`deep_gold_case`
- `status`：`source_doc_ready_pending_machine_readable_audit`
- `source_doc`：`docs/internal/vnext_20260610/p33_ai_semis_humanmade_gold_case.zh-CN.md`
- `vertical`：AI/Semis
- `companies`：
  - demand pool：MSFT、AMZN、GOOGL、META
  - accelerator / platform：NVDA、AMD、GOOGL TPU
  - server OEM / channel：DELL、SMCI、Hon Hai / ODM context
  - foundry / packaging / semicap：TSM、ASML、AMAT、LRCX、KLAC

核心问题：

AI 基建需求是否真实转化为 accelerator、server OEM、foundry/packaging、HBM、semicap 公司的高质量收入和利润，而不是只停留在“AI 需求强”的宏观叙事。

必需研究链：

```text
hyperscaler capex / demand pool
 -> accelerator product capability and supply
 -> customer deployment / OEM adoption
 -> DELL AI server revenue visibility vs margin quality
 -> foundry / packaging / HBM / semicap read-through
 -> market expectation / price-in
 -> counter-thesis and what-would-change
```

最低通过标准：

- 明确区分 DELL 的 AI server 收入能见度和利润质量。
- 说明 NVDA / AMD / TPU 的产品与架构证据能支持什么，不能支持什么。
- 说明 hyperscaler capex 只能先支持 demand pool，不能直接证明供应商份额、订单分配或 DELL 毛利改善。
- 说明 ASML / AMAT / LRCX / KLAC 的 semicap read-through 需要 bookings/backlog/cycle/export/customer concentration，而不能只用 peer group 关系。
- 明确 counter-thesis：capex digestion、GPU pass-through cost、OEM margin dilution、export control、supply bottleneck、price-in。

失败标准：

- 只写“AI 需求强，所以 NVDA/DELL/semicap 受益”。
- 因为没有 SKU revenue 就说产品层无法判断。
- 把 relationship graph 当成订单、收入、毛利事实。
- 上游 payload 有 LRCX / DELL 财务事实，memo 却说缺财务数据。
- 用 source coverage / official issuer context 充当主判断。

## 5. Rubric Gold Case Catalog

这些 case 暂不写长 memo，只用来定义可泛化质量标准。

### RGC-001: Semicap Cycle / Backlog / Export Control

- `case_id`：`semicap_cycle_rubric_v0_1`
- `vertical`：Semiconductor equipment
- `companies`：ASML、AMAT、LRCX、KLAC、TEL
- 核心问题：AI / leading-edge capex 是否转化为 semicap bookings、backlog、shipment、service revenue 和 margin，而不是只形成 peer group scope。
- 必答项：bookings/backlog、EUV/DUV 或 WFE exposure、China/export restriction、memory/foundry/logic cycle、customer concentration、service/mix。
- 失败标准：只用 “ASML/AMAT/LRCX/KLAC 同属 semicap” 当主证据。

### RGC-002: Cloud / SaaS AI Monetization And Capex Tradeoff

- `case_id`：`cloud_saas_ai_monetization_rubric_v0_1`
- `vertical`：Cloud / SaaS
- `companies`：MSFT、AMZN、GOOGL、CRM、NOW、ORCL
- 核心问题：AI capex 是否转化为 cloud revenue、RPO/ARR、margin、retention 或 platform stickiness。
- 必答项：cloud revenue/growth、RPO/ARR、capex and depreciation、gross/operating margin bridge、developer ecosystem、enterprise adoption。
- 失败标准：只说“AI 投入大”而不回答 monetization 和 margin/capex tradeoff。

### RGC-003: Financials Rate / Credit / Capital Return

- `case_id`：`financials_rate_credit_capital_rubric_v0_1`
- `vertical`：Financials
- `companies`：JPM、BAC、WFC、C、SCHW、regional banks
- 核心问题：利率和信用周期如何影响 NIM、存款成本、贷款增长、信用损失、资本充足和回购/分红。
- 必答项：deposits、loan balance、NIM、credit loss/provision、capital ratios、AFS/HTM sensitivity、FDIC/FRED rate proxy。
- 失败标准：只用收入或 EPS 解释银行股，而不分析资产负债表和资金成本。

### RGC-004: Healthcare Product Approval / Adoption / Reimbursement

- `case_id`：`healthcare_regulated_product_adoption_rubric_v0_1`
- `vertical`：Healthcare / Medtech / Pharma
- `companies`：LLY、AMGN、ISRG、MDT、ABT、ZTS
- 核心问题：研发、审批、适应症、临床证据、渠道和 reimbursement 是否能支持产品采用与经营表现。
- 必答项：clinical / FDA / openFDA / ClinicalTrials、procedure volume、product family、pipeline stage、reimbursement、commercialization boundary。
- 失败标准：把 trial existence 或 FDA context 直接写成销售份额或产品收入。

### RGC-005: Energy / Utilities Power Demand And Balance Sheet

- `case_id`：`energy_utilities_power_demand_rubric_v0_1`
- `vertical`：Energy / Utilities / Power
- `companies`：NEE、DUK、SO、CEG、VST、XEL
- 核心问题：数据中心和电气化需求如何进入 load growth、regulated asset base、capex、debt/cash flow 和 allowed return。
- 必答项：load growth、generation mix、regulated asset base、capex plan、debt maturity、power price proxy、rate case/regulatory context。
- 失败标准：只说“AI data center 用电增加”而不分析资产、监管、融资和电价传导。

### RGC-006: Retail / Consumer Traffic / Price / Margin

- `case_id`：`retail_consumer_traffic_margin_rubric_v0_1`
- `vertical`：Retail / Consumer
- `companies`：WMT、COST、TGT、SBUX、MCD、PG、KO
- 核心问题：收入增长来自 traffic、ticket、price/mix、unit volume、store expansion 还是促销，利润率是否可持续。
- 必答项：same-store sales、traffic/ticket、gross margin、inventory、promotion/channel proxy、consumer spending proxy。
- 失败标准：只用 revenue growth 写消费强弱，不拆 traffic/price/mix/margin。

### RGC-007: Auto / EV / Industrial Cycle

- `case_id`：`auto_ev_industrial_cycle_rubric_v0_1`
- `vertical`：Auto / EV / Industrial
- `companies`：TSLA、GM、F、TM、CAT、DE
- 核心问题：交付、ASP、库存、融资成本、召回/质量、产能和周期需求如何影响利润质量。
- 必答项：deliveries、ASP/proxy、inventory、NHTSA recall/safety context、capacity/utilization、financing sensitivity、dealer/channel context。
- 失败标准：只用交付量或订单新闻，不分析 ASP、库存、margin 和融资环境。

### RGC-008: Secondary Market Price-In / Capital Feedback

- `case_id`：`capital_market_feedback_price_in_rubric_v0_1`
- `vertical`：Cross-sector / secondary market
- `companies`：可套用于任何 covered issuer
- 核心问题：基本面和产品变化是否已经被估值、持仓、流动性、期权/衍生品、信用和 corporate action 定价。
- 必答项：valuation percentile / peer valuation、13F/holder proxy、short interest / borrow / options if available、credit funding、buyback/offering、event calendar。
- 失败标准：把 market signal 写成投资建议，或把 options/holder proxy 写成基本面事实。

## 6. Negative Gold Case Catalog

### NGC-001: Missing SKU Revenue Does Not Mean Product Layer Failure

- `case_id`：`negative_sku_revenue_missing_not_product_failure_v0_1`
- 典型场景：NVDA 未披露 H100 / B200 / GB200 SKU revenue。
- 正确处理：仍然必须分析产品规格、架构、代际、benchmark、客户部署、供应链和竞争关系。
- 禁止外推：不能写 SKU revenue、shipment、ASP、market share exact。
- 失败标准：memo 写“没有 SKU revenue，所以产品层无法判断”。

### NGC-002: Demand Pool Is Not Supplier Allocation

- `case_id`：`negative_demand_pool_not_supplier_allocation_v0_1`
- 典型场景：MSFT / AMZN / GOOGL / META capex 上升。
- 正确处理：可以支持 AI infrastructure demand pool 和 read-through direction。
- 禁止外推：不能直接证明 NVDA / DELL / ASML / LRCX 获得订单、份额、毛利改善。
- 失败标准：把 hyperscaler capex 写成某供应商订单或份额提升。

### NGC-003: Relationship Graph Is Not A Financial Fact

- `case_id`：`negative_relationship_graph_not_financial_fact_v0_1`
- 典型场景：ProductRelationshipGraph 显示 supplier/customer/competitor/read-through 边。
- 正确处理：用作机制、范围、传导链和后续 evidence search guide。
- 禁止外推：不能写成订单金额、收入、毛利或 backlog。
- 失败标准：图谱边直接成为主财务判断。

### NGC-004: Parser Gap Is Not Public Source Absence

- `case_id`：`negative_parser_gap_not_public_source_absent_v0_1`
- 典型场景：ASML / TEL / Hon Hai / DART / local exchange / company IR 文件定位到，但表格或数字未抽出。
- 正确处理：标记为 parser / locator / local disclosure adapter gap，并说明下一步需要哪个 parser。
- 禁止外推：不能写“公开源没有数据”。
- 失败标准：已定位公开文件但抽不出数字时，memo 写成 public source absent。

### NGC-005: Available Evidence Must Not Be Reported Missing

- `case_id`：`negative_available_evidence_not_used_v0_1`
- 典型场景：pre_memo_fact_selection / aggregate payload 已有 LRCX revenue/capex 或 DELL margin facts，但 memo 说缺财务数据。
- 正确处理：必须 fail，并归因到 selector / projection / writer consumption，而不是数据缺口。
- 禁止外推：不能用 fallback 文案掩盖已有证据未被消费。
- 失败标准：有可用 evidence，却在最终 memo 中说没有。

### NGC-006: Commercial Tracker Boundary Must Be Explicit

- `case_id`：`negative_commercial_tracker_boundary_v0_1`
- 典型场景：IDC / Gartner / IQVIA / NielsenIQ / POS / app revenue / OPRA / borrow cost 等商业或授权数据。
- 正确处理：公开 proxy 可以进入 context；exact sales/share/app revenue/options/gamma/borrow exact 必须标商业或授权缺口。
- 禁止外推：不能用新闻、评论、电商 listing 或弱 proxy 填 exact market share / sell-through / app revenue。
- 失败标准：把公开 proxy 冒充 commercial tracker exact。

## 7. Gold Set 级通过标准

`HumanmadeGoldSetSpec v0.1` 本身通过需要满足：

- 至少 1 个 `deep_gold_case`，且可追溯到 humanmade source doc。
- 至少 6 个 `rubric_gold_case`，覆盖不同 vertical / research mode，避免单 AI/Semis 过拟合。
- 至少 5 个 `negative_gold_case`，覆盖不能外推、缺口归因、parser boundary、available-but-not-used、commercial boundary。
- 每个 case 都有 `must_answer_items`、`pass_criteria`、`fail_criteria` 和 `forbidden_inferences`。
- 明确当前状态是 `pending_user_review`，不得被误记为 runtime proof。

## 8. 后续第五步，等待用户审阅后再做

用户审阅通过后，下一步才允许进入：

```text
P33-3_humanmade_gold_set_audit_spec_and_runner
```

该步骤要做：

1. 把本文档和 JSON spec 转为 audit runner 输入。
2. 用 no-paid audit 对比 accepted aggregate r7 / Memo Writer payload。
3. 输出 `human_expectation -> current_agent_artifact -> gap -> root_cause`。
4. 对每个 gap 归因到 data/source、parser/locator、runtime projection、specialist skill、JudgmentCard、aggregation、writer。
5. 只有 audit 达到 `pass_or_bounded_pass` 后，才允许进入 scoped paid Memo Writer node rerun。
