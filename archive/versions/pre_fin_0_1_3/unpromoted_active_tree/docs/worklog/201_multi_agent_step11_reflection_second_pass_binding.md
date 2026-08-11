# 201 Multi-agent Step 11 Reflection Second-pass Binding

日期：2026-05-30

## Prompt

继续沿 188 文档执行，在完全对齐 185/186 后从 Step 11 推进 Coverage / Reflection 与 second-pass 闭环业务化。

## Decision

Reflection 不能把“再检索一次”表达成工具调用或物理 route。它必须先把 coverage 缺口绑定回业务层 EvidenceRequirementPlan，再输出可编译的 second-pass business request，由 deterministic retrieval-plan compiler 生成 route，之后才允许 operator 执行。

本轮只完成 Step 11 的合同和 graph 接线，不接入新的真实 LLM 运行。

## Work Completed

- `src/sec_agent/multi_agent_runtime.py`
  - `reflection_report_from_coverage()` 新增 EvidenceRequirementPlan、source gaps、tool ledger summary 输入。
  - coverage 缺口现在携带 `requirement_id`、`task_id`、`source_family_gaps`、`source_families`、`operator_owners`、`evidence_routes`、`route_intents`、`claim_families`。
  - 新增 `second_pass_evidence_requirement_plan_from_reflection()`，把 Reflection second-pass request 转回业务层 EvidenceRequirementPlan。
  - 新增 `compile_second_pass_retrieval_plan()`，强制 second-pass request 经过 deterministic compiler。
  - source family 不可用时，Reflection fail-closed 到 bounded answer / clarification，不进入 second-pass 编译。
- `src/sec_agent/langgraph_orchestrator.py`
  - graph state 记录 `source_gaps`、`second_pass_evidence_requirement_plan`、`second_pass_retrieval_plan`。
  - Coverage / Reflection node 注入 tool ledger summary 和 EvidenceRequirementPlan。
  - optional second-pass node 在 injected executor 之前也先完成 second-pass 编译，避免 executor 绕过 compiler。
  - checkpoint summary 记录 second-pass requirement / route count。
- `tests/test_multi_agent_reflection_second_pass.py`
  - 新增 requirement/source/operator 绑定测试。
  - 新增 Reflection second-pass request 编译到 retrieval plan 的测试。
  - 新增 source family unavailable 阻断测试。
- `docs/worklog/188_multi_agent_architecture_execution_plan.md`
  - Step 11 状态更新为已完成，并补充本轮验证结果。
- `docs/worklog/00_internal_master_checklist.md`
  - 勾选 Step 11 绑定和 compiler 回流项，追加 Step 13 后续项。

## Verification

- `pytest tests/test_multi_agent_reflection_second_pass.py tests/test_multi_agent_tool_call_ledger.py -q`
  - `17 passed in 0.15s`
- `pytest tests/test_multi_agent_langgraph_routing.py tests/test_multi_agent_evidence_requirements.py -q`
  - `11 passed in 0.77s`
- `pytest -q`
  - `328 passed in 11.10s`
- `git diff --check`
  - passed

## Safety Notes

- 未运行真实 DeepSeek / OpenAI LLM 调用。
- 未写入 API key、SSH 密码、private token 或 `.env`。
- 用户先前粘贴过的 DeepSeek key 没有写入任何文件、命令或日志。

## Next Step

继续 Step 12/13：把 Specialist memolets、Risk unsupported claims、Coverage/Reflection 约束和 Verifier 结果汇入 Judgment Plan，并让 Memo Writer 只消费 verified summary / judgment plan，不读取 bounded raw rows 或物理 artifact path。
