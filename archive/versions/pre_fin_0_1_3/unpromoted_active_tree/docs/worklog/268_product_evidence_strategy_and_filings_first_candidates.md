# 268 Product Evidence Strategy 与 filings-first 产品候选落地

## Prompt

用户要求把三张图中的判断固化为下一步数据扩容与处理方向：公开数据系统目标是成为强 `public-evidence research analyst`，产品数据用于补充财务判断支撑面；执行上按行业拆外部验证源，SEC/filings 是 anchor，官网是 taxonomy/enrichment，第三方市场/替代数据才是产品层对财务判断的主要增量；过程中不能偏离该方向做降低或兜底处理。

## Decision

本轮不继续“爬官网大全”，也不把弱 proxy 当作产品事实。工程方向锁定为：

- `company_disclosed`：最高强度路径，来自 SEC/global filings、earnings、official presentations；产品 KPI 必须经过 value/unit/period/product/citation parser 后才能成为事实。
- `official_product_surface`：官网/产品页只支持产品存在、定位、功能、launch/pricing context；不能证明需求、销量、份额或毛利。
- `public_proxy`：只做方向性验证、行业上下文或线索；不能替代商业 tracker 或公司披露。
- `commercial_market_tracker`：当前 no-commercial 策略下只进入 source plan，全部 blocked，不做兜底。

## Work Completed

- 新增 `configs/data_sources/product_evidence_strategy_v0_1.yaml`：
  - 固化图一的研究目标、non-degradation rule、analyst judgment boundary。
  - 按消费电子/半导体、App/软件、汽车、医药、零售/CPG、能源/工业/材料拆分 source plan。
  - 给每类来源标注 `company_disclosed`、`official_product_surface`、`public_proxy`、`commercial_market_tracker`。
- 新增 `scripts/data_expansion/build_product_evidence_strategy_artifacts.py`：
  - 从 Tier1 S&P 500 + Tier2 SEC annual chunks 做 filings-first 产品 taxonomy 候选抽取。
  - 重新做 balanced product KPI candidates，不再使用全局 `300` 条导致字母靠前 ticker 偏置。
  - 生成行业外部验证源计划，并把 commercial tracker 标成 blocked。
- 新增 `tests/test_product_evidence_strategy_artifacts.py`：
  - 覆盖方向边界、balanced extraction、commercial blocked、boilerplate taxonomy rejection。
- 生成新 artifacts：
  - `data/manifests/company_product_taxonomy_candidates_v0_1.jsonl`
  - `data/manifests/company_product_metric_candidates_balanced_v0_1.jsonl`
  - `data/manifests/product_external_validation_source_plan_v0_1.jsonl`
  - `data/manifests/company_product_evidence_strategy_summary_v0_1.json`
  - `docs/internal/vnext_20260610/product_evidence_strategy_execution.zh-CN.md`

## Results

真实 SEC staging run：

- scanned chunks：`192,055`
- scanned tickers：`577`
- product taxonomy candidates：`13,712`
- taxonomy ticker coverage：`577/577`，`100.0%`
- balanced product KPI candidates：`6,663`
- KPI candidate ticker coverage：`576/577`，`99.83%`
- KPI missing ticker：`BK`
- external source-plan rows：`67`
- commercial tracker rows：`16`，全部 `blocked_no_commercial_policy`

Metric family counts：

- backlog/orders：`1,708`
- product revenue：`987`
- production/throughput：`1,516`
- same-store sales：`126`
- shipments：`777`
- subscribers/ARPU：`149`
- unit sales/deliveries：`1,400`

重要边界：

- taxonomy candidates 只是 `taxonomy_candidate_needs_review`。
- KPI candidates 全部仍是 `needs_value_unit_period_product_parser`。
- 任何官网、proxy、commercial source plan row 都没有被提升为公司产品 KPI fact。

## Validation

- `python -m pytest tests\test_product_evidence_strategy_artifacts.py tests\test_public_source_extended_materialization.py tests\test_public_source_strength_materialization_report.py` -> `10 passed`
- `python -m py_compile scripts\data_expansion\build_product_evidence_strategy_artifacts.py scripts\data_expansion\download_public_source_extended_materialization.py scripts\data_expansion\build_public_source_strength_materialization_report.py` -> pass

## Follow-up

- Build product taxonomy review/normalization gate by industry, starting with high-value industries where product-to-financial bridge matters most: semiconductors/hardware, software, automotive, healthcare, retail/CPG.
- Build value/unit/period/product parser for `company_product_metric_candidates_balanced_v0_1.jsonl`; only parser-verified rows can enter evidence/ledger runtime.
- Build industry-specific public proxy adapters only after mapping gates are defined; do not use generic proxy fallback.
- Keep commercial tracker rows blocked unless user explicitly changes data spend policy.

## Safety Notes

- 本轮没有新增 secret、commercial API key 或 paid data。
- 运行中的全量正则扫描耗时约 5-6 分钟；后续可做性能优化，但不能通过截断公司范围或降低证据标准来换速度。
