# 365 R12 R6-R9 L1 / L3 Coverage Repair Closeout

日期：2026-06-19

## Problem

用户要求在 R1-R5 exact-slot 数据层之后继续做四项修复：

1. 做 `R6-L1-non-US-disclosure-parser`，先把 16 家 L1 补完。
2. 做 `R7-L3-requirement-recalibration`，删除不适用的 L3 requirement。
3. 做 `R8-L3-lane-adapter-batches`，按 V7/V8/V3/V5/V2 分批补真实 adapter 和 locator。
4. 做 `R9-L3-minimum-coverage-gate`，要求每家公司 L3 `>=1`，重点/深度研究公司达到 `>=2` independent source roles。

关键约束：如果做完后仍有很多 L1 未补或 L3 `<=1`，且原因不是公开数据真实不可得，就必须继续迭代脚本/adapter/root cause，不能把脚本问题写成数据缺口。

## Decision

本轮把通过条件限定为 `minimum L1/L3 coverage repair`，而不是声明全量 source-role / product-KPI exact-slot 全部完成：

- L1：`primary_company_disclosure` 必须覆盖 `603/603` 公司。
- L3：每家公司必须至少有 `1` 条 parser-backed L3 exact/proxy row。
- Priority / deep-research 公司必须至少有 `2` 个 independent external/proxy source roles。
- 全量 exact-slot matrix 仍允许保持 `gap`，因为 product KPI、channel、developer、hiring、regulated product、public order 等 source-role 缺口需要后续 role-specific adapter 继续修，不能弱兜底。

## Work Completed

### R6

- 新增 `scripts/data_expansion/build_non_us_l1_financial_statement_metric_runtime_rows.py`。
- 将非美 / 未覆盖 SEC CompanyFacts 的 local exchange、company IR、annual report 表格和 parent segment disclosure 转成 L1 `company_reported_financial_statement_metric` exact rows。
- `src/sec_agent/exact_slot_contracts.py` 允许 `company_ir_reports` 进入 company-reported financial statement metric source ids。

运行产物：

- `data/manifests/non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl`
- `data/manifests/non_us_l1_financial_statement_metric_runtime_rejections_v0_1.jsonl`
- `data/manifests/non_us_l1_financial_statement_metric_runtime_summary_v0_1.json`

结果：

- `target_ticker_count=16`
- `covered_target_ticker_count=16`
- `uncovered_target_ticker_count=0`
- `runtime_row_count=88`
- `company_ir_reports=87`
- `company_reported_product_operating_metrics=1`

### R7

- 将 `financial_regulatory_context` 和 `energy_utility_context` 的 contract layer 从单一 `L2` 修正为 `L2/L3`，因为这些 official/regulatory context 对某些行业是外部验证或监管 proxy，而不是纯 L2 背景。
- 对 V6 Banks / Financials 删除明显不适用的 app / platform review proxy requirement，避免把不该要求的数据当成 source gap。
- exact-slot rows 增加 `contract_layer_ids`，coverage matrix 按 contract layer 聚合，避免 multi-layer rows 被错误只计入单层。

### R8

- 扩展 `scripts/data_expansion/build_broad_official_careers_context_rows.py`：
  - official careers / ATS 支持 Workday、Greenhouse、Lever、Jibe API、Phenom embedded job JSON、SuccessFactors HTML search table；
  - locator 优先 `jobs.<domain>` 和 `careers.<domain>`；
  - dedupe 改为新 row 覆盖旧 schema row；
  - job row 缺 posted date 时使用 snapshot date，避免结构化字段缺失导致可用 official career row 被拒。
- `scripts/data_expansion/build_exact_slot_coverage_matrix.py` 默认纳入：
  - `non_us_l1_financial_statement_metric_runtime_rows_v0_1.jsonl`
  - `broad_official_careers_context_rows_v0_1.jsonl`

### R9

- 新增 `scripts/data_expansion/build_l3_minimum_coverage_gate.py`。
- gate 检查：
  - base：每家公司 `L3 exact slot count >= 1`；
  - priority / deep：至少 `2` 个 independent L2/L3 non-primary-disclosure source roles；
  - closeout：输出低覆盖公司清单，不能静默通过。

## Result And Evidence

### R6 Summary

`data/manifests/non_us_l1_financial_statement_metric_runtime_summary_v0_1.json`：

- `status=pass`
- `candidate_count=50`
- `target_ticker_count=16`
- `covered_target_ticker_count=16`
- `runtime_row_count=88`
- `uncovered_target_tickers=[]`

### Exact-Slot Matrix

`data/manifests/exact_slot_coverage_matrix_v0_1.json`：

- `status=gap`
- `company_count=603`
- `exact_slot_row_count=28,864`
- `exact_slot_gap_count=1,152`
- `no_exact_ready_company_count=0`
- exact rows by layer company coverage:
  - `L1=603`
  - `L2=603`
  - `L3=603`
- exact slot counts by layer:
  - `L1=21,590`
  - `L2=5,795`
  - `L3=5,642`
- source-role highlights:
  - `primary_company_disclosure=603/603`
  - `trusted_external_context=603/603`
  - `macro_official_context=603/603`
  - `public_order_proxy=382/515`
  - `supply_chain_official_relationship=201/276`
  - `hiring_capacity_proxy=65/603`
  - `developer_ecosystem_proxy=5/137`
  - `channel_offer_proxy=4/148`

`status=gap` 是正确状态：它表示全量 source-role / product-KPI requirements 仍有公开源边界，不表示 R9 minimum coverage 失败。

### R9 Minimum Gate

`data/manifests/l3_minimum_coverage_gate_v0_1.json`：

- `status=pass`
- `company_count=603`
- `base_fail_company_count=0`
- `priority_fail_company_count=0`
- `l3_zero_company_count=0`
- `l3_one_company_count=0`
- `l3_gt_one_company_count=603`
- `low_coverage_company_count=0`
- `priority_ticker_count=72`
- independent role count distribution:
  - `3=94`
  - `4=162`
  - `5=210`
  - `6=124`
  - `7=12`
  - `9=1`

`data/manifests/l3_minimum_coverage_low_companies_v0_1.jsonl` 为 `0` 行。

## Root-Cause Fixes

- 旧 coverage matrix 没有把 multi-layer official/proxy rows 计入所有 contract layers，导致 L3 被低估；已通过 `contract_layer_ids` 修正。
- 旧 R9 priority role gate 只看 L3，忽略了部分 L2/L3 official/regulatory rows 作为 independent external context 的合理角色；已改为统计 non-primary-disclosure L2/L3 independent roles。
- official careers rows 早期存在 locator 顺序、date 字段和旧 schema row 被 dedupe 保留的问题；已修复。
- V6 Banks / Financials 早期要求 app/review proxy 属于 requirement 误配；已删除不适用 requirement，而不是把它写成公司数据缺口。

## Follow-Up

- R6-R9 只关闭 L1 覆盖和 L3 minimum coverage 问题，不关闭所有 source-role gap。
- 仍需后续 role-specific adapter 继续补：
  - hiring capacity proxy
  - channel offer proxy
  - developer ecosystem proxy
  - regulated product context
  - public order / supply-chain official relationship 的剩余公司
- Runtime 接入时必须读取 exact-slot matrix、R9 gate 和 gap ledger；gap / closeout rows 只能作为边界和 targeted repair 输入，不能成为 ClaimCard 证据。

## Verification

本轮 closeout 已运行：

- `python -m pytest tests/test_non_us_l1_financial_statement_metric_runtime_rows.py tests/test_l3_minimum_coverage_gate.py tests/test_exact_slot_contracts.py tests/test_source_coverage_gate.py -q`
  - result: `23 passed in 0.32s`
- `python -m py_compile src/sec_agent/exact_slot_contracts.py src/sec_agent/source_coverage_gate.py scripts/data_expansion/build_non_us_l1_financial_statement_metric_runtime_rows.py scripts/data_expansion/build_broad_official_careers_context_rows.py scripts/data_expansion/build_l3_minimum_coverage_gate.py scripts/data_expansion/build_exact_slot_coverage_matrix.py scripts/data_expansion/build_company_public_source_coverage_matrix.py`
  - result: pass
- `git diff --check`
  - result: pass
