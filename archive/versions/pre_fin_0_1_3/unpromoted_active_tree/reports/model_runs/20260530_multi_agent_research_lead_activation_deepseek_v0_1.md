# Model Run: 20260530_multi_agent_research_lead_activation_deepseek_v0_1

## Summary

- Purpose: Validate the Step 10 real Research Lead LLM activation route against the 5-case multi-agent activation fixture.
- Status: completed / accepted for Step 10 diagnostic gate.
- Run type: inference smoke + activation routing evaluation.
- Timestamp: 2026-05-30 UTC.
- Environment: local Windows PowerShell, repository `D:\FIN_Insight_Agent`, branch `codex/api-model-call-architecture`.

## Code And Command

- Entry point: `scripts/eval_multi_agent_research_lead_activation.py`
- Graph smoke: inline Python using `build_multi_agent_orchestration_graph(route_activation=...)`.
- Code version: `92148b1` plus dirty local Step 1-10 multi-agent changes.
- Command:

```text
DEEPSEEK_API_KEY=<runtime-only> python scripts/eval_multi_agent_research_lead_activation.py --llm-backend deepseek --base-url https://api.deepseek.com --chat-completions-path /chat/completions --model deepseek-v4-pro --api-key-env DEEPSEEK_API_KEY --strict
```

- Secrets policy: API key was supplied only as a runtime environment variable; no key was written to source, docs, ledger, or output JSON.

## Inputs

- Fixture: `tests/fixtures/multi_agent_activation_cases_v0_1.jsonl`
- Cases: 5 activation routing cases covering `deterministic_lookup`, `focused_answer`, `standard_memo`, `deep_research`, and run-artifact inspection.
- Agent contract: `src/sec_agent/agent_registry.py`
- Activation schema: `src/sec_agent/agent_contracts.py`
- Lead prompt skills:
  - `src/sec_agent/prompts/skills/shared_evidence_boundary_skill_v0_1.md`
  - `src/sec_agent/prompts/skills/research_lead_planning_skill_v0_1.md`

## Model Parameters

- Backend: `deepseek`
- Base URL: `https://api.deepseek.com`
- Chat completions path: `/chat/completions`
- Model: `deepseek-v4-pro`
- Temperature: `0.0`
- Max tokens: `1600`
- Timeout: `180s`
- JSON mode: `response_format={"type": "json_object"}`
- Thinking: disabled
- Max schema repair attempts: `2`
- Deterministic fallback: disabled

## Outputs

- Activation diagnostic:
  - `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260530T093743Z_multi_agent_research_lead_activation_deepseek_v4_pro_v0_1/activation_diagnostic.json`
- Graph smoke output:
  - `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260530T093743Z_multi_agent_research_lead_activation_deepseek_v4_pro_v0_1_graph_smoke_r1/`
- Worklog:
  - `docs/worklog/194_multi_agent_research_lead_llm_activation_gate.md`

## Results

Final activation diagnostic:

```text
gate_status=pass
case_count=5
pass_count=5
all_checks_pass_count=5
mode_correct_count=5
validation_pass_count=5
llm_route_pass_count=5
required_agent_pass_count=5
budget_pass_count=5
forbidden_activation_count=0
total_latency_ms=107367
total_tokens=21103
failures=[]
diagnostic_warnings=[]
```

Focused graph smoke:

```text
status=completed
execution_mode=focused_answer
activation_validation=pass
routing_mode=focused_answer
node_count=12
multi_agent_summary.json exists=true
```

## Experiment Governance

- Hypothesis: A real Research Lead LLM can reliably emit the bounded `AgentActivationPlan` contract when the prompt includes the static registry, role skills, JSON output mode, and per-mode budget rules.
- Decision target: Step 10 hard gate passes if the 5-case fixture has mode exact match `5/5`, validation pass `5/5`, required agents present, and forbidden activation count `0`.
- Baseline: deterministic router from `src/sec_agent/multi_agent_router.py` already passes the same fixture.
- Decision: proceed for Step 10 diagnostic / graph-smoke use. Keep deterministic router as default mainline until Step 11 feature flags and specialist schemas are added.
- Stop condition for this stage: any forbidden activation, schema validation failure, or silent deterministic fallback would block promotion. None occurred in the final run.

## Efficiency Notes

- Total LLM latency for 5 cases: `107367 ms`.
- Total tokens: `21103`.
- This route is acceptable for diagnostic activation gating but not yet optimized for production latency.
- Next efficiency step: cache the static registry/prompt prefix or move common schema text into a compact provider profile before enabling Lead LLM by default.

## Safety Notes

- Raw LLM responses were not saved.
- API key was not saved.
- Generated eval outputs under `eval/sec_cases/outputs/` are runtime artifacts and should not be staged by default.
- The run does not execute real MCP handlers or real specialist LLMs.
