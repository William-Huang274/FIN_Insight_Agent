# Model Run: 20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1

## Summary

- Purpose: validate S1 Research Lead under the new Fin Agent investment-research quality framework and layered gate protocol.
- Status: accepted for S1 layered quality gate.
- Run type: inference evaluation.
- Timestamp: 2026-06-01.
- Environment: local Windows workspace, real DeepSeek `deepseek-v4-pro`.
- Safety: runtime credential was used only through the process environment. Plaintext credential and raw LLM responses were not saved.

## Code And Command

- Entry points:
  - `scripts/eval_multi_agent_research_lead_activation.py`
  - `scripts/audit_fin_agent_layer_quality.py`
- Git commit at run start: `cc37fbf`.
- Changed files at run time: quality framework docs/config/script/tests and worklog updates were in progress; unrelated `docs/interview/agent_architecture_interview_notes_zh.md` remained user-owned dirty state.
- Command shape:

```text
<set DeepSeek credential in process env>
python scripts/eval_multi_agent_research_lead_activation.py --run-id 20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1 --require-evidence-requirements --strict

python scripts/audit_fin_agent_layer_quality.py --summary eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1/activation_diagnostic.json --strict
```

- Seeds: not applicable for remote LLM inference; deterministic schema and quality gates were used for pass/fail interpretation.

## Inputs

- Fixture: `tests/fixtures/multi_agent_activation_cases_v0_1.jsonl`.
- Case count: `5`.
- Candidate boundary:
  - Research Lead consumes user query, focus/search-scope tickers, source inventory, and context only.
  - No retrieval, no SEC search, no market/industry lookup, no full-chain execution.
- Leakage guard:
  - The script saves activation plan, validation summary, routing trace, and model diagnostics only.
  - API key and raw model responses are not saved.

## Results

| Metric | Value |
| --- | ---: |
| Gate status | pass |
| Case count | 5 |
| Pass count | 5 |
| All checks pass count | 5 |
| Mode correct count | 5 |
| Validation pass count | 5 |
| LLM route pass count | 5 |
| Required agent pass count | 5 |
| Budget pass count | 5 |
| Evidence requirement pass count | 5 |
| Forbidden activation count | 0 |
| Total latency | 116,126 ms |
| Total tokens | 28,038 |

New layered quality audit:

| Metric | Value |
| --- | ---: |
| Audit schema | `fin_agent_layer_quality_audit_v0.1` |
| Source type | `research_lead_activation` |
| Gate status | pass |
| Weighted score | 2.688 |
| Quality flags | none |

The weighted score is diagnostic for S1 only. It is below full-deliverable `3.0` because downstream investment-thesis, memo, relationship, and renderer dimensions are intentionally not evaluated before S2-S10.

## Decision

- Proceed to S2 Universe / Relationship using the S1 activation artifact.
- Do not run full chain yet. The execution document requires each agent/node layer to pass its gate before S10 full-chain and multi-turn regression.

## Outputs

- Activation diagnostic: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1/activation_diagnostic.json`
- Layer quality audit JSON: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1/fin_agent_layer_quality_audit.json`
- Layer quality audit Markdown: `eval/sec_cases/outputs/multi_agent_activation_diagnostic/20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1/fin_agent_layer_quality_audit.md`

## Verification

```text
python -m pytest tests/test_fin_agent_layer_quality_audit.py -q
result: 4 passed

python -m compileall scripts/audit_fin_agent_layer_quality.py
result: pass

git diff --check -- <quality framework touched files>
result: pass
```

## Caveats And Next Step

- Not run: S2-S10, full-chain, multi-turn.
- Known risk: S1 validates orchestration intent, not downstream evidence quality or memo usefulness.
- Next decision: implement/run S2 Universe / Relationship under the new quality framework, reusing the S1 artifact.
