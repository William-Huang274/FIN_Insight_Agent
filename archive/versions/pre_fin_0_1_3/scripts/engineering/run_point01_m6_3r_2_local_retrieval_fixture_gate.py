"""Run the M6.3R.2 sanitized immutable local-retrieval fixture matrix.

This runner constructs only reviewed synthetic metadata.  It never imports or
opens any local retriever, graph, SQL database, source document, tool client or
canonical store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.evidence_request import EvidenceRequest  # noqa: E402
from sec_agent.canonical_runtime.local_retrieval_fixture import (  # noqa: E402
    FixtureNeighborReference,
    LocalRetrievalFixtureAdmissionPolicy,
    LocalRetrievalFixtureCorpus,
    LocalRetrievalFixtureEntry,
    LocalRetrievalFixtureHarness,
    SqlFixturePolicyPin,
)
from sec_agent.canonical_runtime.local_retrieval_fixture_oracle import (  # noqa: E402
    FixtureOracleRecord,
    LocalRetrievalFixtureOracle,
)
from sec_agent.canonical_runtime.local_retrieval_skeleton import (  # noqa: E402
    ExactValueSqlBindingCompiler,
    ExactValueSqlBindingPolicy,
    LegacyEvidenceRequestTopKAdapter,
    LegacyTopKMappingRegistry,
    LocalAdapterSnapshot,
    LocalRecallCandidate,
    LocalRetrievalQuery,
    M6_1_EVIDENCE_REQUEST_POLICY_REF,
    ToolInvocationReceiptReference,
    ToolSelectionPlanScopeReference,
    TopKPolicyResolver,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


FIXTURE_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3r_2_fixture_admission_policy_v1_0.json"
SQL_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3r_1_exact_value_sql_binding_policy_v1_0.json"
TOPK_REGISTRY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3r_1_legacy_topk_mapping_registry_v1_0.json"
DEFAULT_CORPUS_OUTPUT = ROOT / "data/manifests/point01_m6_3r_2_sanitized_local_retrieval_fixture_corpus_v1_0.json"
DEFAULT_ORACLE_OUTPUT = ROOT / "data/manifests/point01_m6_3r_2_local_retrieval_fixture_oracle_v1_0.json"
DEFAULT_PACKAGE_OUTPUT = ROOT / "data/manifests/point01_m6_3r_2_local_retrieval_fixture_package_manifest_v1_0.json"
DEFAULT_RESULT_OUTPUT = ROOT / "data/manifests/point01_m6_3r_2_local_retrieval_fixture_gate_result_v1_0.json"

PACKAGE_INPUT_PATHS = (
    "src/sec_agent/canonical_runtime/local_retrieval_skeleton.py",
    "src/sec_agent/canonical_runtime/local_retrieval_fixture.py",
    "src/sec_agent/canonical_runtime/local_retrieval_fixture_oracle.py",
    "src/sec_agent/canonical_runtime/schema_export.py",
    "scripts/engineering/run_point01_m6_3r_2_local_retrieval_fixture_gate.py",
    "tests/contract/test_point01_m6_3r_2_local_retrieval_fixture.py",
    "configs/engineering_handoff/point01_m6_3r_2_fixture_admission_policy_v1_0.json",
    "configs/engineering_handoff/point01_m6_3r_2_fixture_api_owner_mapping_v1_0.json",
    "configs/engineering_handoff/point01_m6_3r_2_fixture_test_manifest_v1_0.json",
)


def _digest(label: str) -> str:
    return canonical_digest({"m6_3r_2_fixture": label})


def _request(*, role: str, source_policy: str | None = None) -> EvidenceRequest:
    profile = {
        "issuer": {
            "accepted_evidence_role": "numeric_fact",
            "evidence_domain": "issuer_disclosure",
            "source_policy": source_policy or "issuer_first",
            "preferred_routes": ("issuer_disclosure_metadata_route",),
            "top_k": 3,
            "candidate_limit": 12,
            "metric_intent": ("revenue",),
            "unit": "USD_millions",
        },
        "relationship": {
            "accepted_evidence_role": "context",
            "evidence_domain": "relationship_graph",
            "source_policy": "relationship_graph_only",
            "preferred_routes": ("relationship_graph_metadata_route",),
            "top_k": 5,
            "candidate_limit": 12,
            "metric_intent": (),
            "unit": None,
        },
        "commercial": {
            "accepted_evidence_role": "gap_evidence",
            "evidence_domain": "commercial_data_boundary",
            "source_policy": "commercial_gap",
            "preferred_routes": ("commercial_gap_record_route",),
            "top_k": 1,
            "candidate_limit": 1,
            "metric_intent": (),
            "unit": None,
        },
    }[role]
    payload = {
        "tenant_id": "tenant-m6-3r-2-fixture",
        "project_id": "project-m6-3r-2-fixture",
        "case_id": "case-m6-3r-2-fixture",
        "decision_surface_id": "surface-m6-3r-2-fixture",
        "decision_surface_contract_version_id": "surface-m6-3r-2-fixture:v1",
        "cell_id": f"cell-{role}",
        "cell_version_id": f"cell-{role}:v1",
        "evidence_slot_id": f"slot-{role}",
        "evidence_slot_version_id": f"slot-{role}:v1",
        "requester_role": "research_lead",
        "accepted_evidence_role": profile["accepted_evidence_role"],
        "evidence_domain": profile["evidence_domain"],
        "target_entities": ("NVDA",),
        "target_periods": ("2025-01-26",),
        "metric_intent": profile["metric_intent"],
        "product_intent": (),
        "granularity": "cell_slot",
        "unit": profile["unit"],
        "source_policy": profile["source_policy"],
        "metadata_binding_requirements": ("document_id", "document_version", "section_or_table_ref", "source_authority"),
        "numeric_binding_requirements": ("row_label", "unit", "period", "source_coordinate") if role == "issuer" else (),
        "acceptable_proxy": (),
        "forbidden_substitutions": ("relationship_graph_only",) if role == "issuer" else ("issuer_metric_substitute",),
        "preferred_routes": profile["preferred_routes"],
        "fallback_routes": (),
        "topk_policy": {"top_k": profile["top_k"], "candidate_limit": profile["candidate_limit"]},
        "budget": {"tool_call_limit": 0, "elapsed_seconds_limit": 30},
        "stop_condition": "sanitized_fixture_stop",
        "required": True,
        "compiler_policy_ref": M6_1_EVIDENCE_REQUEST_POLICY_REF,
        "compiled_from_refs": ("contract:v1", "cell:v1", "slot:v1", M6_1_EVIDENCE_REQUEST_POLICY_REF),
        "planning_authority": "shadow",
        "execution_admission": "not_admitted",
    }
    digest = canonical_digest(payload)
    return EvidenceRequest(request_id=f"evidence_request_{digest[:20]}", request_digest=digest, **payload)


def _registry() -> LegacyTopKMappingRegistry:
    return LegacyTopKMappingRegistry.model_validate(json.loads(TOPK_REGISTRY_PATH.read_text(encoding="utf-8")))


def _fixture_policy() -> LocalRetrievalFixtureAdmissionPolicy:
    return LocalRetrievalFixtureAdmissionPolicy.model_validate(json.loads(FIXTURE_POLICY_PATH.read_text(encoding="utf-8")))


def _sql_policy() -> ExactValueSqlBindingPolicy:
    return ExactValueSqlBindingPolicy.model_validate(json.loads(SQL_POLICY_PATH.read_text(encoding="utf-8")))


def _query(*, adapter_kind: str, source_type: str, role: str = "issuer", source_policy: str | None = None) -> LocalRetrievalQuery:
    request = _request(role=role, source_policy=source_policy)
    registry = _registry()
    topk_request = LegacyEvidenceRequestTopKAdapter().map(request, registry=registry)
    topk = TopKPolicyResolver().resolve(request=topk_request, registry=registry)
    snapshot = LocalAdapterSnapshot(
        snapshot_id=f"fixture-snapshot-{adapter_kind}-{role}:v1",
        snapshot_registry_ref="point01-m6-3r-2-fixture-snapshot-registry",
        snapshot_registry_version="v1",
        snapshot_digest=_digest(f"snapshot:{adapter_kind}:{role}:{source_policy or 'default'}"),
        adapter_id=f"fixture-adapter-{adapter_kind}-{role}",
        adapter_kind=adapter_kind,  # type: ignore[arg-type]
        source_type=source_type,
    )
    if adapter_kind != "exact_value_sql":
        return LocalRetrievalQuery.create(
            tool_selection_plan_id=f"fixture-plan-{adapter_kind}-{role}:v1",
            tool_selection_plan_digest=_digest(f"plan:{adapter_kind}:{role}"),
            adapter_snapshot=snapshot,
            topk=topk,
        )
    plan = ToolSelectionPlanScopeReference(
        tool_selection_plan_id="fixture-plan-exact-value-sql:v1",
        tool_selection_plan_digest=_digest("plan:exact-value-sql"),
        plan_policy_ref="point01-m6-2-tool-selection-plan-policy",
        plan_policy_version="v1",
        plan_policy_digest=_digest("tool-selection-plan-policy"),
        selected_route_id="issuer_disclosure_metadata_route",
    )
    bound = ExactValueSqlBindingCompiler().compile(
        evidence_request=request,
        tool_selection_plan=plan,
        adapter_snapshot=snapshot,
        binding_policy=_sql_policy(),
    )
    if bound.status != "resolved" or bound.execution_scope is None:
        raise RuntimeError("fixture_exact_value_sql_scope_must_resolve_against_pinned_policy")
    scope = bound.execution_scope
    receipt = ToolInvocationReceiptReference(
        receipt_id="fixture-tool-receipt:not-invoked:v1",
        receipt_version=1,
        receipt_digest=_digest("tool-receipt:not-invoked"),
        request_id=request.request_id,
        request_digest=request.request_digest,
        tool_selection_plan_id=plan.tool_selection_plan_id,
        tool_selection_plan_digest=plan.tool_selection_plan_digest,
        adapter_snapshot_id=snapshot.snapshot_id,
        adapter_snapshot_digest=snapshot.snapshot_digest,
        execution_scope_id=scope.execution_scope_id,
        execution_scope_digest=scope.execution_scope_digest,
        exact_filter_selector_contract_digest=scope.exact_filter_selector_contract_digest,
    )
    return LocalRetrievalQuery.create(
        tool_selection_plan_id=plan.tool_selection_plan_id,
        tool_selection_plan_digest=plan.tool_selection_plan_digest,
        adapter_snapshot=snapshot,
        topk=topk,
        exact_value_execution_scope=scope,
        tool_invocation_receipt_ref=receipt,
    )


def _candidate(
    query: LocalRetrievalQuery,
    *,
    candidate_id: str,
    candidate_kind: str = "top_k_seed",
    metadata_rank: int,
    source_family: str = "sec",
    source_name: str = "source-a",
    content_name: str | None = None,
    document_id: str = "sanitized-nvda-2025",
    section_or_table_ref: str = "section:seed",
    previous_ref: str | None = None,
    next_ref: str | None = None,
    parent_section_ref: str | None = None,
    page_ref: str | None = None,
    row_ref: str | None = None,
    previous_page_ref: str | None = None,
    next_page_ref: str | None = None,
    previous_row_ref: str | None = None,
    next_row_ref: str | None = None,
    authority_rank: int = 100,
    recall_score: float = 1.0,
    **overrides: object,
) -> LocalRecallCandidate:
    snapshot = query.adapter_snapshot
    payload: dict[str, object] = {
        "candidate_id": candidate_id,
        "adapter_id": snapshot.adapter_id,
        "adapter_kind": snapshot.adapter_kind,
        "adapter_snapshot_id": snapshot.snapshot_id,
        "adapter_snapshot_digest": snapshot.snapshot_digest,
        "source_type": query.source_type,
        "evidence_role": query.evidence_role,
        "document_id": document_id,
        "document_version": "sanitized:v1",
        "source_artifact_ref": f"sanitized-source:{source_name}",
        "source_artifact_digest": _digest(f"source:{source_name}"),
        "parser_artifact_ref": "sanitized-parser:metadata-only:v1",
        "parser_artifact_digest": _digest("parser:metadata-only"),
        "index_or_graph_coordinate": f"fixture-coordinate:{candidate_id}",
        "entity_ref": "NVDA",
        "period_ref": "2025-01-26",
        "form_type": "10-K",
        "source_tier": "primary_sec",
        "source_policy_ref": query.source_policy_ref,
        "route_id": query.selected_route_id,
        "source_role": query.source_role,
        "source_authority_rank": authority_rank,
        "source_family": source_family,
        "candidate_kind": candidate_kind,
        "section_or_table_ref": section_or_table_ref,
        "page_ref": page_ref,
        "row_ref": row_ref,
        "parent_section_ref": parent_section_ref,
        "previous_ref": previous_ref,
        "next_ref": next_ref,
        "previous_page_ref": previous_page_ref,
        "next_page_ref": next_page_ref,
        "previous_row_ref": previous_row_ref,
        "next_row_ref": next_row_ref,
        "content_ref": f"sanitized-content:{content_name or candidate_id}",
        "content_digest": _digest(f"content:{content_name or candidate_id}"),
        "recall_score": recall_score,
        "metadata_rank": metadata_rank,
    }
    if snapshot.adapter_kind == "exact_value_sql":
        filters = query.exact_value_filters
        assert filters is not None
        payload.update(
            {
                "metric_ref": filters.metric_ref,
                "row_selector_ref": filters.row_selector_ref,
                "unit_ref": filters.unit_ref,
                "scale_ref": filters.scale_ref,
                "form_type": filters.form_type,
                "source_tier": filters.source_tier,
            }
        )
    payload.update(overrides)
    return LocalRecallCandidate.model_validate(payload)


def _entry(
    *,
    fixture_id: str,
    fixture_kind: str,
    query: LocalRetrievalQuery,
    candidates: tuple[LocalRecallCandidate, ...] = (),
    required_candidate_kinds: tuple[str, ...] = (),
    neighbor_references: tuple[FixtureNeighborReference, ...] = (),
    sql_policy_pin: SqlFixturePolicyPin | None = None,
) -> LocalRetrievalFixtureEntry:
    return LocalRetrievalFixtureEntry(
        fixture_id=fixture_id,
        fixture_kind=fixture_kind,  # type: ignore[arg-type]
        request_id=query.request_id,
        request_digest=query.request_digest,
        topk_policy_audit_digest=query.topk_audit.audit_digest,
        topk_registry_digest=query.topk_audit.request.policy_registry_digest,
        adapter_snapshot_id=query.adapter_snapshot.snapshot_id,
        adapter_snapshot_digest=query.adapter_snapshot.snapshot_digest,
        query=query,
        candidates=candidates,
        required_candidate_kinds=required_candidate_kinds,
        neighbor_references=neighbor_references,
        sql_policy_pin=sql_policy_pin,
    )


def build_corpus() -> LocalRetrievalFixtureCorpus:
    policy = _fixture_policy()
    bm25_query = _query(adapter_kind="bm25", source_type="local_bm25")
    bm25_seed = _candidate(
        bm25_query,
        candidate_id="bm25-narrative-seed",
        metadata_rank=0,
        next_ref="section:narrative-next",
        section_or_table_ref="section:narrative-seed",
        source_name="bm25-narrative",
    )
    bm25_neighbor = _candidate(
        bm25_query,
        candidate_id="bm25-narrative-neighbor",
        candidate_kind="neighbor_section",
        metadata_rank=1,
        section_or_table_ref="section:narrative-next",
        source_name="bm25-narrative",
    )
    bm25_second_family = _candidate(
        bm25_query,
        candidate_id="bm25-narrative-second-source-family",
        metadata_rank=2,
        source_family="issuer_ir",
        source_name="bm25-issuer-ir",
        authority_rank=90,
        recall_score=0.95,
    )
    bm25_duplicate = _candidate(
        bm25_query,
        candidate_id="bm25-narrative-duplicate-content",
        metadata_rank=3,
        content_name="bm25-narrative-seed",
        source_name="bm25-narrative-duplicate",
    )
    bm25_source_cap = _candidate(
        bm25_query,
        candidate_id="bm25-narrative-source-artifact-cap",
        metadata_rank=4,
        source_name="bm25-narrative",
    )
    bm25_wrong_entity = _candidate(
        bm25_query,
        candidate_id="bm25-narrative-wrong-entity",
        metadata_rank=5,
        source_name="bm25-wrong-entity",
        entity_ref="WRONG",
    )

    object_query = _query(adapter_kind="object_bm25", source_type="local_bm25")
    object_seed = _candidate(
        object_query,
        candidate_id="object-table-seed",
        metadata_rank=0,
        section_or_table_ref="table:income-statement",
        source_name="object-table",
    )
    object_table = _candidate(
        object_query,
        candidate_id="object-table-context",
        candidate_kind="table_context",
        metadata_rank=1,
        section_or_table_ref="table:income-statement",
        source_name="object-table",
    )
    object_page_seed = _candidate(
        object_query,
        candidate_id="object-page-seed",
        metadata_rank=2,
        section_or_table_ref="section:page-seed",
        page_ref="page:12",
        next_page_ref="page:12",
        source_name="object-page",
    )
    object_page_neighbor = _candidate(
        object_query,
        candidate_id="object-page-neighbor",
        candidate_kind="neighbor_section",
        metadata_rank=3,
        section_or_table_ref="page:12",
        source_name="object-page",
    )
    object_row_seed = _candidate(
        object_query,
        candidate_id="object-row-seed",
        metadata_rank=4,
        section_or_table_ref="section:row-seed",
        row_ref="row:4",
        next_row_ref="row:4",
        source_name="object-row",
    )
    object_row_neighbor = _candidate(
        object_query,
        candidate_id="object-row-neighbor",
        candidate_kind="neighbor_section",
        metadata_rank=5,
        section_or_table_ref="row:4",
        source_name="object-row",
    )

    graph_query = _query(adapter_kind="relationship_graph", source_type="relationship_graph", role="relationship")
    graph_candidate = _candidate(
        graph_query,
        candidate_id="graph-relationship-seed",
        metadata_rank=0,
        source_family="relationship_graph",
        source_name="relationship-graph",
        section_or_table_ref="relationship:customer-supplier",
    )

    sql_query = _query(adapter_kind="exact_value_sql", source_type="exact_value_sql", source_policy="official_first")
    sql_seed = _candidate(
        sql_query,
        candidate_id="sql-revenue-row-seed",
        metadata_rank=0,
        section_or_table_ref="table:income-statement",
        next_ref="table:income-statement",
        source_name="sql-revenue-row",
    )
    sql_table = _candidate(
        sql_query,
        candidate_id="sql-revenue-table-context",
        candidate_kind="table_context",
        metadata_rank=1,
        section_or_table_ref="table:income-statement",
        source_name="sql-revenue-row",
    )
    alternate_pin = policy.sql_fixture_policy_pin.model_copy(update={"policy_ref": "self-signed-unapproved-fixture-policy", "policy_canonical_digest": _digest("self-signed-policy")})

    entries = (
        _entry(
            fixture_id="fixture-bm25-narrative-positive",
            fixture_kind="bm25_narrative",
            query=bm25_query,
            candidates=(bm25_seed, bm25_neighbor, bm25_second_family, bm25_duplicate, bm25_source_cap, bm25_wrong_entity),
            required_candidate_kinds=("top_k_seed", "neighbor_section"),
            neighbor_references=(FixtureNeighborReference(seed_candidate_id=bm25_seed.candidate_id, neighbor_candidate_id=bm25_neighbor.candidate_id, relation="next_section", expected_coordinate_ref="section:narrative-next"),),
        ),
        _entry(
            fixture_id="fixture-object-bm25-table-positive",
            fixture_kind="object_bm25_document_table",
            query=object_query,
            candidates=(object_seed, object_table),
            required_candidate_kinds=("top_k_seed", "table_context"),
            neighbor_references=(FixtureNeighborReference(seed_candidate_id=object_seed.candidate_id, neighbor_candidate_id=object_table.candidate_id, relation="table", expected_coordinate_ref="table:income-statement"),),
        ),
        _entry(
            fixture_id="fixture-object-bm25-page-row-positive",
            fixture_kind="object_bm25_document_table",
            query=object_query,
            candidates=(object_page_seed, object_page_neighbor, object_row_seed, object_row_neighbor),
            required_candidate_kinds=("top_k_seed", "neighbor_section"),
            neighbor_references=(
                FixtureNeighborReference(seed_candidate_id=object_page_seed.candidate_id, neighbor_candidate_id=object_page_neighbor.candidate_id, relation="next_page", expected_coordinate_ref="page:12"),
                FixtureNeighborReference(seed_candidate_id=object_row_seed.candidate_id, neighbor_candidate_id=object_row_neighbor.candidate_id, relation="next_row", expected_coordinate_ref="row:4"),
            ),
        ),
        _entry(
            fixture_id="fixture-relationship-graph-positive",
            fixture_kind="relationship_graph",
            query=graph_query,
            candidates=(graph_candidate,),
            required_candidate_kinds=("top_k_seed",),
        ),
        _entry(
            fixture_id="fixture-exact-value-sql-row-positive",
            fixture_kind="exact_value_sql_row",
            query=sql_query,
            candidates=(sql_seed, sql_table),
            required_candidate_kinds=("top_k_seed", "table_context"),
            neighbor_references=(FixtureNeighborReference(seed_candidate_id=sql_seed.candidate_id, neighbor_candidate_id=sql_table.candidate_id, relation="table", expected_coordinate_ref="table:income-statement"),),
            sql_policy_pin=policy.sql_fixture_policy_pin,
        ),
        _entry(
            fixture_id="fixture-typed-empty-exhaustion",
            fixture_kind="typed_exhaustion",
            query=bm25_query,
        ),
        _entry(
            fixture_id="fixture-table-context-missing",
            fixture_kind="typed_exhaustion",
            query=object_query,
            candidates=(object_seed,),
            required_candidate_kinds=("top_k_seed", "table_context"),
        ),
        _entry(
            fixture_id="fixture-boundary-context-missing",
            fixture_kind="typed_exhaustion",
            query=graph_query,
            candidates=(graph_candidate,),
            required_candidate_kinds=("top_k_seed", "neighbor_section"),
        ),
        _entry(
            fixture_id="fixture-exact-value-sql-alternate-self-signed-policy",
            fixture_kind="exact_value_sql_row",
            query=sql_query,
            candidates=(sql_seed,),
            required_candidate_kinds=("top_k_seed",),
            sql_policy_pin=alternate_pin,
        ),
    )
    return LocalRetrievalFixtureCorpus.create(admission_policy=policy, entries=entries)


def build_oracle(corpus: LocalRetrievalFixtureCorpus) -> LocalRetrievalFixtureOracle:
    """Build the post-evaluation oracle independently from evaluator inputs."""

    records = (
        FixtureOracleRecord(fixture_id="fixture-bm25-narrative-positive", expected_status="accepted_fixture_projection", required_reason_codes=("fixture_projection_nonexecuting",)),
        FixtureOracleRecord(fixture_id="fixture-object-bm25-table-positive", expected_status="accepted_fixture_projection", required_reason_codes=("fixture_projection_nonexecuting",)),
        FixtureOracleRecord(fixture_id="fixture-object-bm25-page-row-positive", expected_status="accepted_fixture_projection", required_reason_codes=("fixture_projection_nonexecuting",)),
        FixtureOracleRecord(fixture_id="fixture-relationship-graph-positive", expected_status="accepted_fixture_projection", required_reason_codes=("fixture_projection_nonexecuting",)),
        FixtureOracleRecord(fixture_id="fixture-exact-value-sql-row-positive", expected_status="accepted_fixture_projection", required_reason_codes=("fixture_projection_nonexecuting",)),
        FixtureOracleRecord(fixture_id="fixture-typed-empty-exhaustion", expected_status="typed_exhaustion", required_reason_codes=("retrieval_exhausted_no_metadata_match",)),
        FixtureOracleRecord(fixture_id="fixture-table-context-missing", expected_status="typed_exhaustion", required_reason_codes=("table_context_missing",)),
        FixtureOracleRecord(fixture_id="fixture-boundary-context-missing", expected_status="typed_exhaustion", required_reason_codes=("boundary_context_missing",)),
        FixtureOracleRecord(fixture_id="fixture-exact-value-sql-alternate-self-signed-policy", expected_status="not_fixture_admitted", required_reason_codes=("exact_value_sql_policy_not_fixture_admitted",)),
    )
    return LocalRetrievalFixtureOracle.create(corpus=corpus, records=records)


def build_fixture_package_manifest(*, corpus: LocalRetrievalFixtureCorpus, oracle: LocalRetrievalFixtureOracle) -> dict[str, Any]:
    """Digest all reviewed R.2 contract inputs, never a runtime/source artifact."""

    file_sha256 = {
        relative_path: hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        for relative_path in PACKAGE_INPUT_PATHS
    }
    payload = {
        "package_version": "finsight_point01_m6_3r_2_fixture_package_v1_0",
        "execution_stage": "M6_3R_2_fixture_repaired_pending_total_reviewer_audit",
        "corpus_id": corpus.corpus_id,
        "corpus_digest": corpus.corpus_digest,
        "oracle_id": oracle.oracle_id,
        "oracle_digest": oracle.oracle_digest,
        "fixture_admission_policy_digest": corpus.admission_policy.policy_digest,
        "pinned_sql_policy_digest": corpus.admission_policy.sql_fixture_policy_pin.policy_canonical_digest,
        "input_file_sha256": file_sha256,
        "execution_admission": "not_admitted",
        "persistence_authorized": False,
        "promotion_authorized": False,
    }
    return {"package_digest": canonical_digest(payload), **payload}


def build_result() -> tuple[dict[str, Any], LocalRetrievalFixtureCorpus]:
    corpus = build_corpus()
    oracle = build_oracle(corpus)
    package_manifest = build_fixture_package_manifest(corpus=corpus, oracle=oracle)
    sql_policy = _sql_policy()
    raw_sha = hashlib.sha256(SQL_POLICY_PATH.read_bytes()).hexdigest()
    harness = LocalRetrievalFixtureHarness(
        admission_policy=corpus.admission_policy,
        pinned_sql_policy=sql_policy,
        pinned_sql_policy_raw_sha256=raw_sha,
    )
    evaluations = tuple(harness.evaluate(entry=entry) for entry in corpus.entries)
    commercial_request = _request(role="commercial")
    commercial_topk_request = LegacyEvidenceRequestTopKAdapter().map(commercial_request, registry=_registry())
    commercial_resolution = TopKPolicyResolver().resolve(request=commercial_topk_request, registry=_registry())
    oracle_checks = oracle.verify(corpus=corpus, evaluations=evaluations)
    accepted_evaluations = tuple(evaluation for evaluation in evaluations if evaluation.status == "accepted_fixture_projection")
    checks = {
        "sql_policy_pin_matches_exact_reviewed_artifact": corpus.admission_policy.sql_fixture_policy_pin.policy_canonical_digest == sql_policy.policy_digest and corpus.admission_policy.sql_fixture_policy_pin.policy_raw_sha256 == raw_sha,
        "alternate_self_signed_policy_is_not_fixture_admitted": next(evaluation for evaluation in evaluations if evaluation.fixture_id == "fixture-exact-value-sql-alternate-self-signed-policy").status == "not_fixture_admitted",
        "commercial_1_1_is_terminal_not_retrieval": commercial_resolution.resolution.status == "typed_commercial_gap" and commercial_resolution.resolution.terminal_reason == "commercial_gap_not_retrieval",
        "all_fixture_projections_non_authoritative": all(
            evaluation.execution_admission == "not_admitted" and not evaluation.persistence_authorized and not evaluation.promotion_authorized and not evaluation.writer_citable and not evaluation.domain_judgment_eligible
            for evaluation in evaluations
        ),
        "all_fixture_candidates_are_supplied_only": all(candidate.candidate_provenance == "fixture_supplied_not_retrieved" for entry in corpus.entries for candidate in entry.candidates),
        "source_family_diversity_selection_verified": all(
            not evaluation.diversity_decision.diversity_applicable
            or len({candidate.source_family for candidate in evaluation.candidate_bundle_projection.candidates}) >= 2  # type: ignore[union-attr]
            for evaluation in accepted_evaluations
            if evaluation.diversity_decision is not None
        ),
        "neighbor_relation_direction_binding_verified": all(
            outcome.status != "validated"
            or (
                outcome.seed_coordinate_ref == outcome.reference.expected_coordinate_ref
                and outcome.neighbor_coordinate_ref == outcome.reference.expected_coordinate_ref
                and outcome.lineage_match
            )
            for evaluation in evaluations
            for outcome in evaluation.neighbor_outcomes
        ),
        "rerank_to_gate_set_preserved": all(evaluation.rerank_to_gate_set_preserved for evaluation in accepted_evaluations),
    }
    checks.update(oracle_checks)
    zero_execution_counts = {
        "adapter_execution_count": 0,
        "network_request_count": 0,
        "external_tool_call_count": 0,
        "tool_invocation_count": 0,
        "model_call_count": 0,
        "provider_call_count": 0,
        "canonical_store_write_count": 0,
        "evidence_promotion_count": 0,
        "parser_numeric_execution_count": 0,
        "sourcehunter_attempt_count": 0,
    }
    entry_counts = Counter(entry.fixture_kind for entry in corpus.entries)
    status_counts = Counter(evaluation.status for evaluation in evaluations)
    adapter_counts = Counter(entry.query.adapter_snapshot.adapter_kind for entry in corpus.entries)
    candidate_kind_counts = Counter(candidate.candidate_kind for entry in corpus.entries for candidate in entry.candidates)
    result = {
        "result_version": "finsight_point01_m6_3r_2_local_retrieval_fixture_gate_result_v1_1",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "execution_stage": "M6_3R_2_fixture_repaired_pending_total_reviewer_audit",
        "corpus_id": corpus.corpus_id,
        "corpus_digest": corpus.corpus_digest,
        "oracle_id": oracle.oracle_id,
        "oracle_digest": oracle.oracle_digest,
        "fixture_package_digest": package_manifest["package_digest"],
        "fixture_package_manifest": package_manifest,
        "fixture_admission_policy_digest": corpus.admission_policy.policy_digest,
        "pinned_sql_policy": corpus.admission_policy.sql_fixture_policy_pin.model_dump(mode="json"),
        "evaluation_digests": {evaluation.fixture_id: evaluation.evaluation_digest for evaluation in evaluations},
        "matrix_coverage": {
            "entries_by_kind": dict(sorted(entry_counts.items())),
            "entries_by_adapter_kind": dict(sorted(adapter_counts.items())),
            "supplied_candidates_by_kind": dict(sorted(candidate_kind_counts.items())),
            "evaluations_by_status": dict(sorted(status_counts.items())),
            "positive_fixture_count": status_counts["accepted_fixture_projection"],
            "negative_fixture_count": status_counts["not_fixture_admitted"] + status_counts["typed_exhaustion"],
            "typed_exhaustion_fixture_count": status_counts["typed_exhaustion"],
            "adapter_kinds": sorted({entry.query.adapter_snapshot.adapter_kind for entry in corpus.entries}),
            "topk_profiles": sorted({entry.query.topk_audit.resolution.resolved_profile.profile_id for entry in corpus.entries if entry.query.topk_audit.resolution.resolved_profile is not None}),
            "topk_terminal_cases": {"commercial_1_1": commercial_resolution.resolution.status},
            "neighbor_relations": sorted({reference.relation for entry in corpus.entries for reference in entry.neighbor_references}),
            "typed_exhaustion_reasons": sorted({evaluation.reasons[0] for evaluation in evaluations if evaluation.status == "typed_exhaustion"}),
            "diversity_applicable_fixture_count": sum(
                1
                for evaluation in accepted_evaluations
                if evaluation.diversity_decision is not None and evaluation.diversity_decision.diversity_applicable
            ),
            "rerank_to_gate_set_preserved_fixture_count": sum(evaluation.rerank_to_gate_set_preserved for evaluation in accepted_evaluations),
        },
        "checks": checks,
        "zero_execution_counts": zero_execution_counts,
        "r3_proposed_plan_only": [
            "separately authorize injected read-only adapter access only after fixed snapshot/admission review",
            "bind any SQL execution to canonical plan/receipt registry resolution rather than R.1 self-contained policy objects",
            "retain no-promotion/non-citable firewall until later M6.6 authority calibration",
        ],
        "note": "All corpus rows are sanitized immutable metadata fixtures. No adapter/index/graph/SQL/source read, ToolInvocation, receipt registration, network/model/provider, parser/numeric, promotion, persistence, Context, Writer or full-chain execution occurred.",
    }
    return result, corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the non-executing Point01 M6.3R.2 fixture matrix.")
    parser.add_argument("--corpus-output", type=Path, default=DEFAULT_CORPUS_OUTPUT)
    parser.add_argument("--oracle-output", type=Path, default=DEFAULT_ORACLE_OUTPUT)
    parser.add_argument("--package-output", type=Path, default=DEFAULT_PACKAGE_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT_OUTPUT)
    args = parser.parse_args()
    result, corpus = build_result()
    oracle = build_oracle(corpus)
    package_manifest = build_fixture_package_manifest(corpus=corpus, oracle=oracle)
    corpus_output = args.corpus_output if args.corpus_output.is_absolute() else ROOT / args.corpus_output
    oracle_output = args.oracle_output if args.oracle_output.is_absolute() else ROOT / args.oracle_output
    package_output = args.package_output if args.package_output.is_absolute() else ROOT / args.package_output
    output = args.output if args.output.is_absolute() else ROOT / args.output
    corpus_output.parent.mkdir(parents=True, exist_ok=True)
    oracle_output.parent.mkdir(parents=True, exist_ok=True)
    package_output.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    corpus_output.write_text(json.dumps(corpus.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    oracle_output.write_text(json.dumps(oracle.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package_output.write_text(json.dumps(package_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "corpus_digest": corpus.corpus_digest, **result["zero_execution_counts"]}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
