from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.api.v1.research_evidence_packs import (
    ResearchEvidencePackResponse,
)
from apps.workbench.backend.api.v1.research_retrieval import (
    ResearchRetrievalResponse,
)
from apps.workbench.backend.api.v1.research_workspace import (
    ResearchWorkspaceEvidenceResponse,
)
from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
    ResearchEvidencePackServiceError,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from apps.workbench.backend.application.research_workspace_service import (
    ResearchWorkspacePrincipal,
    ResearchWorkspaceService,
)
from retrieval.artifact_spine import (
    ArtifactSpineError,
    canonical_json_digest,
    load_artifact_spine_policy,
)
from retrieval.vertical_slice import (
    compile_candidate_decision_ledger,
    load_s1_vs1_vertical_slice_result,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths
from sec_agent.runtime_resource_registry import (
    read_registered_runtime_json,
    resolve_registered_runtime_resource,
)


REQUEST_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs1_dell_pricing_mix_request_v1_0.json"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def runtime_services():
    paths = resolve_runtime_paths(ROOT)
    retrieval = ResearchRetrievalService.from_runtime_paths(ROOT, paths)
    packs = ResearchEvidencePackService.from_runtime_paths(ROOT, paths)
    workspace = ResearchWorkspaceService.from_runtime_paths(ROOT, packs)
    return retrieval, packs, workspace


def _retrieval_principal() -> ResearchRetrievalPrincipal:
    return ResearchRetrievalPrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )


def _pack_principal() -> ResearchEvidencePackPrincipal:
    return ResearchEvidencePackPrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )


def _workspace_principal() -> ResearchWorkspacePrincipal:
    return ResearchWorkspacePrincipal(
        mode="current",
        permissions=frozenset({"current_product:read"}),
    )


def test_vs1_formal_result_covers_the_full_canonical_artifact_spine() -> None:
    policy = load_artifact_spine_policy(
        resolve_registered_runtime_resource(
            ROOT, "application.config.current_s1_artifact_spine_policy"
        )
    )
    raw = read_registered_runtime_json(
        ROOT, "application.result.current_s1_vs1_vertical_slice"
    )
    result = load_s1_vs1_vertical_slice_result(raw, policy=policy)
    types = Counter(row["artifact_type"] for row in result["envelopes"])

    assert len(result["envelopes"]) == 55
    assert types == {
        "source_route_decision": 11,
        "raw_source_capture": 11,
        "parsed_document": 11,
        "financial_evidence_object": 11,
        "object_manifest": 1,
        "index_snapshot": 1,
        "evidence_request": 1,
        "query_facet_plan": 1,
        "candidate_set": 1,
        "candidate_ranking": 1,
        "candidate_decision": 1,
        "evidence_coverage_state": 1,
        "evidence_pack_readiness": 1,
        "workbench_projection": 1,
        "frozen_consumer_probe": 1,
    }
    assert result["stage_acceptance"] == {
        "component_engineering_pass": True,
        "vertical_slice_integrated": True,
        "S1_qualified_stable": False,
        "complete_product_chain_authorized": False,
    }


def test_vs1_exposes_business_reality_without_promoting_rank_or_false_gap() -> None:
    result = read_registered_runtime_json(
        ROOT, "application.result.current_s1_vs1_vertical_slice"
    )
    case = result["cases"]["DELL"]
    ledger = case["candidate_decision_ledger"]
    coverage = case["coverage_state"]
    readiness = case["readiness"]

    assert ledger["decision_counts"] == {
        "accepted": 2,
        "rejected": 0,
        "unjudged": 0,
        "needs_review": 4,
    }
    assert {row["rank"] for row in ledger["decisions"] if row["decision_state"] == "accepted"} == {5, 6}
    assert all(
        row["candidate_text_promoted"] is False
        for row in ledger["decisions"]
    )
    assert len(coverage["reviewed_evidence_not_recalled_digests"]) == 2
    assert len(coverage["gap_eligibility_receipts"]) == 3
    assert all(
        receipt["eligible_as_true_public_information_gap"] is False
        and receipt["disposition"] == "supplement_route_not_yet_executed"
        for receipt in coverage["gap_eligibility_receipts"]
    )
    assert readiness["checks"]["capture_bound_promotion_lineage_visible"] is True
    assert readiness["readiness_state"] == (
        "ready_for_bounded_research_not_complete_conclusion"
    )


def test_candidate_permutation_is_decision_stable_and_future_mutation_fails_closed(
    runtime_services,
) -> None:
    retrieval, packs, _workspace = runtime_services
    request_result = retrieval.execute_request(
        "DELL", _read(REQUEST_PATH), _retrieval_principal()
    )
    pack = packs.get_case("DELL", _pack_principal())
    baseline = compile_candidate_decision_ledger(
        request_result=request_result,
        evidence_pack=pack,
        recorded_at="2026-08-17",
    )

    permuted_request = deepcopy(request_result)
    permuted_request["lanes"][0]["candidates"].reverse()
    permuted = compile_candidate_decision_ledger(
        request_result=permuted_request,
        evidence_pack=pack,
        recorded_at="2026-08-17",
    )
    baseline_by_source = {
        row["source_record_id"]: (
            row["decision_state"], row["accepted_evidence_item_digests"]
        )
        for row in baseline["decisions"]
    }
    permuted_by_source = {
        row["source_record_id"]: (
            row["decision_state"], row["accepted_evidence_item_digests"]
        )
        for row in permuted["decisions"]
    }
    assert permuted_by_source == baseline_by_source

    future_request = deepcopy(request_result)
    accepted_source = next(
        row["source_record_id"]
        for row in baseline["decisions"]
        if row["decision_state"] == "accepted"
    )
    future_candidate = next(
        row
        for row in future_request["lanes"][0]["candidates"]
        if row["source_record_id"] == accepted_source
    )
    future_candidate["publication_date"] = "2026-08-07"
    future = compile_candidate_decision_ledger(
        request_result=future_request,
        evidence_pack=pack,
        recorded_at="2026-08-17",
    )
    future_decision = next(
        row for row in future["decisions"] if row["source_record_id"] == accepted_source
    )
    assert future_decision["decision_state"] == "rejected"
    assert future_decision["reason_codes"] == ["candidate_after_research_as_of"]


def test_cross_case_artifact_scope_mutation_fails_closed() -> None:
    policy = load_artifact_spine_policy(
        resolve_registered_runtime_resource(
            ROOT, "application.config.current_s1_artifact_spine_policy"
        )
    )
    mutated = deepcopy(
        read_registered_runtime_json(
            ROOT, "application.result.current_s1_vs1_vertical_slice"
        )
    )
    request_envelope = next(
        row
        for row in mutated["envelopes"]
        if row["artifact_type"] == "evidence_request"
    )
    request_envelope["scope"]["case_key"] = "MU"
    request_envelope["scope"]["subject_ticker"] = "MU"
    mutated["result_digest"] = canonical_json_digest(
        {key: value for key, value in mutated.items() if key != "result_digest"}
    )

    with pytest.raises(ArtifactSpineError, match="artifact_chain_case_scope_drift"):
        load_s1_vs1_vertical_slice_result(mutated, policy=policy)


def test_pack_retrieval_and_workbench_consume_the_same_canonical_lineage(
    runtime_services,
) -> None:
    retrieval, packs, workspace = runtime_services
    retrieval_view = retrieval.get_case("DELL", _retrieval_principal())
    pack_view = packs.get_case("DELL", _pack_principal())
    case_id = next(
        row["case_id"]
        for row in workspace.list_cases(_workspace_principal())["items"]
        if row["case_key"] == "DELL"
    )
    workspace_view = workspace.get_evidence(case_id, _workspace_principal())

    assert retrieval_view["canonical_spine"] == pack_view["canonical_spine"]
    assert workspace_view["canonical_spine"] == pack_view["canonical_spine"]
    assert pack_view["canonical_spine"]["pack_binding"] == {
        "case_key": "DELL",
        "artifact_digest": pack_view["artifact_digest"],
        "pack_payload_digest": pack_view["pack_payload_digest"],
    }
    assert pack_view["canonical_spine"]["status"] == (
        "canonical_s1_lineage_with_product_evidence_successor"
    )
    assert pack_view["canonical_spine"]["evidence_successor"][
        "complete_s1_qualified"
    ] is False
    assert pack_view["canonical_spine"]["historical_vertical_lineage"][
        "not_current_pack_producer"
    ] is True
    assert len(pack_view["evidence_items"]) == 29
    assert len(pack_view["residual_gaps"]) == 14
    ResearchRetrievalResponse.model_validate(retrieval_view)
    ResearchEvidencePackResponse.model_validate(pack_view)
    ResearchWorkspaceEvidenceResponse.model_validate(workspace_view)


def test_pack_binding_drift_is_rejected_at_the_consumer_seam(runtime_services) -> None:
    _retrieval, packs, _workspace = runtime_services
    original = packs._s1_vertical_slice
    mutated = deepcopy(original)
    mutated["cases"]["DELL"]["workbench_projection"]["pack_binding"][
        "artifact_digest"
    ] = "0" * 64
    packs._s1_vertical_slice = mutated

    try:
        with pytest.raises(
            ResearchEvidencePackServiceError,
            match="current_research_evidence_historical_lineage_invalid",
        ):
            packs.get_case("DELL", _pack_principal())
    finally:
        packs._s1_vertical_slice = original


def test_current_product_pack_artifact_drift_fails_closed(runtime_services) -> None:
    _retrieval, packs, _workspace = runtime_services
    original = packs._result
    mutated = deepcopy(original)
    mutated["pack_artifacts"]["DELL"]["digest"] = "f" * 64
    mutated["result_digest"] = canonical_json_digest(
        {key: value for key, value in mutated.items() if key != "result_digest"}
    )
    packs._result = mutated

    try:
        with pytest.raises(
            ResearchEvidencePackServiceError,
            match="current_research_evidence_pack_object_identity_drift",
        ):
            packs.get_case("DELL", _pack_principal())
    finally:
        packs._result = original


def test_non_vs1_cases_receive_capture_bound_lineage_without_false_qualification(
    runtime_services,
) -> None:
    retrieval, packs, _workspace = runtime_services
    for case_key in ("MU", "NVDA"):
        retrieval_spine = retrieval.get_case(
            case_key, _retrieval_principal()
        )["canonical_spine"]
        pack_spine = packs.get_case(case_key, _pack_principal())["canonical_spine"]
        assert retrieval_spine == pack_spine
        assert pack_spine["case_key"] == case_key
        assert pack_spine["pack_binding"]["case_key"] == case_key
        assert pack_spine["status"] == (
            "canonical_s1_lineage_with_product_evidence_successor"
        )
        assert pack_spine["hard_boundaries"][
            "historical_vs4_summary_not_relabelled_as_successor"
        ] is True
        assert pack_spine["hard_boundaries"]["S1_qualified_stable"] is False
        assert pack_spine["evidence_successor"]["numeric_fact_authorized"] is False
        assert pack_spine["evidence_successor"]["complete_s1_qualified"] is False
