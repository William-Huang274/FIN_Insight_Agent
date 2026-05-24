# 137 SEC Agent Banking Metric Ontology / iXBRL Extraction / Ledger Selection

## Prompt
- User asked to fill the bank-specific `metric ontology / structured extraction / ledger selection` gap found by the JPM banking-quality prompt.
- Target prompt: `JPM 这几年净利息收入和信用风险变化说明银行业务质量怎么样？`

## Root Cause
- Previous JPM run had already fixed the planner JSON fallback, but the runtime ledger still lacked the bank-specific numeric spine.
- Retrieval could surface bank risk narrative, but exact-value support for net interest income, credit-loss provision, charge-offs, deposits, loans, allowance, assets, and capital ratios was incomplete.
- Generic ledger selection also allowed unrelated rows such as human-capital percentages or tax provision rows to enter banking prompts.

## Work Completed
- Extended the Query Contract and Coverage Matrix banking ontology:
  - `net_interest_income`
  - `net_interest_margin`
  - `provision_for_credit_losses`
  - `net_charge_offs`
  - `allowance_for_credit_losses`
  - `nonperforming_assets`
  - `nonperforming_loans`
  - `deposits`
  - `loans`
  - `capital_ratio`
  - `total_assets`
  - related aliases such as `provision for loan lease and other losses`.
- Added a bank iXBRL extraction path in `src/evidence/structured_extractor.py`.
  - The extractor runs only for banking 10-K Item 7 anchor evidence.
  - It resolves raw SEC filing paths and parses iXBRL contexts/facts directly.
  - It maps JPM and US-GAAP facts into `MetricObject` rows using extraction method `banking_ixbrl_fact_heuristic`.
- Updated runtime ledger selection in `scripts/cloud/sec_agent_interactive.py`.
  - Banking intent now expands planner tasks into bank-specific families.
  - Runtime ledger supplements retrieved context with bank iXBRL metric rows.
  - Ledger filtering suppresses human-capital, tax-provision, deposit-insurance, and weak loan false positives.
  - Row capping is balanced by task, metric family, and year.

## Validation
- Local compile passed for the touched modules and scripts.
- Local planner-only JPM smoke returned a valid banking-oriented contract with `validation=pass`.
- Local synthetic table extraction preserved header year order and correctly classified:
  - `net_interest_income`
  - `net_interest_margin`
  - `provision_for_credit_losses`.
- Local JPM 2024 iXBRL smoke extracted bank metrics including net interest income, provision, loans, deposits, allowance, assets, net charge-offs, and CET1 ratio.
- Cloud structured-object rebuild completed:
  - `evidence_count=8461`
  - `table_count=9030`
  - `metric_count=184784`
  - `claim_count=64141`
  - `banking_ixbrl_fact_heuristic=102`
  - JPM metrics increased to `227`.
- Cloud object BM25 rebuild completed with `257955` records.
- Cloud object search for JPM bank terms now ranks `METRIC_BANK_IXBRL` facts at the top.

## JPM Rerun Result
- Artifact: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_161702_914dee0e50`.
- Profile: `USER_OUTPUT=1`, `QUERY_PLANNER=heuristic`, `SYNTHESIS_PROFILE=api_memo_v1`, `MAX_TOKENS=5200`, `TICKERS=ALL`, `YEARS=2023,2024,2025`, `BGE_DEVICE=cuda`, `ask-deepseek`.
- Coverage:
  - `complete=True`
  - `primary_complete=True`
  - `answer_status=complete`
  - support `{'medium': 1, 'strong': 2}`
- Runtime ledger:
  - rows: `24`
  - context rows: `120`
  - elapsed: `220.45 sec`
- Representative exact metrics now available in the ledger:
  - JPM net interest income: 2023 `89,267`, 2024 `92,583`, 2025 `95,443`.
  - JPM provision for credit losses: 2023 `9,320`, 2024 `10,678`, 2025 `14,212`.
  - JPM net charge-offs: 2023 `6,209`, 2024 `8,638`, 2025 `9,849`.
  - JPM loans: 2023 `1,323,706`, 2024 `1,347,988`, 2025 `1,493,429`.
  - JPM deposits: 2023 `2,400,688`, 2024 `2,406,032`, 2025 `2,559,320`.
  - JPM allowance for credit losses: 2023 `22,420`, 2024 `24,345`, 2025 `25,765`.
  - JPM CET1 ratio: 2023 `15.0%`, 2024 `15.7%`, 2025 `14.6%`.
- Gate outcome:
  - `qwen_answer_ratio=1.0`
  - `answer_ledger_gate_pass=true`
  - `metric_source_grounding_gate_pass=true`
  - `ledger_unit_gate_pass=true`
  - `ledger_missing_consistency_gate_pass=true`
  - `caveat_claim_gate_pass=true`
  - `v2_semantic_contract_gate_pass=true`
  - `answer_vs_judgment_plan_gate_pass=true`
  - remaining failure: `named_fact_gate_pass=false` for `Common Equity Tier` because the memo field carried metric IDs but not an evidence ID line for that named phrase.

## Interpretation
- The bank-specific data problem is now materially fixed for JPM-style prompts.
- The previous partial-coverage behavior was upstream extraction/ledger coverage, not merely model weakness.
- The remaining failure is citation/gate formatting around a supported capital-ratio named fact, not a missing bank metric extraction problem.

## Follow-Up
- Fix the named-fact support path so ledger-backed capital-ratio facts carry evidence IDs into memo narrative fields.
- Add a second bank prompt after JPM, preferably another large bank if added to the SEC universe, to make sure the iXBRL fact mapping is not JPM-only.
- Consider adding a small bank-metric unit test fixture around iXBRL context parsing before promoting banking prompts into the main memo eval.
