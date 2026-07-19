# 083 P33 Single Gold Case Risk Dimension And Writer Cost Root-cause Repair

## Prompt

用户要求继续 P33-3，但明确指出不能再一上来烧 token，要先把 full-chain 回归跑太多、specialist 扇出太宽、specialist 输入太胖、claim yield 太低、缺少硬 token budget gate 等问题当作 agent 框架设计核心问题处理。

本轮在前序 plan-reflection 修复之后，只允许对单个 AI/Semis gold case 做 scoped 验证；发现问题后必须先做 deterministic / node-level root-cause repair，不扩大 case 数，不跑 20-50 case，不用 gate/fallback 掩盖内部缺陷。

## Decision

本轮先读取 Project OS / P33 文档与 ledgers，然后用一个 scoped paid attempt 验证 plan-reflection 修复是否进入运行路径。新的 paid attempt 已通过 Research Lead / plan reflection / specialist quality，但在 Memo Writer / verifier 处失败。

核心判断：

- 这不是 Milvus、provider、网络、公开源缺失或 specialist evidence quality 问题。
- 最早 faulty artifact 是 `thesis_driver_pack` / `judgment_state` / `Memo Writer` 之间的 risk/counterevidence 维度投影。
- `risk_counterevidence_analyst` 被 paid specialist whitelist 剪掉，但 `memo_logic_plan.section_order` 仍要求 `risk_and_counterevidence`；上游只有 counter/conflict text，没有可追踪 counter ids，writer 被允许重试，最终烧掉约 `44,255` writer tokens。
- 正确修法不是再加一个最终 gate，而是让 counter ids、required dimensions、writer material gate、salvage、memo claim refs 和 verifier projection 的合同闭合。

## Work Completed

修复代码：

- `src/sec_agent/multi_agent_contracts.py`
  - `dimension_sections` 现在保留 `counter_claim_ids` 和 `counter_driver_ids`。
  - `build_judgment_state()` 现在把 required dimensions 和 counter ids 写入 JudgmentState。
  - JudgmentState validation 会报告 required dimension 缺 writer material。
- `src/sec_agent/memo_llm.py`
  - 新增 pre-writer required-dimension material gate，required dimension 完全没有 writer material 时，在 paid model call 前 fail closed。
  - verified-judgment completion 顺序改为先补 claims，再补/enrich dimensions，再从完成后的 dimensions 回填 claims，减少 stale refs。
  - deterministic salvage 改为合并已有维度与 required-item rows，并按 `MemoLogicPlan.section_order` 排序，不再替换掉 risk/counterevidence。
  - risk/counterevidence 只有文本但无 trace ids 时，显式投影为 low-confidence gap，而不是静默丢失。
  - memo claims 继承 source ClaimCard 的 `analysis_dimension` / `dimension_id`。
  - dimension evidence refs 优先使用当前 ClaimCard refs，避免 stale section refs。
  - language-normalization / verified-judgment completion 元数据在 dimension normalizer 中保留。

补充/修复测试：

- `tests/test_multi_agent_contracts.py`
  - 覆盖 risk/counterevidence counter ids 进入 JudgmentState。
- `tests/test_multi_agent_memo_llm_repair.py`
  - 覆盖 deterministic salvage 保留 risk/counterevidence。
  - 覆盖 required dimensions / verified judgment completion / 中文本地化元数据不丢失。

更新状态文档：

- `docs/project_os/root_cause_issue_ledger.jsonl`
- `docs/project_os/capability_status_ledger.jsonl`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/p33_execution_plan_ledger.jsonl`
- `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`

## Verification

Commands run:

```powershell
python -m pytest tests/test_multi_agent_contracts.py tests/test_multi_agent_memo_llm_repair.py -q
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py -q
python -m py_compile src/sec_agent/multi_agent_contracts.py src/sec_agent/memo_llm.py src/sec_agent/langgraph_orchestrator.py
python scripts/engineering/run_p33_ai_semis_gold_workpaper_preflight.py --root .
python scripts/eval_multi_agent/run_project_os_full_chain_preflight.py --run-scope p33_single_gold_case
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --cases-path tests/fixtures/p33_ai_semis_gold_workpaper_case_v0_1.jsonl --run-id p33_gold_case_token_budget_preflight_after_risk_dimension_fix_20260705_r1 --output-dir eval/sec_cases/outputs/p33_gold_case_runs --project-os-run-scope p33_single_gold_case --token-budget-preflight-only --real-evidence-operators
git diff --check
```

Observed:

- `tests/test_multi_agent_contracts.py tests/test_multi_agent_memo_llm_repair.py`：`120 passed`。
- `tests/test_multi_agent_real_llm_chain_eval.py`：`91 passed`。
- py_compile：pass。
- P33 no-paid preflight：`deterministic_preflight_status=pass`、`gate_fail_count=0`。
- Project OS scoped preflight：`status=pass` for `run_scope=p33_single_gold_case`。
- token budget preflight：`allowed=true`、`estimated_total_tokens=68500`、`estimated_paid_call_count=7`。
- `git diff --check`：pass，但有既有 CRLF/LF warning。

## Boundary

本轮没有 paid rerun。当前状态不是 P33-3 `L4_scope_pass`，也不是 accepted gold workpaper。

下一步如继续，只允许重跑一个 scoped paid AI/Semis case，并且仍需 provider / real-evidence / AIE 等 remaining preflight。不得扩到 broad full-chain、20-50 case、release eval 或模型对比。

## Follow-up

1. paid rerun 前确认 provider / real-evidence / AIE preflight。
2. 只重跑 `p33_3_ai_semis_accelerator_dell_gold_case_v0_1` 一个 paid case。
3. 若再次失败，继续定位最早 faulty artifact；不要用更多 gate 或模型切换掩盖问题。
4. 若通过，再进入人工审阅 gold workpaper、Workbench dogfood 和后续模型对比。
