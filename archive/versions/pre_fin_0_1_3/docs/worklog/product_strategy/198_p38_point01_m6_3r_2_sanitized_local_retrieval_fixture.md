# P38 Point01 M6.3R.2 Sanitized Local-Retrieval Fixture Tranche

## Decision And Status

- Date: 2026-07-14.
- Upstream reviewer decision: `approve_m6_3r_1_non_authoritative_skeleton_authorize_m6_3r_2_fixture_only`.
- Initial implementation status was `fixture_implemented_pending_total_reviewer_audit`; it was subsequently rejected by independent audit because the evaluator read its own expected outcome, did not bind neighbor direction, did not perform declared diversity selection, and did not preserve rerank-to-Gate membership. Its original pass is superseded and is not a closeout result.
- R.1 is accepted only as `skeleton_independently_accepted_non_authoritative`; this does not make any retrieval, SQL policy or evidence object runtime-authoritative.

## Implemented Fixture Boundary

- Added `LocalRetrievalFixtureAdmissionPolicy`, immutable corpus/entry/evaluation contracts and a deterministic fixture harness in `src/sec_agent/canonical_runtime/local_retrieval_fixture.py`.
- The corpus contains sanitized metadata only: BM25 narrative, ObjectBM25 document/table, relationship graph, exact-value SQL-row, section/table/page/row neighbor and typed exhaustion scenarios. It contains no document bytes, index rows, graph reads, SQL rows, source text or credentials.
- Every entry binds exact EvidenceRequest id/digest, Top-K audit/registry digest, adapter snapshot id/digest, candidate source/parser refs+SHA-256 digests, entity/period/source-policy/route/evidence-role/kind, and `fixture_supplied_not_retrieved` provenance.
- The deterministic matrix proves request-bound `12/8/3` and `12/8/5`, commercial `1/1` typed terminal, metadata hard filtering, stable zero-model rerank, source/content duplicate caps, source-family diversity, neighbor lineage, table/boundary/empty typed exhaustion and nonpersistent CandidateBundle/EvidenceGate projections.

## SQL Fixture Authority

Only the reviewed R.1 SQL policy is fixture-admitted. Its path/ref/version, canonical digest `75fff84e1d4684aa47eb7b6dc9d2cef2ff50333f27bbce8e3cda17d5a6ef820f` and raw SHA-256 are pinned in `point01_m6_3r_2_fixture_admission_policy_v1_0.json`. A self-signed policy can still resolve at R.1's intentionally non-authoritative `registry_not_read/not_admitted` layer, but R.2 returns `not_fixture_admitted`; it cannot be calibration basis or runtime admission.

## Evidence And Boundary

- Runner: `scripts/engineering/run_point01_m6_3r_2_local_retrieval_fixture_gate.py`
- Tests: `tests/contract/test_point01_m6_3r_2_local_retrieval_fixture.py`
- Outputs: `data/manifests/point01_m6_3r_2_sanitized_local_retrieval_fixture_corpus_v1_0.json` and `data/manifests/point01_m6_3r_2_local_retrieval_fixture_gate_result_v1_0.json`

The fixture runner must retain all adapter/index/graph/SQL/source reads, ToolInvocation, receipt registration, network/model/provider, parser/numeric, promotion, SourceHunter, Context, Writer, full-chain and canonical/approval-store writes at zero. M6.3R.3 is proposed-plan-only and requires a separate approval.

## Superseded By R.2 Oracle / Selection Repair

The repair is recorded in `199_p38_point01_m6_3r_2_oracle_diversity_neighbor_rerank_repair.md`. It removes expected outcomes from evaluator input, adds a separate corpus-bound oracle artifact, directional neighbor coordinates, post-filter first-pass/fill-pass diversity and a rerank-derived Gate set. R.2 remains pending a new total-reviewer audit; this entry does not claim M6.3 or M6 completion.
