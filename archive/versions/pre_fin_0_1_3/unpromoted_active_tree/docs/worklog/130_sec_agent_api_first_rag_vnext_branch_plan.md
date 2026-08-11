# 130 - API-First SEC Agent/RAG vNext Branch Plan

## Summary
- Date: 2026-05-21
- Branch: `codex/api-model-call-architecture`
- Purpose: separate local deployed model routing from API model calls, and replace the current model-centric synthesis path with a contract-driven Agent/RAG architecture.
- Status: branch created; minimal role-route code scaffold added; implementation plan frozen for the next six steps.
- Secret policy: no API key, SSH password, or temporary credential is stored in this repo.

## Target Architecture

```text
Planner API
  -> Query Contract

Retrieval + Rerank
  -> Evidence Candidates

Coverage Compiler
  -> Evidence Coverage Matrix

Summary API
  -> Final Answer

Deterministic Gates
  -> Audit Only
```

This branch changes the project direction from "one model call plus many downstream repairs" to "role-specific model calls over auditable intermediate artifacts".

## Model Routing Boundary

The code now distinguishes two model-call classes:

- `api_model_call`: external API models such as `deepseek` and `openai_compatible`.
- `local_model_deployment`: local/resident model serving such as `qwen_vllm`.

Current code scaffold:

- `src/sec_agent/model_routes.py`
  - maps backend -> model call mode;
  - emits a public route object without secrets;
  - supports role labels such as `planner` and `synthesizer`.
- `scripts/cloud/sec_agent_interactive.py`
  - records `model_call_mode`, `model_route_role`, and `model_route_backend` in gateway trace tags;
  - exposes `model_routes` in `--print-config`.

This does not yet implement separate provider configs per role. The first branch goal is observability and terminology correctness; role-specific provider selection can be added after the planner and coverage matrix contracts stabilize.

## Step 1 - Build `planner_eval_v1` + Evaluator

### Objective
Create a regression set that evaluates whether the Planner API turns free-form user prompts into valid Query Contracts without checking final answers.

### Work Items
- Create `eval_sets/sec_free_query_planner_eval_v1.jsonl` with 30 cases.
- Include at least these categories:
  - `single_company_growth`
  - `company_peer_analysis`
  - `industry_trend`
  - `profitability_quality`
  - `cash_flow_capex`
  - `risk_factor_analysis`
  - `banking_financials`
  - `pharma_rd_pipeline`
  - `energy_capex_cash_return`
  - `off_scope_or_unsupported_source`
- Add expected labels:
  - `expected_task_type`
  - `primary_tickers`
  - `peer_tickers_any_of`
  - `years`
  - `required_tasks`
  - `required_metric_families`
  - `disallowed_sources`
  - `expected_caveats`
- Implement `scripts/evaluate_sec_free_query_planner.py`.
- The evaluator should run either:
  - saved `query_contract.json` artifacts; or
  - live planner-only mode for a supplied eval set.

### Acceptance Metrics
- `task_type_accuracy >= 0.85`
- `primary_ticker_recall >= 0.95`
- `peer_ticker_recall_any_of >= 0.75` for peer cases.
- `required_task_coverage >= 0.85`
- `metric_family_recall >= 0.75`
- `year_compliance = 1.0`
- `source_boundary_violation_rate = 0`
- `schema_validation_pass_rate = 1.0`

### Fail Conditions
- Any planner output asks for unavailable source types such as stock price, valuation, analyst consensus, earnings call, news, or 10-Q when the inventory only contains 10-K.
- Any peer/competitor case drops the primary company or fails to include a peer task.
- Any broad industry case returns fewer than two decomposed tasks.

## Step 2 - Run Current Planner And Diagnose Drift

### Objective
Measure current Planner API behavior before changing planner prompts or schemas.

### Work Items
- Run planner-only evaluation on `sec_free_query_planner_eval_v1.jsonl`.
- Save outputs under:
  - `reports/query_contracts/planner_eval_v1/current_planner_contracts.jsonl`
  - `reports/query_contracts/planner_eval_v1/current_planner_eval_report.json`
- Add a failure taxonomy:
  - `wrong_task_type`
  - `missing_primary_ticker`
  - `missing_peer_task`
  - `bad_metric_family`
  - `source_policy_violation`
  - `overbroad_scope`
  - `underspecified_scope`
  - `unsupported_year_or_form`
- Update planner prompt only after the baseline report is written.

### Acceptance Metrics
- Baseline report is reproducible with a single command.
- Every failed case has one failure taxonomy label.
- No prompt or schema change is made before the baseline is recorded.
- The report identifies whether current failure is mostly:
  - planner misunderstanding;
  - inventory prompt insufficiency;
  - ontology gap;
  - expected-label design issue.

### Fail Conditions
- Evaluator cannot distinguish planner failure from retrieval/synthesis failure.
- Report only gives aggregate score without per-case diagnostics.

## Step 3 - Add Coverage Matrix Builder

### Objective
Add a deterministic intermediate artifact that explains whether each decomposed task has enough evidence before the Summary API is called.

### New Artifact
`runtime_evidence_coverage_matrix.json`

### Schema Sketch

```json
{
  "schema_version": "sec_agent_evidence_coverage_matrix_v0.1",
  "case_id": "...",
  "tasks": [
    {
      "task_id": "competitor_identification",
      "priority": "primary",
      "required_tickers": ["NVDA"],
      "peer_tickers": ["AMD", "INTC", "AVGO"],
      "required_metric_families": ["revenue", "gross_margin"],
      "covered_tickers": ["NVDA", "AMD"],
      "covered_peer_tickers": ["AMD"],
      "covered_metric_families": ["revenue"],
      "missing_tickers": ["INTC", "AVGO"],
      "missing_metric_families": ["gross_margin"],
      "context_row_count": 18,
      "ledger_row_count": 6,
      "support_level": "partial",
      "allowed_answer_strength": "weak_or_medium",
      "must_caveat": ["Peer coverage is partial; do not claim complete competitor coverage."]
    }
  ]
}
```

### Work Items
- Implement `scripts/build_sec_agent_coverage_matrix.py`.
- Inputs:
  - `case.jsonl`
  - `query_contract.json`
  - `trace/trace_logs.jsonl`
  - `runtime_exact_value_ledger.json`
- Outputs:
  - `runtime_evidence_coverage_matrix.json`
  - optional summary report for debugging.
- Support levels:
  - `strong`: primary task, required ticker(s), key metric family, and at least two years are covered.
  - `medium`: required ticker(s) and at least one key metric family are covered.
  - `partial`: some task evidence exists but missing required peer/ticker/family coverage.
  - `insufficient`: no usable task-level evidence.

### Acceptance Metrics
- Coverage matrix is produced for every interactive run.
- Every decomposed task has exactly one coverage row.
- `support_level` is deterministic and reproducible.
- Peer cases expose `covered_peer_tickers` and `missing_tickers`.
- The NVDA competitor case must mark competitor evidence as `partial` or `insufficient` when peers are absent from ledger/context.

### Fail Conditions
- Matrix only reports global row counts and cannot identify which task lacks evidence.
- Matrix relies on model-generated claims instead of retrieved context and ledger metadata.

## Step 4 - Integrate Coverage Matrix Into NVDA Competitor Case

### Objective
Use the NVDA growth + competitor query as the first representative regression case for the new architecture.

### Target Query
`你觉得nvda的增长势头主要是因为什么，同行业的主要竞争对手是谁`

### Work Items
- Run the query through:
  - Planner API -> Query Contract
  - Retrieval + BGE rerank -> Evidence Candidates
  - Coverage Compiler -> Coverage Matrix
- Pass the matrix to synthesis as a required input.
- Require final answer sections to map to coverage tasks:
  - `growth_driver_analysis`
  - `competitor_identification`
  - `peer_financial_comparison` when evidence exists
- If `competitor_identification` is `partial` or `insufficient`, final answer must explicitly say what is missing.
- Stop presenting the answer as fully successful when a primary task has insufficient evidence.

### Acceptance Metrics
- The final answer directly answers both halves of the user query.
- If peer evidence is present:
  - names at least 3 supported competitors or peer companies;
  - explains each at a high level without unsupported precise numbers.
- If peer evidence is missing:
  - answer states the limitation in the competitor section;
  - no unsupported named competitor list is invented.
- No long ledger dump appears in terminal output.
- Gate footer must distinguish:
  - `audit_ok=true/false`;
  - `coverage_complete=true/false`;
  - `answer_status=complete|partial|insufficient`.

### Fail Conditions
- Final answer mentions "competitors" only as generic categories without supported company names or a missing-evidence explanation.
- Final answer passes as complete while primary peer task coverage is insufficient.

## Step 5 - Replace Synthesis Prompt/Schema With Analysis-Oriented API Contract

### Objective
Make the Summary API write useful analysis from verified evidence instead of producing audit-report style ledger lists.

### New Output Shape

```json
{
  "direct_answer": "...",
  "thesis": "...",
  "analysis_sections": [
    {
      "task_id": "growth_driver_analysis",
      "heading": "增长驱动",
      "support_level": "medium",
      "insight": "...",
      "evidence_used": [
        {
          "metric_id": "...",
          "evidence_id": "...",
          "why_relevant": "..."
        }
      ],
      "caveat": "..."
    }
  ],
  "not_answered_or_weak": [
    {
      "task_id": "competitor_identification",
      "reason": "...",
      "what_would_be_needed": "..."
    }
  ],
  "final_takeaway": "..."
}
```

### Work Items
- Add API synthesis profile `api_analysis_v2`.
- Prompt inputs:
  - Query Contract
  - Evidence Coverage Matrix
  - Evidence Pack summary
  - Exact-Value Ledger
  - Judgment Plan if still useful for driver prioritization
- Prompt rules:
  - strong conclusions only for `support_level in {"strong", "medium"}`;
  - `partial` tasks must be caveated;
  - `insufficient` tasks go to `not_answered_or_weak`;
  - exact values only from ledger;
  - no unsupported named facts.
- Update terminal renderer to prefer:
  - `direct_answer`
  - `thesis`
  - `analysis_sections`
  - `not_answered_or_weak`
  - `final_takeaway`

### Acceptance Metrics
- API response parses as JSON in `>= 95%` of representative runs.
- Terminal output contains no raw metric-id dump unless debug mode is requested.
- Each analysis section references at least one metric/evidence object or explicitly states insufficient support.
- `not_answered_or_weak` is populated when primary task support is insufficient.
- Existing deterministic gates still run, but are labeled as audit-only.

### Fail Conditions
- The prompt rewards "more facts" over task-level coverage.
- Renderer prints a mechanically appended ledger tail.
- Model produces strong claims for `insufficient` tasks.

## Step 6 - Run 3-5 Representative Prompts For Quality Comparison

### Objective
Check whether the new architecture improves answer usefulness without weakening evidence boundaries.

### Prompt Set
Minimum representative set:

1. NVDA growth + competitors.
2. Broad AI industry 2023-2025 trend.
3. Cloud platform comparison: MSFT vs GOOGL vs AMZN.
4. Pharma R&D / pipeline-style question: LLY or JNJ.
5. Energy capex / cash return question: XOM or CVX.

### Comparison Arms
- Current chain baseline if available.
- New API-first architecture.
- Optional local model baseline only for smoke, not for production-quality claims.

### Metrics
- Planner:
  - `task_type_accuracy`
  - `required_task_coverage`
  - `source_boundary_violation_rate`
- Coverage:
  - `primary_task_support_rate`
  - `peer_coverage_rate`
  - `required_metric_family_coverage`
  - `insufficient_task_disclosure_rate`
- Answer:
  - deterministic gates pass/fail;
  - `coverage_complete`;
  - JSON parse success;
  - no ledger dump;
  - no unsupported named facts;
  - direct answer completeness.
- Quality rubric:
  - `thesis_depth`
  - `evidence_usefulness`
  - `driver_coverage`
  - `contrast_and_segmentation`
  - `caveat_quality`
  - `decision_relevance`

### Acceptance Metrics
- `source_boundary_violation_rate = 0`
- `json_parse_success_rate >= 0.95`
- `unsupported_named_fact_count = 0`
- `ledger_dump_present = false` for all representative prompts.
- `primary_task_support_rate >= 0.80`, or the final answer clearly marks unsupported primary tasks as partial/insufficient.
- For NVDA competitor query:
  - either supported competitors are listed with evidence;
  - or the answer explicitly reports insufficient competitor evidence and does not invent unsupported names.
- Quality rubric improves over current chain on at least 3 of 5 prompts without reducing deterministic gate safety.

### Fail Conditions
- New architecture only improves prose polish while preserving hidden evidence gaps.
- API synthesis passes deterministic gates but ignores `Coverage Matrix`.
- Local model and API model results cannot be separated in trace metadata.

## Immediate Next Decision

Proceed to Step 1 on this branch. Do not tune synthesis prompt further until planner eval baseline and coverage matrix contracts are in place.

## Step 1 Implementation Update - 2026-05-21
- Added `eval_sets/sec_free_query_planner_eval_v1.jsonl`.
  - 30 free-query planner cases across single-company growth, company peer analysis, industry trend, profitability quality, cash-flow/capex, risk-factor analysis, banking, pharma, energy, and off-scope questions.
  - Each case records expected task type, primary tickers, peer ticker expectations, years, required task terms, required metric families, disallowed sources, and optional evidence-gap terms.
- Added `scripts/evaluate_sec_free_query_planner.py`.
  - Evaluates saved Query Contract rows without running retrieval or synthesis.
  - Produces per-case failure taxonomy plus aggregate metrics:
    - `task_type_accuracy`
    - `primary_ticker_recall`
    - `peer_ticker_recall_any_of`
    - `required_task_coverage`
    - `metric_family_recall`
    - `year_compliance`
    - `source_boundary_violation_rate`
    - `schema_validation_pass_rate`
  - Acceptance targets are embedded in the report.
- Added `scripts/run_sec_free_query_planner_eval.py`.
  - Runs the current planner over the eval set and writes `current_planner_contracts.jsonl`-style rows.
  - Supports `--query-planner heuristic` for local no-API smoke and `--query-planner llm --llm-backend deepseek` for the API planner baseline.
  - Writes no secrets; provider keys are read only from environment variables.
- Validation:
  - `python -m py_compile scripts\run_sec_free_query_planner_eval.py scripts\evaluate_sec_free_query_planner.py src\sec_agent\model_routes.py scripts\cloud\sec_agent_interactive.py` passed.
  - JSONL parse check found 30 rows: first `planner_nvda_growth_competitors_001`, last `planner_risk_only_ai_export_030`.
  - Missing-contract smoke report wrote successfully to `reports/query_contracts/planner_eval_v1/missing_contracts_smoke_report.json`.
- Heuristic smoke baseline:
  - Contracts: `reports/query_contracts/planner_eval_v1/heuristic_planner_contracts_smoke.jsonl`
  - Report: `reports/query_contracts/planner_eval_v1/heuristic_planner_eval_smoke_report.json`
  - Result:
    - `case_count=30`
    - `pass_count=1`
    - `task_type_accuracy=0.4667`
    - `primary_ticker_recall=1.0`
    - `peer_ticker_recall_any_of=0.9667`
    - `required_task_coverage=0.2333`
    - `metric_family_recall=0.7778`
    - `year_compliance=1.0`
    - `source_boundary_violation_rate=0.1`
    - `schema_validation_pass_rate=1.0`
  - Interpretation:
    - The evaluator and runner work.
    - Heuristic planner is not adequate for vNext free-query planning because task decomposition fails on most non-AI-template cases.
    - The next meaningful baseline should be the API planner, not another heuristic patch.

## Next Command For API Planner Baseline

Run only when `DEEPSEEK_API_KEY` is present in the shell environment:

```bash
python scripts/run_sec_free_query_planner_eval.py \
  --query-planner llm \
  --llm-backend deepseek \
  --output-path reports/query_contracts/planner_eval_v1/current_planner_contracts.jsonl

python scripts/evaluate_sec_free_query_planner.py \
  --contracts-path reports/query_contracts/planner_eval_v1/current_planner_contracts.jsonl \
  --output-path reports/query_contracts/planner_eval_v1/current_planner_eval_report.json
```

## Step 2 Baseline Update - 2026-05-21
- Ran DeepSeek API planner baseline with credentials supplied only through the process environment; no key was written to repo files or reports.
- Contracts:
  - `reports/query_contracts/planner_eval_v1/current_planner_contracts.jsonl`
- Report:
  - `reports/query_contracts/planner_eval_v1/current_planner_eval_report.json`
- Result:
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
  - `meets_step1_acceptance=false`
- Interpretation:
  - API planner is materially better than heuristic planner on task decomposition and metric-family selection.
  - The main blocker is not provider connectivity or schema parsing; it is planner ontology and task-type semantics.
  - Frequent failure mode: single-company questions are classified as `company_comparison` or broad industry trend because the current task-type vocabulary lacks a clean `single_company_analysis` path.
  - A smaller issue is evaluator lexical brittleness around required task terms and evidence-gap synonyms; this should be fixed carefully as evaluator semantics, not by adding production fallbacks.
- Decision:
  - Treat this as diagnostic baseline, not accepted mainline.
  - Do not tune synthesis further until coverage matrix integration is present.
  - Next structural fix should separate:
    - planner ontology improvement;
    - evaluator synonym normalization;
    - coverage matrix before Summary API.

## Step 3 Implementation Update - 2026-05-21
- Added `src/sec_agent/coverage_matrix.py`.
  - Builds deterministic task-level coverage from Query Contract, retrieved context rows, and runtime Exact-Value Ledger.
  - Emits `support_level=strong|medium|partial|insufficient`.
  - Tracks required/focus/peer tickers, covered tickers, missing peer tickers, metric-family coverage, year coverage, ledger/context row counts, sample metric IDs, and sample evidence IDs.
  - Does not inspect model-generated final answers.
- Added `scripts/build_sec_agent_coverage_matrix.py`.
  - Can run over an existing interactive run directory:

```bash
python scripts/build_sec_agent_coverage_matrix.py \
  --run-dir eval/sec_cases/outputs/interactive_sec_agent/20260521_194503_b38c717195
```

- Updated `scripts/cloud/sec_agent_interactive.py`.
  - The interactive chain now has six visible stages:
    1. Query Contract
    2. Retrieval + BGE rerank
    3. Exact-Value Ledger
    4. Evidence Coverage Matrix
    5. Judgment Plan + LLM synthesis
    6. deterministic gates
  - Every new run writes:
    - `runtime_evidence_coverage_matrix.json`
  - Terminal footer now prints:
    - `coverage_complete`
    - `primary_task_support_complete`
    - `answer_status`
    - support-level counts
- Validation:
  - `python -m py_compile src\sec_agent\coverage_matrix.py scripts\build_sec_agent_coverage_matrix.py scripts\cloud\sec_agent_interactive.py` passed.
  - Backfilled coverage matrix for `eval/sec_cases/outputs/interactive_sec_agent/20260521_194503_b38c717195`.
  - Backfill summary:
    - `task_count=3`
    - `primary_task_count=2`
    - `support_counts={"medium":1,"strong":2}`
    - `coverage_complete=true`
    - `ledger_row_count=36`
    - `context_row_count=360`
  - Synthetic NVDA competitor missing-peer smoke returns `support_level=partial` and `missing_peer_tickers=["AMD","AVGO","INTC"]`, proving the matrix can expose the exact failure the user flagged.
- Current limitation:
  - The matrix currently uses deterministic metadata/alias matching; support levels should be audited on several representative prompts before becoming a scoring gate.

## Step 4 Integration Start - 2026-05-21
- Updated `scripts/cloud/sec_agent_interactive.py`.
  - The compact Evidence Coverage Matrix is now injected into the synthesis case payload before the Summary API/model call.
  - The injected matrix contains task IDs, support levels, covered/missing tickers, missing peer tickers, missing metric families, missing years, and sample metric/evidence IDs.
- Updated `scripts/run_sec_eval_synthesis_qwen9b_backend.py`.
  - `_build_prompt()` now includes an `Evidence Coverage Matrix` block when present.
  - Prompt rules now state:
    - `strong/medium` tasks can support analysis conclusions;
    - `partial` tasks require caveats and cannot be treated as complete;
    - `insufficient` tasks must go to `not_found` or `limitations`;
    - incomplete primary tasks must be described as partial.
  - `_normalize_answer()` applies deterministic coverage constraints after required caveat/not_found repair:
    - incomplete primary tasks are appended to `not_found`;
    - answer limitations record the coverage downgrade;
    - strong driver claims are capped to medium when primary coverage is partial/insufficient.
- Validation:
  - `python -m py_compile src\sec_agent\coverage_matrix.py scripts\build_sec_agent_coverage_matrix.py scripts\cloud\sec_agent_interactive.py scripts\run_sec_eval_synthesis_qwen9b_backend.py` passed.
  - `python scripts\cloud\sec_agent_interactive.py --print-config --llm-backend deepseek --model deepseek-v4-pro` shows planner/synthesizer as `api_model_call`.
  - A local synthetic prompt-build smoke confirmed the prompt contains `Evidence Coverage Matrix`, `support_level`, and `missing_peer_tickers`.
  - A local synthetic normalization smoke confirmed partial primary coverage downgrades a strong driver to medium and appends the missing peer task to `not_found`.
- Current limitation:
  - This is integration-level validation, not a live representative DeepSeek answer rerun.
  - Next step is to run the NVDA growth + competitor prompt through the cloud chain and inspect whether the final answer uses coverage status correctly.

## Step 4 Cloud Representative Run And Gate Fix - 2026-05-21
- Representative user query:

```text
你觉得nvda的增长势头主要是因为什么，同行业的主要竞争对手是谁
```

- First cloud reruns exposed three structural issues:
  - Natural-language answer fields contained inline `metric_id` strings, causing `named_fact_gate` to read `total_value` as an unsupported named fact.
  - Runtime ledger admitted percentage-of-revenue and `$ Change` table rows as if they were period-level dollar values, producing bad NVDA R&D examples such as `9.9（百万美元）` and later `$ Change=4,239`.
  - `focus_tickers` was being treated as mandatory answer coverage, even though in free-query mode it is often a retrieval candidate scope. This made the semantic gate fail when a broad competitor discovery prompt did not mention every candidate semiconductor company.
- Structural fixes:
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
    - Exact values remain in prose, but `metric_id` is stripped from natural-language fields and retained only in `metric_ids` / `supporting_metric_ids` arrays.
    - Unsupported named facts are removed from prose instead of being rendered as placeholder text such as `相关命名标签`.
  - `scripts/cloud/sec_agent_interactive.py`
    - Runtime ledger rejects percentage-basis tables when extracted cells are not percent rows.
    - Runtime ledger rejects `$ Change` / `% Change` columns as period-level exact values.
    - Query Contract case-building now sets a `semantic_gate.company_coverage` policy. Competitor discovery prompts use `selected_companies`, while explicit all-company prompts can still require full coverage.
  - `scripts/validate_sec_benchmark_v2_semantic_contracts.py`
    - Semantic peer/entity checking now distinguishes selected-company coverage from all-focus/all-company coverage.
- Passing cloud run:
  - Remote artifact root:
    - `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260521_234353_60a9e00112`
  - Local synced artifact root:
    - `eval/sec_cases/outputs/interactive_sec_agent/20260521_234353_60a9e00112`
  - Metrics:
    - `gates ok=True`
    - `pass=12`
    - `fail=[]`
    - `qwen_answer_ratio=1.0`
    - `ledger_rows=62`
    - `context_rows=120`
    - `coverage_complete=true`
    - `primary_complete=true`
    - `support={'medium': 1, 'strong': 2}`
  - NVDA R&D ledger values after filtering:
    - 2023: `7,339（百万美元）`
    - 2024: `8,675（百万美元）`
    - 2025: `12,914（百万美元）`
- Model run ledger:
  - `reports/model_runs/20260521_sec_agent_api_first_rag_deepseek_nvda_competitor_gatefix_v1.md`
- Interpretation:
  - The API-first RAG architecture is now validated on one representative free-query case with full deterministic audit pass.
  - The main architecture choice is holding: deterministic artifacts constrain evidence and audit outputs; DeepSeek/API synthesis supplies the higher-quality analysis layer.
  - Remaining work is not more fallback rules. Next work should focus on planner ontology, a small free-query quality eval set, and renderer polish for derived ratios / negative proxy formatting.

## Step 5 API Insight v2 Output Quality Update - 2026-05-22
- Representative user query:

```text
你觉得nvda的增长势头主要是因为什么，同行业的主要竞争对手是谁
```

- Changed synthesis direction:
  - API synthesis now defaults to `api_insight_v2` when using API backends.
  - The API prompt asks for an analyst-style thesis, causal read, "so what" interpretation, and weakening-condition caveats, while preserving ledger/evidence boundaries.
  - Broad AI prompts get higher driver/key-point caps; API mode gets a wider answer budget than the local 9B profile.
- Structural fixes completed in this iteration:
  - `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
    - Added `api_insight_v1` / `api_insight_v2` synthesis profiles.
    - Changed the summary rule from a one-line judgment to a 4-7 sentence thesis for API mode.
    - Fixed Judgment Plan matching so one generated driver can map to multiple relevant plan drivers only when metric IDs overlap; evidence-only overlap no longer pulls unrelated support into the answer.
    - Added named-token support for semiconductor role terms such as `ASIC`, `Compute`, `Networking`, `Foundry`, `IDM`, and `Semiconductor`.
    - Sanitized unsupported exact-value placeholders and dropped user-facing key points containing unresolved exact-value placeholders.
  - `scripts/cloud/sec_agent_interactive.py`
    - API mode now sets `synthesis_profile=api_insight_v2` unless overridden.
    - User-facing system prompt for API mode now asks for thesis, driver meaning, caveat, and competitor-role distinction.
  - `scripts/validate_sec_benchmark_named_fact_support.py`
    - Added role-token and metric-ID based support checks for semiconductor and ticker/company aliases.
  - `scripts/validate_sec_benchmark_v2_semantic_contracts.py`
    - Fixed a false positive where percentage values and dollar values appeared in the same supported sentence.
  - `scripts/score_sec_agent_free_query_quality.py`
    - Added a lightweight free-query quality scorer over summary thesis, driver depth, evidence binding, peer-role coverage, caveat quality, and terminal polish.
- Official cloud run:
  - Remote artifact root:
    - `/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260522_010002_60a9e00112`
  - Local synced artifact root:
    - `eval/sec_cases/outputs/interactive_sec_agent/20260522_010002_60a9e00112`
  - Query/output appendix:
    - `eval/sec_cases/outputs/interactive_sec_agent/20260522_010002_60a9e00112/qwen/input_output.md`
  - Deterministic gates:
    - `gates ok=True`
    - `pass=12`
    - `fail=[]`
    - `qwen_answer_ratio=1.0`
    - `answer_ledger_gate_pass=true`
    - `named_fact_gate_pass=true`
    - `v2_semantic_contract_gate_pass=true`
    - `answer_vs_judgment_plan_gate_pass=true`
    - `metric_source_grounding_gate_pass=true`
    - `ledger_unit_gate_pass=true`
  - Evidence profile:
    - `ledger_rows=62`
    - `context_rows=120`
    - coverage support: `{'medium': 1, 'strong': 2}`
    - `coverage_complete=true`
    - `primary_complete=true`
  - Runtime:
    - `elapsed=289.48 sec`
- Quality report:
  - `free_query_quality_report.json`
  - `mean_score_total=0.9033`
  - Dimension means:
    - `summary_thesis=1.0`
    - `driver_depth=0.82`
    - `evidence_binding=1.0`
    - `peer_role_coverage=1.0`
    - `caveat_quality=0.6`
    - `format_polish=1.0`
- Interpretation:
  - This output is materially better than the local 9B path and better than the earlier all-green API baseline because it gives a real thesis: NVDA growth is tied to Compute & Networking revenue, margin expansion, operating cash flow, and R&D reinvestment, while competitor pressure is separated into GPU, ASIC/networking, CPU/foundry/platform, and cloud self-developed-chip roles.
  - The chain is still bounded by SEC-only evidence. It should not invent market-share, valuation, price, consensus, or post-period claims unless those source policies are explicitly expanded later.
  - The remaining weakness is not deterministic grounding. It is answer quality: caveats and peer comparison still need richer reasoning when evidence is partial or proxy-based.
- Caveat:
  - The official all-green run still contained one user-facing key point with `当前引用未保留的精确金额`.
  - A display-cleanup patch was applied after the official run to drop such unresolved key points, but that exact patch has not yet been rerun as the official API result.
- Model run ledger:
  - `reports/model_runs/20260522_sec_agent_api_insight_v2_deepseek_nvda_competitor_quality_v1.md`
