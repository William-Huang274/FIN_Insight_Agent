from __future__ import annotations

from collections import deque
import hashlib
import json
from pathlib import Path

import pytest

from scripts.data_retrieval import (
    promote_s1_reviewed_public_pdf_to_current_runtime as r35_promotion,
)
from retrieval.contracts import (
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.evidence_role_v2 import evaluate_evidence_role as evaluate_legacy_role
from retrieval.hybrid_candidate_runtime import _legacy_shortlist_compatibility_lane
from retrieval.query_plan import canonical_digest
from retrieval.query_plan import compile_query_facet_plan_for_request
from retrieval.route_compiler import load_query_object_fact_route_policy


ROOT = Path(__file__).resolve().parents[1]


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _sha256(relative: str) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _jsonl_tail(relative: str, count: int) -> list[dict]:
    rows: deque[dict] = deque(maxlen=count)
    with (ROOT / relative).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return list(rows)


def test_r35_promotion_rejects_current_r38_before_any_write(monkeypatch) -> None:
    writes: list[str] = []
    monkeypatch.setattr(
        r35_promotion,
        "_write_json",
        lambda ref, _value: writes.append(ref),
    )

    with pytest.raises(
        ValueError,
        match="reviewed_public_pdf_runtime_R34_predecessor_required",
    ):
        r35_promotion.main()

    assert writes == []


def test_r35_promotion_requires_every_versioned_output_to_be_fresh(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(r35_promotion, "ROOT", tmp_path)
    r35_promotion._require_new_outputs()

    for ref in r35_promotion.VERSIONED_OUTPUT_REFS:
        path = tmp_path / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(
            FileExistsError,
            match="reviewed_public_pdf_runtime_output_exists",
        ):
            r35_promotion._require_new_outputs()
        path.unlink()
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("partial", encoding="utf-8")
        with pytest.raises(
            FileExistsError,
            match="reviewed_public_pdf_runtime_output_exists",
        ):
            r35_promotion._require_new_outputs()
        temporary.unlink()


def test_reviewed_pdf_successor_contracts_are_single_lane_and_fail_closed() -> None:
    kernel_payload = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_5.json"
    )
    kernel = load_financial_research_kernel(kernel_payload)
    route = load_query_object_fact_route_policy(
        _json(
            "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_5.json"
        ),
        kernel,
    )
    program = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_3.json"
    )
    requests = {
        row["request_id"]: load_evidence_request(row, kernel)
        for row in program["evidence_requests"]
    }
    assert len(requests) == 12
    changed = {
        "REQ::DELL::PRICE_CONFIGURATION::V1": "bounded_price_configuration_context",
        "REQ::DELL::PVM_BRIDGE::V1": "bounded_price_configuration_context",
        "REQ::DELL::UNIT_VOLUME::V1": "bounded_unit_volume_context",
        "REQ::DELL::SUPPLY_RELATIONSHIP::V1": "current_platform_relationship_context",
    }
    family_by_facet = route.family_by_facet()
    for request_id, facet_id in changed.items():
        request = requests[request_id]
        assert request.requested_facet_ids == (facet_id,)
        assert "PUBLIC_PDF" in request.acceptable_sources
        assert facet_id in family_by_facet
    assert program["successor_change"]["candidate_is_not_evidence"] is True
    assert program["successor_change"]["numeric_authority"] is False
    assert (
        program["successor_change"][
            "public_procurement_unit_is_not_company_units_or_share"
        ]
        is True
    )
    assert (
        program["successor_change"][
            "bundled_quote_or_contract_is_not_company_asp"
        ]
        is True
    )


def test_reviewed_pdf_successor_is_exact_append_with_lineage_and_cuda_cache() -> None:
    result = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_reviewed_public_pdf_reachability_successor_result_v1_0.json"
    )
    body = dict(result)
    result_digest = body.pop("result_digest")
    assert result_digest == canonical_digest(body)
    assert result["summary"]["base_object_count"] == 34166
    assert result["summary"]["pdf_object_count"] == 23
    assert result["summary"]["successor_object_count"] == 34189
    assert result["summary"]["base_source_record_count"] == 1877
    assert result["summary"]["pdf_canonical_source_record_count"] == 9
    assert result["summary"]["successor_source_record_count"] == 1886
    assert result["acceptance"]["base_objects_retained_exactly"] is True
    assert result["acceptance"]["base_source_records_retained_exactly"] is True

    objects_ref = result["outputs"]["objects_ref"]
    assert _sha256(objects_ref) == result["outputs"]["objects_sha256"]
    appended_objects = _jsonl_tail(objects_ref, 23)
    assert len(appended_objects) == 23
    assert {
        row["base_object_view"]["source_type"] for row in appended_objects
    } == {"PUBLIC_PDF"}
    assert {
        row["base_object_view"]["source_lineage"]["source_page_record_id"]
        for row in appended_objects
    } == set(result["summary"]["pdf_source_ids"])

    records_ref = result["outputs"]["source_records_ref"]
    appended_records = _jsonl_tail(records_ref, 9)
    assert len(appended_records) == 9
    assert {row["source_type"] for row in appended_records} == {"PUBLIC_PDF"}
    assert sum(
        (row.get("metadata") or {}).get("object_level")
        == "source_page_lineage_parent"
        for row in appended_records
    ) == 3

    manifest = _json(
        "data/workbench_private/fin_0_1_3_s1c_hybrid_candidate_runtime/model_cache_v7/qwen3_embedding_0_6b_v1/manifest.json"
    )
    assert manifest["object_count"] == 34189
    assert manifest["object_sha256"] == result["outputs"]["objects_sha256"]
    assert manifest["append"] == {
        "cpu_fallback_count": 0,
        "execution_device": "cuda:0",
        "object_count": 23,
        "output_dtype": "float16",
        "parameter_dtype": "torch.float16",
    }


def test_r37_current_receipt_binds_pdf_successor_without_stage_qualification() -> None:
    receipt = _json(
        "configs/runtime/fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_13.json"
    )
    assert receipt["registry_binding"]["registry_id"].endswith("R37")
    assert receipt["source_object_index_lineage"]["source_record_count"] == 1886
    assert receipt["source_object_index_lineage"]["compiled_object_count"] == 34189
    assert receipt["embedding_index"]["object_count"] == 34189
    assert receipt["acceptance"]["s1_qualified_stable"] is False
    assert receipt["product_readiness"]["public_information_gap_authority"] is False


def test_r36_source_route_successor_covers_bounded_public_roles() -> None:
    policy = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_source_route_portfolio_policy_v1_1.json"
    )
    routes = {row["route_id"]: row for row in policy["routes"]}
    bounded_roles = {
        "issuer_or_bounded_price_configuration_context",
        "issuer_or_bounded_customer_demand_context",
        "issuer_or_registered_supplier_direct_mention",
    }
    local = routes["current_local_snapshot"]
    assert {"PUBLIC_WEB", "PUBLIC_PDF"}.issubset(local["source_types"])
    assert bounded_roles.issubset(local["source_roles"])
    exact = routes["registered_reviewed_public_document_intake"]
    assert exact["capture_required"] is True
    assert exact["exhaustion_authority"] is True
    assert exact["exact_registry_required"] is True
    assert policy["successor_change"]["candidate_is_not_evidence"] is True
    assert policy["successor_change"]["public_information_gap_authority"] is False


def test_r37_all_current_facets_have_need_and_material_policy() -> None:
    kernel = load_financial_research_kernel(
        _json(
            "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_5.json"
        )
    )
    program = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_3.json"
    )
    requested_facets = {
        facet_id
        for raw in program["evidence_requests"]
        for facet_id in load_evidence_request(raw, kernel).requested_facet_ids
    }
    need = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_vs5_retrieval_need_compiler_policy_v1_3.json"
    )
    material = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_product_material_evidence_runtime_policy_v1_2.json"
    )
    assert requested_facets.issubset(need["facet_role_cues"])
    assert requested_facets.issubset(material["facet_required_roles"])
    assert need["successor_change"]["candidate_is_not_evidence"] is True
    assert material["successor_change"]["numeric_fact_authority"] is False


def test_r37_hybrid_adapts_bounded_facets_without_mutating_frozen_v2() -> None:
    kernel = load_financial_research_kernel(
        _json(
            "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_5.json"
        )
    )
    program = _json(
        "configs/retrieval/fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_3.json"
    )
    bounded = {
        "bounded_unit_volume_context",
        "bounded_price_configuration_context",
        "current_platform_relationship_context",
    }
    expected_aliases = {
        "bounded_unit_volume_context": "downstream_demand_context",
        "bounded_price_configuration_context": "pricing_and_mix",
        "current_platform_relationship_context": "counterparty_direct_mention",
    }
    requests = [
        load_evidence_request(raw, kernel)
        for raw in program["evidence_requests"]
        if set(raw["requested_facet_ids"]).intersection(bounded)
    ]
    seen: set[str] = set()
    for request in requests:
        lane = compile_query_facet_plan_for_request(kernel, request).lanes[0]
        compatibility_lane = _legacy_shortlist_compatibility_lane(lane)
        role = evaluate_legacy_role(
            {
                "ticker": lane.evidence_owner_tickers[0],
                "section": "product availability and reported results",
                "subsection": "configuration",
                "source_type": "PUBLIC_PDF",
                "object_kind": "claim",
                "document_text": (
                    "Dell reported systems, configuration, partnership and "
                    "product availability context."
                ),
            },
            slot_id=compatibility_lane.slot_id,
            subject_ticker=compatibility_lane.subject_ticker,
            facet_id=compatibility_lane.facet_id,
            evidence_owner_ticker=compatibility_lane.evidence_owner_tickers[0],
            relationship_direction=compatibility_lane.relationship_constraints[0],
        )
        assert role.evidence_promoted is False
        assert compatibility_lane.facet_id == expected_aliases[lane.facet_id]
        assert request.requested_facet_ids == (lane.facet_id,)
        seen.add(lane.facet_id)
    assert seen == bounded
