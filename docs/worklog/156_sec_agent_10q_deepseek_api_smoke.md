# 156 SEC Agent 10-Q DeepSeek API Smoke

## Summary

- Date: 2026-05-24
- Scope: 2026 SEC 10-Q pilot, MSFT and AMZN, DeepSeek API synthesis.
- Status: completed diagnostic smoke.
- Cloud run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_125319_3cc2b2f480`
- Rendered answer: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_125319_3cc2b2f480/qwen/rendered_answer.md`

## Problem

The first real DeepSeek API smoke over the new 10-Q pilot proved that the full chain could call the model, but the rendered output still exposed 10-Q integration defects:

- Query Contract could allow `10-Q` while offscope repairs still listed `10-Q` as forbidden.
- Runtime ledger missed AWS segment operating income and kept weaker operating-income proxy rows.
- MSFT segment tables with broad titles caused `Revenue` / `Operating expenses` rows to be misclassified as `operating_income`.
- Change-rate values such as cloud revenue `31%` / `32%` were present in SEC text but not represented in the ledger, causing user-facing placeholders.
- Gross margin change rates could be rendered as gross-margin levels.
- Rendered support lines only showed counts, not readable evidence refs.

## Changes

- `scripts/cloud/sec_agent_interactive.py`
  - Treat years present in the selected inventory, including `2026`, as in-scope instead of automatically offscope.
  - Build forbidden filing-source text from actual allowed `filing_types`, so allowed `10-Q` is not listed as forbidden.
  - Let 10-Q evidence IDs render as short refs such as `AMZN 2026 10-Q Item 2`.
  - Include readable evidence refs in rendered support lines.
  - Admit AWS operating-income segment rows while filtering operating expenses, revenue rows, FX impact rows, and change-only rows from `operating_income`.
  - Add growth-rate ledger rows from metric sentences like `or 31%`, when the percentage is attached to an increase/decrease sentence.
  - Keep high-value segment metrics such as AWS from being skipped by one-row-per-family supplement logic.
  - Drop gross-margin percentage change rows when they are not actual margin levels.
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - Allow `future_10q` / `future_sec_filing` watch-item source labels.
  - Remove memo rows containing unresolved exact-value placeholders after ledger sanitization.

## Cloud Validation

Command shape, with the key injected only as a process environment variable:

```bash
DEEPSEEK_API_KEY=<env only> \
/root/autodl-tmp/envs/sec-agent-cu128/bin/python scripts/cloud/sec_agent_interactive.py \
  --llm-backend deepseek \
  --base-url https://api.deepseek.com \
  --chat-completions-path /chat/completions \
  --model deepseek-v4-pro \
  --api-key-env DEEPSEEK_API_KEY \
  --query-planner llm \
  --max-tokens 4000 \
  --bge-first \
  --bge-device cuda \
  --manifest-path data/processed_private/manifests/sec_tech_10q_pilot_manifest_2026.jsonl \
  --bm25-index-dir data/indexes/bm25/sec_tech_10q_pilot \
  --object-bm25-index-dir data/indexes/bm25/sec_tech_10q_pilot_objects \
  --tickers MSFT,AMZN \
  --years 2026 \
  --quiet \
  --prompt "只基于2026年10-Q证据，比较MSFT和AMZN云业务最新季度表现，并说明证据边界。"
```

Final run:

- Run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_125319_3cc2b2f480`
- Total elapsed: `92.1937 sec`
- DeepSeek latency: `52892 ms`
- Total tokens: `57193`
- Runtime ledger rows: `66`
- Retrieved context rows: `120`
- Render checks:
  - `当前引用未保留`: absent
  - `56,058%`: absent
  - `Operating expenses`: absent
  - false `整体毛利率为17%`: absent
  - false `Intelligent Cloud ... 76,387`: absent

Post-gates:

- `answer_ledger_gate_pass=true`
- `metric_role_term_gate_pass=true`
- `named_fact_gate_pass=true`
- `ledger_missing_consistency_gate_pass=true`
- `abstract_judgment_gate_pass=true`
- `caveat_claim_gate_pass=true`
- `v2_semantic_contract_gate_pass=true`
- `answer_vs_judgment_plan_gate_pass=true`
- `metric_source_grounding_gate_pass=true`
- `ledger_unit_gate_pass=true`
- `qwen_answer_gate_pass=false`

The remaining `qwen_answer_gate_pass=false` is not a chain failure in this run. The scored report has no failure types, `mean_score_pct=0.88`, `ledger_text_contract_violation_count=0`, `ledger_text_contract_sanitized_count=0`, `named_fact_contract_sanitized_count=0`, `claim_first_rejected_count=0`, and `claim_first_downgraded_count=6`.

## Output Quality Notes

The rendered answer is now usable for a manual session:

- It clearly labels the evidence boundary as 2026 10-Q unaudited SEC evidence.
- It shows short evidence refs in user-facing support lines.
- It uses AWS revenue, AWS operating income, MSFT cloud revenue growth, and AMZN capex values from the runtime ledger.
- It does not expose raw JSON or unresolved ledger placeholders.

Residual limitations:

- 10-Q table parsing for MSFT segment tables still loses some row-group structure, so the chain should avoid strong segment-profit claims unless the ledger row itself is unambiguous.
- `qwen_answer_gate_pass` remains a coarse quality threshold; the individual deterministic factual gates are the more useful pass/fail signal for this smoke.
- The test covers a 10-Q-only pilot, not a mixed 10-K/10-Q answer.

## Next Steps

- Completed in `157_sec_agent_10q_source_scope_contract.md`: add a small regression test for 10-Q Query Contract allowed/forbidden filing consistency and source inventory gaps.
- Completed in `157_sec_agent_10q_source_scope_contract.md`: add ledger/source-scope regression tests for:
  - AWS operating income from `Operating income by segment`.
  - MSFT cloud revenue growth percentage extraction.
  - rejection of operating-expense/revenue rows from operating-income ledgers.
  - rejection of gross-margin change rates as margin levels.
- Completed in `157_sec_agent_10q_source_scope_contract.md`: make retrieval and Coverage Matrix enforce requested `filing_types` / `source_tiers`, so 10-K rows cannot satisfy 10-Q-only tasks.
- Later, improve section/table parsing so MSFT segment tables preserve row groups instead of relying on defensive ledger filters.
