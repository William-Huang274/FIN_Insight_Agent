# P38 Point01 M6.3R.0 Local Retrieval / Rerank / Context Expansion Design Repair

## Scope And Status

- Date: 2026-07-13
- Status: `design_repair_independently_accepted`.
- The total reviewer accepted the v5 artifact-contract closeout independently. It does not raise M6.3/M6.5 maturity or authorize downstream execution.
- This repair supersedes the rejected fixed-cap/SQL-omission design only. Authorized work remains design, schema, adapter inventory, static tests and fixture/calibration planning.
- Runtime activity: adapter execution, network, external tool, model, provider, canonical-store write and evidence promotion are all `0`.

## Top-K And Reranker Contract

The old global `50/20/8` caps were rejected. `EvidenceRequest.topk_policy` is now the required input to a versioned, request-bound resolver; an agent may not select raw values or enlarge capacity.

- Default resolved profile: CandidateBundle `50`, rerank `20`, future Evidence Gate input `5`.
- Standard bounds: CandidateBundle `20-50`, rerank `8-20`, Evidence Gate candidate `1-5`.
- A source-type/evidence-role profile may lower quantities only when it has an explicit id, version and lowering authority. Any future increase needs profile/version/authority/package review and remains capped.
- Audit projection must preserve requested and resolved policies, profile/version, source-role, clamp/reject reason, CandidateBundle ids and separately named future Evidence Gate ids.
- `local_lexical_metadata_reranker:v1` is a zero-model deterministic baseline. A model reranker is a separate profile and execution route requiring independent resource authority.

`CandidateBundleProjection` and `EvidenceGateCandidateProjection` are deliberately distinct: the latter is at most five non-promoted future inputs, never evidence acceptance or promotion at this point.

## Adapter Decision

- `retrieval_plan.py` remains metadata planning only. BM25/ObjectBM25, index registry and relationship graph remain future read-only candidates after exact snapshot/authority/coordinate contracts.
- `ledger_store.query_ledger_facts` is now explicitly inventoried as a DuckDB read-only exact-value SQL candidate. In M6.3R.3 it may only emit a bounded candidate row from a pinned immutable snapshot; entity/period/unit/scale/form/source-tier/lineage/selector/numeric validation remains mandatory and it cannot promote evidence.
- The typed `sec_query_exact_value_ledger` MCP contract can be reused only through a future M6.2 ToolRegistry and `ToolInvocationReceipt` route. The current direct registry handler is rejected: it bypasses that receipt and contains relaxed filing/period fallback behavior.
- D-series readers are governance/history candidate context only and are not immutable read-only issuer-fact adapters. `build_pre_memo_fact_selection` is expressly rejected as retrieval because it is downstream governed selection.
- Research-graph builder/runtime-source-context direct reuse, Hybrid/Dense model paths and archived prototype reuse remain rejected or deferred as before.

M6.3R.3 must include a bounded local read-only exact-value ledger SQL lane, guarded by pinned snapshot plus M6.2 receipt/admission and with no relaxed-filter fallback. It is not being implemented now.

## Validation

- `python scripts/engineering/run_point01_m6_3r_0_local_retrieval_rerank_design_lint.py` → `pass`.
- `python -m pytest -q tests/contract/test_point01_m6_3r_0_local_retrieval_rerank_design.py` → `8 passed`.
- `python -m compileall -q scripts/engineering/run_point01_m6_3r_0_local_retrieval_rerank_design_lint.py tests/contract/test_point01_m6_3r_0_local_retrieval_rerank_design.py` → `pass`.

Negative regressions cover a global Top-K source, evidence-cap `8`, missing Top-K audit fields, direct MCP handler reuse and D-series fact-selection reuse. All checks are static and perform no adapter/store/network/model work.

## Boundary

This remains neither M6.3 full/calibrated nor a retrieval runtime. Total reviewer independently accepted the repaired design and authorized only M6.3R.1 typed skeleton implementation. It does not execute a local retriever, query graph/SQL, invoke any tool/reranker/model, persist Evidence, run parser/numeric logic, call SourceHunter, inject Context, or feed Writer/full-chain. R.2 fixtures still require a new audit decision.
