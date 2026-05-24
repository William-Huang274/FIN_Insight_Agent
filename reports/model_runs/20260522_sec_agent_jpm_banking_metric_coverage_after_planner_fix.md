# Model Run: 20260522_sec_agent_jpm_banking_metric_coverage_after_planner_fix

## Summary
- Purpose: Separate planner failure from retrieval/ledger coverage failure for the JPM banking-quality prompt.
- Status: diagnostic-only; planner fixed and gates pass, but bank-specific metric coverage remains partial.
- Run type: planner smoke + free-query API memo inference + deterministic audit.
- Environment: cloud RTX 5090, `/root/autodl-tmp/FIN_Insight_Agent`.

## Code And Command
- Entry point: `scripts/cloud/sec_agent_interactive.sh`.
- Prompt: `JPM 这几年净利息收入和信用风险变化说明银行业务质量怎么样？`
- Planner command profile: `LLM_BACKEND=deepseek`, `QUERY_PLANNER=llm`, `PLANNER_MAX_TOKENS=2200`, `TICKERS=ALL`, `YEARS=2023,2024,2025`, `plan`.
- Full-chain command profile: `USER_OUTPUT=1`, `SYNTHESIS_PROFILE=api_memo_v1`, `QUERY_PLANNER=llm`, `PLANNER_MAX_TOKENS=2200`, `MAX_TOKENS=5200`, `TICKERS=ALL`, `YEARS=2023,2024,2025`, `BGE_DEVICE=cuda`, `ask-deepseek`.
- API key was passed through environment variable only and was not written to files.

## Results
- Old baseline artifact: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_130400_914dee0e50`.
  - `planner_status=fallback_after_error`
  - `planner_error=ValueError: planner_returned_no_json_object`
  - Fallback metric families were generic and missed bank-specific metrics.
- Planner-only rerun:
  - `planner=llm:deepseek:ok`
  - `validation=pass`
  - Decomposed tasks included JPM net interest income / margin and credit-risk indicators.
- Full-chain rerun artifact: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_151540_914dee0e50`.
  - Gates: `ok=True`, `pass=12`, `fail=[]`
  - Coverage: `complete=False`, `primary_complete=False`, `answer_status=partial`
  - Coverage support: `{'medium': 1, 'partial': 2}`
  - Ledger rows: `13`
  - Context rows: `120`
  - Elapsed: `229.48 sec`

## Interpretation
- The planner parser fix works for JPM. The rerun no longer falls back to a generic finance trend contract.
- The model output is now safer: it does not fabricate JPM net-interest or credit-risk values and instead states that current evidence/ledger coverage is insufficient for a quantitative banking-quality judgment.
- The remaining bottleneck is upstream coverage: bank-specific structured metric extraction and ledger selection are missing, while irrelevant human-capital percentages can still enter the ledger.

## Next Decision
- Add a banking metric ontology and ledger filters before rerunning JPM as a quality target.
- Required metric families should include `net_interest_income`, `net_interest_margin`, `provision_for_credit_losses`, `net_charge_offs`, `allowance_for_credit_losses`, `nonperforming_assets`, deposits, and loan book metrics.
