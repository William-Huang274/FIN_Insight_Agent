# 358 R12 V2-V8 Vertical Lane Closeout

日期：2026-06-17

## 背景

16 文档的主线要求先把 L1-L3 具体按行业 / 公司类别 / 产品细分扩 source lane 做踏实，再讨论 17 或后续 agent graph / skill。前一轮只完成了 L4 runtime contract、VerticalSourceLaneRegistry、V1 package 和 V1 source closeout；V2-V8 仍停留在 registry/profile 层。

## 本轮实现

- 泛化 V1 source closeout：
  - `src/sec_agent/vertical_source_lane_closeout.py`
  - `scripts/data_expansion/build_vertical_lane_source_closeouts.py`
- 新增通用 lane package builder：
  - `src/sec_agent/vertical_source_lane_package.py`
  - `scripts/data_expansion/build_vertical_lane_packages.py`
- 新增 V2-V8 lane-scoped public context backfill：
  - `scripts/data_expansion/build_vertical_lane_public_context_rows.py`
  - 输出 `data/manifests/vertical_lane_public_context_rows_v0_1.jsonl`
- 为 V2-V8 生成：
  - AnalystPlaybook；
  - SourcePlaybook；
  - lane coverage report；
  - lane coverage JSON；
  - 每 lane `3` 个 representative deterministic cases。

## 数据结果

- `vertical_lane_public_context_rows_v0_1.jsonl`：`77` 条 parser-backed bounded context rows。
- 覆盖 source route：
  - `industry_association_reports`
  - `fred_api`
  - `eia_open_data`
  - `job_postings_hiring_signals`
  - `channel_pricing_quotations`
  - `platform_reviews_rankings_downloads`
  - `public_tenders_contracts_orders`
  - `openalex_api`
- 真实 fetch/API attempts：`23/23 materialized`。
- `vertical_lane_source_closeouts_v0_1.json`：
  - `8/8` lanes pass；
  - 所有 lane `source_gap_requirement_count=0`；
  - commercial gaps 继续保留，公开 proxy 不替代 tracker。

## Closeout Summary

| lane | requirements | observed rows | observed primary | source gaps | commercial gaps |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 10/10 | 475 | 15/43 | 0 | 15 |
| V2 | 8/8 | 250 | 4/9 | 0 | 16 |
| V3 | 9/9 | 687 | 31/94 | 0 | 16 |
| V4 | 8/8 | 939 | 28/68 | 0 | 6 |
| V5 | 9/9 | 376 | 7/17 | 0 | 15 |
| V6 | 4/4 | 632 | 30/77 | 0 | 7 |
| V7 | 7/7 | 2,514 | 77/216 | 0 | 16 |
| V8 | 7/7 | 921 | 29/79 | 0 | 10 |

## 边界

- Closeout pass 是 requirement-level route availability，不等于每个 ticker、product、SKU、车型、适应症、资产都完整覆盖。
- 新增 rows 全部是 `context_only=true`、`can_support_company_exact_fact=false`、`exact_value_authority=false`。
- V5 初版 Tesla careers / configurator 出现 403，已改用 Uber Careers、Chevrolet official model page、USAspending、FRED bridge 完成 lane route；这不代表 Tesla 单公司 channel/hiring coverage 完整。
- V7 初版 GE Careers URL 错误，已改为 `https://careers.gevernova.com/jobs` 后 materialized。

## 验收

- `python -m py_compile src\sec_agent\vertical_source_lane_closeout.py src\sec_agent\vertical_source_lane_package.py scripts\data_expansion\build_vertical_lane_packages.py scripts\data_expansion\build_vertical_lane_public_context_rows.py scripts\data_expansion\build_vertical_lane_source_closeouts.py`
- `python -m pytest tests\test_vertical_source_lane_package_and_closeout.py tests\test_v1_semiconductor_ai_infrastructure_lane.py tests\test_vertical_source_lane_registry.py -q`
  - `6 passed`
- `python scripts\data_expansion\build_vertical_lane_source_closeouts.py`
  - `8/8 pass`

## 后续

16 的 L4 runtime contract、V1-V8 lane package、V1-V8 source closeout 已闭环。下一阶段如果回到 09-15 / R12，应基于这个 lane baseline 跑 successor/broader release case，并持续检查 role-specific selector 和 memo quality，而不是继续用全局 source list 零散补源。
