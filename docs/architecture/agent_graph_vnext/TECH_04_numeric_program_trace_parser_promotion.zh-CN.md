# TECH_04：Structured Numeric Fact Compiler / NumericProgramTrace / DerivedMetricRegistry

创建日期：2026-07-09

最近修订：2026-07-10

状态：技术合同草案。本文定义 parser、row/column selection、metric binding、unit/period/scope sanity、derived metric 可复算和 numeric promotion subgate；不代表现有 runtime 已实现或 P36 parser/numeric blocker 已关闭。

## 0. 准确定义与硬边界

TECH_04 是 FinSight-Agent 的结构化数字事实编译器与可复算计算运行时。它把 TECH_03 提供的 source / table / structured candidates 和 TECH_02 提供的 numeric binding requirement，编译为可寻址、可复算、可拒绝的数字事实、derived features 和 NumericProgramTrace。

TECH_04 负责回答：

- 候选数字究竟属于哪个 entity、period、metric、unit、currency、scope 和 source revision；
- 哪一行/列是 headline fact，哪些只是 growth、delta、deferred、subtotal、footnote 或误分类；
- 输入是否足以计算 growth、margin、CAGR、bridge、peer comp、valuation multiple 或 factor feature；
- 结果是 deterministic exact、bounded delayed market metric、assumption-based estimate、repair required 还是 cannot infer。

TECH_04 不负责：

- 发现新网页、外部补源或决定 SourceHunter scope；
- RAG recall、neighbor chunk / section expansion 的存储与寻址；
- 业务线价值判断、投资结论、factor 显著性或 alpha 验证；
- writer 成稿、图表排版或跨 artifact 最终一致性裁决。

一句话边界：

> TECH_04 compiles numeric candidates into reproducible facts and features; it does not discover sources, validate alpha, make business judgments, or write the report.

## 1. 要解决的问题

P36 Node03 说明基础财务 exact-value rows 可用，但不能把“数据库有数字”等同于“数字能回答用户问题”。当前主要缺口包括：

- Exact-Value Ledger 按 ticker / metric family 返回候选，不按 DecisionSurfaceCell 返回可用事实；
- NVDA revenue / margin 候选中可能混入百分比、同比变动或局部表格值；
- SMCI 同一表格可能同时出现 `usd_thousands` / `usd_millions` 重复值；
- KLAC deferred system revenue 可能被误选成 headline revenue；
- ASML inventory / bank account / reserve utilization 可能被误归为 product revenue；
- company-level revenue / margin 不能回答 HBM-only、CoWoS-only、AI server-only 或 semicap AI-specific economics；
- market snapshot、ownership、capital rows 可以支持 price-in context，但不能提权为基本面事实；
- derived number 如果没有 as-of、formula、input rows、normalization 和 execution trace，无法进入 memo / Excel / PPT / dashboard。

TECH_04 的目标是让所有对外展示数字和进入量化 feature store 的数字都可复算、可审、可拒绝，并把无法计算的原因结构化为 gap，而不是让模型自行补公式或替代口径。

## 2. 输入输出合同

### 2.1 输入

来自 TECH_02：

- `EvidenceRequest.numeric_binding_requirements`
- `cell_id` / `evidence_slot_id`
- required metric / period / scope / source authority
- accepted evidence role
- forbidden substitutions
- freshness / as-of requirement

来自 TECH_03：

- `CandidateBundle`
- `SourceDocument` / `DocumentRevision` / `SourceSnapshot`
- `TableObject` / `TableRowObject` / `TableCellObject`
- parent section / table header / footnote / page lineage
- structured source rows，例如 SEC CompanyFacts / XBRL / official API rows
- market / ownership / macro / event PIT candidates

### 2.2 输出

- `NormalizedNumericFact`
- `DerivedMetricResult`
- `NumericProgramTrace`
- `NumericPromotionAssessment`
- `NumericGap`
- `RejectedNumericCandidate`
- `FactTableBlock`
- `QuantFeatureCandidate`

TECH_04 输出的是 numeric sub-assessment。最终 evidence identity 仍由 TECH_02 Evidence Gate 合并 source authority、permission、claim scope、citation lineage 后决定。

## 3. 核心对象

### 3.1 ParserCandidate

- `candidate_id`
- `source_ref`
- `source_revision_id`
- `page`
- `section`
- `table_lineage`
- `raw_text_or_cell_ref`
- `parser_family`
- `parser_version`
- `parser_confidence`
- `metadata_binding_status`
- `parse_boundary`

### 3.2 NormalizedNumericFact

- `fact_id`
- `cell_id`
- `evidence_slot_id`
- `issuer`
- `security_id`
- `ticker`
- `metric_definition_id`
- `metric_role`
- `scope_type`
- `segment_or_product_scope`
- `period_start`
- `period_end`
- `as_of_date`
- `filed_at`
- `available_at`
- `raw_value`
- `raw_unit`
- `normalized_value`
- `normalized_unit`
- `scale_multiplier`
- `currency`
- `source_authority`
- `source_revision_id`
- `restatement_status`
- `row_selector_reason`
- `lineage_ref`
- `numeric_assessment`
- `forbidden_claims`

### 3.3 MetricDefinition / DerivedMetricRegistry

- `metric_id`
- `formula_version`
- `metric_family`
- `formula`
- `required_inputs`
- `optional_inputs`
- `minimum_history`
- `frequency_policy`
- `period_alignment_policy`
- `as_of_alignment_policy`
- `scope_policy`
- `currency_policy`
- `denominator_policy`
- `negative_or_zero_policy`
- `lag_policy`
- `missing_policy`
- `normalization_policy`
- `allowed_output_classes`
- `allowed_claims`
- `forbidden_substitutions`
- `forbidden_claims`
- `fallback_metric_ids`
- `registry_status`

### 3.4 ComputeEligibilityAssessment

- `metric_id`
- `eligible`
- `input_row_refs`
- `missing_input_refs`
- `history_coverage`
- `as_of_compatibility`
- `period_compatibility`
- `scope_compatibility`
- `currency_compatibility`
- `staleness_days`
- `repair_action`
- `gap_type`

### 3.5 NumericProgramTrace

所有 growth、margin、CAGR、bridge、peer comp、valuation multiple 和 quant feature 必须有：

- `trace_id`
- `metric_id`
- `formula_version`
- `operation`
- `input_row_refs`
- `input_values`
- `formula`
- `periods`
- `as_of_dates`
- `units`
- `currencies`
- `normalization_steps`
- `rounding_policy`
- `result`
- `sanity_checks`
- `cross_foot_checks`
- `execution_code_version`
- `executed_at`
- `review_status`

### 3.6 NumericPromotionAssessment

TECH_04 的 numeric status 固定为：

- `numeric_valid`
- `numeric_valid_scope_limited`
- `bounded_delayed_market_metric`
- `assumption_based_estimate`
- `repair_required`
- `numeric_invalid`
- `cannot_infer`

这些状态不能直接替代 TECH_02 的 `accepted / context_only / rejected / typed_gap / commercial_gap`。

### 3.7 NumericSanityLedger

至少记录：

- `period_unit_mismatch`
- `scale_mismatch`
- `currency_mismatch`
- `row_label_ambiguous`
- `metric_role_mismatch`
- `headline_selector_conflict`
- `business_line_scope_gap`
- `source_revision_conflict`
- `restatement_conflict`
- `as_of_mismatch`
- `history_incomplete`
- `formula_input_missing`
- `source_authority_insufficient`
- `cannot_infer`

## 4. 三条数字事实流水线

### 4.1 Official Structured Fact Pipeline

适用于 SEC CompanyFacts / XBRL、official regulatory API、issuer structured disclosure。

```text
structured candidate
 -> concept/context selection
 -> period role / duration check
 -> entity / unit / scale binding
 -> duplicate / amendment / restatement resolution
 -> normalized numeric fact
```

能从官方结构化来源获得 exact fact 时，不应使用 PDF 表格或普通 RAG chunk 替代。

### 4.2 Table Fact Pipeline

适用于 IR PDF、earnings release PDF、non-US annual report、press table、capacity/backlog/order table。

```text
table candidate
 -> header / row / column / unit / footnote reconstruction
 -> source-specific parser
 -> row selector
 -> cross-foot / duplicate / scale sanity
 -> normalized numeric fact or parser gap
```

表格不按普通 word chunk 直接提权。TECH_04 创建/验证 table lineage，TECH_03 保存并提供可寻址 TableObject。

### 4.3 Derived Metric Pipeline

适用于 growth、margin、CAGR、bridge、peer comp、valuation、market reaction 和 quant feature。

```text
metric intent
 -> DerivedMetricRegistry lookup/metric/scope/period
 -> run row selector and negative rules
 -> normalize unit/scale/currency
 -> check as-of/history/corporate actions
 -> execute NumericProgramTrace
 -> numeric assessment
 -> return to TECH_02 Evidence Gate
```

## 5. Bounded Numeric Repair Loop

允许的 repair：扩展同表/同 section、切 parser、重新绑定 header/footnote、比较 parser outputs、重跑 row selector、修正单位/scale、请求缺失的已知输入。

禁止的 repair：自行 web 补源、用 company total 替代 business-line metric、用 market reaction 替代 fundamentals、用 proxy 冒充 consensus/flow/gamma、要求 writer 自行计算或补数。

源文档缺失时，返回 TECH_02 `SourceHunterRequest`；公开未披露或合理需要商业数据时，返回 `commercial_gap` 建议；不要在 TECH_04 内无限搜索。

## 6. Row / Metric Binding 规则

Row selector 必须联合使用 metric ontology、table title、row label、column header、period role、XBRL concept/context、source-specific policy、neighbor rows、footnotes、headline preference 和 negative labels。

查询 `revenue` 时必须排除或降级：

- revenue growth / percentage contribution；
- deferred revenue；
- remaining performance obligation；
- revenue delta；
- inventory、bank accounts 等 parser false positive；
- total-company row 对 product/business-line request 的错误替代。

Scope 必须显式区分：`consolidated`、`segment`、`geography`、`product_family`、`business_line`、`customer`、`channel`、`market_context`。scope 不兼容时只能 `numeric_valid_scope_limited` 或 `cannot_infer`。

## 7. DerivedMetricRegistry 计算分层

### 7.1 基础自动计算层

| Domain | 默认计算 | 硬条件 |
| --- | --- | --- |
| Financial trend | YoY、可比 QoQ、TTM、2-3 year CAGR | duration / period / currency / scope 可比 |
| Profit quality | gross/operating/net/FCF margin、margin change bps | GAAP/non-GAAP 不混用；分子分母同 scope |
| Cash / investment | FCF、CFO/NI、capex/revenue、R&D/revenue、SBC/revenue、net debt | 现金流分类、期间和单位完整 |
| Working capital | DSO、DIO、DPO、cash-conversion cycle | 平均余额与收入/成本口径可得 |
| Market reaction | 1d/5d/1m/3m return、relative return、short-window volatility、drawdown | 完整交易日、复权、benchmark、lookback coverage |
| Event reaction | 1/3/5/10 trading-day absolute/excess return | event available time、anchor trading day、足够后续 bars |

### 7.2 按 DecisionSurfaceCell 计算层

- market cap、enterprise value、P/E TTM、P/S、EV/Sales、EV/EBITDA、FCF yield；
- peer rank、cross-sectional percentile、premium/discount；
- net debt change、leverage、interest coverage、dilution、buyback/issuance yield；
- lagged 13F/N-PORT ownership change、holder concentration、holder breadth；
- backlog/revenue、book-to-bill、segment mix、capacity growth、inventory days；
- macro/commodity/rate/FX exposure 和 event-study features；
- R53 FeatureSpec 所需、且已通过 compute eligibility 的 source-backed feature。

### 7.3 当前不应计算或宣传

在没有相应源和合同前，固定为 `unavailable / commercial_gap / cannot_infer`：

- forward P/E、NTM EV/EBITDA、consensus revision、target price；
- real-time fund flow、active/passive split、complete holder positioning；
- single-stock IV surface、dealer gamma、borrow cost、securities-lending depth；
- issuer CDS 或完整 credit-spread curve；
- 单一 snapshot 下的 historical valuation percentile；
- 短历史数据下的稳定长期 beta / regime model；
- 未披露的 HBM-only、CoWoS-only、AI-server-only revenue/margin/allocation；
- 用 price action 反推 revenue、margin、order 或 product adoption。

## 8. Public-Market 数据充分性合同

当前 market snapshot 主线只有短窗口 price/volume 和有限 valuation fields，不能因为公式可执行就自动开放所有指标。每个 market metric 需检查：

- `history_start` / `history_end`
- `expected_trading_days`
- `observed_trading_days`
- `history_coverage_ratio`
- `adjustment_status`
- `corporate_action_coverage`
- `benchmark_coverage`
- `as_of_date`
- `provider_delay`
- `license_policy`
- `field_missingness`

现有 `_ytd_return` 类实现必须增加 year-start completeness gate：如果 bars 未覆盖当年首个可交易日，结果只能叫 `available_window_return`，不能标为 true YTD。

市场 cap 使用 delayed price 与 filed shares 时，必须同时显示 `price_as_of`、`shares_as_of` 和 `staleness_days`。Enterprise value 只有在 debt、cash、preferred/minority interest 等 denominator policy 满足时才能计算；缺组件不得静默使用 provider placeholder。

## 9. Derived Metric 输出身份

- `deterministic_derived_exact`：全部输入为 accepted exact facts，公式与期间/scope 确定。
- `bounded_delayed_market_metric`：基于延迟行情、季度 shares、lagged ownership 或 mixed-as-of market/fundamental inputs。
- `assumption_based_estimate`：包含公开假设，必须显示区间、敏感性和 estimate policy。
- `diagnostic_score`：只用于研究诊断，不是显著因子或 alpha。
- `unavailable_or_commercial_gap`：输入或公开源不足，不计算。

任何 writer、dashboard、Excel、PPT 都必须保留该身份；不能只保留数值。

## 10. TECH_04 与 R53 Research-to-Quant 的边界

TECH_04 生成 source-backed derived feature 和 NumericProgramTrace；R53/S9 才负责：

- FactorHypothesis / FeatureSpec / LabelSpec / UniverseSpec；
- PIT dataset materialization；
- leakage、survivorship、multiple-testing、OOS / walk-forward gate；
- IC / RankIC、quantile return、decay、turnover、event study、backtest；
- risk attribution、FactorCard、ResearchExperienceRecord 和 human approval。

```text
TECH_04 DerivedMetric
 -> R53 PIT Feature
 -> FactorAnalysis / EventStudy / Backtest
 -> FactorCard
 -> TECH_05 QuantValidationDecisionSurfaceProjection
 -> TECH_09 Workbench review
```

TECH_04 不得把 `diagnostic_score` 标成 `validated factor`，也不根据一次计算或短样本宣称统计显著性。

## 11. Numeric Promotion Sub-Gate

```text
ParserCandidate
 -> metadata binding
 -> row selector
 -> unit / period / metric / scope sanity
 -> as-of / revision / history / corporate-action sanity
 -> compute eligibility
 -> NumericProgramTrace
 -> NumericPromotionAssessment
 -> TECH_02 Evidence Gate
```

硬约束由 deterministic gate 执行，LLM/Numeric Agent 只可给 row-mapping suggestion、ambiguity classification 和 repair suggestion。Agent 不能 override entity、period、unit、scale、scope、lineage、formula execution 或 forbidden-substitution hard fail。

## 12. Fact Table Surface

Workbench、specialist 和 writer 消费结构化 blocks：

- `issuer_fact_table`
- `segment_economics_table`
- `peer_comp_table`
- `bridge_table`
- `valuation_multiple_table`
- `market_reaction_table`
- `capital_positioning_table`
- `derived_metric_table`
- `estimate_sensitivity_table`
- `cannot_infer_table`

每个 block 保留 source refs、numeric trace refs、as-of/lag、output identity、rejected row explanations 和 supersession status。

## 13. 与其他 TECH 的边界

- `TECH_01` 定义 DecisionSurfaceCell 和 metric intent；
- `TECH_02` 负责 source/tool orchestration 和最终 Evidence Gate；
- `TECH_03` 提供 DocumentMetadataIndex、TableObject、PIT source/address layer；
- `TECH_04` 实现 parser、row selector、normalization、DerivedMetricRegistry 和 numeric sub-gate；
- `TECH_05` 使用 promoted rows / FactorCard 形成 domain cell judgment；
- `TECH_06` 管理工具 permission、trace、budget、retry；
- `TECH_09` 检查 numeric/factor lineage 和跨 artifact 一致性；
- `TECH_10` 评估 parser precision、numeric reproducibility、factor projection 和 trajectory quality；
- 现有 R53/S9 负责 quant validation lifecycle，不并入 Numeric Agent。

## 14. 现有 Runtime 审计前置

在重切全部 chunk、重跑全部 parser、补全市场历史或开展因子训练前，先输出：

- `parser_family_quality_by_source`
- `table_extraction_quality_summary`
- `row_selector_precision_by_metric_role`
- `headline_selector_false_positive_report`
- `numeric_scale_unit_audit`
- `period_scope_asof_mismatch_report`
- `market_history_completeness_audit`
- `corporate_action_adjustment_audit`
- `security_master_pit_coverage`
- `derived_metric_compute_eligibility_report`
- `numeric_trace_replay_report`
- `factor_feature_source_availability_matrix`

当前判断是 audit-first，不做 blind full reingestion 或直接启动因子挖掘。

## 15. 第一批 Fixture

1. AI server margin / Dell-HPE-SMCI company-vs-segment-vs-business-line scope fixture。
2. HBM economics / memory supplier proxy cannot-infer fixture。
3. CoWoS capacity / pricing / allocation estimate boundary fixture。
4. Semicap backlog / bookings / order timing fixture。
5. XBRL vs PDF table exact-row consistency fixture。
6. False-positive parser / headline / scale rejection fixture。
7. Market history completeness / false-YTD rejection fixture。
8. Mixed-as-of market cap / EV trace fixture。
9. Lagged ownership change identity fixture。
10. DerivedMetric -> R53 FeatureSpec provenance fixture。
11. Diagnostic score cannot promote to validated factor fixture。

## 16. 验收标准

- 对外展示数字 100% 有 NumericProgramTrace 或明确 `estimate_only` / `cannot_infer` / `commercial_gap`。
- Writer 不得使用无 trace 派生数字。
- Verifier 能阻止 period / unit / scale / scope / as-of / metric-role 错配。
- Workbench 能打开 raw source -> selected row -> normalization -> formula -> result -> artifact 的 numeric trace drawer。
- Parser failure 必须 typed，不能写成 public source absent。
- market metric 必须显示 history coverage、as-of、delay、corporate-action 和 benchmark 状态。
- diagnostic score、in-sample factor 和 out-of-sample factor 必须显式区分。
- TECH_04 不能绕过 R53 PIT / leakage / OOS / human approval 宣称 factor significance。

## 17. 2026-07-10 DerivativeMetricRegistry

衍生品 derived metrics 必须作为 `DerivedMetricRegistry` 的专门 family，不允许 Numeric Agent 根据市场惯例自由拼公式。

### 17.1 Futures / COT metrics

允许计算：

- front/second/third contract curve slope；
- contango / backwardation；
- calendar spread、basis、annualized roll yield；
- volume / open-interest change；
- curve percentile、realized volatility；
- COT category net position、weekly change、OI share、history percentile、concentration where reported；
- commodity/rate/FX event-window reaction。

必须记录 contract roll、continuous-series construction、first notice/expiry、settlement source、preliminary/final、OI lag、COT report/release time。不同 contract month、multiplier、currency 或 COT category 不能静默合并。

### 17.2 Options metrics

只有 quotes / settlement / OI / volume / contract master 满足对应公式时，才可计算：

- put/call volume 和 OI ratio；
- ATM implied volatility；
- IV term structure；
- delta-consistent skew；
- IV minus realized volatility；
- event implied move；
- strike/expiry OI concentration；
- volume/OI anomaly。

必须处理 split-adjusted contract、multiplier、American/European exercise、cash/physical settlement、calendar/timezone、stale/zero bid、deep ITM/OTM quote quality 和 expiry proximity。

固定禁止：

- 只有 OI 时推断 dealer long/short；
- 无 dealer inventory/side 时把 gamma proxy 写成真实 GEX；
- 无稳定 bid/ask 时硬算 IV surface；
- 把 `max pain` 作为正式研究指标；
- 用 bullish option volume 证明 fundamentals、order、revenue 或 product demand。

### 17.3 Credit / swap / convertible metrics

- TRACE bond yield / Treasury benchmark 可计算 bounded spread、yield change、liquidity/activity 和 equity-credit divergence；不能称为 CDS。
- CFTC weekly swap aggregates 可计算 rates/credit/FX swap regime、notional/volume/maturity/clearing mix；不能还原单个机构仓位。
- issuer convertible / warrant 可计算 conversion premium、potential dilution、coupon/maturity/funding pressure；必须绑定 filing terms、share adjustment 和 as-of price。
- public SBS/SDR rows 只有在 underlying/entity/lifecycle/correction/capped-notional audit 后才能进入 investigative metric。

### 17.4 输出身份

DerivativeMetricResult 只能是：

- `official_or_exchange_reported_metric`
- `deterministic_derived_derivative_metric`
- `bounded_delayed_positioning_proxy`
- `assumption_based_model_proxy`
- `commercial_or_source_gap`

其中 `assumption_based_model_proxy` 默认不能进入 writer 主结论，只能进入 Workbench review 或 R53 diagnostic experiment。

## 18. 2026-07-12 Numeric Business Truth / Model and Recompute Contract

根据 TECH_00/02/03，TECH_04 是 NumericFact、MetricDefinition、NumericProgramRun、ModelInputSnapshot 和 AssumptionSet 的业务真相 writer，并向 TECH_02 提供不可被 LLM override 的 numeric hard-gate result。

### 18.1 Canonical numeric objects

- `MetricDefinitionVersion`：canonical name、formula/aggregation、entity/segment/product scope、period/vintage、unit/scale/currency、sign、GAAP/non-GAAP、source eligibility 和 forbidden substitutions；
- `ModelInputSnapshot`：exact fact/input versions、as-of/available-at、permission/license、missingness、override refs 和 content digest；
- `AssumptionSetVersion`：reported/guidance/licensed consensus/public proxy/user/model assumptions 分层，记录 owner、reason、range、expiry 和 approval policy；
- `NumericProgramVersion`：可执行 program/formula、code/runtime version、rounding、error policy 和 expected outputs；
- `NumericProgramRun`：input snapshot、intermediate values、output、sanity checks、actor/attempt/event、hash 和 reproducibility status；
- `NumericImpactSet`：input/definition/program change 后受影响的 facts、judgments、SurfaceClaims、tables/charts/artifacts。

### 18.2 Numeric promotion subgate

TECH_04 返回 `numeric_eligible / numeric_context_only / numeric_rejected / numeric_gap` 及 hard-fail reasons。Entity/period/unit/scale/definition/row lineage/formula/permission 任一 required hard check 失败，TECH_02 不能把 numeric claim 晋升为 accepted；语义 Evidence Gate 通过也不能覆盖 numeric fail。

`usd_thousands`、`usd_millions`、百分比与百分点、stock/flow、quarter/YTD/TTM、reported/restated、actual/guidance/consensus/assumption 必须是 typed identity，不靠 prose 推断。

### 18.3 Selective recompute / version impact

Source amendment、row correction、MetricDefinition、AssumptionSet、corporate action、FX/calendar 或 permission change产生新 input/program version。系统根据 dependency graph 生成 `NumericImpactSet`，只重跑受影响 program；旧 run immutable，不能覆盖。

TECH_05 重新解释受影响 Judgment，TECH_09 把相关 SurfaceClaim/table/chart/artifact 标为 impact-pending/stale，TECH_11 将 WWC/monitoring trigger 与新 metric value 对比。是否改变 Case 主结论仍由 TECH_01/05 adjudication 决定。

### 18.4 Human modification and accountability

任何 manual override、assumption change、row selection、metric mapping 或 formula change必须记录 ActorSnapshot、before/after version、reason、scope、review requirement 和 downstream impact。Reviewer 可修改 assumption 并触发新 run，不能直接编辑 output value 后沿用旧 trace。

### 18.5 R2-R4 fixtures

1. 百万/千单位、百分点/百分比和 YTD/quarter 错配 hard fail。
2. Reviewer 修改 assumption 后只重算依赖的 valuation/sensitivity/artifact nodes。
3. Source restatement 可重建旧 as-of run，并生成新 run/supersession。
4. 同一 approved NumericProgramRun 在 memo/model/deck/dashboard 保持 value/unit/period/rounding identity。

本节状态为 `documented / contract_draft`；不表示现有 SQL rows、表格抽取或 derived metrics 已通过新 hard gate。
