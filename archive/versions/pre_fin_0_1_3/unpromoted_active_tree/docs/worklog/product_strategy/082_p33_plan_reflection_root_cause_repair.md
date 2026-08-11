# 082 P33 Plan Reflection Root-cause Repair

## Prompt

用户要求继续 P33-3，但前序 scoped paid attempt 已经显示 full-chain 在 Research Lead 之后早停，且用户明确要求不要继续烧 token，要先把 deterministic / node-level 能定位的问题修掉。

## Decision

本轮不重跑 paid full-chain。先复盘 `p33_gold_case_deepseek_full_chain_r1` 的 artifact，定位最早 faulty artifact，再做 deterministic 修复。

核心判断：

- 早停不是模型最终 memo 质量问题，因为 run 没进入 evidence operators / specialists / writer。
- 早停也不是数据源缺失问题，因为 P33-2 / P33-3 upstream packs 和 case preflight 已可用。
- 根因在 Research Lead activation / evidence route / plan reflection 合同归一化，以及 real-chain scoring 对 early-stop diagnostics 的投影。

## Work Completed

修复代码：

- `src/sec_agent/research_lead_llm.py`
  - 在 evidence route / source alignment 后新增 plan-reflection contract normalizer。
  - 对 `relationship_graph` / `universe_relationship` 自动补齐 deep-research mode、`relationship_scope_rationale` 和 required source metadata 清理。
  - 扩展 relationship intent：`read-through`、`supply-chain`、`deployment`、`capex to` 等。
  - 让 evidence requirement 本身的 supply-chain / read-through 语义保留 relationship route，不被前置 policy 误删。
  - 保持无关系意图的普通产品/财务查询仍会 prune relationship overroute。
- `scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py`
  - 早停时如果没有 `multi_agent_summary.json`，Research Lead checks 回看 `result.research_lead_model_diagnostics`。
  - `vnext_contract_audit.required` 现在反映任一子合同要求，而不是只看 `require_vnext_contract` 总开关。
- `tests/fixtures/p33_ai_semis_gold_workpaper_case_v0_1.jsonl`
  - 新增 `require_plan_reflection_gate=true`。

补充测试：

- `tests/test_multi_agent_research_lead_llm.py`
  - 新增 evidence-route relationship contract regression，直接调用 `plan_reflection_gate` 验证归一化后可通过。
- `tests/test_multi_agent_real_llm_chain_eval.py`
  - 新增 early-stop scoring regression：Research Lead diagnostics 必须显示已调用，plan reflection audit 必须 fail。

更新状态：

- `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/root_cause_issue_ledger.jsonl`
- `docs/project_os/capability_status_ledger.jsonl`
- `docs/project_os/p33_execution_plan_ledger.jsonl`

## Verification

Commands run:

```powershell
python -m pytest tests/test_multi_agent_research_lead_llm.py -q
python -m pytest tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_scoring_reports_plan_reflection_early_stop_without_hiding_lead_call tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_scoring_accepts_vnext_contract_summary tests/test_multi_agent_real_llm_chain_eval.py::test_real_llm_chain_scoring_rejects_milvus_exact_authority_misuse -q
python -m py_compile src/sec_agent/research_lead_llm.py scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py
python scripts/engineering/run_p33_ai_semis_gold_workpaper_preflight.py --root .
python scripts/eval_multi_agent/run_project_os_full_chain_preflight.py --run-scope p33_single_gold_case
python scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py --cases-path tests/fixtures/p33_ai_semis_gold_workpaper_case_v0_1.jsonl --run-id p33_gold_case_token_budget_preflight_after_plan_gate_fix_20260705_r1 --output-dir eval/sec_cases/outputs/p33_gold_case_runs --project-os-run-scope p33_single_gold_case --token-budget-preflight-only --real-evidence-operators
```

Observed:

- Research Lead LLM tests: `33 passed`。
- real-chain scoring targeted tests: `3 passed`。
- py_compile: pass。
- P33 no-paid preflight: `status=ready_for_paid_run_preflights`、`deterministic_preflight_status=pass`、`open_full_chain_blocker_count=0`、`paid_run_allowed=true`。
- Project OS scoped preflight: `status=pass` for `run_scope=p33_single_gold_case`。
- token budget preflight: `allowed=true`、`estimated_total_tokens=68500`、`estimated_paid_call_count=7`。

## Boundary

本轮没有重跑 paid full-chain，没有生成 rendered memo，也没有关闭 P33-3 gold workpaper。下一次如果继续 P33-3，只能跑单个 scoped paid case，并且必须先通过 provider / real-evidence / AIE preflight；不能扩到 broad full-chain、20-50 case 或 release eval。

## Follow-up

- 跑 provider preflight / real-evidence / AIE preflight。
- 若通过，只重跑 `p33_3_ai_semis_accelerator_dell_gold_case_v0_1` 一个 paid real-evidence case。
- 若仍失败，继续从最早 faulty artifact 定位，不扩大 case 数量。
