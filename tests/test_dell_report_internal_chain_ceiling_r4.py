from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

from retrieval.dell_report_internal_chain_ceiling_r4 import (
    ATTEMPT_ID,
    ATTEMPT_RECEIPT_REF,
    AUTHORITY,
    BRANCH,
    EXECUTION_CONTRACT,
    EXPECTED_BOUND_INPUT_IDS,
    EXPECTED_IMPLEMENTATION_PATHS,
    POLICY_REF,
    POLICY_SCHEMA_VERSION,
    PRIVATE_REF,
    PROGRAM_ID,
    PUBLIC_REF,
    SEMANTIC_CONTRACT,
    DellReportInternalChainCeilingR4Error,
    assess_dell_report_internal_chain_r4_packages,
    classify_dell_report_internal_chain_r4_package,
    validate_dell_report_internal_chain_ceiling_r4_policy,
)
from retrieval.query_plan import canonical_digest


def _metadata(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "source_type": "PUBLIC_WEB",
        "source_tier": "named_counterparty_or_standards_primary",
        "publication_date": "2025-05-27",
    }


def _source(source_id: str, text: str, ticker: str = "NVDA") -> dict:
    return {
        "evidence_id": source_id,
        "text": text,
        "metadata": {},
        **_metadata(ticker),
    }


def _object(
    object_id: str,
    source_id: str,
    text: str,
    *,
    ticker: str = "NVDA",
    char_start: int | None = None,
    page_id: str | None = None,
    slice_id: str | None = None,
) -> dict:
    base = {
        "source_record_id": source_id,
        "focus_binding": (
            {"mode": "offset_bound_text", "char_start": char_start, "char_end": char_start + len(text)}
            if char_start is not None
            else {"mode": "parent_context"}
        ),
        **_metadata(ticker),
    }
    if page_id:
        base["source_lineage"] = {
            "source_page_record_id": page_id,
            "source_slice_record_id": slice_id or source_id,
        }
    return {
        "compiled_object_id": object_id,
        "candidate_not_evidence": True,
        "evidence_promoted": False,
        "numeric_authority": False,
        "lineage_source_record_ids": [source_id],
        "model_text": text,
        "base_object_view": base,
    }


@pytest.mark.parametrize(
    ("target_id", "text"),
    [
        (
            "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
            "Dell and NVIDIA have not partnered and do not collaborate on delivery.",
        ),
        (
            "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
            "Current wafer manufacturing yield rate is 90%, a target for future A14 SRAM.",
        ),
        (
            "DELL-RSQ-03A-TARGET-UNITS",
            "The university confirmed delivery of four Dell PowerEdge XE9680 AI systems in fiscal Q1.",
        ),
    ],
)
def test_R4_audit_counterexamples_are_not_complete(target_id: str, text: str) -> None:
    result = classify_dell_report_internal_chain_r4_package(
        target_id=target_id,
        text=text,
        metadata=_metadata(),
    )
    assert result["classification"] != "complete_bounded_target_package"


def test_R4_positive_supplier_and_Dell_seller_period_units_still_pass() -> None:
    supplier = classify_dell_report_internal_chain_r4_package(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        text=(
            "Dell and NVIDIA have partnered for decades. Dell servers with "
            "NVIDIA GB200 are shipping at scale."
        ),
        metadata=_metadata(),
    )
    units = classify_dell_report_internal_chain_r4_package(
        target_id="DELL-RSQ-03A-TARGET-UNITS",
        text=(
            "Dell delivered four PowerEdge XE9680 AI systems during fiscal Q1 "
            "2026."
        ),
        metadata=_metadata("DELL"),
    )
    assert supplier["classification"] == "complete_bounded_target_package"
    assert units["classification"] == "complete_bounded_target_package"
    assert "Dell_seller_or_shipper_role" in units["matched_group_ids"]
    assert "company_period_surface" in units["matched_group_ids"]


def test_R4_generic_Dell_supply_or_delivery_text_is_not_supplier_material_gap() -> None:
    source_id = "SRC::GENERIC-DELL-DELIVERY"
    result = assess_dell_report_internal_chain_r4_packages(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        source_rows=[
            _source(
                source_id,
                "Dell Technologies drives global growth by delivering solutions "
                "through its worldwide supply chain.",
                "DELL",
            )
        ],
        object_rows=[],
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 0


def test_R4_far_apart_price_and_configuration_do_not_form_ASP_package() -> None:
    source_id = "SRC::DISTANT-ASP"
    price = "Dell quoted a purchase price of $757,231 including support and switches."
    configuration = "The two Dell PowerEdge XE9680 AI server nodes are configured systems."
    objects = [_object("COBJ::PRICE", source_id, price, ticker="ORG::BUYER")]
    objects.extend(
        _object(
            f"COBJ::NOISE::{index:03d}",
            source_id,
            f"Unrelated same-source administrative object number {index}.",
            ticker="ORG::BUYER",
        )
        for index in range(300)
    )
    objects.append(
        _object("COBJ::CONFIG", source_id, configuration, ticker="ORG::BUYER")
    )
    result = assess_dell_report_internal_chain_r4_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, f"{price} {configuration}", "ORG::BUYER")],
        object_rows=objects,
    )
    assert result["compiled_packages"][0]["classification"] != (
        "complete_bounded_target_package"
    )


def test_R4_adjacent_price_and_configuration_form_bounded_ASP_package() -> None:
    source_id = "SRC::ADJACENT-ASP"
    price = "Dell quoted a purchase price of $757,231 including support and switches."
    configuration = "The two Dell PowerEdge XE9680 AI server nodes are configured systems."
    result = assess_dell_report_internal_chain_r4_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, f"{price} {configuration}", "ORG::BUYER")],
        object_rows=[
            _object("COBJ::PRICE", source_id, price, ticker="ORG::BUYER"),
            _object("COBJ::CONFIG", source_id, configuration, ticker="ORG::BUYER"),
        ],
        selected_object_ids={"COBJ::PRICE", "COBJ::CONFIG"},
        rank_by_object_id={"COBJ::PRICE": 2, "COBJ::CONFIG": 16},
    )
    package = result["compiled_packages"][0]
    assert package["classification"] == "complete_bounded_target_package"
    assert package["completion_rank"] == 16
    assert package["window_unit_span"] <= 8


def _real_R39_family() -> tuple[list[dict], list[dict]]:
    page_id = "PUBLIC::DELL-EXT::2184F13EB685F627C757"
    source_path = (
        ROOT
        / "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
        "v5/records.jsonl"
    )
    sources = [
        json.loads(line)
        for line in source_path.read_text(encoding="utf-8").splitlines()
        if page_id in line
    ]
    object_path = (
        ROOT
        / "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
        "v9/objects.jsonl"
    )
    objects = []
    with object_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if page_id not in line:
                continue
            row = json.loads(line)
            lineage = (
                (row.get("base_object_view") or {}).get("source_lineage") or {}
            )
            if lineage.get("source_page_record_id") == page_id:
                objects.append(row)
    return sources, objects


def test_R4_R39_factory_claim_closes_one_canonical_gap_not_two_occurrences() -> None:
    sources, objects = _real_R39_family()
    without_repair = [
        row
        for row in objects
        if "factories can ship thousands" not in str(row.get("model_text") or "")
    ]
    missing = assess_dell_report_internal_chain_r4_packages(
        target_id="DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
        source_rows=sources,
        object_rows=without_repair,
    )
    repaired = assess_dell_report_internal_chain_r4_packages(
        target_id="DELL-RSQ-03A-TARGET-CAPACITY-RELEASE",
        source_rows=sources,
        object_rows=objects,
    )
    assert missing["coverage_gap_canonical_family_claim_count"] == 1
    assert missing["coverage_gap_source_occurrence_count"] == 2
    gap = missing["coverage_gaps"][0]
    assert "thousands" in gap["material_anchors"]
    assert "week" in gap["material_anchors"]
    assert repaired["coverage_gap_canonical_family_claim_count"] == 0
    assert repaired["coverage_gap_source_occurrence_count"] == 0


def test_R4_R39_units_do_not_create_false_local_repair_obligations() -> None:
    sources, objects = _real_R39_family()
    result = assess_dell_report_internal_chain_r4_packages(
        target_id="DELL-RSQ-03A-TARGET-UNITS",
        source_rows=sources,
        object_rows=objects,
    )
    assert result["coverage_gap_canonical_family_claim_count"] == 0
    assert result["coverage_gap_source_occurrence_count"] == 0


def test_R4_real_R39_ASP_pair_remains_a_rank_16_reranker_case() -> None:
    selected_ids = {
        "COBJ::f042c5df4e6d3a1aa92564c0",
        "COBJ::1c6a8e27529b35e3e733b0ad",
    }
    object_path = (
        ROOT
        / "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
        "v9/objects.jsonl"
    )
    selected_rows = []
    all_rows = []
    page_id = ""
    with object_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not any(object_id in line for object_id in selected_ids):
                continue
            row = json.loads(line)
            selected_rows.append(row)
            page_id = row["base_object_view"]["source_lineage"][
                "source_page_record_id"
            ]
    assert len(selected_rows) == 2 and page_id
    with object_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if page_id in line:
                row = json.loads(line)
                lineage = (
                    (row.get("base_object_view") or {}).get("source_lineage")
                    or {}
                )
                if lineage.get("source_page_record_id") == page_id:
                    all_rows.append(row)
    source_path = (
        ROOT
        / "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
        "v5/records.jsonl"
    )
    sources = [
        json.loads(line)
        for line in source_path.read_text(encoding="utf-8").splitlines()
        if page_id in line
    ]
    result = assess_dell_report_internal_chain_r4_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=sources,
        object_rows=all_rows,
        selected_object_ids=selected_ids,
        rank_by_object_id={
            "COBJ::f042c5df4e6d3a1aa92564c0": 15,
            "COBJ::1c6a8e27529b35e3e733b0ad": 16,
        },
    )
    package = result["compiled_packages"][0]
    assert package["classification"] == "complete_bounded_target_package"
    assert package["completion_rank"] == 16
    assert package["window_unit_span"] <= 8


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _R4_policy_inputs() -> tuple[dict, dict[str, dict]]:
    refs = {
        "R1_policy": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_0.json",
        "R3_policy": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_2.json",
        "R3_public": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_2.json",
        "R3_private": "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r3/full_result.json",
        "R3_fresh_audit": "configs/audits/fin_ia_0_1_3_commit_28158e04_dell_03b_r3_fresh_audit_fail_v1_0.json",
        "R39_repair_result": "configs/retrieval/fin_ia_0_1_3_s1_abbreviation_claim_repair_successor_result_v1_0.json",
        "R39_embedding_result": "configs/retrieval/fin_ia_0_1_3_s1c_qwen_embedding_cache_successor_result_v1_3.json",
        "R39_route_policy": "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_6.json",
        "R39_hybrid_policy": "configs/retrieval/fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_9.json",
        "runtime_registry": "configs/runtime/fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json",
        "runtime_binding_receipt": "configs/runtime/fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_15.json",
        "residual_program": "configs/retrieval/fin_ia_0_1_3_s1_dell_report_residual_source_ladder_program_v1_1.json",
        "execution_program": "configs/retrieval/fin_ia_0_1_3_s1_dell_proposition_coverage_execution_program_v1_3.json",
        "dell_product_readiness": "configs/retrieval/fin_ia_0_1_3_s1_dell_current_product_readiness_result_v1_7.json",
    }
    assert set(refs) == EXPECTED_BOUND_INPUT_IDS
    values = {
        key: json.loads((ROOT / ref).read_text(encoding="utf-8"))
        for key, ref in refs.items()
    }
    policy = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "status": "same_stage_R4_execution_authorized_after_fresh_R3_audit_failure",
        "program_id": PROGRAM_ID,
        "attempt_id": ATTEMPT_ID,
        "recorded_at": "2026-08-26",
        "execution_contract": deepcopy(EXECUTION_CONTRACT),
        "semantic_contract": deepcopy(SEMANTIC_CONTRACT),
        "output_contract": {
            "policy_ref": POLICY_REF,
            "private_result_ref": PRIVATE_REF,
            "public_result_ref": PUBLIC_REF,
            "attempt_consumption_receipt_ref": ATTEMPT_RECEIPT_REF,
            "alternate_output_paths_authorized": False,
            "private_public_same_path_authorized": False,
            "exclusive_create_required": True,
            "atomic_pair_with_rollback_required": True,
            "same_attempt_retry_authorized": False,
        },
        "bound_inputs": {
            key: {"ref": ref, "sha256": _sha(ROOT / ref)}
            for key, ref in refs.items()
        },
        "execution_identity": {
            "branch": BRANCH,
            "implementation_commit": "a" * 40,
            "implementation_tree": "b" * 40,
            "authority_commit_changed_paths": [POLICY_REF],
            "authority_commit_parent_must_equal_implementation_commit": True,
            "HEAD_must_equal_upstream": True,
        },
        "implementation_bindings": [
            {"path": path, "sha256": "c" * 64}
            for path in sorted(EXPECTED_IMPLEMENTATION_PATHS)
        ],
        "TokenBudgetBasis": {
            "node_purpose": "one exact R4 local candidate-chain audit",
            "input_scale": "five requests, 1,888 sources, 34,199 objects",
            "required_outputs": "bounded packages, material coverage and route eligibility",
            "schema_burden": "R3 audit, R39 runtime, ranks and zero-authority counters",
            "materiality_quality_risk": "false gaps or false ASP, supplier, yield and units",
            "comparable_run_evidence": "immutable R3 plus fresh failed audit and R39 repair",
            "reasoning_profile": "one local 0.6B query batch and deterministic classification",
            "stop_and_truncation": "any identity, count, rank or authority drift stops",
        },
        "authority": deepcopy(AUTHORITY),
    }
    policy["result_digest"] = canonical_digest(policy)
    return policy, values


def _validate_policy(policy: dict, values: dict[str, dict]) -> dict:
    return validate_dell_report_internal_chain_ceiling_r4_policy(
        policy,
        r1_policy=values["R1_policy"],
        r3_policy=values["R3_policy"],
        r3_public=values["R3_public"],
        r3_private=values["R3_private"],
        r3_fresh_audit=values["R3_fresh_audit"],
        r39_repair_result=values["R39_repair_result"],
        r39_embedding_result=values["R39_embedding_result"],
        r39_route_policy=values["R39_route_policy"],
        r39_hybrid_policy=values["R39_hybrid_policy"],
        runtime_registry=values["runtime_registry"],
        runtime_binding_receipt=values["runtime_binding_receipt"],
        residual_program=values["residual_program"],
        execution_program=values["execution_program"],
        dell_product_readiness=values["dell_product_readiness"],
    )


def test_R4_policy_binds_failed_R3_audit_and_R39_runtime() -> None:
    policy, values = _R4_policy_inputs()
    legacy = _validate_policy(policy, values)
    assert len(legacy["target_contracts"]) == 6


def test_R4_policy_rejects_removed_finding_and_route_mode_drift() -> None:
    policy, values = _R4_policy_inputs()
    audit_drift = deepcopy(values)
    audit_drift["R3_fresh_audit"] = deepcopy(values["R3_fresh_audit"])
    audit_drift["R3_fresh_audit"]["material_findings"] = []
    body = dict(audit_drift["R3_fresh_audit"])
    body.pop("result_digest")
    audit_drift["R3_fresh_audit"]["result_digest"] = canonical_digest(body)
    with pytest.raises(DellReportInternalChainCeilingR4Error, match="required_findings"):
        _validate_policy(policy, audit_drift)

    route_drift = deepcopy(values)
    route_drift["R39_route_policy"] = deepcopy(values["R39_route_policy"])
    route_drift["R39_route_policy"]["object_compiler"][
        "claim_segmentation_mode"
    ] = "sentence_with_wrapped_line_reflow_v1"
    with pytest.raises(DellReportInternalChainCeilingR4Error, match="runtime_policy"):
        _validate_policy(policy, route_drift)
