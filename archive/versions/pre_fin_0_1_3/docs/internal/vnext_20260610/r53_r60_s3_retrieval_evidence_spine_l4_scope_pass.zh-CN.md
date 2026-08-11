# R53-R60 S3 Retrieval / Evidence Spine L4 Scope Closeout

Generated: `2026-06-28T18:27:49Z`
Status: `pass`
Release decision: `S3_L4_scope_pass`
Closeout level: `L4_scope_pass`

## Scope

S3 closes the auditable retrieval and evidence spine: intent, route policy, plan, route execution, candidate, selected evidence, dropped candidate, typed gap, and qrels are SQL-final and linked back to S1/S2 runtime trace.

## Counts

- `retrieval_spine_metadata`: `2`
- `retrieval_intent_registry`: `1`
- `retrieval_route_policy_matrix`: `7`
- `retrieval_plans`: `1`
- `retrieval_route_executions`: `7`
- `retrieval_candidates`: `49`
- `retrieval_selected_evidence`: `15`
- `retrieval_dropped_candidates`: `34`
- `retrieval_gap_ledger`: `0`
- `retrieval_eval_qrels`: `2`
- `gate_count`: `12`
- `gate_fail_count`: `0`

## Selected By Route

- `bm25`: `2`
- `graph`: `2`
- `milvus_semantic`: `2`
- `object_bm25`: `2`
- `parser_row`: `3`
- `sql_exact`: `3`
- `web_repair`: `1`

## Gate Rows

- `pass` `schema_tables_present`: All S3 retrieval and evidence spine tables exist.
- `pass` `upstream_rd_contracts_available`: Accepted RD/PIG upstream summaries are present and in allowed status.
- `pass` `route_policy_matrix_covers_required_routes`: RoutePolicyMatrix covers SQL, graph, BM25, ObjectBM25, Milvus, web repair, and parser rows.
- `pass` `retrieval_plan_has_facets_and_budgets`: RetrievalPlan carries route ids, facets, query rewrites, budget and typed-gap policy.
- `pass` `route_executions_are_tool_trace_linked`: Each route execution is trace-linked, and SQL exact is also S2 tool-call linked.
- `pass` `candidate_ledger_has_selected_and_dropped`: Candidate ledger records selected and dropped rows.
- `pass` `selected_evidence_authority_guard`: Selected evidence only includes exact/bounded authority rows with evidence refs.
- `pass` `dropped_candidates_have_reasons`: Dropped candidates are explicit and reasoned.
- `pass` `qrels_target_in_candidates_and_selected`: Deterministic qrels prove target refs enter candidates and selected evidence.
- `pass` `gap_ledger_typed_no_hidden_fallback`: Any unresolved route has a typed gap instead of fallback selection.
- `pass` `runtime_projection_parity`: S1 projection/event/artifact/trace rows cover S3 retrieval activity.
- `pass` `no_raw_retrieval_rows_to_memo`: S3 produces retrieval plan, selected evidence pack, and typed gap ledger only; raw retrieval rows remain candidates.

## Outputs

- `schema`: `configs/r53_r60/s3_retrieval_evidence_spine_schema_v0_1.json`
- `sqlite_store`: `data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`
- `gate_rows`: `data/manifests/r53_r60_s3_retrieval_evidence_spine_gate_rows_v0_1.jsonl`
- `summary`: `data/manifests/r53_r60_s3_retrieval_evidence_spine_summary_v0_1.json`
- `closeout_report`: `docs/internal/vnext_20260610/r53_r60_s3_retrieval_evidence_spine_l4_scope_pass.zh-CN.md`

## Boundary

S3 closes retrieval/evidence route ledger scope only; it does not tune full recall/rerank algorithms or write final memos.
