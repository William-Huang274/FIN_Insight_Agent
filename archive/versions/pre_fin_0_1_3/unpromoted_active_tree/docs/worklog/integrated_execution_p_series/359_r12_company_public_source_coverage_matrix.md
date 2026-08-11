# 359 R12 Company Public Source Coverage Matrix

日期：2026-06-18

## 问题

用户指出 16 文档的 `8/8 lane pass` 仍不能代表 600+ 公司、每个产品/车型/适应症/SKU 已完整覆盖。需要把覆盖口径从 lane-level route 下钻到 issuer-level matrix，避免 Research Lead 在 full-chain 中误把 lane closeout 当成公司级数据已齐。

## 决策

- 保留现有 lane closeout，不改变 `source_gap_requirement_count=0` 的含义。
- 新增更严格的 company matrix：`Company x SourceRole x Parser x Binding x Gap`。
- 每家公司按自己的 primary lane requirements 生成 source role rows，记录 parser-backed runtime row、issuer/product/counterparty binding、exact-authority violation 和 gap class。
- 对不能 pass 的 requirement 生成 repair queue；后续按 lane / requirement / source_id 分 tranche 补源，而不是继续全局零散接源。

## 完成

- 新增 `src/sec_agent/company_public_source_coverage_matrix.py`。
- 新增 `scripts/data_expansion/build_company_public_source_coverage_matrix.py`。
- 新增 `tests/test_company_public_source_coverage_matrix.py`。
- 生成：
  - `data/manifests/company_public_source_coverage_matrix_v0_1.json`；
  - `data/manifests/company_public_source_coverage_matrix_v0_1.jsonl`；
  - `data/manifests/company_public_source_repair_queue_v0_1.jsonl`；
  - `docs/internal/vnext_20260610/vertical_lanes/company_public_source_coverage_matrix.zh-CN.md`。
- 更新：
  - `docs/architecture/agent_graph_vnext/16_l4_weak_signal_and_vertical_source_lane_framework.zh-CN.md`；
  - `docs/architecture/agent_graph_vnext/17_09_15_completion_gap_register.zh-CN.md`；
  - `docs/worklog/00_internal_master_checklist.md`；
  - `docs/worklog/README.md`。

## 结果

首次 603 公司矩阵：

- `company_count=603`；
- `requirement_count=4,418`；
- `pass_requirement_count=432`；
- `gap_requirement_count=3,986`；
- `fail_requirement_count=0`；
- `public_interface_ready_company_count=1`；
- `partial_public_interface_company_count=220`；
- `public_interface_gap_company_count=382`；
- `repair_queue_count=3,986`。
- repair seed status:
  - `seed_available=1,584`；
  - `seed_missing=2,402`。

gap 分布：

- `company_specific_runtime_row_missing=3,569`；
- `sec_or_company_disclosure_runtime_row_missing=402`；
- `non_us_public_filing_or_company_ir_runtime_row_missing=15`。

主要 repair requirement：

- `trusted_external_context=567`；
- `macro_official_context=566`；
- `hiring_capacity_proxy=515`；
- `public_order_proxy=421`；
- `primary_company_disclosure=417`；
- `official_product_surface=214`。

high-priority seed 情况：

- `primary_company_disclosure`：`417/417` 有 Z 盘 product graph seed；
- `official_product_surface`：`208/214` 有 Z 盘 product graph seed。

结论：当前主要问题不是 parser-backed row 的 parser/resolver 失败，而是大量 company-specific runtime rows 尚未物化。Lane route 已通，但 issuer-level public source interface 还没有完成。

## 验证

- `python -m py_compile src\sec_agent\company_public_source_coverage_matrix.py scripts\data_expansion\build_company_public_source_coverage_matrix.py` 通过。
- `python -m pytest tests\test_company_public_source_coverage_matrix.py -q`：`2 passed`。
- `python scripts\data_expansion\build_company_public_source_coverage_matrix.py`：生成 `603` 公司矩阵和 `3,986` 条 repair queue。

## 后续

1. 先按 repair queue 做 high-priority tranche：
   - `primary_company_disclosure`；
   - `official_product_surface`。
2. 再补 L2：
   - trusted external / mainstream financial news；
   - macro official exposure bridge；
   - regulatory / official API issuer-product binding。
3. 最后补 L3：
   - hiring；
   - public order；
   - channel/ecommerce/app marketplace/developer proxy。
4. 每个 tranche 后必须重跑 company matrix，把 gap 降低、改类为 parser/resolver、或证明为 bounded/commercial gap。
