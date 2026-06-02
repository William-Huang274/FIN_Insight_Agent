# Model Run: 20260530_multi_agent_step14_deepseek_graph_closeout_v0_1

## Summary

- Purpose: Validate the Step 14 multi-agent graph closeout with real DeepSeek calls for Research Lead activation, Specialist memolets, Universe Relationship planning, Memo Writer, and Verifier.
- Status: completed / accepted as diagnostic gate.
- Run type: inference smoke + routing/evaluation.
- Timestamp: 2026-05-30.
- Environment: local Codex workspace on Windows, Python pytest/runtime from repo environment.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent_research_lead_activation.py`
  - `scripts/eval_multi_agent_specialist_memolet.py`
  - inline Python smoke for `route_universe_relationship_llm`, `route_memo_writer_llm`, and `route_verifier_llm`.
- Commands:
  - `DEEPSEEK_API_KEY=<env> LLM_BACKEND=deepseek MODEL_NAME=deepseek-v4-pro python scripts/eval_multi_agent_research_lead_activation.py --strict --require-evidence-requirements --run-id codex_full_research_lead_real_llm_after_step14_gate_pass`
  - `DEEPSEEK_API_KEY=<env> LLM_BACKEND=deepseek MODEL_NAME=deepseek-v4-pro python scripts/eval_multi_agent_specialist_memolet.py --strict --run-id codex_specialist_memolet_real_llm_after_step14`
  - Inline route smoke used the same process-only environment variables and did not write raw responses.
- Config:
  - `llm_backend=deepseek`
  - `model=deepseek-v4-pro`
  - JSON response format enabled through the local LLM gateway.
  - Deterministic fallback disabled for the strict Research Lead gate.
- Git commit / dirty files:
  - Branch: `codex/api-model-call-architecture`
  - Base commit at task start: `92148b1`
  - Worktree dirty with ongoing multi-agent implementation files.
- Seeds: none.

## Inputs

- Research Lead fixture:
  - `tests/fixtures/multi_agent_activation_cases_v0_1.jsonl`
  - 5 cases covering deterministic metric lookup, focused answer, standard memo, deep research, and run-artifact inspection.
- Specialist fixture:
  - `tests/fixtures/multi_agent_specialist_memolet_cases_v0_1.jsonl`
  - 4 bounded memolet cases across role-specific specialist skills.
- Universe/Memo/Verifier inline smoke:
  - Bounded NVDA/MSFT relationship lookup fixture.
  - Verified judgment plan with one supported fundamental claim and one risk conflict.
- Candidate boundary / leakage guard:
  - LLMs only received bounded fixture payloads and data views.
  - No raw evidence rows, private paths, or API key were written to outputs.

## Model Parameters

- Model: `deepseek-v4-pro`
- Temperature: `0.0`
- Research Lead max tokens: `2400`
- Specialist max tokens: `1400`
- Universe smoke max tokens: `1600`
- Memo smoke max tokens: `1400`
- Verifier smoke max tokens: `900`
- Max repair attempts:
  - Research Lead: `2`
  - Specialist: `2`
  - Universe: default route budget
  - Memo: default route budget

## Outputs

- Research Lead diagnostic:
  - `eval/sec_cases/outputs/multi_agent_activation_diagnostic/codex_full_research_lead_real_llm_after_step14_gate_pass/activation_diagnostic.json`
- Specialist diagnostic:
  - `eval/sec_cases/outputs/multi_agent_specialist_memolet_diagnostic/codex_specialist_memolet_real_llm_after_step14/specialist_memolet_diagnostic.json`
- Raw LLM responses saved: no.
- API key saved: no.

## Results

- Research Lead strict gate:
  - `gate_status=pass`
  - `case_count=5`
  - `pass_count=5`
  - `mode_correct_count=5`
  - `validation_pass_count=5`
  - `llm_route_pass_count=5`
  - `required_agent_pass_count=5`
  - `budget_pass_count=5`
  - `evidence_requirement_pass_count=5`
  - `forbidden_activation_count=0`
  - `total_latency_ms=125748`
  - `total_tokens=27228`
- Specialist memolet strict gate:
  - `gate_status=pass`
  - `case_count=4`
  - `pass_count=4`
  - `validation_pass_count=4`
  - `llm_route_pass_count=4`
  - `evidence_refs_known_count=4`
  - `unsupported_expected_pass_count=4`
  - `forbidden_tool_call_count=0`
  - `total_latency_ms=35329`
  - `total_tokens=7563`
- Universe/Memo/Verifier smoke:
  - `universe_validation_status=pass`
  - `universe_call_count=1`
  - `memo_route_status=pass`
  - `memo_answer_status=draft`
  - `verifier_status=pass`
  - `verifier_error_count=0`

## Experiment Governance

- Hypothesis: Adding bounded graph integration, run-artifact route handling, role-specific scope validation, and real LLM route gates should close the remaining 185/186 Step 14 gaps without weakening source-boundary constraints.
- Decision target: Research Lead strict gate `5/5`, Specialist strict gate `4/4`, Universe/Memo/Verifier smoke `pass`, full pytest pass.
- Ceiling / upper bound: fixtures are diagnostic and bounded; they do not prove production memo quality or full graph production readiness.
- Baselines to beat: previous Step 10 Research Lead gate and deterministic unit tests.
- Split and leakage guard: fixture-only diagnostic; no private raw evidence or key persistence.
- Stop conditions: forbidden tool calls, unknown evidence refs, relationship evidence used as financial fact, run-artifact route mismatch, or full pytest regression.
- Efficiency gate: local diagnostic latency acceptable for small fixture suite; not a production latency claim.
- Decision label: proceed to Step 15/16 diagnostic graph smoke.
- Mainline decision: accepted as Step 14 diagnostic closeout, not production default.

## Runtime Efficiency

- Research Lead wall time: approximately `126.7 sec`.
- Specialist wall time: approximately `36.2 sec`.
- Universe/Memo/Verifier inline smoke wall time: approximately `14.4 sec`.
- Bottleneck diagnosis: API latency and multi-call repair-capable JSON routing dominate; no local GPU path involved.
- Efficiency improvement: keep fixture gates compact; avoid per-ticker deep evidence requirements in Research Lead output.
- Serving latency implication: real multi-agent graph needs staged async / trace UX before user-facing production use.

## Caveats And Next Step

- Not run: full real multi-agent graph end-to-end with retrieval execution and final rendered memo.
- Known risks: fixture gates are narrow; DeepSeek output shape may drift on broader prompts.
- Reproduce/rollback:
  - Re-run the two scripts above with `DEEPSEEK_API_KEY` supplied in the process environment.
  - Disable feature flags to return to the native graph path.
- Next decision: Step 15/16 Workbench / CLI trace productization and small real graph smoke while keeping multi-agent diagnostic-only.
