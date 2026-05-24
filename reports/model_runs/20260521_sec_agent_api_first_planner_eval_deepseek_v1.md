# Model Run: 20260521_sec_agent_api_first_planner_eval_deepseek_v1

## Summary
- Purpose: baseline the API Query Contract planner before changing planner ontology or synthesis prompts.
- Status: diagnostic-only.
- Run type: inference + evaluation.
- Timestamp: 2026-05-21.
- Environment: local Windows workspace, DeepSeek API model call through environment-provided credential.

## Code And Command
- Entry point:
  - `scripts/run_sec_free_query_planner_eval.py`
  - `scripts/evaluate_sec_free_query_planner.py`
- Commands:
  - `python scripts/run_sec_free_query_planner_eval.py --query-planner llm --llm-backend deepseek --output-path reports/query_contracts/planner_eval_v1/current_planner_contracts.jsonl --resume`
  - `python scripts/evaluate_sec_free_query_planner.py --contracts-path reports/query_contracts/planner_eval_v1/current_planner_contracts.jsonl --output-path reports/query_contracts/planner_eval_v1/current_planner_eval_report.json`
- Config:
  - Eval set: `eval_sets/sec_free_query_planner_eval_v1.jsonl`
  - Backend: `deepseek`
  - Model: `deepseek-v4-pro`
  - Secret handling: API key supplied through process environment only; not written to files.

## Inputs
- Data profile: 30 free-query SEC planner cases over the current 30-company 10-K inventory.
- Candidate boundary: project inventory only; no stock prices, news, earnings calls, analyst consensus, 10-Q, 8-K, or macro data as source facts.
- Output object: Query Contract only. Retrieval, ledger, synthesis, and gates are intentionally out of scope for this run.

## Outputs
- Contracts: `reports/query_contracts/planner_eval_v1/current_planner_contracts.jsonl`
- Metrics: `reports/query_contracts/planner_eval_v1/current_planner_eval_report.json`

## Results
- `case_count=30`
- `pass_count=14`
- `fail_count=16`
- `task_type_accuracy=0.7`
- `primary_ticker_recall=1.0`
- `peer_ticker_recall_any_of=1.0`
- `required_task_coverage=0.9`
- `metric_family_recall=0.9328`
- `year_compliance=1.0`
- `source_boundary_violation_rate=0.0333`
- `schema_validation_pass_rate=1.0`
- Failure types:
  - `wrong_task_type=9`
  - `missing_required_task=8`
  - `missing_required_evidence_gap=3`
  - `bad_metric_family=2`
  - `source_boundary_violation=1`

## Interpretation
- DeepSeek planner is significantly stronger than the heuristic baseline on task decomposition, metric-family selection, peer ticker inclusion, and schema compliance.
- The run does not meet Step 1 acceptance because `task_type_accuracy` is below `0.85` and source-boundary violations are not zero.
- The dominant blocker is planner ontology/task-type semantics, especially single-company questions being classified as comparison or broad industry tasks.

## Experiment Governance
- Hypothesis: API planner should produce more accurate Query Contracts than heuristic fallback.
- Baseline: heuristic planner smoke report with `task_type_accuracy=0.4667`, `required_task_coverage=0.2333`, `source_boundary_violation_rate=0.1`.
- Decision target: Step 1 acceptance targets in `current_planner_eval_report.json`.
- Decision label: diagnostic-only.
- Mainline decision: do not promote planner prompt/schema yet; fix ontology and evaluator semantics first.

## Runtime Efficiency
- Wall time: about 18 minutes for the full resumed API baseline after incremental writer patch.
- Bottleneck diagnosis: API latency and strict planner timeout, not local GPU.
- Serving implication: planner should be cached and logged per user query; interactive synthesis should not block on repeated planner retries.

## Caveats And Next Step
- This run does not evaluate retrieval, BGE rerank, coverage matrix, synthesis quality, or deterministic answer gates.
- Next step: add Evidence Coverage Matrix as a first-class artifact, then refine planner ontology around `single_company_analysis` and source-boundary evidence gaps.
