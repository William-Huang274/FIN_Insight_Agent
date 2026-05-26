# SEC Agent Cloud Full-Source Runbook v1

Date: 2026-05-26

## Purpose

This runbook records the reproducible cloud setup for the first resume-facing SEC agent release. It covers the private full-source artifact contract, ObjectBM25 rebuild, planner/readiness gates, and demo entrypoints without storing credentials.

## Private Artifact Contract

Required cloud paths:

- Manifest: `data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl`
- BM25 index: `data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027`
- ObjectBM25 index: `data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027_objects`
- Evidence objects: `data/processed_private/evidence_objects/sec_tech_primary_mixed_with_8k_earnings_full30_evidence_fy2023_2027.jsonl`
- Market evidence: `data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl`

Current manifest content verified on cloud:

- FY2023 10-K: 30 companies
- FY2024 10-K: 30 companies
- FY2025 10-K: 30 companies
- FY2026 latest 10-Q: 30 companies
- FY2026 earnings-release 8-K: 30 companies

Do not claim FY2027 coverage unless the manifest rows actually contain `fiscal_year=2027`.

## Rebuild Full30 ObjectBM25 Index

Use this when the full-source manifest/evidence exists but the ObjectBM25 index is missing:

```bash
cd /root/autodl-tmp/FIN_Insight_Agent
PY=/root/autodl-tmp/envs/sec-agent-cu128/bin/python
PREFIX=data/processed_private/evidence_objects/sec_tech_primary_mixed_with_8k_earnings_full30
EVID=${PREFIX}_evidence_fy2023_2027.jsonl
OUT=data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027_objects

"$PY" scripts/build_structured_objects.py \
  --evidence-path "$EVID" \
  --prefix "$PREFIX"

"$PY" scripts/build_object_bm25_index.py \
  --prefix "$PREFIX" \
  --output-dir "$OUT"
```

The 2026-05-26 cloud rebuild produced:

- object records: `347015`
- metrics: `257458`
- claims: `77745`
- tables: `11812`

## Real DeepSeek Planner-Contract Gate

Inject the API key through the shell environment only.

```bash
cd /root/autodl-tmp/FIN_Insight_Agent
PY=/root/autodl-tmp/envs/sec-agent-cu128/bin/python
OUT_DIR=reports/query_contracts/planner_eval_v1
CONTRACTS=$OUT_DIR/release_closeout_deepseek_contracts_20260526_r3.jsonl
REPORT=$OUT_DIR/release_closeout_deepseek_eval_20260526_r3.json

SEC_AGENT_SOURCE_POLICY=SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT \
QUERY_PLANNER=llm \
LLM_BACKEND=deepseek \
MODEL_NAME=deepseek-v4-pro \
ENABLE_THINKING=0 \
DISABLE_THINKING=1 \
PLANNER_MAX_TOKENS=4000 \
PLANNER_TIMEOUT_S=240 \
"$PY" scripts/run_sec_free_query_planner_eval.py \
  --eval-path eval_sets/sec_agent_resume_closeout_planner_eval_v1.jsonl \
  --output-path "$CONTRACTS" \
  --query-planner llm \
  --llm-backend deepseek \
  --model deepseek-v4-pro \
  --api-key-env DEEPSEEK_API_KEY \
  --disable-thinking \
  --planner-max-tokens 4000 \
  --planner-timeout-s 240 \
  --years 2023,2024,2025,2026,2027 \
  --tickers ALL \
  --manifest-path data/processed_private/manifests/sec_tech_primary_mixed_with_8k_earnings_full30_manifest_fy2023_2027.jsonl \
  --bm25-index-dir data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027 \
  --object-bm25-index-dir data/indexes/bm25/sec_tech_primary_mixed_with_8k_earnings_full30_fy2023_2027_objects

"$PY" scripts/evaluate_sec_free_query_planner.py \
  --eval-path eval_sets/sec_agent_resume_closeout_planner_eval_v1.jsonl \
  --contracts-path "$CONTRACTS" \
  --output-path "$REPORT" \
  --fail-on-threshold
```

Latest accepted result:

- report: `reports/query_contracts/planner_eval_v1/release_closeout_deepseek_eval_20260526_r3.json`
- `case_count=5`
- `pass_count=5`
- `task_type_accuracy=1.0`
- `required_task_coverage=1.0`
- `metric_family_recall=0.96`
- `year_compliance=1.0`
- `source_boundary_violation_rate=0.0`
- `schema_validation_pass_rate=1.0`
- `meets_step1_acceptance=true`

## Full-Source Readiness Gate

Attach a saved full-source DeepSeek run directory:

```bash
cd /root/autodl-tmp/FIN_Insight_Agent
PY=/root/autodl-tmp/envs/sec-agent-cu128/bin/python

"$PY" scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir eval/sec_cases/outputs/full_source_deepseek_yahoo_fmp_latest_coverage_fix_benchmark/20260526_024807_3fbff2951a \
  --require-full-source-artifacts \
  --latency-profile-case-path eval/sec_cases/outputs/interactive_sec_agent/20260526_182016_e9ca76fb2b/case.jsonl \
  --timeout-s 900
```

Latest accepted full30 readiness result:

- report: `reports/quality/resume_closeout/20260526_202136_resume_closeout_readiness_local_v1.json`
- blocker failures: `0`
- status counts: `pass=11`, `warn=1`, `skipped=0`
- P0 readiness: `pass=6/6`
- saved full30 run market rows: `30`
- saved full30 run gate failures: `0`
- fallback answers: `0`

## Non-Production Boundaries

- JSON-backed session state is validated for single-process demo and small pressure smoke, not multi-worker serving.
- Private data and indexes are required for full-source answer quality but remain outside the public repository.
- Market snapshot is non-real-time and must show `snapshot_id` and `as_of_date`.
- DeepSeek provider latency is outside local optimization control; local P0 timing covers retrieval, ledger, coverage, gates, and context/session overhead.
