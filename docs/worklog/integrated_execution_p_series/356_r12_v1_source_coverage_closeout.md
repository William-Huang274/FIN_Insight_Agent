# 356 R12 V1 Source Coverage Closeout

日期：2026-06-17

## Problem

16 文档完成 L4 runtime contract、VerticalSourceLaneRegistry 和 V1 lane package 后，V1 仍只有 package-level `lane_source_coverage_gate.status=gap`。这不足以指导下一步：需要知道哪些 requirement 已经有真实 runtime rows，哪些只是 source profile ready 但没有 V1 数据，哪些是 parser/resolver gap，哪些必须保持 commercial gap。

## Decision

新增 V1 source coverage closeout runtime，不用弱 fallback，也不把 registry profile 当成真实覆盖：

- registry gate 继续说明 source profile / route readiness；
- closeout gate 同时读取真实 materialized L1/L2/L3 rows；
- requirement 只有在 primary V1 ticker 上有 parser-backed row，且需要绑定时绑定足够，才记 `pass`；
- 只有 secondary / adjacent ticker rows 时不算 primary V1 coverage，写 `adjacent_or_secondary_route_only_gap`；
- commercial tracker 缺口单独进入 commercial gap ledger，不被 public proxy 兜底。

## Work Completed

- 新增 `src/sec_agent/vertical_source_lane_closeout.py`。
- 新增 `scripts/data_expansion/build_v1_source_coverage_closeout.py`。
- 新增 `tests/test_v1_source_coverage_closeout.py`。
- 生成真实 V1 closeout 产物：
  - `data/manifests/v1_semiconductors_ai_infrastructure_source_closeout_v0_1.json`
  - `docs/internal/vnext_20260610/vertical_lanes/v1_source_coverage_closeout.zh-CN.md`
- 更新 16 文档、master checklist、worklog README。

## Real Closeout Result

- status: `gap`
- requirement_count: `10`
- pass_requirement_count: `4`
- source_gap_requirement_count: `6`
- observed_runtime_row_count: `390`
- observed_primary_ticker_count: `13/43`
- commercial_gap_count: `15`

Pass requirements:

- `primary_company_disclosure`
- `official_product_surface`
- `developer_ecosystem_proxy`
- `channel_offer_proxy`

Remaining source gaps:

- `trusted_external_context`: source profile ready, but V1 runtime rows `0`.
- `supply_chain_official_relationship`: only secondary / adjacent ticker rows, primary V1 rows `0`.
- `public_order_proxy`: only secondary / adjacent ticker rows, primary V1 rows `0`.
- `hiring_capacity_proxy`: source profile ready, but V1 runtime rows `0`.
- `macro_official_context`: source profile ready, but V1 runtime rows `0`.
- `technology_research_proxy`: OpenAlex / PatentsView parser or mapping not runtime-ready for V1.

## Verification

Commands:

```powershell
python -m py_compile src\sec_agent\vertical_source_lane_closeout.py scripts\data_expansion\build_v1_source_coverage_closeout.py
python -m pytest tests\test_v1_source_coverage_closeout.py -q
python scripts\data_expansion\build_v1_source_coverage_closeout.py
git diff --check
```

Results:

- `py_compile` pass.
- `tests/test_v1_source_coverage_closeout.py`: `2 passed`.
- Real builder status: `gap`, validation `pass`.
- `git diff --check` pass at this checkpoint.

## Boundary

This closes out the ambiguity, not the source coverage itself. V1 now has an explicit repair list. The next step is `R12 V1 source repair tranche`, starting with public/free sources that are already reachable but not mapped to primary V1 issuers.
