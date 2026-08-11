# P34 AI/Semis Adapter Fixture Report

日期：2026-07-07

## 背景

P34-4 已经把 AI/Semis 的 20 个 evidence slot 绑定到 source route 和 adapter family。P34-5 的目标不是继续扩路线图，而是验证首批 adapter family 能把代表性输入解析为统一 runtime row，并且保留 parser lineage、authority scope 和 cannot-infer 边界。

## 本轮完成

- 扩展 `src/sec_agent/p34_lane_quality_runtime.py`，新增 adapter fixture parser contract。
- 新增 `scripts/eval_multi_agent/run_p34_ai_semis_adapter_fixtures.py`。
- 新增 `tests/test_p34_ai_semis_adapter_fixtures.py`。
- 生成 `docs/project_os/p34_ai_semis_adapter_fixture_report_v0_1.json`。
- 生成 `docs/internal/vnext_20260610/p34_ai_semis_adapter_fixture_report_v0_1.zh-CN.md`。

## 覆盖的 Adapter Family

1. `sec_8k_earnings_release_table_adapter`
2. `official_product_spec_page_adapter`
3. `semicap_bookings_backlog_adapter`

## 结果

- adapter family：`3`。
- fixture：`9`。
- normalized runtime rows：`9`。
- rejected false-substitute candidates：`9`。
- typed gaps：`0`。
- rows with parser lineage：`9`。
- rows with authority scope：`9`。

## 验证

- `python scripts/eval_multi_agent/run_p34_ai_semis_adapter_fixtures.py --strict`
- `python -m pytest tests/test_p34_ai_semis_adapter_fixtures.py tests/test_p34_ai_semis_source_route_plan.py tests/test_p34_lane_quality_first_program.py -q`
- `python -m py_compile src/sec_agent/p34_lane_quality_runtime.py scripts/eval_multi_agent/run_p34_ai_semis_adapter_fixtures.py scripts/eval_multi_agent/run_p34_ai_semis_source_route_plan.py`

当前 P34 focused tests 合计 `13 passed`。

## 边界

这一步是本地 artifact-backed parser contract fixture，不是 live fetch/crawl/parser closeout。`source_url` 使用 `source-ledger://p34/...`，只能表示 fixture lineage，不能当真实 URL snapshot。fixture rows 的 `promotion_status=fixture_parser_contract_pass_live_fetch_pending`，不能直接进入 live evidence bundle。

## 下一步

P34 下一步是把首批 adapter 接到真实 source route attempts，或对无法公开取得/无法解析的 slot 写 attempt-backed typed gap；然后运行 P34 no-paid quality audit，检查 judgment chain answerability、slot coverage、promoted row quality、specialist input readiness 和 writer payload readiness。
