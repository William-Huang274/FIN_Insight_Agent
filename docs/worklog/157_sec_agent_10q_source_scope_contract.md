# 157 SEC Agent 10-Q Source Scope Contract

## Summary

- Date: 2026-05-24
- Scope: Stage 1 SEC 10-Q source expansion contract hardening.
- Status: local and cloud regression complete; real DeepSeek 10-Q pilot rerun passed targeted postchecks.

## Problem

The 10-Q pilot proved the real API path can run, but the next chain issue was upstream of rendering:

- Query Contract did not carry an explicit mixed recent SEC source policy or selected source tiers.
- Evidence Coverage Matrix matched coverage by ticker/year/metric family only, so a mixed 10-K/10-Q index could count a 10-K row toward a 10-Q-only task.
- Retrieval trace rows did not consistently preserve `form_type`, `source_tier`, and period metadata.
- Runtime ledger rows carried values but not enough source metadata for downstream source-policy gates.
- The real DeepSeek rerun exposed additional source-chain defects:
  - Planner/model caveats could say the protocol had no concrete numbers even when runtime ledger rows existed.
  - MSFT summary tables with multi-row headers could misalign `Percentage Change` columns and admit `17%` as a gross-margin level.
  - MSFT operating-income growth amounts such as `$6.4 billion` could be admitted as `total_value` operating income.

This is a chain contract issue, not an answer-format issue. The fix therefore changes planner/query contract, retrieval filters, coverage matching, structured-object schema, and ledger metadata propagation.

## Changes

- `src/sec_agent/query_contract.py`
  - Derives source policy from selected filing/source scope:
    - `SEC_ONLY_10K` for 10-K-only primary SEC scope.
    - `SEC_PRIMARY_MIXED_RECENT` when 10-Q is in primary SEC scope.
  - Adds `source_tiers` to Query Contract and `scope`.
  - Adds `source_coverage_gaps` with reasons such as `10q_not_in_inventory`.
  - Adds required 10-Q caveats for unaudited quarterly evidence and mixed annual/quarterly boundaries.
  - Normalizes false required-caveat wording such as “protocol contains no concrete numbers” into a ledger-only sourcing rule.
- `src/sec_agent/coverage_matrix.py`
  - Filters coverage rows by `filing_types` and `source_tiers`.
  - Reports covered/missing filing types and source tiers per task and in the summary.
  - Carries Query Contract source coverage gaps into the matrix.
- `src/retrieval/bm25_retriever.py` and `src/retrieval/object_bm25_retriever.py`
  - Make source-scope filters infer legacy form type from IDs like `*_10Q_*`.
  - Default legacy SEC rows to `primary_sec_filing` only for filtering, so old 10-K indexes remain usable.
- `scripts/run_sec_benchmark_eval.py`
  - Applies case `filing_types` / `source_tiers` filters during evidence and object BM25 retrieval.
  - Writes source and period metadata into trace rows.
- `src/evidence/structured_objects.py` and `src/evidence/structured_extractor.py`
  - Add source metadata fields to structured objects.
  - Align common multi-row SEC table headers so `Percentage Change` cells remain `change_value` instead of period values.
- `scripts/cloud/sec_agent_interactive.py`
  - Carries source policy, tiers, source gaps, filing types, and period/source metadata through case, compact coverage prompt, and runtime ledger.
  - Preserves table `cell_kind` metadata in runtime ledger rows.
  - Rejects gross-margin percent rows when they are unlabeled percentage-change artifacts from metric tables.
  - Uses sentence context for `metric_role`, then rejects `operating_income` period-change amounts as level metrics.
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
  - Exposes source gaps and missing filing/source tiers to the synthesis prompt.
  - Deterministic coverage constraints now add source gaps to `not_found` / `limitations` instead of letting another filing type fill them.
  - Removes false “protocol has no concrete numbers” limitations when runtime ledger rows exist.
- `tests/test_sec_agent_10q_source_contract.py`
  - Adds regression coverage for 10-Q Query Contract gaps, coverage filtering, retriever source filters, runtime ledger source metadata, growth-rate extraction, false operating-income/gross-margin rows, false no-number caveats, multi-row `Percentage Change` table alignment, and banking heuristic source-tier initialization.

## Validation

Commands:

```powershell
python -m compileall -q src scripts tests
python -m pytest -q tests/test_sec_agent_10q_source_contract.py
python scripts/evaluate_sec_agent_context_api_smoke.py
python scripts/run_sec_free_query_planner_eval.py --query-planner heuristic --max-cases 1 --output-path .tmp_planner_source_scope_smoke.jsonl --quiet
```

Results:

- Compile: passed.
- 10-Q source contract regression: `9 passed`.
- Context API smoke: `6/6`, `all_pass=true`.
- Planner smoke: `1/1`, `error_count=0`. Temporary output was removed after the run.

Cloud validation:

- Compile: passed.
- 10-Q source contract regression: `9 passed`.
- Planner smoke: `1/1`, `error_count=0`. Temporary output was removed after the run.

Real DeepSeek 10-Q pilot rerun:

- Prompt: `只基于2026年10-Q证据，比较MSFT和AMZN云业务最新季度表现，并说明证据边界。`
- Run root: `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260524_144253_3cc2b2f480`
- Elapsed: `105.37 sec`
- Ledger rows: `62`
- Context rows: `120`
- Gates: `ok=false`, `pass=11`, `fail=['qwen_answer_gate_pass']`; targeted postcheck showed `failed_gates=[]` in the post-gate summary payload inspected for this run.
- Targeted postchecks:
  - `bad_protocol_no_number_entries=[]`
  - `bad_msft_17pct_gross_rows=[]`
  - `bad_msft_operating_income_change_rows=[]`
  - `rendered_bad_markers=[]`

The remaining `qwen_answer_gate_pass` is still the coarse answer-quality threshold already observed in 156. The chain-specific source, ledger role, and rendered-marker checks passed.

## Decision

Proceed. The chain now fails closed at retrieval/coverage when the requested filing/source scope is unavailable, and it records source gaps explicitly instead of relying on rendering repair.

The current 2026 10-Q MSFT/AMZN DeepSeek path is usable as a diagnostic Stage 1 pilot. It should not yet be promoted as a full mixed-source production path because QTD/YTD/TTM/annual period roles still need stricter metric-level extraction.

## Follow-Up

- Add a mixed 10-K/10-Q prompt that requires explicit audited annual versus unaudited quarterly source boundaries.
- Add metric-level QTD/YTD period extraction before promoting 10-Q exact-value comparisons beyond diagnostic use.
- Rebuild or version the 10-Q object index after the multi-row table-header parser fix, so future generated object records carry corrected `cell_kind` without relying on runtime rejection of stale indexed rows.
