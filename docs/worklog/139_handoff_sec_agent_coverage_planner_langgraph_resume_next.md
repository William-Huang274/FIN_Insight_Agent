# Handoff: SEC Agent Coverage/Planner Fixes And Memo Eval Resume

## Current Status
- Branch: `codex/api-model-call-architecture`.
- Local repo: `D:\FIN_Insight_Agent`.
- Cloud repo path: `/root/autodl-tmp/FIN_Insight_Agent`.
- Cloud endpoint used this turn: `connect.westd.seetacloud.com:33109`.
- Credentials were used only at runtime. Do not write passwords or API keys into repo files.
- No 5-case memo eval is currently running. Remote `ps` showed only system notebook/tensorboard processes, and `nvidia-smi` showed `0 MiB / 32607 MiB`.

## What Was Completed
### 1. Named-Fact / Evidence-ID Propagation
Goal: do not let ledger-supported facts fail because the model omitted citation-formatted `evidence_ids`.

Changed files:
- `src/sec_agent/claim_verifier.py`
- `scripts/validate_sec_benchmark_named_fact_support.py`

Implemented behavior:
- Claim verifier now builds `metric_id -> evidence_ids` from runtime ledger rows.
- If a model/memo item cites valid `metric_ids` but has missing/partial `evidence_ids`, verifier propagates ledger-backed `source_evidence_id`, `evidence_id`, and `object_id`.
- Propagation applies to legacy `decision_drivers` / `key_points` and memo fields:
  - `what_changed`
  - `why_it_matters`
  - `peer_readthrough`
  - `counterarguments`
- Named-fact gate now indexes context text by `evidence_id`, `source_evidence_id`, and `object_id`, so ledger object citations can resolve to text.

Local smoke:
```text
metric_id=m1, no evidence_ids in what_changed
=> claim_status=verified
=> evidence_ids=['E1', 'O1']
```

### 2. Planner Eval Systematic Repair
Goal: keep Query Contract inside project scope and stop planner drift without relying on model output being perfect.

Changed files:
- `scripts/cloud/sec_agent_interactive.py`
- `scripts/evaluate_sec_free_query_planner.py`

Implemented behavior:
- Added `_repair_query_contract_from_prompt(...)` after heuristic and LLM planner output.
- Repair is deterministic and project-bound:
  - clamps tickers/years/forms to inventory;
  - derives task type from prompt shape, ticker mentions, risk/off-scope intent, and comparison intent;
  - adds a user-question anchor task so eval/task coverage sees the original query semantics;
  - adds prompt-driven task families for cloud/capex/cash-flow, advertising/R&D, pharma pipeline, semis, energy/industrial cycles, bank rate metrics, risk, shareholder return, services/product margin, mobile/edge AI, etc.;
  - records off-scope items such as 2026 forecasts, stock price, valuation, consensus, and macro as `evidence_gaps` / caveats rather than letting them enter retrieval as positive evidence needs.
- Fixed evaluator bug where `source_boundary_violation_rate=0.0` was treated as falsy and replaced with `1.0`, making acceptance false despite no violations.

Local planner eval after repair:
```text
case_count=30
pass_count=30
fail_count=0
task_type_accuracy=1.0
primary_ticker_recall=1.0
peer_ticker_recall_any_of=1.0
required_task_coverage=1.0
metric_family_recall=0.9783
year_compliance=1.0
source_boundary_violation_rate=0.0
schema_validation_pass_rate=1.0
meets_step1_acceptance=true
```

Cloud planner eval after sync:
```text
/root/autodl-tmp/FIN_Insight_Agent/reports/query_contracts/planner_eval_v1/current_planner_eval_repair_cloud_report.json
case_count=30
pass_count=30
fail_count=0
meets_step1_acceptance=true
```

### 3. Coverage Matrix Drives Evidence Pack Selection
Goal: make Evidence Coverage Matrix affect what the synthesis model sees, instead of only being shown as diagnostic metadata.

Changed files:
- `scripts/cloud/sec_agent_interactive.py`
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`

Implemented behavior:
- Added coverage-prioritized context selection through `_select_prompt_context_rows(..., coverage_matrix=...)`.
- Selection order is now:
  1. coverage matrix task sample evidence IDs / sample metric IDs mapped to ledger evidence IDs;
  2. ledger-backed object/source IDs;
  3. high-value caveat/context rows;
  4. balanced remaining context.
- Interactive runs now write `runtime_evidence_pack.json`.
- The qwen/API synthesis trace now stores the selected Evidence Pack context rows, not just the full retrieval trace, making downstream named-fact and gate checks closer to what the model actually saw.

Local smoke:
```text
context rows: A, B, C
coverage sample_evidence_ids: B
ledger source_evidence_id: C
selected with max_rows=2 => B, C
```

## LangGraph / Resume State Status
Prior work already split the interactive pipeline into resumable stages:
- `retrieve_context`
- `build_runtime_ledger`
- `build_coverage_matrix`
- `build_judgment_plan`
- `synthesize_memo`
- `run_deterministic_gates`
- `render_answer`

Relevant files:
- `scripts/cloud/sec_agent_interactive.py`
- `scripts/cloud/sec_agent_graph_runner.py`
- `src/sec_agent/graph_state.py`
- `src/sec_agent/graph_nodes.py`

State artifact:
- Each interactive run writes `sec_agent_state.json` under its run root.

Graph commands:
```bash
bash scripts/cloud/sec_agent_interactive.sh graph-inspect-state <path/to/sec_agent_state.json>
bash scripts/cloud/sec_agent_interactive.sh graph-resume-state <path/to/sec_agent_state.json>
```

Important caveat:
- `graph-resume-state` depends on missing/downstream artifacts to infer the next ready node.
- To test expensive-node precision, use a completed run, delete only memo/gate/render artifacts, then inspect state. Expected `next_ready_node=synthesize_memo`.

## Validation Already Done
Local:
```bash
python scripts/run_sec_free_query_planner_eval.py \
  --query-planner heuristic \
  --output-path reports/query_contracts/planner_eval_v1/current_planner_contracts_repair_local.jsonl \
  --quiet

python scripts/evaluate_sec_free_query_planner.py \
  --contracts-path reports/query_contracts/planner_eval_v1/current_planner_contracts_repair_local.jsonl \
  --output-path reports/query_contracts/planner_eval_v1/current_planner_eval_repair_local_report.json
```

Cloud:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
/root/miniconda3/bin/python scripts/run_sec_free_query_planner_eval.py \
  --query-planner heuristic \
  --output-path reports/query_contracts/planner_eval_v1/current_planner_contracts_repair_cloud.jsonl \
  --quiet

/root/miniconda3/bin/python scripts/evaluate_sec_free_query_planner.py \
  --contracts-path reports/query_contracts/planner_eval_v1/current_planner_contracts_repair_cloud.jsonl \
  --output-path reports/query_contracts/planner_eval_v1/current_planner_eval_repair_cloud_report.json
```

Cloud AST syntax check:
```text
cloud_ast_ok 7
```

Note:
- Local `python -m py_compile` hit a Windows `__pycache__` permission issue on `scripts/cloud/__pycache__`, but direct `ast.parse(...)` syntax checks passed.

## What Is Not Done Yet
The 5-case memo eval has not been rerun after the fixes.

Before interruption, only these checks were done:
- cloud scripts synced;
- cloud AST check passed;
- cloud planner eval passed;
- cloud process/GPU check showed no active run and GPU memory free.

## Next Step: Run 5-Case Memo Eval
Use the existing cloud runner:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
export DEEPSEEK_API_KEY='<runtime only>'
bash /tmp/run_sec_agent_5case_memo_eval.sh
```

Expected baseline to beat:
- Previous run: `reports/quality/20260522_api_memo_v1_5case_125123`
- Previous result: `2/5` all-gates green.
- Target after this patch: at least `4/5` all-gates green.

After run:
```bash
cat reports/quality/<new_run_id>/summary.json
```

Useful prior failure comparison:
- Previous AMZN/META/JPM failures were `named_fact_gate_pass`.
- This patch should specifically improve:
  - missing `evidence_ids` for ledger-backed facts;
  - JPM banking planner/metric selection;
  - coverage-driven Evidence Pack selection.

## Next Step: Test `synthesize_memo` Precise Resume
Pick one completed artifact from the new 5-case run, then:
```bash
cd /root/autodl-tmp/FIN_Insight_Agent
ART=<eval/sec_cases/outputs/interactive_sec_agent/...>

rm -f "$ART/qwen/agent_outputs.jsonl" \
      "$ART/qwen/claim_verification.jsonl" \
      "$ART/qwen/scores.jsonl" \
      "$ART/qwen/raw_model_outputs.jsonl" \
      "$ART/qwen/run_summary.json" \
      "$ART/qwen/input_output.md" \
      "$ART/post_gates/sec_benchmark_post_gates_summary.json"

bash scripts/cloud/sec_agent_interactive.sh graph-inspect-state "$ART/sec_agent_state.json"
```

Expected inspect result:
```text
next_ready_node=synthesize_memo
```

Then resume:
```bash
export DEEPSEEK_API_KEY='<runtime only>'
bash scripts/cloud/sec_agent_interactive.sh graph-resume-state "$ART/sec_agent_state.json"
```

Acceptance:
- It must not rerun retrieval/BGE/ledger/coverage/Judgment Plan.
- It should start at model synthesis and then run gates/render.
- New `qwen/run_summary.json`, `qwen/agent_outputs.jsonl`, `post_gates/sec_benchmark_post_gates_summary.json`, and `qwen/input_output.md` should be recreated.

## Files Changed This Turn
- `scripts/cloud/sec_agent_interactive.py`
- `scripts/run_sec_eval_synthesis_qwen9b_backend.py`
- `src/sec_agent/claim_verifier.py`
- `scripts/validate_sec_benchmark_named_fact_support.py`
- `scripts/evaluate_sec_free_query_planner.py`

Previously relevant LangGraph/state files:
- `scripts/cloud/sec_agent_graph_runner.py`
- `src/sec_agent/graph_state.py`
- `src/sec_agent/graph_nodes.py`
- `requirements.txt`

## Recommended Continue Order
1. Run cloud 5-case memo eval.
2. Inspect `summary.json`; record gate count and failed gate keys.
3. If at least one case completed, run `synthesize_memo` resume test on that case.
4. Only after these pass, update model run ledger and decide whether to expand ontology/cases.

## Do Not Do Yet
- Do not add more industry ontology or more cases before rerunning 5-case.
- Do not add named-fact allowlists unless a failure is genuinely a tokenizer/gate artifact.
- Do not claim production quality until all-gates pass rate and resume precision are verified.
