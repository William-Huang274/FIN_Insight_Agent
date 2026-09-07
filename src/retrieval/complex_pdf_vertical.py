from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from retrieval.artifact_spine import (
    ArtifactEnvelope,
    ArtifactScope,
    ArtifactSpinePolicy,
    build_artifact_envelope,
    canonical_json_digest,
    validate_artifact_chain,
    validate_inline_payload_refs,
)
from retrieval.candidate_retriever import CandidateCorpus, retrieve_query_plan
from retrieval.contracts import (
    load_evidence_request,
    load_financial_research_kernel,
)
from retrieval.query_plan import compile_query_facet_plan_for_request
from retrieval.vertical_slice import (
    build_vs1_artifact_chain,
    compile_candidate_decision_ledger,
)


VS2_RESULT_SCHEMA_VERSION = "fin_ia_s1_vs2_complex_pdf_vertical_result_v1_0"
VS2_RESULT_RESOURCE_ID = "application.result.current_s1_vs2_complex_pdf_vertical"
VS2_COVERAGE_SCHEMA_VERSION = "fin_ia_s1_vs2_complex_pdf_coverage_v1_0"
VS2_READINESS_SCHEMA_VERSION = "fin_ia_s1_vs2_complex_pdf_readiness_v1_0"
VS2_WORKBENCH_SCHEMA_VERSION = "fin_ia_s1_vs2_complex_pdf_workbench_v1_0"
VS2_S2_SIBLING_SCHEMA_VERSION = "fin_ia_s1_vs2_s2_sibling_binding_v1_0"


class S1ComplexPdfVerticalError(ValueError):
    """The VS2 complex-document vertical lost a required authority boundary."""


def compile_vs2_inline_payloads(
    *,
    source_spec: Mapping[str, Any],
    parsed: Mapping[str, Any],
    object_set: Mapping[str, Any],
    evaluation: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile the exact result-local payloads asserted by the VS2 envelopes."""

    source_id = "IFX_2025_ANNUAL_REPORT_COMPLEX_LAYOUT"
    source_route = {
        "source_id": source_id,
        "input_kind": "parsed_complex_pdf_layout_document",
        "source_url": source_spec["source_url"],
        "route_id": parsed.get("route_id"),
        "expected_sha256": parsed.get("raw_object_sha256"),
        "required": True,
    }
    financial_object = {
        "source_id": source_id,
        "document_parents_added": 1,
        "retrieval_children_added": object_set.get("object_count"),
        "invalid_records_excluded": 0,
        "source_sha256": parsed.get("raw_object_sha256"),
    }
    frozen_body = {
        "schema_version": "fin_ia_s1_vs2_frozen_consumer_probe_v1_0",
        "status": "complex_document_workbench_projection_bound",
        "case_key": source_spec["ticker"],
        "readiness_digest": evaluation["readiness"]["readiness_digest"],
        "workbench_projection_digest": evaluation["workbench_projection"][
            "workbench_projection_digest"
        ],
        "same_canonical_spine": True,
        "product_case_enrollment": False,
    }
    frozen_probe = {
        **frozen_body,
        "frozen_consumer_probe_digest": canonical_json_digest(frozen_body),
    }
    sibling_payload = {
        "schema_version": VS2_S2_SIBLING_SCHEMA_VERSION,
        "status": "candidate_rows_bound_numeric_adjudication_pending",
        "source_owner_ticker": source_spec["ticker"],
        "document_id": object_set.get("document_id"),
        "material_row_object_count": int(
            (object_set.get("object_type_counts") or {}).get(
                "financial_table_metric_row", 0
            )
        ),
        "numeric_fact_authority_granted": False,
        "disposition": "S2_source_bound_numeric_adjudication_required",
    }
    decisions = evaluation["decision_ledger"].get("decisions") or ()
    return {
        "source_routes": {source_id: source_route},
        "financial_objects": {source_id: financial_object},
        "evidence_request": deepcopy(evaluation["request_result"]["request"]),
        "query_facet_plan": deepcopy(evaluation["request_result"]["query_plan"]),
        "candidate_set": {
            "candidate_state": "candidate_not_evidence",
            "request_id": evaluation["request_result"]["request"].get("request_id"),
            "source_record_ids": [row["source_record_id"] for row in decisions],
        },
        "candidate_ranking": {
            "ranking_contract": "current_typed_financial_candidate_order",
            "candidate_state": "candidate_not_evidence",
            "rows": [
                {
                    "rank": row["rank"],
                    "source_record_id": row["source_record_id"],
                    "score": row.get("score"),
                }
                for row in decisions
            ],
        },
        "candidate_decision_ledger": deepcopy(evaluation["decision_ledger"]),
        "evidence_coverage_state": deepcopy(evaluation["coverage"]),
        "evidence_pack_readiness": deepcopy(evaluation["readiness"]),
        "workbench_projection": deepcopy(evaluation["workbench_projection"]),
        "frozen_consumer_probe": frozen_probe,
        "s2_sibling_binding": sibling_payload,
    }


def compile_vs2_evaluation(
    *,
    base_kernel_payload: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    parsed: Mapping[str, Any],
    objects: Sequence[Mapping[str, Any]],
    object_set: Mapping[str, Any],
    reference: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    """Run the same query/decision/coverage seams on one complex official PDF."""

    kernel_payload = _development_kernel_payload(base_kernel_payload, source_spec)
    kernel = load_financial_research_kernel(kernel_payload)
    request_payload = _request_payload(source_spec)
    request = load_evidence_request(request_payload, kernel)
    plan = compile_query_facet_plan_for_request(kernel, request)
    corpus = CandidateCorpus(
        records=tuple(deepcopy(dict(row)) for row in objects),
        records_scanned=len(objects),
        invalid_records_excluded=0,
    )
    retrieval = retrieve_query_plan(kernel, plan, corpus)
    request_result = {
        "schema_version": "fin_ia_request_scoped_retrieval_projection_v1_0",
        "status": "request_scoped_typed_local_retrieval_ready",
        "product_mode": "train_internal_complex_document_evaluation",
        "case_key": request.case_key,
        "candidate_state": "candidate_not_evidence",
        "execution_mode": "immutable_complex_document_object_snapshot",
        "request": request.as_dict(),
        "request_digest": canonical_json_digest(request.as_dict()),
        "query_plan": plan.as_dict(),
        "execution_plan": None,
        "source_snapshot": {
            "snapshot_id": "FIN-0.1.3-S1-VS2-IFX-2025-ANNUAL-REPORT",
            "object_set_digest": object_set.get("object_set_digest"),
        },
        "summary": {
            "requested_facet_count": len(request.requested_facet_ids),
            "compiled_lane_count": len(retrieval["lane_results"]),
            "nonempty_lane_count": sum(
                bool(row["candidates"]) for row in retrieval["lane_results"]
            ),
            "unique_candidates": retrieval["summary"]["unique_candidates"],
            "typed_gap_count": 0,
            "network_calls": 0,
            "model_calls": 0,
        },
        "typed_gaps": [],
        "typed_fact_results": [],
        "lanes": [
            {
                "lane": deepcopy(row["lane"]),
                "candidate_state": "candidate_not_evidence",
                "candidates": deepcopy(row["candidates"]),
                "missing_required_source_roles": deepcopy(
                    row["missing_required_source_roles"]
                ),
                "snapshot_exclusion_counts": deepcopy(row["exclusion_counts"]),
                "request_exclusion_counts": {},
            }
            for row in retrieval["lane_results"]
        ],
        "known_boundary": (
            "This is a train-internal complex-document retrieval vertical. Labels "
            "are joined only after candidate generation; parsed text and rank do not "
            "grant Evidence or NumericFact authority."
        ),
    }
    reviewed_ids = _resolve_reviewed_object_ids(objects, reference)
    pack = _reviewed_pack(
        source_spec=source_spec,
        parsed=parsed,
        objects=objects,
        reviewed_ids=reviewed_ids,
        recorded_at=recorded_at,
    )
    ledger = compile_candidate_decision_ledger(
        request_result=request_result,
        evidence_pack=pack,
        recorded_at=recorded_at,
    )
    coverage = _coverage(
        request_result=request_result,
        ledger=ledger,
        pack=pack,
        parsed=parsed,
        recorded_at=recorded_at,
    )
    readiness = _readiness(
        coverage=coverage,
        ledger=ledger,
        pack=pack,
        recorded_at=recorded_at,
    )
    workbench = _workbench(
        parsed=parsed,
        object_set=object_set,
        ledger=ledger,
        coverage=coverage,
        readiness=readiness,
        recorded_at=recorded_at,
    )
    return {
        "request_result": request_result,
        "reviewed_pack": pack,
        "decision_ledger": ledger,
        "coverage": coverage,
        "readiness": readiness,
        "workbench_projection": workbench,
        "reviewed_object_ids": reviewed_ids,
    }


def build_vs2_artifact_chain(
    *,
    policy: ArtifactSpinePolicy,
    source_spec: Mapping[str, Any],
    parsed: Mapping[str, Any],
    parsed_ref: str,
    parsed_sha256: str,
    object_set: Mapping[str, Any],
    object_set_ref: str,
    object_set_sha256: str,
    index_ref: str,
    index_sha256: str,
    evaluation: Mapping[str, Any],
    inline_payload_ref_prefix: str,
) -> tuple[ArtifactEnvelope, ...]:
    source_id = "IFX_2025_ANNUAL_REPORT_COMPLEX_LAYOUT"
    source_manifest = {
        "schema_version": "fin_ia_s1_vs2_complex_pdf_object_manifest_v1_0",
        "sources": [
            {
                "source_id": source_id,
                "input_kind": "parsed_complex_pdf_layout_document",
                "ticker": source_spec["ticker"],
                "source_url": source_spec["source_url"],
                "route_id": parsed.get("route_id"),
                "expected_sha256": parsed.get("raw_object_sha256"),
                "required": True,
            }
        ],
    }
    source_results = [
        {
            "source_id": source_id,
            "document_parents_added": 1,
            "retrieval_children_added": object_set.get("object_count"),
            "invalid_records_excluded": 0,
            "source_sha256": parsed.get("raw_object_sha256"),
        }
    ]
    source_bindings = {
        source_id: {
            "capture_ref": parsed.get("raw_object_ref"),
            "capture_sha256": parsed.get("raw_object_sha256"),
            "capture_schema_version": str(parsed.get("capture_schema_version") or "fin_ia_immutable_official_pdf_capture_v1_0"),
            "parsed_ref": parsed_ref,
            "parsed_sha256": parsed_sha256,
            "parsed_schema_version": parsed.get("schema_version"),
        }
    }
    inline_payloads = compile_vs2_inline_payloads(
        source_spec=source_spec,
        parsed=parsed,
        object_set=object_set,
        evaluation=evaluation,
    )
    frozen_probe = inline_payloads["frozen_consumer_probe"]
    base = list(
        build_vs1_artifact_chain(
            policy=policy,
            source_manifest=source_manifest,
            source_results=source_results,
            source_payload_bindings=source_bindings,
            object_manifest_ref=object_set_ref,
            object_manifest_sha256=object_set_sha256,
            index_snapshot_ref=index_ref,
            index_snapshot_sha256=index_sha256,
            request_result=evaluation["request_result"],
            decision_ledger=evaluation["decision_ledger"],
            coverage=evaluation["coverage"],
            readiness=evaluation["readiness"],
            workbench_projection=evaluation["workbench_projection"],
            frozen_consumer_probe=frozen_probe,
            inline_payload_ref_prefix=inline_payload_ref_prefix,
        )
    )
    manifest = next(row for row in base if row.artifact_type == "object_manifest")
    sibling_payload = inline_payloads["s2_sibling_binding"]
    sibling = build_artifact_envelope(
        artifact_type="s2_sibling_binding",
        artifact_version="v1.0",
        producer_id="s1_vs2_complex_pdf_object_compiler",
        payload_schema_version=VS2_S2_SIBLING_SCHEMA_VERSION,
        payload_ref=f"{inline_payload_ref_prefix}/s2_sibling_binding",
        payload_sha256=canonical_json_digest(sibling_payload),
        lifecycle_state="typed_gap",
        scope=ArtifactScope(
            binding_state="aggregate",
            research_as_of=str(source_spec["research_as_of"]),
        ),
        parent_refs=(manifest.as_ref("bound_to"),),
    )
    base.append(sibling)
    validate_artifact_chain(base, policy)
    return tuple(base)


def validate_vs2_result(
    payload: Mapping[str, Any], *, policy: ArtifactSpinePolicy
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    if value.get("schema_version") != VS2_RESULT_SCHEMA_VERSION:
        raise S1ComplexPdfVerticalError("vs2_result_schema_invalid")
    expected = canonical_json_digest(
        {key: raw for key, raw in value.items() if key != "result_digest"}
    )
    if value.get("result_digest") != expected:
        raise S1ComplexPdfVerticalError("vs2_result_digest_invalid")
    envelopes = tuple(
        ArtifactEnvelope.model_validate(row) for row in value.get("envelopes") or ()
    )
    required = {
        "source_route_decision",
        "raw_source_capture",
        "parsed_document",
        "financial_evidence_object",
        "object_manifest",
        "index_snapshot",
        "s2_sibling_binding",
        "evidence_request",
        "query_facet_plan",
        "candidate_set",
        "candidate_ranking",
        "candidate_decision",
        "evidence_coverage_state",
        "evidence_pack_readiness",
        "workbench_projection",
        "frozen_consumer_probe",
    }
    if not required.issubset({row.artifact_type for row in envelopes}):
        raise S1ComplexPdfVerticalError("vs2_artifact_spine_incomplete")
    validate_artifact_chain(envelopes, policy)
    validate_inline_payload_refs(
        value,
        envelopes,
        resource_id=VS2_RESULT_RESOURCE_ID,
    )
    sibling = value.get("payloads", {}).get("s2_sibling_binding") or {}
    if not (
        sibling.get("numeric_fact_authority_granted") is False
        and sibling.get("status")
        == "candidate_rows_bound_numeric_adjudication_pending"
        and sibling.get("disposition")
        == "S2_source_bound_numeric_adjudication_required"
    ):
        raise S1ComplexPdfVerticalError("vs2_numeric_authority_boundary_invalid")
    acceptance = value.get("stage_acceptance") or {}
    if not (
        acceptance.get("component_engineering_pass") is True
        and acceptance.get("vertical_slice_integrated") is True
        and acceptance.get("S1_qualified_stable") is False
    ):
        raise S1ComplexPdfVerticalError("vs2_stage_acceptance_invalid")
    return value


def _development_kernel_payload(
    base: Mapping[str, Any], source_spec: Mapping[str, Any]
) -> dict[str, Any]:
    payload = deepcopy(dict(base))
    operating_slot = next(
        row
        for row in payload["evidence_slots"]
        if row["slot_id"] == "operating_performance"
    )
    if "ANNUAL_REPORT" not in operating_slot["source_types"]:
        operating_slot["source_types"].append("ANNUAL_REPORT")
    payload["industry_packs"].append(
        {
            "pack_id": "power_semiconductor_development",
            "lexical_terms": [
                "power semiconductor",
                "segment result",
                "operating profit",
            ],
            "slot_terms": {
                "operating_performance": [
                    "segment result",
                    "operating profit",
                    "comparative figures adjusted",
                ]
            },
        }
    )
    payload["cases"].append(
        {
            "case_key": source_spec["ticker"],
            "subject": {
                "ticker": source_spec["ticker"],
                "legal_name": source_spec["company"],
                "aliases": ["Infineon Technologies", "Infineon"],
            },
            "research_as_of": source_spec["research_as_of"],
            "industry_pack_id": "power_semiconductor_development",
            "related_entities": [],
            "slot_terms": {
                "operating_performance": [
                    "segment result",
                    "operating profit",
                    "comparative figures adjusted",
                ]
            },
        }
    )
    # VS2 intentionally samples up to 20 candidates from this single complex
    # document: the page/context/table/row/footnote/continuation object roles
    # must all remain observable before VS3 ranks them.  This is a zero-model,
    # zero-network candidate ceiling, not a hidden research-token shortcut.
    payload["budgets"]["candidates_per_slot"] = 20
    payload["budgets"]["candidates_per_document"] = 20
    return payload


def _request_payload(source_spec: Mapping[str, Any]) -> dict[str, Any]:
    ticker = str(source_spec["ticker"])
    return {
        "schema_version": "fin_ia_evidence_request_v1_0",
        "request_id": "REQ-IFX-VS2-COMPLEX-RESULTS-001",
        "cell_id": "IFX-VS2-COMPLEX-RESULTS-CELL-001",
        "requester_role": "operating_performance_specialist",
        "evidence_domain": "operating_performance",
        "case_key": ticker,
        "subject_ticker": ticker,
        "research_as_of": source_spec["research_as_of"],
        "target_entities": [ticker],
        "requested_facet_ids": ["reported_results"],
        "metric_intents": [
            "segment result",
            "operating profit",
            "year over year change",
        ],
        "product_intents": ["segment structure change"],
        "period": {
            "start_date": "2024-10-01",
            "end_date": source_spec["period_end"],
            "fiscal_years": [source_spec["fiscal_year"]],
        },
        "granularity": "fiscal_year_and_segment",
        "unit": "EUR_millions_reported_source_unit",
        "acceptable_sources": ["ANNUAL_REPORT"],
        "acceptable_proxy": False,
        "forbidden_proxy": [
            "OCR text treated as reviewed Evidence",
            "table row treated as NumericFact before S2 adjudication",
            "previous-year comparatives used without restatement context",
        ],
        "stop_condition": (
            "Determine what the official FY2025 annual report says about segment "
            "results and preserve reclassification, table, footnote and cross-page "
            "lineage without granting premature numeric authority."
        ),
        "clarification_policy": "return_typed_gap",
    }


def _resolve_reviewed_object_ids(
    objects: Sequence[Mapping[str, Any]], reference: Mapping[str, Any]
) -> list[str]:
    selected: list[str] = []
    for raw_selector in reference.get("reviewed_target_selectors") or ():
        selector = _mapping(raw_selector, "vs2_reference_selector_invalid")
        expected_type = str(selector.get("evidence_type") or "")
        substrings = [str(value) for value in selector.get("contains_all") or ()]
        matches = [
            str(row.get("evidence_id") or "")
            for row in objects
            if str(row.get("evidence_type") or "") == expected_type
            and all(value in str(row.get("text") or "") for value in substrings)
        ]
        if len(matches) != 1:
            raise S1ComplexPdfVerticalError(
                f"vs2_reference_selector_not_unique:{expected_type}:{len(matches)}"
            )
        selected.extend(matches)
    if not selected or len(selected) != len(set(selected)):
        raise S1ComplexPdfVerticalError("vs2_reviewed_targets_invalid")
    return selected


def _reviewed_pack(
    *,
    source_spec: Mapping[str, Any],
    parsed: Mapping[str, Any],
    objects: Sequence[Mapping[str, Any]],
    reviewed_ids: Sequence[str],
    recorded_at: str,
) -> dict[str, Any]:
    by_id = {str(row.get("evidence_id") or ""): row for row in objects}
    items: list[dict[str, Any]] = []
    for object_id in reviewed_ids:
        row = by_id[object_id]
        source = {
            "material_ref": "source_material_" + content_id(row["text"]),
            "source_record_id": object_id,
            "evidence_owner_ticker": source_spec["ticker"],
            "source_tier": source_spec["source_tier"],
            "source_type": source_spec["source_type"],
            "source_url": source_spec["source_url"],
            "publication_date": source_spec["publication_date"],
            "period_end": source_spec["period_end"],
            "license_scope": source_spec["license_scope"],
            "redistributable": False,
            "source_text_digest": canonical_json_digest(row["text"]),
            "raw_capture_sha256": parsed["raw_object_sha256"],
            "reviewed_source_excerpt": str(row["text"])[:900],
            "reviewed_anchor_bound": True,
        }
        item_body = {
            "case_key": source_spec["ticker"],
            "target_id": object_id,
            "source_record_id": object_id,
            "object_type": row["evidence_type"],
            "disposition": "accepted_direct_source_evidence",
            "evidence_role": "issuer_direct_source",
            "publication_date": source_spec["publication_date"],
            "source_reporting_period_end": source_spec["period_end"],
            "research_as_of": source_spec["research_as_of"],
            "relationship_directions": ["subject_self_disclosure"],
            "slot_bindings": [
                {
                    "slot_id": "operating_performance",
                    "facet_ids": ["reported_results"],
                    "qualification_id": "ifx-vs2-complex-results",
                    "business_meaning_zh": (
                        "验证复杂年报中的分部结果、重述说明、脚注和跨页关系。"
                    ),
                    "claim_boundary_zh": (
                        "当前对象可作为经复核来源证据；精确数字仍须 S2 单独裁决。"
                    ),
                }
            ],
            "numeric_use_boundary": (
                "Source-visible values remain S1 Evidence only; S2 adjudication is required."
            ),
            "causal_attribution_authorized": False,
            "writer_citable": True,
            "source": source,
        }
        item_body["evidence_item_digest"] = canonical_json_digest(item_body)
        items.append(item_body)
    pack_body = {
        "schema_version": "fin_ia_s1_vs2_train_internal_reviewed_pack_v1_0",
        "status": "capture_bound_reviewed_complex_pdf_evidence_pack",
        "recorded_at": recorded_at,
        "case_key": source_spec["ticker"],
        "evidence_items": items,
        "residual_gaps": [
            {
                "gap_id": "GAP-IFX-VS2-REAL-SCANNED-SOURCE",
                "gap_code": "real_scanned_financial_source_not_enrolled",
                "slot_id": "operating_performance",
                "business_reason_zh": "当前 OCR 证明来自官方页栅格化 mutation，不等于真实扫描资料异质性资格。",
            },
            {
                "gap_id": "GAP-IFX-VS2-S2-NUMERIC-ADJUDICATION",
                "gap_code": "material_table_rows_not_yet_adjudicated_by_s2",
                "slot_id": "operating_performance",
                "business_reason_zh": "表格数值已定位但尚未成为 source-bound NumericFact。",
            },
        ],
    }
    pack_body["pack_payload_digest"] = canonical_json_digest(pack_body)
    pack_body["artifact_digest"] = canonical_json_digest(
        {"pack_payload_digest": pack_body["pack_payload_digest"]}
    )
    return pack_body


def _coverage(
    *,
    request_result: Mapping[str, Any],
    ledger: Mapping[str, Any],
    pack: Mapping[str, Any],
    parsed: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    accepted = list(ledger.get("accepted_evidence_item_digests") or ())
    reviewed = {
        str(row.get("evidence_item_digest") or "")
        for row in pack.get("evidence_items") or ()
    }
    receipts = [
        {
            "gap_id": "GAP-IFX-VS2-REAL-SCANNED-SOURCE",
            "owning_stage": "S1-B",
            "classification": "evaluation_corpus_shape_not_yet_observed",
            "eligible_as_true_public_information_gap": False,
            "checks": {
                "official_document_available": True,
                "native_layout_path_executed": True,
                "ocr_mutation_path_executed": True,
                "real_scanned_financial_document_enrolled": False,
            },
            "disposition": "retain_as_heterogeneity_qualification_boundary",
            "last_checked_at": recorded_at,
        },
        {
            "gap_id": "GAP-IFX-VS2-S2-NUMERIC-ADJUDICATION",
            "owning_stage": "S2",
            "classification": "source_visible_numbers_without_numeric_authority",
            "eligible_as_true_public_information_gap": False,
            "checks": {
                "page_and_bbox_locator_present": True,
                "table_rows_materialized": True,
                "S2_source_bound_adjudication_executed": False,
            },
            "disposition": "route_to_S2_sibling_without_silent_promotion",
            "last_checked_at": recorded_at,
        },
    ]
    for receipt in receipts:
        receipt["receipt_digest"] = canonical_json_digest(receipt)
    body = {
        "schema_version": VS2_COVERAGE_SCHEMA_VERSION,
        "status": "complex_document_proposition_coverage_materialized",
        "recorded_at": recorded_at,
        "case_key": request_result["case_key"],
        "research_as_of": request_result["request"]["research_as_of"],
        "proposition_id": "PROP::" + request_result["request_digest"][:24].upper(),
        "research_question": request_result["request"]["stop_condition"],
        "request_id": request_result["request"]["request_id"],
        "slot_ids": ["operating_performance"],
        "coverage_state": (
            "bounded_complex_document_evidence_with_typed_parser_and_s2_boundaries"
            if accepted
            else "complex_document_evidence_not_recalled"
        ),
        "accepted_evidence_item_digests": sorted(accepted),
        "reviewed_evidence_not_recalled_digests": sorted(reviewed - set(accepted)),
        "candidate_decision_counts": deepcopy(ledger["decision_counts"]),
        "gap_eligibility_receipts": receipts,
        "quality_receipt_digest": parsed["quality_receipt"]["quality_digest"],
        "known": [
            "Official FY2025 pages preserve segment structure, table, footnote and cross-page candidates.",
            "Candidate ranking does not grant Evidence or NumericFact authority.",
        ],
        "unknown": [
            "Behavior on a naturally scanned financial filing remains unqualified.",
            "Material table values have not completed S2 numeric adjudication.",
        ],
        "why_unknown": [
            "The development corpus contains a rasterized official-page mutation, not a naturally scanned filing.",
            "VS2 deliberately stops before NumericFact promotion and emits an S2 sibling binding.",
        ],
    }
    return {**body, "coverage_state_digest": canonical_json_digest(body)}


def _readiness(
    *,
    coverage: Mapping[str, Any],
    ledger: Mapping[str, Any],
    pack: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    counts = ledger["decision_counts"]
    body = {
        "schema_version": VS2_READINESS_SCHEMA_VERSION,
        "status": "complex_pdf_vertical_readiness_materialized",
        "recorded_at": recorded_at,
        "case_key": coverage["case_key"],
        "research_as_of": coverage["research_as_of"],
        "proposition_id": coverage["proposition_id"],
        "readiness_state": (
            "ready_for_complex_pdf_bounded_research_not_numeric_conclusion"
            if coverage["accepted_evidence_item_digests"]
            else "not_ready_complex_pdf_evidence_not_recalled"
        ),
        "pack_binding": {
            "case_key": pack["case_key"],
            "artifact_digest": pack["artifact_digest"],
            "pack_payload_digest": pack["pack_payload_digest"],
        },
        "checks": {
            "all_retrieved_candidates_have_persistent_decisions": sum(counts.values())
            == int(ledger["candidate_count"]),
            "reviewed_layout_evidence_recalled": bool(
                coverage["accepted_evidence_item_digests"]
            ),
            "ocr_mutation_does_not_auto_promote": True,
            "material_numbers_routed_to_S2_sibling": True,
            "real_scanned_source_qualified": False,
            "complete_product_conclusion_ready": False,
            "S1_qualified_stable": False,
        },
        "accepted_evidence_count": len(coverage["accepted_evidence_item_digests"]),
        "unresolved_gap_count": len(coverage["gap_eligibility_receipts"]),
        "known_boundary": (
            "VS2 integrates one train-internal complex official PDF through the same "
            "spine and Workbench consumer. It does not enroll IFX as a product case, "
            "qualify naturally scanned filings, grant NumericFact authority or close S1."
        ),
    }
    return {**body, "readiness_digest": canonical_json_digest(body)}


def _workbench(
    *,
    parsed: Mapping[str, Any],
    object_set: Mapping[str, Any],
    ledger: Mapping[str, Any],
    coverage: Mapping[str, Any],
    readiness: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    quality = parsed["quality_receipt"]
    body = {
        "schema_version": VS2_WORKBENCH_SCHEMA_VERSION,
        "status": "complex_document_quality_and_lineage_ready",
        "recorded_at": recorded_at,
        "display_scope": "operations_train_internal_source_quality",
        "product_case_enrollment": False,
        "source": {
            "ticker": parsed["source_owner_ticker"],
            "issuer_name": parsed["issuer_name"],
            "document_type": parsed["document_type"],
            "title": parsed["title"],
            "publication_date": parsed["publication_date"],
            "page_count": parsed["page_count"],
            "selected_page_numbers": parsed["selected_page_numbers"],
        },
        "document_quality": {
            "status": quality["status"],
            "complete_document_page_count_verified": quality[
                "complete_document_page_count_verified"
            ],
            "extraction_modes": deepcopy(quality["extraction_modes"]),
            "page_statuses": deepcopy(quality["page_statuses"]),
            "table_region_count": quality["table_region_count"],
            "footnote_count": quality["footnote_count"],
            "low_confidence_material_token_count": quality[
                "low_confidence_material_token_count"
            ],
            "forced_ocr_pages": deepcopy(quality["forced_ocr_pages"]),
        },
        "financial_objects": {
            "object_count": object_set["object_count"],
            "object_type_counts": deepcopy(object_set["object_type_counts"]),
            "cross_page_relation_count": object_set["cross_page_relation_count"],
            "numeric_fact_authority_granted": False,
        },
        "candidate_decision_summary": deepcopy(ledger["decision_counts"]),
        "coverage_summary": {
            "coverage_state": coverage["coverage_state"],
            "accepted_evidence_count": len(
                coverage["accepted_evidence_item_digests"]
            ),
            "reviewed_not_recalled_count": len(
                coverage["reviewed_evidence_not_recalled_digests"]
            ),
            "typed_boundary_count": len(coverage["gap_eligibility_receipts"]),
            "true_public_information_gap_count": 0,
        },
        "pack_binding": deepcopy(readiness["pack_binding"]),
        "hard_boundaries": {
            "candidate_is_not_evidence": True,
            "rank_never_grants_evidence_authority": True,
            "ocr_never_grants_evidence_authority": True,
            "S2_numeric_adjudication_required": True,
            "IFX_is_not_a_current_product_case": True,
            "S1_qualified_stable": False,
        },
    }
    return {**body, "workbench_projection_digest": canonical_json_digest(body)}


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise S1ComplexPdfVerticalError(code)
    return value


def content_id(value: object) -> str:
    return canonical_json_digest(value)[:24]


__all__ = [
    "S1ComplexPdfVerticalError",
    "VS2_RESULT_SCHEMA_VERSION",
    "VS2_RESULT_RESOURCE_ID",
    "build_vs2_artifact_chain",
    "compile_vs2_inline_payloads",
    "compile_vs2_evaluation",
    "validate_vs2_result",
]
