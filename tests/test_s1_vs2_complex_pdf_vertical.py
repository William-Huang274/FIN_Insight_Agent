from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from ingestion.pdf_layout import PdfLayoutParseError, parse_captured_pdf_layout
from retrieval.artifact_spine import (
    ArtifactSpineError,
    canonical_json_digest,
    load_artifact_spine_policy,
)
from retrieval.complex_pdf_vertical import (
    S1ComplexPdfVerticalError,
    validate_vs2_result,
)
from retrieval.financial_objects import FinancialObjectError
from retrieval.pdf_layout_objects import compile_pdf_layout_document
from scripts.data_retrieval.materialize_s1_vs1_vertical_slice import (
    compile_result as compile_vs1_result,
)
from sec_agent.runtime_resource_registry import (
    read_registered_runtime_json,
    resolve_registered_runtime_resource,
)


PRIVATE_ROOT = ROOT / "data/workbench_private/s1_vs2_complex_pdf/v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _policy():
    return load_artifact_spine_policy(
        resolve_registered_runtime_resource(
            ROOT, "application.config.current_s1_artifact_spine_policy"
        )
    )


def test_vs2_formal_result_uses_the_same_complete_spine_without_false_qualification() -> None:
    raw = read_registered_runtime_json(
        ROOT, "application.result.current_s1_vs2_complex_pdf_vertical"
    )
    result = validate_vs2_result(raw, policy=_policy())

    assert len(result["envelopes"]) == 16
    assert {row["artifact_type"] for row in result["envelopes"]} == {
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
    assert result["stage_acceptance"] == {
        "component_engineering_pass": True,
        "vertical_slice_integrated": True,
        "real_scanned_source_qualified": False,
        "S1_qualified_stable": False,
        "complete_product_chain_authorized": False,
    }
    assert result["scope"]["usage_role"] == (
        "train_internal_development_only_not_product_case"
    )
    assert result["evaluation"]["workbench_projection"][
        "product_case_enrollment"
    ] is False


def test_vs2_preserves_complex_business_objects_but_exposes_ranking_failure() -> None:
    result = read_registered_runtime_json(
        ROOT, "application.result.current_s1_vs2_complex_pdf_vertical"
    )
    object_set = result["payloads"]["object_set"]
    assert object_set["object_count"] == 67
    assert object_set["object_type_counts"] == {
        "cross_page_table_continuation_candidate": 1,
        "financial_table_footnote": 1,
        "financial_table_metric_row": 56,
        "financial_table_region": 5,
        "pdf_page_context": 3,
        "revision_or_restatement_context": 1,
    }
    evaluation = result["evaluation"]
    assert evaluation["reviewed_target_count"] == 4
    assert evaluation["reviewed_target_recalled_and_accepted_count"] == 1
    assert evaluation["reviewed_target_not_recalled_count"] == 3
    assert evaluation["candidate_decision_ledger"]["decision_counts"] == {
        "accepted": 1,
        "rejected": 0,
        "unjudged": 0,
        "needs_review": 19,
    }
    assert result["business_result"][
        "current_retrieval_recalled_all_reviewed_complex_objects"
    ] is False
    assert "分部结果总计行、脚注和跨页续表未进入" in result[
        "business_result"
    ]["current_retrieval_failure_zh"]


def test_native_and_ocr_outputs_preserve_locators_and_authority_boundaries() -> None:
    native = _read(PRIVATE_ROOT / "parsed_native_layout.json")
    ocr = _read(PRIVATE_ROOT / "parsed_ocr_mutation.json")
    objects = [
        json.loads(line)
        for line in (PRIVATE_ROOT / "financial_objects.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert native["quality_receipt"]["table_region_count"] == 5
    assert native["quality_receipt"]["footnote_count"] == 1
    assert native["quality_receipt"]["accepted_evidence_authority_granted"] is False
    assert native["quality_receipt"]["numeric_fact_authority_granted"] is False
    assert ocr["quality_receipt"]["forced_ocr_pages"] == [166]
    assert ocr["pages"][0]["page_status"] == "ocr_candidate_needs_review"
    assert ocr["pages"][0]["low_confidence_material_token_count"] == 0
    for anchor in ("Segment Result", "2,560", "3,105", "14,662", "14,955"):
        assert anchor in ocr["pages"][0]["text"]

    revision = next(
        row
        for row in objects
        if row["evidence_type"] == "revision_or_restatement_context"
    )
    assert revision["metadata"]["locator_type"] == "page_bbox"
    assert "comparative figures for the previous year" in revision["text"]
    continuation = next(
        row
        for row in objects
        if row["evidence_type"] == "cross_page_table_continuation_candidate"
    )
    assert continuation["metadata"]["left_page"] == 166
    assert continuation["metadata"]["right_page"] == 167
    assert continuation["metadata"]["matching_numeric_tokens"] == [
        "(18)",
        "(545)",
        "2,560",
        "3,105",
    ]
    assert all(
        row["metadata"]["candidate_is_not_evidence"] is True
        and row["metadata"]["numeric_fact_authority"] is False
        for row in objects
    )


def test_parser_object_and_result_mutations_fail_closed() -> None:
    metadata_path = (
        ROOT
        / "data/raw_private/global_public_disclosures/eu_regulated/IFX_DE/2025/"
        "ANNUAL_REPORT/locator_metadata.json"
    )
    metadata = _read(metadata_path)
    bad_capture = deepcopy(metadata)
    bad_capture["sha256"] = "0" * 64
    with pytest.raises(PdfLayoutParseError, match="raw_capture_digest_mismatch"):
        parse_captured_pdf_layout(
            bad_capture,
            repository_root=ROOT,
            selected_page_numbers=[166],
        )

    native = _read(PRIVATE_ROOT / "parsed_native_layout.json")
    source_spec = _read(
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1_vs2_ifx_complex_pdf_source_spec_v1_0.json"
    )
    bad_parsed = deepcopy(native)
    bad_parsed["pages"][0]["text"] += " mutation"
    with pytest.raises(FinancialObjectError, match="page_text_digest_mismatch"):
        compile_pdf_layout_document(
            bad_parsed,
            source_spec=source_spec,
            parsed_ref="private/parsed.json",
            parsed_sha256="0" * 64,
        )

    result = deepcopy(
        read_registered_runtime_json(
            ROOT, "application.result.current_s1_vs2_complex_pdf_vertical"
        )
    )
    result["business_result"]["parser_preserved_cross_page_continuation"] = False
    with pytest.raises(S1ComplexPdfVerticalError, match="result_digest_invalid"):
        validate_vs2_result(result, policy=_policy())


def test_cross_case_scope_and_s2_authority_mutations_fail_closed() -> None:
    result = deepcopy(
        read_registered_runtime_json(
            ROOT, "application.result.current_s1_vs2_complex_pdf_vertical"
        )
    )
    request = next(
        row for row in result["envelopes"] if row["artifact_type"] == "evidence_request"
    )
    request["scope"]["case_key"] = "DELL"
    request["scope"]["subject_ticker"] = "DELL"
    result["result_digest"] = canonical_json_digest(
        {key: value for key, value in result.items() if key != "result_digest"}
    )
    with pytest.raises(ArtifactSpineError, match="artifact_chain_case_scope_drift"):
        validate_vs2_result(result, policy=_policy())

    result = deepcopy(
        read_registered_runtime_json(
            ROOT, "application.result.current_s1_vs2_complex_pdf_vertical"
        )
    )
    result["payloads"]["s2_sibling_binding"][
        "numeric_fact_authority_granted"
    ] = True
    with pytest.raises(S1ComplexPdfVerticalError, match="result_digest_invalid"):
        validate_vs2_result(result, policy=_policy())


def test_result_local_payload_refs_must_resolve_and_match_the_envelope_digest() -> None:
    result = deepcopy(
        read_registered_runtime_json(
            ROOT, "application.result.current_s1_vs2_complex_pdf_vertical"
        )
    )
    del result["payloads"]["workbench_projection"]
    result["result_digest"] = canonical_json_digest(
        {key: value for key, value in result.items() if key != "result_digest"}
    )
    with pytest.raises(
        ArtifactSpineError,
        match="artifact_inline_payload_missing:workbench_projection",
    ):
        validate_vs2_result(result, policy=_policy())

    result = deepcopy(
        read_registered_runtime_json(
            ROOT, "application.result.current_s1_vs2_complex_pdf_vertical"
        )
    )
    result["payloads"]["candidate_set"]["source_record_ids"].reverse()
    result["result_digest"] = canonical_json_digest(
        {key: value for key, value in result.items() if key != "result_digest"}
    )
    with pytest.raises(
        ArtifactSpineError,
        match="artifact_inline_payload_digest_mismatch:candidate_set",
    ):
        validate_vs2_result(result, policy=_policy())


def test_vs1_replay_is_byte_stable_after_vs2_parser_and_object_contracts() -> None:
    existing = read_registered_runtime_json(
        ROOT, "application.result.current_s1_vs1_vertical_slice"
    )
    replay = compile_vs1_result()
    assert replay["result_digest"] == existing["result_digest"]
    assert json.loads(json.dumps(replay, ensure_ascii=False)) == existing
