# Model Run: 20260530_multi_agent_specialist_real_evidence_deepseek_v0_1

## Summary

- Purpose: 用真实 bounded evidence rows 评测 Specialist Analyst 的证据绑定、source-family 边界、unsupported/conflict 处理和 direct tool-call 禁止。
- Status: accepted for diagnostic Specialist quality gate.
- Run type: inference evaluation.
- Timestamp: 2026-05-30.
- Environment: local Windows workspace; API key injected only as a temporary process environment variable and removed after the command.
- Model: `deepseek-v4-pro`.

## Code And Command

- Entry point: `scripts/eval_multi_agent_specialist_real_evidence_quality.py`
- Fixture: `tests/fixtures/multi_agent_specialist_real_evidence_cases_v0_1.jsonl`
- Command: `python scripts/eval_multi_agent_specialist_real_evidence_quality.py --run-id codex_specialist_real_evidence_deepseek_v0_1 --strict`
- Output: `eval/sec_cases/outputs/multi_agent_specialist_real_evidence_quality/codex_specialist_real_evidence_deepseek_v0_1/specialist_real_evidence_quality_eval.json`
- Raw LLM response: not saved.
- API key: not saved.

## Inputs

- Case count: `4`
- Materialized bounded real evidence rows: `28`
- Source types:
  - `runtime_ledger_json`
  - `market_evidence_jsonl`
  - `industry_evidence_jsonl`
  - `coverage_matrix_json`
  - `relationship_graph_lookup`
- Cases:
  - `specialist_real_fundamental_jpm_bank_metrics`
  - `specialist_real_market_jpm_snapshot`
  - `specialist_real_industry_relationship_ai_scope`
  - `specialist_real_risk_jpm_missing_operating_income`

## Results

- Gate status: `pass`
- Passed: `4/4`
- Failed: `0`
- Total latency: `77725 ms`
- Total tokens: `16574`
- Direct tool calls: `0`

Case summary:

- Fundamental: `14` primary SEC filing rows, `5` supported observations, `3` unsupported/caveat claims.
- Market-Valuation: `1` market snapshot row, `6` supported observations, no unsupported claims.
- Industry/Supply-Chain: `4` relationship graph rows + `2` industry snapshot rows, `2` supported observations, `2` unsupported claims.
- Risk/Counterevidence: `6` primary SEC filing rows + `1` coverage gap row, `4` supported observations, `1` unsupported claim, `1` conflict.

## Interpretation

The Specialist layer now has a diagnostic gate that distinguishes structural routing success from evidence-backed analysis quality. The model cited only known evidence refs, stayed within allowed source families, avoided direct tool calls, preserved relationship graph as hypothesis/context evidence, and flagged missing operating-income support as unsupported/conflicting instead of promoting it into a supported claim.

This still remains diagnostic-only. The next step is wiring this real-evidence Specialist quality scoring into the full Step17 chain eval and expanding coverage beyond the JPM/AI-scope pilot cases.

## Safety Notes

- `raw_llm_response_saved=false`.
- `api_key_saved=false`.
- Generated eval outputs remain diagnostic artifacts and are not default tracking candidates.
