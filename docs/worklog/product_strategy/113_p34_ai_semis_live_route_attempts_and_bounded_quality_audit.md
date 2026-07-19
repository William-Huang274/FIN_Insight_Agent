# 113 P34 AI/Semis Live Route Attempts And Bounded Quality Audit

日期：2026-07-07

## 背景

用户要求继续 P34，但不能直接跑 paid writer 或 full-chain。当前必须先补真实 `source route attempts` 和 `attempt-backed typed gaps`，重点覆盖：

- hyperscaler capex；
- customer deployment / OEM config；
- market price-in / capital feedback；
- counter-thesis；
- DELL AI server margin bridge。

执行口径继承 Project OS / Global Stewardship：不能用 gate 掩盖 parser/source-route 问题；不能把 source route plan、adapter fixture 或 no-paid audit 当成最终研究质量通过；只有真实 route attempt 或 attempt-backed typed gap 才能进入下一步 scoped writer 判断。

## 完成工作

1. 修复 owned source-fetch 问题。
   - AMD 官方 HTML/PDF 在 PowerShell 和 requests 下可达，但原 Python urllib 路径 timeout，导致可得 source 被误判为 `locator_gap`。
   - `src/sec_agent/p34_lane_quality_runtime.py` 现在优先使用 `requests.get()` + browser-like headers；PDF 使用 `pypdf` 解析前 5 页；失败后再回退 urllib。

2. 修复 source route specificity。
   - AMD MI300X 官方规格 keyword 从 `192GB` 改为 `192 GB`，避免误判。
   - LRCX route 从泛 quarterly-result 新闻稿改为 Lam 官方 advanced packaging 技术页，能抓到 `HBM / TSV / etch / deposition` 相关内容。

3. 执行真实 live route attempts。
   - Artifact：`docs/project_os/p34_ai_semis_live_route_attempt_report_v0_1.json`
   - 报告：`docs/internal/vnext_20260610/p34_ai_semis_live_route_attempt_report_v0_1.zh-CN.md`

4. 更新 no-paid quality audit 两级语义。
   - 如果所有 slot 均已尝试，且剩余 gaps 都是 attempt-backed typed gaps，则允许 scoped paid Memo Writer node。
   - 该状态仍不允许 broad full-chain、模型对比、case expansion 或 release eval。

5. 更新源文档、Project OS、checklist 和 README。
   - `docs/internal/vnext_20260610/p34_lane_quality_first_source_runtime_program.zh-CN.md`
   - `docs/project_os/current_context_pack.zh-CN.md`
   - `docs/worklog/00_internal_master_checklist.md`
   - `docs/internal/vnext_20260610/README.md`
   - `docs/worklog/README.md`

## 结果

Live route attempt 结果：

- `slot_count=20`
- `attempted_slot_count=20`
- `attempt_count=21`
- `accepted_live_runtime_row_count=21`
- `accepted_slot_count=20`
- `network_attempt_count=15`
- `network_ok_count=15`
- `unattempted_slot_count=0`
- `typed_gap_count=2`
- `attempt_backed_gap_slot_count=2`
- `paid_llm_run=false`
- `full_chain_run=false`

No-paid quality audit 第二轮结果：

- `status=bounded_quality_audit_pass_scoped_writer_allowed_full_chain_blocked`
- `judgment_chain_count=7`
- `chain_pass_count=5`
- `chain_partial_count=2`
- `chain_fail_count=0`
- `source_route_gap_count=0`
- `allow_scoped_paid_memo_writer=true`
- `allow_paid_memo_writer=true`
- `allow_full_chain=false`

## 剩余边界

1. `dell_ai_server_margin_bridge_quality_gap`
   - 类型：`source_absent_after_attempt`。
   - Dell 公开 rows 能支持 AI server revenue / order visibility 和 ISG baseline，但没有披露 AI server mix、GPU pass-through cost、AI server gross margin 或 backlog conversion。
   - 后续 writer 只能写 bounded margin-quality view，不能写成 AI server 毛利改善已被证明。

2. `market_price_in_exact_positioning_gap`
   - 类型：`commercial_gap`。
   - 公开 delayed/context rows 能支持 price-in discussion，但 exact crowding、real-time flow、complete options positioning、borrow cost、institutional flow 需要商业数据或更深 adapter。
   - 后续 writer 只能写 valuation / expectation / price-reaction context，不能写精确拥挤度或资金流。

## 验证

已运行：

```powershell
python -m py_compile src/sec_agent/p34_lane_quality_runtime.py scripts/eval_multi_agent/run_p34_ai_semis_live_route_attempts.py scripts/eval_multi_agent/run_p34_ai_semis_no_paid_quality_audit.py
python scripts/eval_multi_agent/run_p34_ai_semis_live_route_attempts.py --live-probe --timeout-seconds 20 --strict
python scripts/eval_multi_agent/run_p34_ai_semis_no_paid_quality_audit.py --strict
python -m pytest tests/test_p34_ai_semis_no_paid_quality_audit.py tests/test_p34_ai_semis_live_route_attempts.py
python -m pytest tests/test_p34_lane_quality_first_program.py tests/test_p34_ai_semis_source_route_plan.py tests/test_p34_ai_semis_adapter_fixtures.py tests/test_p34_ai_semis_live_route_attempts.py tests/test_p34_ai_semis_no_paid_quality_audit.py
```

结果：

- py_compile pass。
- live route attempts strict pass。
- no-paid quality audit strict pass。
- focused tests `7 passed`。
- P34 combined focused tests `20 passed`。

未运行：

- paid LLM。
- paid Memo Writer。
- broad full-chain。
- 模型对比。
- case expansion。
- release eval。

## 下一步

下一步只允许 P34-9 scoped paid Memo Writer node：

1. 使用 P34 accepted live rows + 两个 attempt-backed typed gaps 生成 bounded writer payload。
2. Memo Writer 必须覆盖 7 条 judgment chains，并显式保留 DELL margin bridge 与 market price-in 的边界。
3. 之后必须跑 renderer projection、final verifier projection、Workbench projection 和人工审阅。
4. 如果 writer 把 proxy 写成 exact fact、把 attempt-backed gap 写成 public-source absent、或忽略 live rows，必须回到 writer payload / JudgmentCard / graph projection 修复，不得用 full-chain 重跑掩盖。
