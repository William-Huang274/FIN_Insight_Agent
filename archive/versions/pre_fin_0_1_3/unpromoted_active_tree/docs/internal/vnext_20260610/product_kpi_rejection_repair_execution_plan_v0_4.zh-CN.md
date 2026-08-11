# Product KPI Rejection Repair v0.4 执行计划

日期：2026-06-12

## 目标

把 v0.3 rejection ledger 中剩余 `1,321` 条 rejected / `100` 个 ticker 按公开、免费、可得数据能否继续处理进行收口。

最终返回用户前必须满足：

1. 已覆盖/重复项被明确标为非缺口，不重复提权。
2. 能靠 SEC/global filing parser、source-specific table gate、schema 扩展、operating metric gate 或 local citation verifier 修复的项已经物化。
3. 不能提权的项必须有机器可读原因：公开数据不直接披露、当前公开披露只有 proxy、需要商业 tracker、或需要人工/新 schema 后续版本。
4. 不允许用弱 proxy、官网泛爬、宏观/行业数据替代公司披露的产品 KPI。

## 输入与当前基线

- Accepted baseline：`Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_with_structured_v0_1.jsonl`
- Current monotonic layer：`Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_with_monotonic_repair_v0_3.jsonl`
- v0.3 promoted：`Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_monotonic_repair_promoted_v0_3.jsonl`
- v0.3 rejections：`Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_monotonic_repair_rejections_v0_3.jsonl`
- Repair candidate source：`Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_targeted_repair_strict_sentence_v0_1.jsonl`

v0.3 状态：

- Accepted facts：`6,186` / `184` tickers.
- Promoted repair facts：`24` / `6` tickers.
- Evidence graph gaps：`2,981`.
- Company-disclosed KPI gap：`419` companies.

## 四类处理策略

### 1. 已覆盖或重复：不修，不计缺口

范围：

- `claim_already_covered_by_baseline`
- `duplicate_promoted_semantic_fact`
- mixed table 中已被正确拒绝的 share/percentage cells

执行：

1. 生成 closeout ledger，标记 `already_covered_not_gap` 或 `correctly_rejected_cell_not_gap`。
2. 保留引用到 baseline/promoted fact claim key，便于审计。
3. 不生成新的 promoted fact。

通过条件：

- 这类项不再出现在 unresolved public gap 计数里。
- 不改变 current accepted fact layer。
- 对同一 ticker/product/metric/period/unit 不出现重复 promoted fact。

### 2. 可修但要 parser/schema：优先修

范围：

- Source-specific table gate candidates：segment sales + operating income、sales + average annual sales、principal product/geographic sales、表头截断但结构可恢复的表。
- Taxonomy/product binding candidates：row label 与产品别名可由表上下文可靠恢复。
- Region/geographic schema candidates：地理 revenue 可提权为 geographic/region revenue，但不能冒充 total product revenue。
- Period/column-group candidates：需要保留 sales block、current/prior year block 或 source fiscal year version。

执行顺序：

1. Table column-group repair：
   - TSN `Sales | Operating Income (Loss)`：只提权 Sales block，拒绝 Operating Income block。
   - DRI `Sales | Average Annual Sales per Restaurant`：只提权 Sales `(in millions)` block，拒绝 average annual sales per restaurant。
   - 类似 table 只在 source-specific signature 命中时启用。
2. Geographic/region revenue repair：
   - 允许 `company_disclosed_geographic_segment_revenue`。
   - 如果 row 同时包含 product + region，例如 `Repatha - U.S.`，必须标记 region/product-region scope，不进入 total product revenue。
3. Restatement/source-version closeout：
   - GPC 这类同一 period 在不同 filing/version 中出现多个大额值时，不自动选值；若 schema 暂无 `source_fiscal_year/version`，标记 `public_disclosure_restatement_conflict_requires_versioned_schema`。

通过条件：

- 每个 promoted fact 必须有 source-specific gate 名、scope、runtime boundary。
- 同一 claim 多个大额值仍拒绝，除非新增 schema 能表达版本或 region。
- 提权后 graph builder 默认使用最新 monotonic layer。

### 3. 非 revenue 但可能是产品表现：另建 operating metric fact layer

范围：

- `not_product_revenue`
- 部分 `not_currency_revenue` 仅在确认为非百分比变化且有直接公司披露 operating metric 时处理。

执行：

1. 不把这类项塞回 `product_revenue`。
2. 输出独立 operating metric promoted layer：
   - `unit_sales_or_deliveries`
   - `shipments`
   - `backlog_or_orders`
   - `subscribers_or_arpu`
   - `production_or_throughput`
   - `same_store_sales`
3. Source-specific correction：
   - WBD subscriber table：如果 citation 明确 `Subscriber information ... (in millions)`，把误判的 `USD/currency_per_user` 修正为 `subscribers`，value 以 actual subscribers 计。
   - ED gas delivered：先在 quality filter 压掉原始 `units/systems` 错 unit rows；只有 citation 明确 `Gas Delivered (MDt)`、row 为 `Total Gas Delivered to CECONY Customers`、且 value 达到交付量级时，才以 `MDt` operating metric 回填；同一 row 下的小值/customer-count/subtotal 仍拒绝。

通过条件：

- 新 fact layer 不改变 product_revenue 事实语义。
- 每条 operating metric fact 必须有 metric family、metric name、unit、value、period、product/segment、citation、scope boundary。
- 不能把 customer count、change percentage、ARPU、throughput 混成 units sold。

### 4. 非结构句子/非表格：最后做 local verifier

范围：

- `not_structured_table_metric`
- sentence-derived product revenue candidates

执行：

1. 只处理 USD currency revenue；percent/change sentence 默认不提权。
2. local citation verifier 必须同时满足：
   - product alias 与 value 在同一句或同一短 citation span 内。
   - citation 含明确 revenue/sales/product sales 词。
   - 不含 increase/decrease/change/growth/volume/price/currency/expense/capex 等变化解释语境。
   - 不与 baseline/v0.3/v0.4 已覆盖 claim 冲突。
3. 对公司级 narrative、行业描述、贡献/增长原因、收购贡献等句子，只能进入 review/lead，不进 runtime fact。

通过条件：

- Sentence promoted fact 数量可以很少；宁可少提权，不允许把增长原因句误当 product revenue。
- 每条 sentence promoted fact 必须保存 verifier decision 和 rejected contrast reasons。
- 剩余 sentence rows 必须有 closeout reason：`needs_commercial_tracker`、`public_disclosure_insufficient_relation`、`change_context_not_fact`、`baseline_already_covers_claim` 等。

## 执行顺序

1. `v0_4_closeout_audit`：生成四类分类 ledger 和当前 ceiling。
2. `v0_4_revenue_table_schema_repair`：修 table column-group / geographic / region-safe revenue。
3. `v0_1_operating_metric_repair`：独立 operating metric layer，先做 WBD，可证明才做 ED。
4. `v0_5_sentence_local_verifier`：只做严格 sentence verifier。
5. 重建 `company_product_evidence_graph`，并输出 final unresolved gap ledger。
6. 更新 worklog/checklist，并跑 targeted tests / py_compile / diff check / secret scan。

## Stop / Gap 判定

以下原因可以在最终结果中作为“公开数据已尽力后仍不能提权”：

- `public_disclosure_restatement_conflict_requires_versioned_schema`：公开披露有值，但当前 fact schema 无法安全表达 source version。
- `public_disclosure_row_subrow_ambiguity`：公开表格同时含多个不同口径；若能用 source-specific gate 明确区分则回填，不能区分的小值/customer-count/subtotal 保持拒绝。
- `public_disclosure_region_dimension_required`：公开披露为 region/product-region，不可冒充 total product revenue。
- `public_disclosure_insufficient_relation`：句子中产品、值、指标关系不在局部 citation 内成立。
- `change_or_growth_context_not_fact`：只有增长/变化/价格/汇率/volume 解释，不是 level KPI。
- `commercial_tracker_required`：公开披露没有真实销量、市占率、ASP、channel inventory、POS sell-through、app revenue/downloads、处方份额等直接 measurement。
