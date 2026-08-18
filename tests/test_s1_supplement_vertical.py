from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from retrieval.query_plan import canonical_digest
from retrieval.supplement_vertical import (
    CASE_SUPPLEMENT_SUMMARY_SCHEMA_VERSION,
    SUPPLEMENT_SUMMARY_SET_SCHEMA_VERSION,
    SupplementVerticalError,
    build_capture_bound_pack_successor,
    compile_supplement_workbench_projection,
    project_capture_bound_supplement_lineage,
    resolve_supplement_successor_binding,
    validate_supplement_vertical_summary,
    validate_supplement_vertical_summary_set,
)
from sec_agent.research.reviewed_evidence_pack import (
    REVIEWED_EVIDENCE_PACK_CONTRACT,
    REVIEWED_EVIDENCE_PACK_SCHEMA,
    validate_reviewed_evidence_pack,
)


def _evidence_item_body() -> dict[str, object]:
    return {
        "case_key": "DELL",
        "target_id": "LEGACY::DELL::BROAD",
        "object_type": "source_segment",
        "source_record_id": "LEGACY::DELL::BROAD",
        "source_material_ref": "source_material_legacy",
        "source_content_digest": hashlib.sha256(b"legacy broad text").hexdigest(),
        "publication_date": "2026-03-16",
        "source_reporting_period_end": "2026-01-30",
        "research_as_of": "2026-08-06",
        "disposition": "accepted_direct_source_evidence",
        "evidence_role": "issuer_direct_source",
        "relationship_directions": ["subject_self_disclosure"],
        "slot_bindings": [
            {
                "slot_id": "demand_volume_quality",
                "facet_ids": ["conversion_and_durability"],
                "qualification_id": "legacy",
                "business_meaning_zh": "旧宽片段。",
                "claim_boundary_zh": "不授权营运资金结论。",
            }
        ],
        "writer_citable": True,
        "causal_attribution_authorized": False,
        "numeric_use_boundary": "No numeric authority.",
    }


def _predecessor_pack() -> dict[str, object]:
    evidence_body = _evidence_item_body()
    evidence = {**evidence_body, "evidence_item_digest": canonical_digest(evidence_body)}
    body: dict[str, object] = {
        "schema_version": REVIEWED_EVIDENCE_PACK_SCHEMA,
        "status": "reviewed_local_evidence_pack_materialized",
        "case_key": "DELL",
        "contract_ref": REVIEWED_EVIDENCE_PACK_CONTRACT,
        "consumer_contract": {},
        "evidence_items": [evidence],
        "rejected_items": [],
        "residual_gaps": [
            {
                "gap_id": "dell-gap-ai-working-capital",
                "gap_code": "metric_not_disclosed",
                "slot_id": "cash_conversion_balance_sheet",
                "facet_id": "ai_working_capital_absorption",
                "business_reason_zh": "方向和量化均未知。",
                "supplement_direction_zh": "查找管理层解释。",
                "attempted_lane_ids": [],
            }
        ],
        "source_materials": [
            {
                "material_ref": "source_material_legacy",
                "source_record_id": "LEGACY::DELL::BROAD",
                "source_text": "legacy broad text",
                "source_text_digest": hashlib.sha256(b"legacy broad text").hexdigest(),
                "source_url": "https://example.test/legacy",
                "source_type": "10-K",
                "source_tier": "primary_sec_filing",
                "evidence_owner_ticker": "DELL",
                "publication_date": "2026-03-16",
                "period_end": "2026-01-30",
                "license_scope": "public_official_source_research_use",
                "redistributable": False,
            }
        ],
        "observed_counts": {
            "accepted_evidence_items": 1,
            "direct_evidence_items": 1,
            "bounded_context_items": 0,
            "rejected_items": 0,
            "residual_gaps": 1,
            "source_materials": 1,
        },
        "content_gate_basis": "test_predecessor",
        "known_boundary": "test",
    }
    return {**body, "pack_payload_digest": canonical_digest(body)}


def _fixture(tmp_path: Path) -> dict[str, object]:
    capture_path = tmp_path / "capture.bin"
    capture_path.write_bytes(b"immutable source capture")
    capture_sha256 = hashlib.sha256(capture_path.read_bytes()).hexdigest()
    parent = {
        "document_id": "CURRENT_DOC::DELL::10_K::TEST",
        "lineage_state": "immutable_capture_bound",
        "ticker": "DELL",
        "source_type": "10-K",
        "publication_date": "2026-03-16",
        "period_end": "2026-01-30",
        "capture_ref": "capture.bin",
        "capture_sha256": capture_sha256,
    }
    positive_text = (
        "Working capital during Fiscal 2025 was primarily impacted by AI dynamics, "
        "which led to higher inventory, accounts receivable, and accounts payable levels."
    )
    negative_text = "Operating office leases are typically non-cancelable."
    source_record = {
        "evidence_id": "CURRENT_DOC::DELL::10_K::TEST::ITEM_7::BLOCK_1",
        "company": "Dell Technologies Inc.",
        "ticker": "DELL",
        "source_type": "10-K",
        "source_tier": "primary_sec_filing",
        "publication_date": "2026-03-16",
        "period_end": "2026-01-30",
        "source_url": "https://example.test/dell-10k",
        "license_scope": "public_official_source_research_use",
        "redistributable": False,
        "section": "Item 7. Management's Discussion and Analysis",
        "subsection": "Overview",
        "text": f"{positive_text} {negative_text}",
        "metadata": {
            "parent_document_id": parent["document_id"],
            "source_capture_ref": "capture.bin",
            "source_capture_sha256": capture_sha256,
            "legacy_source_record_ids": ["LEGACY::DELL::BROAD"],
        },
    }

    def compiled(object_id: str, surface: str) -> dict[str, object]:
        base = {
            "ticker": "DELL",
            "company": "Dell Technologies Inc.",
            "source_type": "10-K",
            "source_tier": "primary_sec_filing",
            "publication_date": "2026-03-16",
            "period_end": "2026-01-30",
            "section": "Item 7. Management's Discussion and Analysis",
            "subsection": "Overview",
            "source_record_id": source_record["evidence_id"],
            "source_record_digest": canonical_digest(source_record),
            "parent_document_id": parent["document_id"],
            "parent_document_digest": canonical_digest(parent),
            "surface_text": surface,
            "surface_digest": canonical_digest(surface),
        }
        return {
            "compiled_object_id": object_id,
            "object_kind": "claim",
            "candidate_not_evidence": True,
            "evidence_promoted": False,
            "numeric_authority": False,
            "base_object_view": base,
            "lineage_source_record_ids": [source_record["evidence_id"]],
        }

    positive = compiled("COBJ::POSITIVE", positive_text)
    negative = compiled("COBJ::NEGATIVE", negative_text)
    old_digest = _predecessor_pack()["evidence_items"][0]["evidence_item_digest"]
    policy = {
        "policy_id": "TEST-S1-SUPPLEMENT",
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "retire_evidence_item_digests": [old_digest],
        "review_relations": [
            {
                "atom_id": "ATOM::WC",
                "compiled_object_id": positive["compiled_object_id"],
                "judgement": "positive",
                "evidence_action": "add_capture_bound_evidence",
                "slot_id": "cash_conversion_balance_sheet",
                "facet_id": "working_capital_risk",
                "relationship_direction": "subject_self_disclosure",
                "evidence_spec": {
                    "relationship_directions": ["subject_self_disclosure"],
                    "slot_bindings": [
                        {
                            "slot_id": "cash_conversion_balance_sheet",
                            "facet_ids": ["working_capital_risk"],
                            "qualification_id": "dell-wc-direction",
                            "business_meaning_zh": "AI 动态提高营运资金占用。",
                            "claim_boundary_zh": "没有产品级量化桥。",
                        }
                    ],
                },
            },
            {
                "atom_id": "ATOM::WC",
                "compiled_object_id": negative["compiled_object_id"],
                "judgement": "hard_negative",
                "evidence_action": "reject_candidate",
                "slot_id": "cash_conversion_balance_sheet",
                "facet_id": "working_capital_risk",
                "relationship_direction": "subject_self_disclosure",
            },
        ],
        "gap_updates": [
            {
                "gap_id": "dell-gap-ai-working-capital",
                "action": "narrow",
                "classification": "authoritative_issuer_quantification_not_disclosed",
                "replacement": {
                    "gap_id": "dell-gap-ai-working-capital",
                    "gap_code": "magnitude_and_product_attribution_not_disclosed",
                    "slot_id": "cash_conversion_balance_sheet",
                    "facet_id": "ai_working_capital_absorption",
                    "business_reason_zh": "方向已知，AI 产品级量化桥未披露。",
                    "supplement_direction_zh": "保持量化归属缺口。",
                    "attempted_lane_ids": ["ATOM::WC"],
                },
                "route_checks": {
                    "local_object_route_executed": True,
                    "official_source_capture_verified": True,
                    "external_route_required_for_issuer_authority": False,
                },
                "known_boundary": "不等于所有公开或商业估计均不存在。",
            }
        ],
        "successor_known_boundary": (
            "营运资金方向和机制已获得公司原文支持；产品级量化归属仍为缺口。"
        ),
    }
    return {
        "capture_path": capture_path,
        "parent": parent,
        "source_record": source_record,
        "positive": positive,
        "negative": negative,
        "policy": policy,
    }


def _run(
    fixture: dict[str, object],
    *,
    policy: dict[str, object] | None = None,
    legacy_capture_attestations: dict[str, dict[str, object]] | None = None,
):
    source_record = fixture["source_record"]
    parent = fixture["parent"]
    positive = fixture["positive"]
    negative = fixture["negative"]
    return build_capture_bound_pack_successor(
        predecessor=_predecessor_pack(),
        policy=policy or fixture["policy"],
        ranked_candidates_by_atom={
            "ATOM::WC": [
                positive["compiled_object_id"],
                negative["compiled_object_id"],
            ]
        },
        compiled_objects_by_id={
            positive["compiled_object_id"]: positive,
            negative["compiled_object_id"]: negative,
        },
        source_records_by_id={source_record["evidence_id"]: source_record},
        parent_documents_by_id={parent["document_id"]: parent},
        capture_resolver=lambda _ref: fixture["capture_path"],
        recorded_at="2026-08-18",
        legacy_capture_attestations_by_parent_id=legacy_capture_attestations,
    )


def test_capture_bound_successor_replaces_broad_evidence_and_narrows_gap(
    tmp_path: Path,
) -> None:
    result = _run(_fixture(tmp_path))
    successor = result["successor_pack"]
    validate_reviewed_evidence_pack(successor)

    assert result["coverage_delta"] == {
        "predecessor_evidence_count": 1,
        "successor_evidence_count": 1,
        "retired_broad_or_legacy_evidence_count": 1,
        "added_capture_bound_claim_count": 1,
        "predecessor_gap_count": 1,
        "successor_gap_count": 1,
        "narrowed_gap_count": 1,
        "added_gap_count": 0,
        "closed_gap_count": 0,
        "candidate_text_promoted_count": 0,
        "numeric_authority_granted_count": 0,
    }
    assert successor["evidence_items"][0]["compiled_object_id"] == "COBJ::POSITIVE"
    assert successor["residual_gaps"][0]["gap_code"] == (
        "magnitude_and_product_attribution_not_disclosed"
    )
    assert result["gap_change_receipts"][0][
        "eligible_as_blanket_public_information_absence"
    ] is False
    assert all(
        row["candidate_text_promoted"] is False
        and row["numeric_authority"] is False
        for row in result["review_receipts"]
    )


def test_legacy_local_html_capture_attestation_preserves_object_identity(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    source = deepcopy(fixture["source_record"])
    parent = deepcopy(fixture["parent"])
    parent["lineage_state"] = "local_candidate_store_lineage_only"
    parent["capture_ref"] = None
    parent["capture_sha256"] = None
    source["metadata"].pop("source_capture_ref")
    source["metadata"].pop("source_capture_sha256")
    capture = tmp_path / "legacy.html"
    capture.write_text(
        f"<html><body><p>{source['text']}</p></body></html>",
        encoding="utf-8",
    )
    capture_sha256 = hashlib.sha256(capture.read_bytes()).hexdigest()
    fixture["capture_path"] = capture
    fixture["source_record"] = source
    fixture["parent"] = parent
    for key in ("positive", "negative"):
        fixture[key]["base_object_view"]["source_record_digest"] = canonical_digest(
            source
        )
        fixture[key]["base_object_view"]["parent_document_digest"] = canonical_digest(
            parent
        )
    attestation = {
        "schema_version": "fin_ia_legacy_local_capture_attestation_v1_0",
        "status": "legacy_local_source_capture_attested",
        "parent_document_id": parent["document_id"],
        "parent_document_digest": canonical_digest(parent),
        "source_url": source["source_url"],
        "capture_ref": "legacy.html",
        "capture_sha256": capture_sha256,
        "capture_format": "html",
        "extraction_method": "stdlib_htmlparser_visible_text_v1",
    }

    result = _run(
        fixture,
        legacy_capture_attestations={parent["document_id"]: attestation},
    )
    assert all(
        receipt["capture_binding_kind"] == "legacy_local_capture_attestation"
        for receipt in result["capture_receipts"]
    )

    broken = deepcopy(attestation)
    broken["capture_sha256"] = "0" * 64
    with pytest.raises(SupplementVerticalError, match="capture_sha256_drift"):
        _run(
            fixture,
            legacy_capture_attestations={parent["document_id"]: broken},
        )


def test_positive_candidate_must_have_ranked_retrieval_lineage(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(
        SupplementVerticalError, match="supplement_positive_not_in_candidate_pool"
    ):
        build_capture_bound_pack_successor(
            predecessor=_predecessor_pack(),
            policy=fixture["policy"],
            ranked_candidates_by_atom={"ATOM::WC": ["COBJ::NEGATIVE"]},
            compiled_objects_by_id={
                "COBJ::POSITIVE": fixture["positive"],
                "COBJ::NEGATIVE": fixture["negative"],
            },
            source_records_by_id={
                fixture["source_record"]["evidence_id"]: fixture["source_record"]
            },
            parent_documents_by_id={
                fixture["parent"]["document_id"]: fixture["parent"]
            },
            capture_resolver=lambda _ref: fixture["capture_path"],
            recorded_at="2026-08-18",
        )


def test_capture_digest_drift_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["capture_path"].write_bytes(b"mutated")
    with pytest.raises(SupplementVerticalError, match="capture_sha256_drift"):
        _run(fixture)


def test_identity_mutation_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    source = deepcopy(fixture["source_record"])
    source["ticker"] = "MU"
    fixture["source_record"] = source
    for key in ("positive", "negative"):
        fixture[key]["base_object_view"]["source_record_digest"] = canonical_digest(source)
    with pytest.raises(SupplementVerticalError, match="supplement_ticker_binding_invalid"):
        _run(fixture)


def test_capture_binding_preserves_source_date_and_uses_reported_period(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    source = fixture["source_record"]
    parent = fixture["parent"]
    source["period_end"] = "2026-05-28"
    source["metadata"]["reported_period_end"] = "2026-05-01"
    parent["period_end"] = "2026-05-28"
    temporal = {
        "reporting_fiscal_year": None,
        "reporting_fiscal_year_source": "source_record.fiscal_year",
        "reporting_period_end": "2026-05-01",
        "reporting_period_end_source": "metadata.reported_period_end",
        "source_record_fiscal_year": None,
        "source_record_period_end": "2026-05-28",
    }
    for key in ("positive", "negative"):
        base = fixture[key]["base_object_view"]
        base["period_end"] = "2026-05-01"
        base["temporal_binding"] = temporal
        base["source_record_digest"] = canonical_digest(source)
        base["parent_document_digest"] = canonical_digest(parent)

    result = _run(fixture)
    receipt = result["capture_receipts"][0]
    assert receipt["schema_version"] == "fin_ia_s1_capture_bound_object_receipt_v1_1"
    assert receipt["period_end"] == "2026-05-01"
    assert receipt["source_record_period_end"] == "2026-05-28"
    assert receipt["reporting_period_end_source"] == "metadata.reported_period_end"
    assert receipt["checks"]["reporting_period_projection_matched"] is True

    fixture["positive"]["base_object_view"]["temporal_binding"] = {
        **temporal,
        "reporting_period_end": "2026-05-02",
    }
    with pytest.raises(
        SupplementVerticalError, match="supplement_temporal_binding_invalid"
    ):
        _run(fixture)


def test_gap_cannot_be_silently_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    policy = deepcopy(fixture["policy"])
    policy["gap_updates"][0]["action"] = "close"
    with pytest.raises(SupplementVerticalError, match="supplement_gap_action_invalid"):
        _run(fixture, policy=policy)


def test_review_order_does_not_change_successor(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    baseline = _run(fixture)
    policy = deepcopy(fixture["policy"])
    policy["review_relations"].reverse()
    permuted = _run(fixture, policy=policy)
    assert permuted["result_digest"] == baseline["result_digest"]


def test_workbench_projection_does_not_claim_s1_or_numeric_readiness(
    tmp_path: Path,
) -> None:
    result = _run(_fixture(tmp_path))
    projection = compile_supplement_workbench_projection(
        result=result,
        proposition_rows=[
            {
                "proposition_id": "PROP::WC",
                "coverage_state": "qualitative_mechanism_established",
            }
        ],
    )
    assert projection["readiness"]["bounded_dell_supplement_ready"] is True
    assert projection["readiness"]["bounded_case_supplement_ready"] is True
    assert projection["readiness"]["complete_s1_ready"] is False
    assert projection["readiness"]["numeric_fact_ready"] is False


def test_successor_can_add_owned_cross_stage_gap_without_claiming_public_absence(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    policy = deepcopy(fixture["policy"])
    policy["gap_additions"] = [
        {
            "classification": "owned_s2_numeric_bridge_pending",
            "gap": {
                "gap_id": "dell-gap-value-bridge",
                "gap_code": "formula_input_missing",
                "slot_id": "pricing_mix_value_capture",
                "facet_id": "price_volume_mix_bridge",
                "business_reason_zh": "精确叙事不能替代数值桥。",
                "supplement_direction_zh": "交由 S2。",
                "attempted_lane_ids": ["ATOM::WC"],
            },
            "route_checks": {
                "s2_numeric_bridge_required": True,
                "external_public_information_absence_claimed": False,
            },
            "known_boundary": "不是公开信息不存在。",
        }
    ]

    result = _run(fixture, policy=policy)

    assert result["coverage_delta"]["predecessor_gap_count"] == 1
    assert result["coverage_delta"]["successor_gap_count"] == 2
    assert result["coverage_delta"]["added_gap_count"] == 1
    receipt = next(
        row
        for row in result["gap_change_receipts"]
        if row["gap_id"] == "dell-gap-value-bridge"
    )
    assert receipt["action"] == "add"
    assert receipt["before"] is None
    assert receipt["eligible_as_blanket_public_information_absence"] is False


def test_capture_bound_lineage_projection_requires_exact_predecessor_and_successor(
    tmp_path: Path,
) -> None:
    result = _run(_fixture(tmp_path))
    projection = compile_supplement_workbench_projection(
        result=result,
        proposition_rows=[
            {"proposition_id": "PROP::WC", "coverage_state": "narrowed"}
        ],
    )
    predecessor_payload = _predecessor_pack()["pack_payload_digest"]
    successor_payload = result["successor_pack"]["pack_payload_digest"]
    predecessor_artifact = "1" * 64
    successor_artifact = "2" * 64
    base = {
        "status": "canonical_s1_lineage_ready",
        "pack_binding": {
            "case_key": "DELL",
            "artifact_digest": predecessor_artifact,
            "pack_payload_digest": predecessor_payload,
        },
        "workbench_projection_digest": "3" * 64,
    }
    summary = {
        "schema_version": "fin_ia_s1_vs4_dell_supplement_vertical_summary_v1_0",
        "status": "vs4_dell_capture_bound_supplement_vertical_materialized",
        "recorded_at": "2026-08-18",
        "result_digest": result["result_digest"],
        "bound_inputs": {
            "predecessor_pack_sha256": predecessor_artifact,
            "predecessor_pack_payload_digest": predecessor_payload,
        },
        "storage": {
            "full_result_digest": result["result_digest"],
            "successor_pack_sha256": successor_artifact,
            "successor_pack_payload_digest": successor_payload,
        },
        "coverage_delta": result["coverage_delta"],
        "decision": {
            "successor_pack_authorized": True,
            "complete_s1_qualified": False,
        },
        "workbench_projection": projection,
    }

    projected = project_capture_bound_supplement_lineage(
        base_projection=base,
        supplement_summary=summary,
        case_key="DELL",
        artifact_digest=successor_artifact,
        pack_payload_digest=successor_payload,
    )
    assert projected["status"] == (
        "canonical_s1_lineage_with_capture_bound_supplement"
    )
    assert projected["supplement_vertical"]["complete_s1_qualified"] is False
    assert projected["pack_binding"]["artifact_digest"] == successor_artifact

    for field, mutation in (
        ("predecessor_pack_sha256", "4" * 64),
        ("predecessor_pack_payload_digest", "5" * 64),
    ):
        broken = deepcopy(summary)
        broken["bound_inputs"][field] = mutation
        with pytest.raises(
            SupplementVerticalError, match="supplement_current_pack_binding_drift"
        ):
            project_capture_bound_supplement_lineage(
                base_projection=base,
                supplement_summary=broken,
                case_key="DELL",
                artifact_digest=successor_artifact,
                pack_payload_digest=successor_payload,
            )


def test_generic_case_summary_set_projects_without_dell_special_case(
    tmp_path: Path,
) -> None:
    result = _run(_fixture(tmp_path))
    projection_input = deepcopy(result)
    projection_input["case_key"] = "MU"
    projection = compile_supplement_workbench_projection(
        result=projection_input,
        proposition_rows=[
            {"proposition_id": "PROP::MU", "coverage_state": "narrowed"}
        ],
    )
    predecessor_payload = _predecessor_pack()["pack_payload_digest"]
    successor_payload = result["successor_pack"]["pack_payload_digest"]
    predecessor_artifact = "1" * 64
    successor_artifact = "2" * 64
    summary = {
        "schema_version": CASE_SUPPLEMENT_SUMMARY_SCHEMA_VERSION,
        "status": "vs4_case_capture_bound_supplement_vertical_materialized",
        "recorded_at": "2026-08-18",
        "case_key": "MU",
        "result_digest": result["result_digest"],
        "bound_inputs": {
            "predecessor_pack_sha256": predecessor_artifact,
            "predecessor_pack_payload_digest": predecessor_payload,
        },
        "storage": {
            "full_result_digest": result["result_digest"],
            "successor_pack_sha256": successor_artifact,
            "successor_pack_payload_digest": successor_payload,
        },
        "coverage_delta": result["coverage_delta"],
        "decision": {
            "successor_pack_authorized": True,
            "complete_s1_qualified": False,
        },
        "workbench_projection": projection,
    }
    set_body = {
        "schema_version": SUPPLEMENT_SUMMARY_SET_SCHEMA_VERSION,
        "status": "vs4_case_supplement_summary_set_ready",
        "recorded_at": "2026-08-18",
        "case_summaries": {"MU": summary},
    }
    summary_set = {
        **set_body,
        "summary_set_digest": canonical_digest(set_body),
    }
    base = {
        "status": "canonical_s1_lineage_ready",
        "pack_binding": {
            "case_key": "MU",
            "artifact_digest": predecessor_artifact,
            "pack_payload_digest": predecessor_payload,
        },
    }

    assert resolve_supplement_successor_binding(
        summary_set, case_key="MU"
    ) == {
        "artifact_digest": successor_artifact,
        "pack_payload_digest": successor_payload,
    }
    assert resolve_supplement_successor_binding(
        summary_set, case_key="NVDA"
    ) is None
    projected = project_capture_bound_supplement_lineage(
        base_projection=base,
        supplement_summary=summary_set,
        case_key="MU",
        artifact_digest=successor_artifact,
        pack_payload_digest=successor_payload,
    )
    assert projected["pack_binding"]["case_key"] == "MU"
    assert projected["supplement_vertical"]["complete_s1_qualified"] is False

    initialized = project_capture_bound_supplement_lineage(
        base_projection=None,
        supplement_summary=summary_set,
        case_key="MU",
        artifact_digest=successor_artifact,
        pack_payload_digest=successor_payload,
    )
    assert initialized["pack_binding"]["case_key"] == "MU"
    assert initialized["coverage_summary"]["reviewed_not_recalled_count"] is None
    assert initialized["hard_boundaries"]["base_vs1_decision_rows_available"] is False


def test_summary_set_validation_is_idempotent_for_legacy_dell_member(
    tmp_path: Path,
) -> None:
    result = _run(_fixture(tmp_path))
    projection = compile_supplement_workbench_projection(
        result=result,
        proposition_rows=[
            {"proposition_id": "PROP::WC", "coverage_state": "narrowed"}
        ],
    )
    legacy = {
        "schema_version": "fin_ia_s1_vs4_dell_supplement_vertical_summary_v1_0",
        "status": "vs4_dell_capture_bound_supplement_vertical_materialized",
        "recorded_at": "2026-08-18",
        "result_digest": result["result_digest"],
        "bound_inputs": {
            "predecessor_pack_sha256": "1" * 64,
            "predecessor_pack_payload_digest": _predecessor_pack()[
                "pack_payload_digest"
            ],
        },
        "storage": {
            "full_result_digest": result["result_digest"],
            "successor_pack_sha256": "2" * 64,
            "successor_pack_payload_digest": result["successor_pack"][
                "pack_payload_digest"
            ],
        },
        "coverage_delta": result["coverage_delta"],
        "decision": {
            "successor_pack_authorized": True,
            "complete_s1_qualified": False,
        },
        "workbench_projection": projection,
    }
    normalized = validate_supplement_vertical_summary(legacy)
    body = {
        "schema_version": SUPPLEMENT_SUMMARY_SET_SCHEMA_VERSION,
        "status": "vs4_case_supplement_summary_set_ready",
        "recorded_at": "2026-08-18",
        "case_summaries": {"DELL": normalized},
    }
    payload = {**body, "summary_set_digest": canonical_digest(body)}

    once = validate_supplement_vertical_summary_set(payload)
    twice = validate_supplement_vertical_summary_set(once)

    assert twice == once
