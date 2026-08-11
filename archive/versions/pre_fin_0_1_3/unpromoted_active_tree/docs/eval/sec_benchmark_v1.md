# SEC Benchmark v1

Archived note: this document records the original v1 benchmark design. The
one-off seed builders and early gold-gate scripts that appeared in the first
prototype have been removed from the main script surface. Current runnable
entrypoints are listed in `scripts/README.md`; release checks should start from
`scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py` and the current
`scripts/eval_sec_benchmark/run_sec_benchmark_post_gates.py` validator bundle.

This benchmark turns the external SEC evaluation plan into the project-native
evaluation contract for the current Fin Insight Agent pipeline.

## Purpose

The benchmark must separate these failure sources:

- source resolution: wrong company, year, filing type, or missing filing;
- retrieval and reranking: correct evidence did not enter the candidate pool;
- parsing and extraction: tables, sections, units, or metric roles were wrong;
- synthesis: evidence was correct but the model produced weak or unsupported insight;
- validation: citations, numeric values, metric roles, and caveats were not enforced.

Final answer quality is not judged by whether the prose sounds fluent. Every
case is evaluated against gold points, source scope, citations, numeric support,
and hard validators.

## Case Tiers

### Tier A: Formal Seed

These are L1-L3 cases adapted from the external plan. They are the first MVP
benchmark slice because they test whether the agent can handle grounded SEC
summaries before harder multi-company synthesis.

### Tier B: Project Regression

These are cases added from current project findings:

- metric family vs source table context conflicts;
- prose relation direction errors such as `from X grew to Y`;
- exact-value ledger and metric_id discipline;
- metric/table cell JSON and unit-scale consistency.

### Tier C: Diagnostic Stress

The existing `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl` remains the L4/L5
stress set. It should not be used as the main MVP score until Tier A and Tier B
are stable.

## Required Modes

Each non-trap case should support two modes.

- `gold_context`: the model receives manually verified or programmatically
  frozen correct evidence. This tests model/prompt/synthesis capacity.
- `pipeline_context`: the full agent performs source resolution, retrieval,
  reranking, evidence building, synthesis, and validation. This tests the end to
  end system.

If gold context is good but pipeline context is bad, the failure is upstream.
If both are bad, inspect model capacity, prompt contract, output schema, or
context noise.

## Scoring

Each case uses a 10-point score.

| Dimension | Points | Meaning |
|---|---:|---|
| retrieval | 2 | correct company, year, filing, section, and relevant evidence |
| factuality | 3 | facts, numbers, units, metric roles, and years are correct |
| coverage | 2 | gold points and required companies/years are covered |
| synthesis | 2 | answer is analytical, calibrated, and not just chunk repetition |
| citation | 1 | each material claim has valid evidence IDs |

Hard failures can cap or zero the score even when prose is fluent.

## Failure Taxonomy

Use this controlled vocabulary in reports:

- `pass`
- `retrieval_miss`
- `wrong_company`
- `wrong_year`
- `wrong_filing_type`
- `wrong_section`
- `table_parse_error`
- `numeric_error`
- `unit_error`
- `metric_role_error`
- `metric_family_context_conflict`
- `relation_direction_error`
- `unsupported_claim`
- `hallucination`
- `missing_required_point`
- `weak_synthesis`
- `over_general_summary`
- `citation_missing`
- `citation_mismatch`
- `not_found_failure`
- `format_failure`
- `model_capacity_limit`

## Current Hard Validators

These validators are mandatory before promoting a run:

- citation validator: object IDs exist, roles are allowed, source trace exists;
- metric/table cell validator for table cases;
- exact-value ledger validator for precise numeric claims;
- metric-family/table-context validator before ledger rows are promoted;
- prose numeric relation validator for trend direction claims;
- conclusion calibration gate: missing primary evidence must downgrade the
  conclusion.

## MVP Acceptance Targets

- L1 factual/trap cases: average score at least 8.5/10.
- L2 numeric and single-company summary: average score at least 8.0/10.
- L3 cross-year trend: average score at least 7.0/10.
- Anti-hallucination traps: refusal/qualification correctness at least 90%.
- L4/L5 diagnostic cases: no pass threshold initially; use them to expose
  failure modes.

## First-Step Readiness Test

The current local readiness check is not a model run. It validates that the
agent script surface, context flow, source policy, market smoke, and structural
contracts are executable:

```powershell
python scripts\eval_context\evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

Older prototype commands for v1 schema-only validation were retired with the
historical script cleanup.

## Seed Gold Context

Seed Gold Context files in this document are historical review candidates, not
current public entrypoints. Current promotion should use checked-in eval cases,
current retrieval traces, and the post-gate validator bundle instead of
regenerating old v1 seed packs.

## Context-Only Runner

Before invoking a synthesis model, prepare both modes with:

```powershell
python scripts\eval_sec_benchmark\run_sec_benchmark_eval.py `
  --mode all `
  --output-dir eval\sec_cases\outputs\run_20260518_context_only_smoke
```

This writes `agent_outputs.jsonl`, `claim_verification.jsonl`, `scores.jsonl`,
`trace_logs.jsonl`, `bad_cases.md`, and `run_summary.json`, but marks them as
`context_only`. No model answer or score attribution is produced until a model
backend and claim verifier are connected.

## Gold Review Gate

Seed Gold Context / Gold Facts are review candidates, not scored benchmark
labels. Current scored runs should use the active post-gate bundle:

```powershell
python scripts\eval_sec_benchmark\run_sec_benchmark_post_gates.py `
  --gold-run-dir eval\sec_cases\outputs\<gold_run> `
  --pipeline-run-dir eval\sec_cases\outputs\<pipeline_run>
```

The active bundle includes answer-ledger, table-cell, named-fact,
ledger-missing, semantic-contract, metric-source-grounding, trap, and
gold-vs-pipeline checks where applicable.
