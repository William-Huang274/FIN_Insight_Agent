# 136 SEC Agent JPM Banking Metric Coverage

## Prompt
- User asked whether the JPM issue was caused by the planner selecting the right task while retrieval/rerank failed to put the right evidence in front of the model.
- Test prompt: `JPM 这几年净利息收入和信用风险变化说明银行业务质量怎么样？`

## Diagnostic Baseline
- Old 5-case run artifact: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_130400_914dee0e50`.
- Old `query_contract.json` recorded `planner_status=fallback_after_error` with `planner_error=ValueError: planner_returned_no_json_object`.
- Fallback contract used generic metric families: `revenue`, `operating_income`, `operating_cash_flow`, and `gross_margin`.
- Old runtime ledger drifted to JPM human-capital percentage rows from Item 1 rather than bank quality metrics.

## Fix Validation
- Planner-only rerun after the planner JSON extractor fix:
  - `planner=llm:deepseek:ok`
  - `validation=pass`
  - Decomposed tasks now ask for net interest income / net interest margin, income drivers, and credit-risk indicators.
- This confirms the original JPM run was not a clean case of "correct planner, failed reranker"; it was first affected by planner fallback.

## Full-Chain Rerun
- Artifact: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_151540_914dee0e50`.
- Settings: `USER_OUTPUT=1`, `SYNTHESIS_PROFILE=api_memo_v1`, `QUERY_PLANNER=llm`, `PLANNER_MAX_TOKENS=2200`, `MAX_TOKENS=5200`, `TICKERS=ALL`, `YEARS=2023,2024,2025`, `BGE_DEVICE=cuda`, `LLM_BACKEND=deepseek`.
- Gates: `ok=True`, `pass=12`, `fail=[]`.
- Coverage: `complete=False`, `primary_complete=False`, `answer_status=partial`, support `{'medium': 1, 'partial': 2}`.
- Ledger rows: `13`; context rows: `120`; elapsed: `229.48 sec`.
- Answer behavior improved: the model refused to invent JPM net-interest and credit-risk values, explicitly stated the evidence/ledger did not support a quantitative banking-quality judgment, and marked the output as limited.

## Interpretation
- Current JPM problem after the planner fix is no longer mainly Query Contract planning.
- The chain is now safer, but still weak for banking analysis because the structured extraction / metric ontology / runtime ledger selection do not capture core bank metrics such as:
  - `net_interest_income`
  - `net_interest_margin`
  - `provision_for_credit_losses`
  - `net_charge_offs`
  - `allowance_for_credit_losses`
  - `nonperforming_assets` / `nonperforming_loans`
  - deposits and loan book metrics
- The retrieval stage can surface qualitative risk evidence, but the exact-value ledger still does not provide the bank-specific numeric spine required for a high-quality memo.
- Human-capital percentage rows should be filtered out for banking financial-quality prompts unless explicitly requested.

## Follow-Up
- Add a banking metric ontology and extraction aliases before treating JPM-style prompts as production-quality.
- Extend runtime ledger selection to prioritize bank financial tables and suppress human-capital rows for bank-quality/credit-risk contracts.
- Rerun the JPM case after extraction coverage changes and require `coverage_complete=True` or a transparent partial-coverage answer before memo-quality scoring.
