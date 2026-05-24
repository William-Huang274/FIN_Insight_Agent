# SEC Benchmark v1

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

The first local test is not a model run. It validates that the benchmark itself
is executable:

```powershell
python scripts\validate_sec_benchmark.py `
  --cases-path eval\sec_cases\test_cases_v1.jsonl `
  --output-path reports\quality\sec_benchmark_v1_step1_readiness.json `
  --run-bm25-smoke
```

This checks schema validity, filing availability, section/evidence coverage,
structured object availability, and a small BM25 smoke for pipeline-context
readiness. Gold-context files are allowed to be missing in this first step, but
the report must warn on them.

## Seed Gold Context

Seed Gold Context files can be generated with:

```powershell
python scripts\build_sec_gold_context_seed.py --overwrite
```

These files are not final human gold. They are reproducible review candidates
selected from filtered BM25 over `EvidenceObject` plus object-BM25 over
structured metric/table objects. Every row carries `review_status:
seed_needs_review`.

## Context-Only Runner

Before invoking a synthesis model, prepare both modes with:

```powershell
python scripts\run_sec_benchmark_eval.py `
  --mode all `
  --output-dir eval\sec_cases\outputs\run_20260518_context_only_smoke
```

This writes `agent_outputs.jsonl`, `claim_verification.jsonl`, `scores.jsonl`,
`trace_logs.jsonl`, `bad_cases.md`, and `run_summary.json`, but marks them as
`context_only`. No model answer or score attribution is produced until a model
backend and claim verifier are connected.

## Gold Review Gate

Seed Gold Context / Gold Facts are review candidates, not scored benchmark
labels. Before any scored Gold-vs-Pipeline run, enforce the gold gate:

```powershell
python scripts\validate_sec_gold_gate.py `
  --gate mainline_scored `
  --output-path reports\quality\sec_benchmark_v1_gold_gate_mainline.json
```

Current manual review status blocks mainline scoring. Allowed gates are:

```powershell
python scripts\validate_sec_gold_gate.py --gate context_smoke
python scripts\validate_sec_gold_gate.py --gate trap_smoke
```

The mainline gate requires a manual-review overall status of
`approved_for_mainline_scored_benchmark`, per-case approved decisions, and no
`seed_needs_review` rows in the active gold context or fact files.

The first reviewed artifacts are case-filtered numeric regression packs:

```powershell
python scripts\validate_sec_gold_gate.py `
  --gate mainline_scored `
  --case-id AMZN_AWS_NUMERIC_2023_2025_001 `
  --case-id GOOGL_CLOUD_CONTEXT_ROLE_2025_001 `
  --gold-context-dir eval\sec_cases\reviewed_gold_context `
  --gold-facts-dir eval\sec_cases\reviewed_gold_facts `
  --manual-review-path reports\quality\sec_benchmark_v1_reviewed_gold_partial_approval.json `
  --output-path reports\quality\sec_benchmark_v1_gold_gate_reviewed_numeric_cases.json
```

This is a case-filtered partial approval only. It does not unblock the full
benchmark. For numeric cases, the gate also checks that each declared
`numeric_checks` company-year-metric has exactly one reviewed target fact with
matching ticker, fiscal year, period, metric family, metric role, `object_id`,
and `source_evidence_id`.
