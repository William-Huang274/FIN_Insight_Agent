# 353 R12 Vertical Source Lane Registry

Date: 2026-06-17

## Prompt

继续执行 16 文档 Step 1：构建 600+ 公司 `VerticalSourceLaneRegistry`，包括 primary / secondary lane、representative tickers、product taxonomy scope、L1/L2/L3/L4 source requirements、public data ceiling、commercial gaps 和 lane coverage gates。

## Decision

不再用全局 source bucket 推进 600+ 公司扩容。先把每家公司归入 vertical source lane，再让 Research Lead / Specialist 读取 lane brief 和 lane source requirements。

registry builder 必须读真实输入，不用 mock：

- 603 公司 universe；
- product evidence graph nodes/gaps；
- company-reported product KPI runtime rows；
- official product surface runtime rows；
- source-layer capability audit rows。

## Work Completed

- 新增 `src/sec_agent/vertical_source_lane_registry.py`：
  - 定义 V1-V8 lane contract；
  - 构建 `VerticalSourceLaneRegistry`；
  - 分配 company primary / secondary lane；
  - 聚合 product KPI / official product surface / commercial gap coverage；
  - 调用 source coverage gate 生成 registry phase lane gate；
  - 输出 registry report。
- 新增 `scripts/data_expansion/build_vertical_source_lane_registry.py`：
  - 默认读取真实 D/Z 盘输入；
  - 写出 JSON registry、company assignment JSONL 和中文 report。
- 新增 `tests/test_vertical_source_lane_registry.py`：
  - 验证 8 个代表行业公司的 primary lane；
  - 验证 MSFT primary V3、secondary V1/V2；
  - 验证 DELL primary V1、secondary V2；
  - 验证 validator fail-closed。
- 真实生成：
  - `data/manifests/vertical_source_lane_registry_v0_1.json`
  - `data/manifests/vertical_source_lane_company_assignments_v0_1.jsonl`
  - `docs/internal/vnext_20260610/vertical_source_lane_registry.zh-CN.md`
- 更新 `docs/architecture/agent_graph_vnext/16_l4_weak_signal_and_vertical_source_lane_framework.zh-CN.md`，记录 Step 1 当前实现状态、真实输出路径和 lane 分布。
- 更新 `docs/worklog/00_internal_master_checklist.md`，将 R12 vertical source lane registry 标记为完成。
- 更新 `docs/worklog/README.md`。

## Real Registry Result

Registry validation: `pass`.

Company count: `603`.

Primary lane distribution:

| lane | primary | inclusive |
| --- | ---: | ---: |
| V1 Semiconductors / AI Infrastructure | 43 | 57 |
| V2 Consumer Electronics / Hardware Devices | 9 | 12 |
| V3 SaaS / Cloud / Developer Products | 94 | 97 |
| V4 Pharma / Biotech / Medtech | 68 | 68 |
| V5 Auto / Mobility / Transport Platforms | 17 | 17 |
| V6 Banks / Financials / Capital Markets | 77 | 77 |
| V7 Energy / Utilities / Industrials | 216 | 219 |
| V8 Retail / CPG / Restaurants / Travel | 79 | 80 |

Important cross-lane checks:

- `MSFT`: primary V3, secondary V1/V2.
- `DELL`: primary V1, secondary V2.
- `AAPL`: primary V2, secondary V3.
- `ASML` / `TSM` / `NVDA`: primary V1.

## Verification

Commands:

```powershell
python -m py_compile src\sec_agent\vertical_source_lane_registry.py scripts\data_expansion\build_vertical_source_lane_registry.py
python -m pytest tests\test_vertical_source_lane_registry.py -q
python scripts\data_expansion\build_vertical_source_lane_registry.py
```

Results:

- `py_compile` pass.
- `tests/test_vertical_source_lane_registry.py`: `2 passed`.
- Real builder status: `pass`, company_count `603`, lane_count `8`.

## Boundary

Step 1 freezes the registry and source requirements. It does not mean each lane has complete source coverage.

Current lane source coverage gates are still `gap`, which is expected at this stage. The next step is V1 Semiconductors / AI Infrastructure lane closeout:

- analyst/source playbook;
- V1 ticker universe freeze and representative cases;
- L1 financial/product KPI focus;
- L2 official/regulatory/source resolvers;
- L3 proxy routes;
- L4 discovery rules;
- lane coverage report;
- 2-3 representative deterministic/eval cases.
