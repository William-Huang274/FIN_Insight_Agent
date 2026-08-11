# 202 Multi-agent Step 13 Judgment Memo Verifier Loop

日期：2026-05-30

## Prompt

用户要求继续沿 188 文档往下做。Step 11 已完成后，下一个确定性主线缺口是 Step 13：把 Specialist Analysis 输出、Judgment Plan、Memo Writer、Verifier 连接成业务闭环。

## Decision

本轮不追求真实 LLM 写作质量，而先保证合同和门控：

- Specialist 的 supported / conflict / unsupported 输出不能在 graph state 中丢失。
- Memo Writer 只能消费 `verified_judgment_plan` / `verified_summary`，不能读 raw rows、不能调用工具。
- Verifier 只做 inspect-only 检查，不生成新观点、不扩范围、不触发检索。
- Market / industry / relationship source 不能被用作公司披露财务事实。

## Work Completed

- `src/sec_agent/multi_agent_contracts.py`
  - 扩展 `aggregate_specialist_judgment_plan()`：输出 `source_boundary_notes`、`memo_constraints`、`memo_writer_allowed`。
  - 扩展 `verify_specialist_outputs_for_memo()`：输出 `verified_judgment_plan` 和 blocked reasons。
  - 新增 `build_multi_agent_memo_draft()`：deterministic Memo Writer，只消费 verified plan / verified summary；不允许 raw rows / tool calls。
  - 新增 `verify_multi_agent_memo_draft()`：阻断 unsupported claim text、raw rows、tool calls、unknown evidence refs、market/industry/relationship source misuse，并输出 repair instruction。
- `src/sec_agent/langgraph_orchestrator.py`
  - `aggregate_judgment_plan` node 注入 reflection report、EvidenceRequirementPlan、source gaps、tool ledger summary。
  - graph state 新增 `verified_judgment_plan`。
  - default Memo Writer 改为走 deterministic memo draft builder。
  - default Verifier 改为走 memo draft verifier，并在失败时设置 bounded answer。
  - default Renderer 在 verifier fail 时输出 bounded answer。
- `tests/test_multi_agent_judgment_memo_verifier.py`
  - 新增 Step 13 gate，覆盖 Judgment Plan 保留冲突/unsupported、Memo Writer input boundary、Verifier raw/tool/unsupported/source misuse 阻断，以及 graph 状态传播。
- `docs/worklog/188_multi_agent_architecture_execution_plan.md`
  - 更新 Step 13 当前状态和验证结果。
- `docs/worklog/00_internal_master_checklist.md`
  - 勾选 Step 13 业务闭环和 Memo Writer / Verifier gate，追加 Step 14 后续项。

## Verification

- `pytest tests/test_multi_agent_judgment_memo_verifier.py tests/test_multi_agent_contracts.py tests/test_multi_agent_langgraph_routing.py -q`
  - `19 passed in 0.93s`
- `pytest -q`
  - `335 passed in 11.59s`
- `git diff --check`
  - passed

## Safety Notes

- 未运行真实 LLM 调用。
- 未写入 API key、SSH 密码、private token 或 `.env`。
- 本轮没有执行 git stage / commit。

## Next Step

进入 Step 14：Universe / Relationship 与 Industry / Supply Chain Analyst 的真实业务合同。重点是 relationship graph 只能支持研究范围和假设，不能直接支持财务事实；它应驱动 EvidenceRequirementPlan 的范围扩展和 source-family 需求，而不是绕过 operator 或 verifier。
