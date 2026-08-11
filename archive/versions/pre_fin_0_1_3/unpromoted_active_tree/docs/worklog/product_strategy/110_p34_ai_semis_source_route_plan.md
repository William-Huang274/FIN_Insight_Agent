# P34 AI/Semis SourceRoutePlan

日期：2026-07-07

## 背景

P34 的核心口径是先定义研究质量，再倒推 judgment chain、evidence slot、source route、parser 和 runtime promotion。P34-1 到 P34-3 已经把 AI/Semis 的研究质量、判断链和 evidence slot contract 落成机器可读 artifacts。P34-4 的目标是把这些 slot 明确绑定到 source route / adapter family，而不是继续用泛数据或宽松匹配冒充可提权证据。

## 本轮完成

- 新增 `src/sec_agent/p34_lane_quality_runtime.py`。
- 新增 `scripts/eval_multi_agent/run_p34_ai_semis_source_route_plan.py`。
- 新增 `tests/test_p34_ai_semis_source_route_plan.py`。
- 生成 `docs/project_os/p34_ai_semis_source_route_plan_v0_1.json`。
- 生成 `docs/internal/vnext_20260610/p34_ai_semis_source_route_plan_v0_1.zh-CN.md`。

## 结果

- evidence slots：`20`。
- source routes：`47`。
- primary routes：`20`。
- fallback routes：`27`。
- slots with primary route：`20/20`。
- slots with fallback route：`20/20`。
- route gaps：`0`。
- adapter family：`15`。

## 验证

- `python scripts/eval_multi_agent/run_p34_ai_semis_source_route_plan.py --strict`
- `python -m pytest tests/test_p34_ai_semis_source_route_plan.py tests/test_p34_lane_quality_first_program.py -q`
- `python -m py_compile src/sec_agent/p34_lane_quality_runtime.py scripts/eval_multi_agent/run_p34_ai_semis_source_route_plan.py`

当前 P34 focused tests 合计 `9 passed`。

## 边界

这一步只证明 AI/Semis evidence slot 到 primary/fallback source route 和 adapter family 的规划完整。它不证明：

- source 已抓取；
- crawler/parser 已实现；
- parser lineage 已存在；
- runtime row 可提权；
- Research Lead / specialist 已消费；
- paid Memo Writer 或 full-chain 已通过；
- 模型对比有意义。

## 下一步

P34-5 固定优先做三个 adapter-family fixture：

1. `sec_8k_earnings_release_table_adapter`
2. `official_product_spec_page_adapter`
3. `semicap_bookings_backlog_adapter`

每个 fixture 必须有真实 parser lineage、typed failure reason 和 runtime row boundary。不能把 route plan 当成 source/parser readiness。
