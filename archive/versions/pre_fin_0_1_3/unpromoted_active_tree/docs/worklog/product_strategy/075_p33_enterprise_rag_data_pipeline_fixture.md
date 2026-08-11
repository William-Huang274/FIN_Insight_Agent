# P33-1.1 Enterprise RAG / Data Pipeline Fixture

Date: 2026-07-05

## Prompt

The user approved starting the P33 sequence with only one subagent. The first P33 task is to close out the `enterprise_rag_data_pipeline` deferred contract before moving to sandbox/resource, capital-market, Workbench surface, and research-to-quant fixtures.

## Decision

Treat this as a no-paid deterministic fixture, not a full-chain or model-quality test. The correct root-cause-first path is to reuse the existing P14 data ingestion/retrieval control plane and prove the stricter P33 L3 contract:

- promoted evidence rows must trace to raw source, parser execution, parsed object, retrieval index, and authority;
- parser failure must be typed as `parser_gap`, not `public_source_absent`;
- Milvus/vector hit remains recall support and cannot override exact-first source authority.

One read-only subagent audited reusable anchors and confirmed P14/RD1/RD5/S3 are the right foundations. The subagent did not edit files or run tests.

## Work Completed

- Added `src/sec_agent/p33_enterprise_rag_data_pipeline_fixture.py`.
- Added `scripts/engineering/run_p33_enterprise_rag_data_pipeline_fixture.py`.
- Added `tests/test_p33_enterprise_rag_data_pipeline_fixture.py`.
- Generated `data/manifests/p33_enterprise_rag_data_pipeline_fixture_v0_1.json`.
- Generated `docs/internal/vnext_20260610/p33_enterprise_rag_data_pipeline_fixture_report.zh-CN.md`.
- Updated `scripts/engineering/validate_p32_registry_promotion.py` so active registry promotion can cite P33 per-contract L4 fixture manifests, not only the original P32 AI/Semis fixture.
- Updated `tests/test_p32_registry_promotion_validation.py`.
- Updated `docs/project_os/p32_active_registry_promotion_ledger.jsonl`: `l3_enterprise_rag_data_pipeline_contract_v0_1` is now `active_registry_ready_runtime_alignment_only`.
- Updated P33 source docs, Project OS context/capability ledgers, and indexes.

## Result

The P33-1.1 fixture passed:

- `8` promoted evidence rows checked.
- `8/8` rows have complete required fields and complete lineage.
- Parser failure is typed as `parser_gap` with `public_source_absent=false`.
- `5` index refresh rows have visible refresh status and complete lineage.
- `5` quality probes are visible and pass.
- Milvus/vector boundary is explicit: semantic recall only, not exact authority.

## Validation

Commands run:

```powershell
python -m pytest tests/test_p33_enterprise_rag_data_pipeline_fixture.py -q
python scripts/engineering/run_p33_enterprise_rag_data_pipeline_fixture.py
python scripts/engineering/validate_p32_registry_promotion.py --output data/manifests/p32_registry_promotion_validation_v0_1.json
python -m pytest tests/test_p32_registry_promotion_validation.py tests/test_p33_enterprise_rag_data_pipeline_fixture.py -q
```

Results:

- P33 fixture tests: `4 passed`.
- Official P33 fixture manifest/report generation: `status=pass`.
- P32 promotion validator: `status=pass`, `active_registry_ready_count=11`, `deferred_count=4`, `error_count=0`.
- Combined targeted tests: `8 passed`.

No paid LLM, no full-chain, and no broad case run was executed.

## Boundary

This proves runtime alignment for the enterprise RAG/data pipeline contract only. It does not prove broad crawler coverage, production p95/p99, paid-model memo quality, or that every live graph node already consumes the P14 strategy pack.

## Next Step

Proceed to `P33-1.2 sandbox_resource_scheduler` with the same no-paid deterministic fixture discipline.
