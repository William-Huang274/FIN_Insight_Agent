from __future__ import annotations

from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys

from pypdf import PdfWriter
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from ingestion.official_pdf import (  # noqa: E402
    OfficialPdfParseError,
    parse_captured_official_pdf,
)
from retrieval.official_pdf_objects import compile_official_pdf_document  # noqa: E402
from sec_agent.research.official_pdf_evidence import (  # noqa: E402
    OfficialPdfEvidenceError,
    build_reviewed_pack_successor,
    combine_official_pdf_evidence_results,
    evaluate_official_pdf_evidence,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    canonical_digest,
    validate_reviewed_evidence_pack,
)


POLICY_PATH = (
    ROOT
    / "configs"
    / "retrieval"
    / "fin_ia_0_1_3_s1d_tsm_official_pdf_evidence_gate_policy_v1_0.json"
)


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _attempt(root: Path, body: bytes) -> dict[str, object]:
    digest = hashlib.sha256(body).hexdigest()
    relative = Path("raw") / "sha256" / digest[:2] / digest[2:4] / f"{digest}.bin"
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(body)
    return {
        "schema_version": "fin_ia_source_intake_attempt_v1_0",
        "attempt_id": "test-tsm-r1",
        "route_id": "TSM_Q2_2026_EARNINGS_CALL_TRANSCRIPT",
        "case_key": "TSM",
        "issuer_name": "Taiwan Semiconductor Manufacturing Company Limited",
        "document_type": "earnings_call_transcript",
        "title": "TSMC Q2 2026 Earnings Call Transcript",
        "publication_date": "2026-07-16",
        "source_url": "https://investor.tsmc.com/test.pdf",
        "status": "captured_ready_for_parse",
        "raw_object_ref": relative.as_posix(),
        "raw_object_sha256": digest,
        "raw_object_bytes": len(body),
        "pdf_signature_valid": True,
        "pdf_eof_valid": True,
        "pdf_page_count": 1,
        "pdf_encrypted": False,
        "capture_before_parse": True,
        "source_body_is_evidence": False,
        "promotion_status": "source_only_not_evidence",
    }


def _parsed_pages() -> dict[str, object]:
    pages = [
        {
            "page_number": 10,
            "text": (
                "Management said advanced packaging capacity is so tight that it "
                "limits my customers' growth and the company is working to narrow "
                "the demand and capacity gap."
            ),
        },
        {
            "page_number": 20,
            "text": (
                "Management said advanced packaging can face a bottleneck and the "
                "company may buy the bottleneck tools or put more CapEx in packaging."
            ),
        },
    ]
    for page in pages:
        page["text_characters"] = len(page["text"])
        page["text_sha256"] = hashlib.sha256(page["text"].encode()).hexdigest()
    return {
        "schema_version": "fin_ia_parsed_official_pdf_document_v1_0",
        "parser_adapter": "pypdf_page_text_v1",
        "attempt_id": "source-intake-direct-tsm-r2",
        "route_id": "TSM_Q2_2026_EARNINGS_CALL_TRANSCRIPT",
        "case_key": "TSM",
        "issuer_name": "Taiwan Semiconductor Manufacturing Company Limited",
        "document_type": "earnings_call_transcript",
        "title": "TSMC Q2 2026 Earnings Call Transcript",
        "publication_date": "2026-07-16",
        "source_url": "https://investor.tsmc.com/test.pdf",
        "raw_object_ref": "raw/test.bin",
        "raw_object_sha256": "a" * 64,
        "raw_object_bytes": 1000,
        "page_count": 2,
        "nonempty_page_count": 2,
        "text_characters": sum(page["text_characters"] for page in pages),
        "source_text_digest": "b" * 64,
        "pages": pages,
        "capture_before_parse": True,
        "parsed_document_is_evidence": False,
        "promotion_status": "parsed_source_only_not_evidence",
    }


def _source_spec() -> dict[str, object]:
    return {
        "route_id": "TSM_Q2_2026_EARNINGS_CALL_TRANSCRIPT",
        "ticker": "TSM",
        "company": "Taiwan Semiconductor Manufacturing Company Limited",
        "source_type": "EARNINGS_CALL_TRANSCRIPT",
        "source_tier": "official_hosted_management_call_transcript",
        "publication_date": "2026-07-16",
        "period_end": "2026-06-30",
        "fiscal_year": 2026,
        "source_url": "https://investor.tsmc.com/test.pdf",
        "license_scope": "official_hosted_third_party_transcript_private_research_use",
    }


def _minimal_pack() -> dict[str, object]:
    source_text = "Existing issuer evidence."
    source_digest = hashlib.sha256(source_text.encode()).hexdigest()
    item = {
        "case_key": "DELL",
        "causal_attribution_authorized": False,
        "disposition": "accepted_direct_source_evidence",
        "evidence_role": "issuer_direct_source",
        "numeric_use_boundary": "source visible only",
        "object_type": "claim",
        "publication_date": "2026-05-28",
        "relationship_directions": ["subject_self_disclosure"],
        "research_as_of": "2026-08-06",
        "slot_bindings": [{"slot_id": "operating_performance"}],
        "source_content_digest": source_digest,
        "source_material_ref": "source_material_existing",
        "source_record_id": "existing-record",
        "source_reporting_period_end": "2026-05-01",
        "target_id": "existing-target",
        "writer_citable": True,
    }
    item["evidence_item_digest"] = canonical_digest(item)
    body = {
        "schema_version": "fin_ia_0_1_3_s1_local_evidence_pack_v1_0",
        "contract_ref": "fin_0_1_3.S1.candidate_to_local_evidence_pack:v1",
        "case_key": "DELL",
        "status": "local_evidence_pack_ready_with_declared_residual_gaps",
        "candidate_manifest_digest": "c" * 64,
        "retrieval_result_digest": "d" * 64,
        "generalization_contract_digest": "e" * 64,
        "content_gate_basis": "test",
        "consumer_contract": {},
        "evidence_items": [item],
        "rejected_items": [],
        "residual_gaps": [
            {
                "gap_id": "dell-gap-advanced-packaging",
                "gap_code": "commercial_data_gap",
                "slot_id": "capacity_inputs_execution",
            },
            {
                "gap_id": "dell-gap-capacity-release-timing",
                "gap_code": "commercial_data_gap",
                "slot_id": "capacity_inputs_execution",
            },
        ],
        "source_materials": [
            {
                "material_ref": "source_material_existing",
                "source_text": source_text,
                "source_text_digest": source_digest,
            }
        ],
        "observed_counts": {
            "accepted_evidence_items": 1,
            "bounded_context_items": 0,
            "direct_evidence_items": 1,
            "rejected_items": 0,
            "residual_gaps": 2,
            "source_materials": 1,
        },
        "known_boundary": "test",
    }
    return {**body, "pack_payload_digest": canonical_digest(body)}


def test_pdf_parser_fails_closed_on_digest_and_empty_text(tmp_path: Path) -> None:
    body = _pdf_bytes()
    attempt = _attempt(tmp_path, body)
    with pytest.raises(OfficialPdfParseError, match="text_empty_or_too_short"):
        parse_captured_official_pdf(
            attempt, private_source_intake_root=tmp_path
        )
    attempt["raw_object_sha256"] = "0" * 64
    with pytest.raises(OfficialPdfParseError, match="digest_mismatch"):
        parse_captured_official_pdf(
            attempt, private_source_intake_root=tmp_path
        )


def test_object_compiler_preserves_page_lineage_and_candidate_boundary() -> None:
    parsed = _parsed_pages()
    parent, children = compile_official_pdf_document(
        parsed,
        source_spec=_source_spec(),
        parsed_ref="private/parsed.json",
        parsed_sha256="f" * 64,
    )
    assert parent["ticker"] == "TSM"
    assert parent["lineage_state"] == "immutable_capture_bound"
    assert [row["metadata"]["page_number"] for row in children] == [10, 20]
    assert all(row["metadata"]["candidate_is_not_evidence"] for row in children)


def test_evidence_gate_and_pack_successor_close_only_declared_gap() -> None:
    parent, children = compile_official_pdf_document(
        _parsed_pages(),
        source_spec=_source_spec(),
        parsed_ref="private/parsed.json",
        parsed_sha256="f" * 64,
    )
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    policy["source_url"] = "https://investor.tsmc.com/test.pdf"
    policy["gap_ids_satisfied"] = ["dell-gap-advanced-packaging"]
    result = evaluate_official_pdf_evidence(
        parent=parent,
        children=children,
        policy=policy,
        research_as_of="2026-08-06",
    )
    assert result["status"] == "official_pdf_evidence_gate_passed"
    assert len(result["accepted_evidence_items"]) == 2
    assert all(
        row["causal_attribution_authorized"] is False
        and row["evidence_role"] == "counterparty_or_ecosystem_readthrough"
        for row in result["accepted_evidence_items"]
    )

    successor = build_reviewed_pack_successor(
        predecessor=_minimal_pack(),
        evidence_result=result,
        gap_ids_satisfied=["dell-gap-advanced-packaging"],
        successor_lineage={"test": True},
    )
    validate_reviewed_evidence_pack(successor)
    assert [row["gap_id"] for row in successor["residual_gaps"]] == [
        "dell-gap-capacity-release-timing"
    ]
    assert len(successor["evidence_items"]) == 3


def test_gate_rejects_owner_and_anchor_mutations() -> None:
    parsed = _parsed_pages()
    parent, children = compile_official_pdf_document(
        parsed,
        source_spec=_source_spec(),
        parsed_ref="private/parsed.json",
        parsed_sha256="f" * 64,
    )
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    owner_mutation = deepcopy(parent)
    owner_mutation["ticker"] = "DELL"
    with pytest.raises(OfficialPdfEvidenceError, match="identity_invalid"):
        evaluate_official_pdf_evidence(
            parent=owner_mutation,
            children=children,
            policy=policy,
            research_as_of="2026-08-06",
        )
    polluted = deepcopy(children)
    polluted[0]["text"] = "generic AI demand statement without packaging facts"
    result = evaluate_official_pdf_evidence(
        parent=parent,
        children=polluted,
        policy=policy,
        research_as_of="2026-08-06",
    )
    assert len(result["accepted_evidence_items"]) == 1
    assert result["rejected_items"][0]["rejection_code"] == (
        "required_anchor_group_missing"
    )


def test_direct_source_multi_slot_bundle_can_add_evidence_without_closing_gap() -> None:
    parsed = _parsed_pages()
    parsed["route_id"] = "DELL_Q1_FY2027_EARNINGS_CALL_TRANSCRIPT"
    parsed["case_key"] = "DELL"
    parsed["issuer_name"] = "Dell Technologies Inc."
    parsed["title"] = "Dell Technologies Fiscal Year 2027 First Quarter Results Transcript"
    parsed["publication_date"] = "2026-05-28"
    parsed["pages"][0]["text"] = (
        "Dell booked $24.4 billion in AI orders and had $51.3 billion of AI "
        "backlog. Demand continues to exceed supply."
    )
    parsed["pages"][1]["text"] = (
        "AI server profitability was in line with our mid-single-digit "
        "operating income rate target."
    )
    for page in parsed["pages"]:
        page["text_characters"] = len(page["text"])
        page["text_sha256"] = hashlib.sha256(page["text"].encode()).hexdigest()
    parsed["text_characters"] = sum(
        page["text_characters"] for page in parsed["pages"]
    )
    source_spec = {
        "route_id": parsed["route_id"],
        "ticker": "DELL",
        "company": parsed["issuer_name"],
        "source_type": "EARNINGS_CALL_TRANSCRIPT",
        "source_tier": "official_hosted_management_call_transcript",
        "publication_date": parsed["publication_date"],
        "period_end": "2026-05-01",
        "fiscal_year": 2027,
        "source_url": parsed["source_url"],
        "license_scope": "official_hosted_third_party_transcript_private_research_use",
    }
    parent, children = compile_official_pdf_document(
        parsed,
        source_spec=source_spec,
        parsed_ref="private/dell-parsed.json",
        parsed_sha256="f" * 64,
    )
    shared = {
        "schema_version": "fin_ia_official_pdf_evidence_gate_policy_v1_0",
        "status": "active_bounded_official_pdf_evidence_gate",
        "route_id": parsed["route_id"],
        "consumer_case_key": "DELL",
        "evidence_owner_ticker": "DELL",
        "max_accepted_pages": 1,
        "max_excerpt_characters": 900,
        "relationship_directions": ["subject_self_disclosure"],
        "license_scope": source_spec["license_scope"],
        "redistributable": False,
        "causal_attribution_authorized": False,
        "disposition": "accepted_direct_source_evidence",
        "evidence_role": "issuer_direct_source",
        "gap_ids_satisfied": [],
    }
    demand_policy = {
        **shared,
        "policy_id": "DELL-DEMAND",
        "allowed_page_numbers": [10],
        "required_anchor_groups": [
            {"group_id": "orders", "any_literals": ["24.4 billion in AI orders"]},
            {"group_id": "backlog", "any_literals": ["51.3 billion of AI backlog"]},
            {"group_id": "supply", "any_literals": ["demand continues to exceed supply"]},
        ],
        "slot_bindings": [
            {
                "slot_id": "demand_volume_quality",
                "facet_ids": ["ai_orders", "ai_backlog"],
                "qualification_id": "dell-demand",
                "business_meaning_zh": "Dell 直接披露订单和积压。",
                "claim_boundary_zh": "不证明取消率或线性兑现。",
            }
        ],
    }
    profit_policy = {
        **shared,
        "policy_id": "DELL-PROFIT",
        "allowed_page_numbers": [20],
        "required_anchor_groups": [
            {"group_id": "profit", "any_literals": ["AI server profitability"]},
            {"group_id": "target", "any_literals": ["mid-single-digit operating income rate target"]},
        ],
        "slot_bindings": [
            {
                "slot_id": "pricing_mix_value_capture",
                "facet_ids": ["ai_system_margin"],
                "qualification_id": "dell-profit",
                "business_meaning_zh": "Dell 直接披露 AI 服务器利润目标。",
                "claim_boundary_zh": "目标不等于审计后的产品利润桥。",
            }
        ],
        "gap_ids_satisfied": ["dell-gap-advanced-packaging"],
    }
    results = [
        evaluate_official_pdf_evidence(
            parent=parent,
            children=children,
            policy=policy,
            research_as_of="2026-08-06",
        )
        for policy in (demand_policy, profit_policy)
    ]
    bundle = combine_official_pdf_evidence_results(results)
    assert bundle["status"] == "official_pdf_evidence_gate_bundle_passed"
    assert len(bundle["accepted_evidence_items"]) == 2
    assert all(
        item["disposition"] == "accepted_direct_source_evidence"
        and item["evidence_role"] == "issuer_direct_source"
        for item in bundle["accepted_evidence_items"]
    )

    successor = build_reviewed_pack_successor(
        predecessor=_minimal_pack(),
        evidence_result=bundle,
        gap_ids_satisfied=["dell-gap-advanced-packaging"],
        successor_lineage={"test": True},
    )
    validate_reviewed_evidence_pack(successor)
    assert len(successor["evidence_items"]) == 3
    assert len(successor["residual_gaps"]) == 1
    assert "dell-gap-advanced-packaging" in successor["known_boundary"]


def test_direct_source_policy_rejects_cross_company_owner() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    policy.update(
        {
            "consumer_case_key": "DELL",
            "evidence_owner_ticker": "TSM",
            "disposition": "accepted_direct_source_evidence",
            "evidence_role": "issuer_direct_source",
            "relationship_directions": ["subject_self_disclosure"],
        }
    )
    with pytest.raises(OfficialPdfEvidenceError, match="policy_invalid"):
        evaluate_official_pdf_evidence(
            parent={}, children=[], policy=policy, research_as_of="2026-08-06"
        )


def test_successor_cannot_close_gap_not_qualified_by_evidence_policy() -> None:
    predecessor = _minimal_pack()
    evidence_result = {
        "status": "official_pdf_evidence_gate_passed",
        "consumer_case_key": "DELL",
        "evidence_qualified": True,
        "gap_ids_satisfied": [],
        "accepted_evidence_items": [deepcopy(predecessor["evidence_items"][0])],
        "source_materials": [deepcopy(predecessor["source_materials"][0])],
    }
    evidence_result["accepted_evidence_items"][0]["target_id"] = "new-target"
    evidence_result["accepted_evidence_items"][0]["source_material_ref"] = (
        "source_material_new"
    )
    evidence_result["source_materials"][0]["material_ref"] = "source_material_new"
    with pytest.raises(OfficialPdfEvidenceError, match="gap_not_qualified"):
        build_reviewed_pack_successor(
            predecessor=predecessor,
            evidence_result=evidence_result,
            gap_ids_satisfied=["dell-gap-advanced-packaging"],
            successor_lineage={"test": True},
        )
