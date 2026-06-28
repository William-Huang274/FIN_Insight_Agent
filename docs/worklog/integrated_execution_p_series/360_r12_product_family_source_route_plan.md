# 360 R12 Product-Family Source Route Plan

日期：2026-06-18

## 背景

16 文档 Step 8 的 company-level source matrix 已证明：lane source route 已经存在，但大量公司还没有 company-specific runtime rows。用户进一步要求不要只停留在 lane 层，需要先保证每家公司都有自己的：

- `ProductFamilyLaneRegistry`
- `CompanyProductFamilyAssignment`
- `FamilySourceRoutePlan`

并且在 full-chain 前先审计抓下来的信息是否与公司 / 产品族方向一致。

## 本轮实现

新增 runtime contract 和 builder：

- `src/sec_agent/product_family_source_routes.py`
- `scripts/data_expansion/build_product_family_source_route_plan.py`
- `tests/test_product_family_source_routes.py`

生成 artifacts：

- `data/manifests/product_family_lane_registry_v0_1.json`
- `data/manifests/company_product_family_assignments_v0_1.jsonl`
- `data/manifests/family_source_route_plan_v0_1.jsonl`
- `data/manifests/family_source_fetch_audit_v0_1.json`
- `docs/internal/vnext_20260610/vertical_lanes/product_family_source_route_plan.zh-CN.md`

## 关键结果

- `company_count=603`
- `family_count=45`
- `family_assignment_count=799`
- `route_plan_count=3,132`
- `runtime_family_row_available=141`
- `runtime_company_row_available=460`
- `seed_available_not_materialized=1,360`
- `not_materialized=1,171`

所有 `603/603` 公司都有至少一个 product-family assignment 和 route plan。

## 修复的问题

1. `_family()` helper 初始位置会导致运行期 import 失败，已移动到 registry 定义前。
2. 官方产品页 materialized snapshot 初版会被所有 route 复用，导致 `channel_offer_proxy/public_order_proxy` 等 L3 route 被错误满足；已收紧为只有 `official_product_surface` 可以消费该类 page snapshot。
3. 弱关键词会污染 family assignment，例如 `ip/node/power/rack/server/cloud/vehicle/mobility` 会把 ASML/TSM/NVDA/AAPL/TSLA 误挂到不相关 family；已加入 weak-term gate。
4. trusted external / macro / peer context 不能参与 company product-family assignment，否则行业对标词会被误认为公司产品族；已把 assignment 文本索引限制为 issuer-bound company/product rows。

## 抽样核验

本轮抽查结果：

- `NVDA -> gpu_accelerator / networking`
- `ASML -> semicap_equipment`
- `TSM -> foundry`
- `DELL -> server_oem`
- `SMCI -> server_oem`
- `ANET -> networking`
- `VRT -> power_grid_cooling`
- `AAPL -> smartphones_tablets / pcs_peripherals / wearables_devices`
- `MSFT -> cloud_infrastructure / ai_platform / gaming_devices / pcs_peripherals`
- `AMZN -> cloud_infrastructure`
- `GOOGL -> cloud_infrastructure / ai_platform`
- `LLY -> glp1_metabolic / oncology_immunology`
- `TSLA -> ev_vehicle_platform / battery_charging_autonomy`

## 边界

这一步完成的是 family-scoped route baseline，不等于全部 L2/L3 非 SEC 源已经抓取解析。

当前剩余队列：

- `1,360` 条 `seed_available_not_materialized`：有 seed，但还没转成真实 parser-backed runtime row。
- `1,171` 条 `not_materialized`：还需要按 family route 做官方源 / 可信源 / proxy 源发现、抓取、解析，或最终暴露为 bounded/commercial gap。

## 验证

- `python -m py_compile src\sec_agent\product_family_source_routes.py scripts\data_expansion\build_product_family_source_route_plan.py`
- `python -m pytest tests\test_product_family_source_routes.py -q` -> `3 passed`
- `python scripts\data_expansion\build_product_family_source_route_plan.py` -> generated 603-company family route artifacts

## 下一步

1. 优先处理 `seed_available_not_materialized`：从 product evidence graph / company matrix seed 解析 URL 或 raw locator，抓取并转成 bounded runtime rows。
2. 再处理 `not_materialized`：按 family route policy 做 source discovery，不允许直接 fallback 成 gap。
3. 每轮 repair 后重跑：
   - `build_company_public_source_coverage_matrix.py`
   - `build_product_family_source_route_plan.py`
4. 每个 lane 抽样 5-10 个代表公司核验 family assignment、sample URL、parser row 和 claim boundary。
