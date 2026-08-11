# 084 P33 Method-to-Runtime Observability / Attribution Layer

## Prompt

用户要求在继续 P33 之前先解决两个核心问题：

1. 给 Codex / 项目自身纠偏：不能再把金融研究方法、行业 playbook、外部 agent 工程模式写进文档、registry 或 fixture 后，就误判为 runtime 能力完成。
2. 修 P33 runtime：Research Lead、specialist skill、JudgmentCard contract、ProductIntelligenceGraph projection 和 writer prompt 必须真正消费这些方法，不能继续让 final memo 像证据摘要。

本轮禁止 paid/full-chain rerun，必须先用 deterministic / node-level 测试验证方法被消费。

## Decision

在 P33-3 paid rerun 前插入 `P33-3A Method-to-Runtime Observability & Attribution Layer`。

核心口径：

- `documented` / `registry_only` / `fixture_proven` 不是 runtime active。
- Runtime active 至少要达到：
  - Research Lead 收到并使用 method contract；
  - specialist 收到 role-specific rubric；
  - specialist 输出 `judgment_candidates`；
  - JudgmentCandidate 能进入 ClaimCard / JudgmentCard；
  - ProductIntelligenceGraph 边有投资含义；
  - writer 只吃 writer-ready material；
  - deterministic test 证明上述消费链。

## Work Completed

代码与合同：

- 新增 `src/sec_agent/method_runtime.py`：
  - 定义 method lifecycle、AI/Semis required items、specialist rubrics、judgment candidate contract、graph edge investment roles、gap attribution taxonomy。
- 更新 `src/sec_agent/research_lead_llm.py`：
  - Research Lead prompt 注入 compact `method_runtime_pack`；
  - system schema 明确要求 `thesis_path`。
- 更新 `src/sec_agent/specialist_llm.py`：
  - specialist request 注入 `method_runtime_pack` 与 `specialist_runtime_rubric`；
  - output contract 要求 `judgment_candidates`。
- 更新 `src/sec_agent/multi_agent_contracts.py`：
  - `normalize_specialist_memolet()` 支持 `judgment_candidates`；
  - `aggregate_specialist_judgment_plan()` 将 JudgmentCandidate 投影为 writer-ready Claim/JudgmentCard；
  - 修复 JudgmentCandidate 缺省 `memo_slot` 先被归一为 `evidence_gap` 的 bug；
  - 修复 `_claim_card_annotations()` 覆盖原 `analyst_depth`，导致 `graph_edge_refs` / `cannot_infer` / `what_would_change_view` 丢失的 bug。
- 更新 `src/sec_agent/product_intelligence_runtime.py`：
  - ProductIntelligenceGraph relationship rows 增加 `edge_investment_role`、`supports_judgment`、`cannot_infer`、`needed_confirmation`。
- 更新 prompt skills：
  - Research Lead 从 router 明确升级为 thesis lead；
  - product / fundamental / industry / risk specialist 要按 method runtime rubric 输出 judgment candidates；
  - memo writer 以 thesis_path / JudgmentCards / MemoLogicPlan 为主输入。
- 更新 Codex skills：
  - `fin-insight-global-stewardship`
  - `fin-insight-project-os`
  - 明确 Method-to-Runtime lifecycle 和不得宣称 runtime active 的规则。

文档与 ledgers：

- `docs/internal/vnext_20260610/p33_p32_closeout_to_ai_semis_gold_workpaper_program.zh-CN.md`
- `docs/project_os/current_context_pack.zh-CN.md`
- `docs/project_os/p33_execution_plan_ledger.jsonl`
- `docs/project_os/root_cause_issue_ledger.jsonl`
- `docs/project_os/capability_status_ledger.jsonl`

## Verification

Initial targeted deterministic tests:

```powershell
python -m pytest tests/test_method_runtime.py tests/test_multi_agent_research_lead_llm.py::test_research_lead_prompt_exposes_cost_aware_route_selection_policy tests/test_multi_agent_specialist_llm.py::test_build_specialist_request_from_state_includes_task_card_and_claim_slots tests/test_multi_agent_contracts.py::test_judgment_candidate_becomes_writer_ready_judgment_card tests/test_product_spec_pack.py::test_product_intelligence_pack_flows_into_product_spec_pack_and_specialist_refs -q
```

Observed:

- `6 passed`。
- 第一次运行暴露真实 owned bug：JudgmentCandidate 的 writer-ready fields 在 ClaimCard annotation 中被覆盖。
- 已修复后重跑通过。

Full targeted deterministic verification:

```powershell
python -m pytest tests/test_method_runtime.py tests/test_multi_agent_contracts.py tests/test_multi_agent_research_lead_llm.py tests/test_multi_agent_specialist_llm.py tests/test_product_spec_pack.py -q
python -m py_compile src/sec_agent/method_runtime.py src/sec_agent/research_lead_llm.py src/sec_agent/specialist_llm.py src/sec_agent/multi_agent_contracts.py src/sec_agent/product_intelligence_runtime.py
git diff --check
```

Observed:

- targeted deterministic suite：`143 passed`。
- py_compile：pass。
- `git diff --check`：pass，仅有既有 CRLF/LF warning。

## Boundary

本轮没有 paid rerun，也没有 gold workpaper artifact。

P33-3A 当前只证明 method-to-runtime 的节点级消费链已完成 deterministic closeout。它不证明 paid memo 质量，也不证明 gold workpaper accepted。

## Follow-up

1. 回到 P33-3 scoped single-case paid preflight 前，仍要确认 provider / real-evidence / AIE / token budget。
2. 如 paid case 仍输出像证据摘要，继续定位最早 faulty artifact，不能扩大测试数量或换模型掩盖。
3. 仍不得扩到 20-50 case 或 broad full-chain。
