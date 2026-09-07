from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

from retrieval.dell_report_internal_chain_ceiling_r3 import (
    ATTEMPT_ID,
    ATTEMPT_RECEIPT_REF,
    BRANCH,
    EXECUTION_CONTRACT,
    INHERITED_WITHOUT_CHANGE,
    ONLY_SUCCESSOR_CHANGES,
    POLICY_REF,
    POLICY_SCHEMA_VERSION,
    PRIVATE_REF,
    PUBLIC_REF,
    SEMANTIC_CONTRACT,
    AUTHORITY,
    DellReportInternalChainCeilingR3Error,
    assess_dell_report_internal_chain_r3_packages,
    build_dell_report_internal_chain_ceiling_r3_public_projection,
    classify_dell_report_internal_chain_r3_package,
    compile_dell_report_internal_chain_ceiling_r3_result,
    validate_dell_report_internal_chain_ceiling_r3_execution,
    validate_dell_report_internal_chain_ceiling_r3_policy,
)
from retrieval.query_plan import canonical_digest


pytestmark = pytest.mark.requires_local_data

ROOT = Path(__file__).resolve().parents[1]
R1_POLICY_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_0.json"
)
R1_FAILURE_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_r1_failure_receipt_v1_0.json"
)
R2_POLICY_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_1.json"
)
R2_PUBLIC_PATH = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_1.json"
)
R2_PRIVATE_PATH = (
    ROOT
    / "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/"
    "dell-rsq-03b-internal-chain-r2/full_result.json"
)
R2_AUDIT_PATH = (
    ROOT
    / "configs/audits/fin_ia_0_1_3_commit_2a604156_dell_03b_r2_fresh_audit_fail_v1_0.json"
)
RUNNER_PATH = (
    ROOT
    / "scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r3.py"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reseal(value: dict, field: str = "result_digest") -> None:
    value[field] = canonical_digest(
        {key: row for key, row in value.items() if key != field}
    )


@pytest.fixture(scope="module")
def bound_inputs() -> dict[str, dict]:
    r1 = _read(R1_POLICY_PATH)
    bindings = r1["bound_inputs"]
    return {
        "r1": r1,
        "r1_failure": _read(R1_FAILURE_PATH),
        "r2": _read(R2_POLICY_PATH),
        "r2_public": _read(R2_PUBLIC_PATH),
        "r2_private": _read(R2_PRIVATE_PATH),
        "r2_audit": _read(R2_AUDIT_PATH),
        "residual": _read(ROOT / bindings["residual_program_ref"]),
        "execution_program": _read(ROOT / bindings["execution_program_ref"]),
        # The current-runtime registry path advanced to R39. R3 remains an
        # immutable R38 attempt and must be replayed against the exact identity
        # sealed by R1, never against whatever the current pointer contains.
        "registry": {
            "registry_id": bindings["runtime_registry_id"],
            "resource_canonical_digest": bindings["runtime_registry_digest"],
        },
        "receipt": _read(ROOT / bindings["runtime_binding_receipt_ref"]),
    }


@pytest.fixture(scope="module")
def runner_module():
    spec = importlib.util.spec_from_file_location("dell_03B_R3_runner", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _r3_policy(inputs: dict[str, dict]) -> dict:
    value = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "status": "same_stage_R3_execution_authorized_after_fresh_R2_audit_failure",
        "program_id": "FIN-0.1.3-S1-DELL-RSQ-03B-R3",
        "attempt_id": ATTEMPT_ID,
        "recorded_at": "2026-08-25T00:00:00+08:00",
        "predecessor": {
            "R1_policy_ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_0.json",
            "R1_policy_sha256": _sha(R1_POLICY_PATH),
            "R1_failure_ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_r1_failure_receipt_v1_0.json",
            "R1_failure_sha256": _sha(R1_FAILURE_PATH),
            "R2_policy_ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_policy_v1_1.json",
            "R2_policy_sha256": _sha(R2_POLICY_PATH),
            "R2_public_ref": "configs/retrieval/fin_ia_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling_result_v1_1.json",
            "R2_public_sha256": _sha(R2_PUBLIC_PATH),
            "R2_public_digest": inputs["r2_public"]["result_digest"],
            "R2_private_ref": "data/workbench_private/fin_0_1_3_s1_dell_03b_internal_chain_candidate_ceiling/dell-rsq-03b-internal-chain-r2/full_result.json",
            "R2_private_sha256": _sha(R2_PRIVATE_PATH),
            "R2_private_digest": inputs["r2_private"]["result_digest"],
            "R2_audit_ref": "configs/audits/fin_ia_0_1_3_commit_2a604156_dell_03b_r2_fresh_audit_fail_v1_0.json",
            "R2_audit_sha256": _sha(R2_AUDIT_PATH),
            "R2_audit_digest": inputs["r2_audit"]["result_digest"],
            "R2_result_commit": "2a604156777a027d06a15c3e379632d945c70703",
            "R2_result_tree": "2baf3d50282f1cd76c9775e429d0556bbc631da5",
        },
        "inherited_without_change": deepcopy(INHERITED_WITHOUT_CHANGE),
        "only_successor_changes": deepcopy(ONLY_SUCCESSOR_CHANGES),
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
            for path in sorted(
                {
                    "src/retrieval/dell_report_internal_chain_ceiling.py",
                    "src/retrieval/dell_report_internal_chain_ceiling_r3.py",
                    "scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r3.py",
                    "apps/workbench/backend/application/research_retrieval_service.py",
                }
            )
        ],
        "TokenBudgetBasis": {
            "node_purpose": "sealed same-stage R3 rerun",
            "input_scale": "five requests, 1,888 sources, 34,198 objects",
            "required_outputs": "bounded packages and exact route eligibility",
            "schema_burden": "raw receipt, source coverage, atomic pair",
            "materiality_quality_risk": "false ASP, units, relationship or allocation",
            "comparable_run_evidence": "immutable R2 plus failed fresh audit",
            "reasoning_profile": "one local 0.6B query batch and deterministic rules",
            "stop_and_truncation": "any identity, count, rank, authority or output drift stops",
        },
        "authority": deepcopy(AUTHORITY),
        "known_boundary": "candidate not evidence",
    }
    _reseal(value)
    return value


def _validate_policy(value: dict, inputs: dict[str, dict]) -> dict:
    return validate_dell_report_internal_chain_ceiling_r3_policy(
        value,
        r2_policy=inputs["r2"],
        r1_policy=inputs["r1"],
        r1_failure_receipt=inputs["r1_failure"],
        r2_public_result=inputs["r2_public"],
        r2_private_result=inputs["r2_private"],
        r2_audit=inputs["r2_audit"],
        residual_program=inputs["residual"],
        execution_program=inputs["execution_program"],
        runtime_registry=inputs["registry"],
        runtime_binding_receipt=inputs["receipt"],
    )


def test_R3_policy_binds_failed_R2_and_exact_delta(bound_inputs) -> None:
    value = _r3_policy(bound_inputs)
    inherited = _validate_policy(value, bound_inputs)
    assert inherited["program_id"] == "FIN-0.1.3-S1-DELL-RSQ-03B-R1"
    assert value["predecessor"]["R2_audit_digest"] == bound_inputs["r2_audit"][
        "result_digest"
    ]
    assert value["execution_contract"]["candidate_union_count_per_request"] == 96


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (
            lambda value: value["execution_contract"].update(
                {"candidate_union_count_per_request": 95}
            ),
            "dell_03B_R3_execution_contract_invalid",
        ),
        (
            lambda value: value["semantic_contract"].update(
                {"evidence_unit_mode": "whole_filing"}
            ),
            "dell_03B_R3_semantic_contract_invalid",
        ),
        (
            lambda value: value["output_contract"].update(
                {"alternate_output_paths_authorized": True}
            ),
            "dell_03B_R3_output_contract_invalid",
        ),
        (
            lambda value: value["authority"].update({"reranker_authorized": True}),
            "dell_03B_R3_authority_invalid",
        ),
        (
            lambda value: value["predecessor"].update(
                {"R2_result_commit": "d" * 40}
            ),
            "dell_03B_R3_predecessor_identity_invalid",
        ),
    ],
)
def test_R3_policy_mutations_fail_closed(bound_inputs, mutation, reason) -> None:
    value = _r3_policy(bound_inputs)
    mutation(value)
    _reseal(value)
    with pytest.raises(DellReportInternalChainCeilingR3Error, match=reason):
        _validate_policy(value, bound_inputs)


def _seed(object_id: str, raw_rank: int, final_rank: int | None) -> dict:
    return {
        "compiled_object_id": object_id,
        "rank_trace": {
            "raw_union_rank": raw_rank,
            "financial_rank": raw_rank,
            "review_priority_rank": raw_rank,
            "final_output_rank": final_rank,
        },
        "route_membership": ["bm25_lexical"],
        "route_ranks": {
            "bm25_lexical": raw_rank,
            "qwen3_embedding_0_6b_dense": None,
            "typed_relationship_graph": None,
        },
        "material_alignment_state": "eligible_not_reserved",
        "candidate_not_evidence": True,
        "evidence_promoted": False,
        "numeric_authority": False,
    }


def _execution(request_ids: list[str]) -> dict:
    request_results = []
    for request_index, request_id in enumerate(request_ids, start=1):
        seeds = [
            _seed(
                f"COBJ::{request_index:02d}::{rank:03d}",
                rank,
                rank if rank <= 16 else None,
            )
            for rank in range(1, 97)
        ]
        request_results.append(
            {
                "request": {"request_id": request_id},
                "projection_digest": f"DIGEST::{request_id}",
                "summary": {
                    "typed_fact_resolved_count": 0,
                    "typed_fact_gap_count": 1,
                    "typed_fact_conflict_count": 0,
                },
                "route_execution_truth": {
                    "narrative_route_requests": [
                        {"routes": [{"execution_state": "executed"}]}
                    ],
                    "typed_fact_route_requests": [],
                },
                "hybrid_object_retrieval": {
                    "candidate_decision_seed": seeds,
                    "candidates": [
                        {"compiled_object_id": seed["compiled_object_id"]}
                        for seed in seeds[:16]
                    ],
                },
            }
        )
    body = {
        "schema_version": "test",
        "status": "current_runtime_request_batch_zero_call_executed",
        "product_mode": "current",
        "case_key": "DELL",
        "summary": {
            "request_count": 5,
            "compiled_lane_count": 5,
            "snapshot_nonempty_lane_count": 5,
            "hybrid_selected_candidate_count": 80,
            "hybrid_union_candidate_count": 480,
            "typed_fact_resolved_count": 0,
            "typed_fact_gap_count": 5,
            "typed_fact_conflict_count": 0,
            "numeric_fact_count": 0,
            "material_scope_required_request_count": 0,
            "material_scope_ready_request_count": 5,
            "material_set_complete_request_count": 5,
            "local_embedding_inference_batches": 1,
            "network_calls": 0,
            "model_calls": 0,
            "generation_model_calls": 0,
            "provider_calls": 0,
            "external_capture_calls": 0,
            "4B_embedding_calls": 0,
            "reranker_calls": 0,
            "retries": 0,
            "current_mutations": 0,
            "candidate_promotions": 0,
            "evidence_promotions": 0,
            "gap_closures": 0,
        },
        "material_scope": {},
        "material_compilation_receipts": [],
        "request_results": request_results,
        "known_boundary": "test",
    }
    return {**body, "projection_digest": canonical_digest(body)}


@pytest.fixture()
def exact_execution(bound_inputs) -> tuple[list[str], dict]:
    request_ids = sorted(
        {
            request_id
            for contract in bound_inputs["r1"]["target_contracts"]
            for request_id in contract["request_ids"]
        }
    )
    return request_ids, _execution(request_ids)


def test_R3_exact_execution_accepts_5_by_96_by_16(exact_execution) -> None:
    request_ids, value = exact_execution
    result = validate_dell_report_internal_chain_ceiling_r3_execution(
        value, expected_request_ids=request_ids
    )
    assert len(result["request_results"]) == 5
    assert result["summary"]["local_embedding_inference_batches"] == 1


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (
            lambda value: value["summary"].update(
                {"local_embedding_inference_batches": 0}
            ),
            "dell_03B_R3_fresh_batch_count_invalid",
        ),
        (
            lambda value: value["summary"].update({"provider_calls": 1}),
            "dell_03B_R3_execution_authority_invalid:provider_calls",
        ),
        (
            lambda value: value["request_results"].append(
                deepcopy(value["request_results"][0])
            ),
            "dell_03B_R3_request_result_count_invalid",
        ),
        (
            lambda value: value["request_results"][0]["hybrid_object_retrieval"][
                "candidate_decision_seed"
            ].pop(),
            "dell_03B_R3_union_count_invalid",
        ),
        (
            lambda value: value["request_results"][0]["hybrid_object_retrieval"][
                "candidates"
            ].pop(),
            "dell_03B_R3_final_count_invalid",
        ),
        (
            lambda value: value["request_results"][0]["hybrid_object_retrieval"][
                "candidate_decision_seed"
            ][1]["rank_trace"].update({"raw_union_rank": 1}),
            "dell_03B_R3_raw_rank_permutation_invalid",
        ),
        (
            lambda value: value["request_results"][0]["hybrid_object_retrieval"][
                "candidate_decision_seed"
            ][1]["rank_trace"].update({"final_output_rank": 1}),
            "dell_03B_R3_final_rank_permutation_invalid",
        ),
    ],
)
def test_R3_execution_attacks_fail_closed(exact_execution, mutation, reason) -> None:
    request_ids, original = exact_execution
    value = deepcopy(original)
    mutation(value)
    _reseal(value, "projection_digest")
    with pytest.raises(DellReportInternalChainCeilingR3Error, match=reason):
        validate_dell_report_internal_chain_ceiling_r3_execution(
            value, expected_request_ids=request_ids
        )


def _metadata(ticker: str = "ORG::BUYER") -> dict:
    return {
        "ticker": ticker,
        "source_type": "PUBLIC_PDF",
        "source_tier": "issuer_regulator_or_government_primary",
        "publication_date": "2025-07-23",
    }


def test_Wendell_is_not_Dell_and_generic_collaboration_is_not_relationship() -> None:
    result = classify_dell_report_internal_chain_r3_package(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        text=(
            "Thank you, Wendell. Taiwan Semiconductor collaborates closely with "
            "CPU customers on manufacturing capacity."
        ),
        metadata=_metadata("TSM"),
    )
    assert result["classification"] == "not_target_semantic_equivalent"
    assert "dell_subject" not in result["matched_group_ids"]


def test_supplier_directional_morphology_is_complete_but_allocation_stays_open() -> None:
    result = classify_dell_report_internal_chain_r3_package(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        text=(
            "Dell and NVIDIA have partnered for decades. Dell servers with NVIDIA "
            "GB200 are shipping at scale."
        ),
        metadata=_metadata("NVDA"),
    )
    assert result["classification"] == "complete_bounded_target_package"
    assert "supplier_capacity_or_allocation_readthrough_remains_open" in result[
        "limitations"
    ]


def test_GPU_count_and_procurement_systems_are_not_Dell_company_units() -> None:
    for text in (
        "Dell deployed 100,000 NVIDIA GPUs in six weeks.",
        "Purchase agreement for four Dell PowerEdge AI systems with delivery and support.",
    ):
        result = classify_dell_report_internal_chain_r3_package(
            target_id="DELL-RSQ-03A-TARGET-UNITS",
            text=text,
            metadata=_metadata("DELL"),
        )
        assert result["classification"] != "complete_bounded_target_package"


def test_future_A14_SRAM_yield_is_not_current_Dell_supply_yield() -> None:
    result = classify_dell_report_internal_chain_r3_package(
        target_id="DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD",
        text="Future A14 SRAM manufacturing yield target is 90% for the next process.",
        metadata=_metadata("TSM"),
    )
    assert result["classification"] != "complete_bounded_target_package"


def _source(source_id: str, text: str, ticker: str = "ORG::BUYER") -> dict:
    return {"evidence_id": source_id, "text": text, **_metadata(ticker)}


def _object(object_id: str, source_id: str, text: str, ticker: str = "ORG::BUYER") -> dict:
    return {
        "compiled_object_id": object_id,
        "candidate_not_evidence": True,
        "evidence_promoted": False,
        "numeric_authority": False,
        "lineage_source_record_ids": [source_id],
        "model_text": text,
        "base_object_view": {
            "source_record_id": source_id,
            **_metadata(ticker),
            "period_end": "",
            "section": "test",
            "subsection": "test",
        },
    }


def test_same_source_adjacent_slices_form_ASP_package_at_rank_16() -> None:
    source_id = "SRC::ASP"
    quote = "Dell quoted $757,231 as the purchase price including support and switches."
    configuration = "The two PowerEdge XE9680 GPU worker nodes are the configured AI systems."
    result = assess_dell_report_internal_chain_r3_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[_source(source_id, f"{quote} {configuration}")],
        object_rows=[
            _object("COBJ::QUOTE", source_id, quote),
            _object("COBJ::CONFIG", source_id, configuration),
        ],
        selected_object_ids={"COBJ::QUOTE", "COBJ::CONFIG"},
        rank_by_object_id={"COBJ::QUOTE": 2, "COBJ::CONFIG": 16},
    )
    package = result["compiled_packages"][0]
    assert package["classification"] == "complete_bounded_target_package"
    assert package["completion_rank"] == 16
    assert "not_company_wide_realized_ASP" in package["limitations"]


def test_different_sources_never_blindly_concatenate_ASP_roles() -> None:
    result = assess_dell_report_internal_chain_r3_packages(
        target_id="DELL-RSQ-03A-TARGET-ASP",
        source_rows=[
            _source("SRC::QUOTE", "Dell quoted $757,231 as purchase price."),
            _source("SRC::CONFIG", "The two PowerEdge XE9680 AI server nodes."),
        ],
        object_rows=[
            _object("COBJ::QUOTE", "SRC::QUOTE", "Dell quoted $757,231 as purchase price."),
            _object("COBJ::CONFIG", "SRC::CONFIG", "The two PowerEdge XE9680 AI server nodes."),
        ],
    )
    assert all(
        row["classification"] != "complete_bounded_target_package"
        for row in result["compiled_packages"]
    )


def test_material_source_sentence_loss_is_visible_and_fail_closed() -> None:
    source_id = "SRC::NVDA"
    source_text = (
        "Dell and NVIDIA have partnered for decades. Dell servers with NVIDIA GB200 "
        "are shipping at scale. One of Dell's factories can ship thousands of NVIDIA "
        "Blackwell GPUs in a week."
    )
    result = assess_dell_report_internal_chain_r3_packages(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        source_rows=[_source(source_id, source_text, "NVDA")],
        object_rows=[
            _object(
                "COBJ::NVDA",
                source_id,
                "Dell and NVIDIA have partnered for decades. Dell servers with NVIDIA GB200 are shipping at scale.",
                "NVDA",
            )
        ],
    )
    assert any("factories can ship thousands" in row["material_sentence"] for row in result["coverage_gaps"])


@pytest.fixture(scope="module")
def real_r38(bound_inputs) -> tuple[list[dict], list[dict]]:
    receipt = bound_inputs["receipt"]
    source_path = ROOT / receipt["bindings"]["source_records"]["ref"]
    object_path = ROOT / receipt["bindings"]["compiled_objects"]["ref"]
    sources = [json.loads(line) for line in source_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    objects = [json.loads(line) for line in object_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return sources, objects


def test_real_R38_counterexamples_close_R2_false_negatives(real_r38) -> None:
    sources, objects = real_r38
    for row_number in (1878, 1879):
        result = classify_dell_report_internal_chain_r3_package(
            target_id="DELL-RSQ-03A-TARGET-ASP",
            text=sources[row_number - 1]["text"],
            metadata=sources[row_number - 1],
        )
        assert result["classification"] == "complete_bounded_target_package"
        assert "not_company_wide_realized_ASP" in result["limitations"]
    supplier = classify_dell_report_internal_chain_r3_package(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        text=sources[1887 - 1]["text"],
        metadata=sources[1887 - 1],
    )
    false_positive = classify_dell_report_internal_chain_r3_package(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        text=sources[1824 - 1]["text"],
        metadata=sources[1824 - 1],
    )
    assert supplier["classification"] == "complete_bounded_target_package"
    assert false_positive["classification"] != "complete_bounded_target_package"
    source_id = sources[1887 - 1]["evidence_id"]
    scoped_objects = [
        row
        for row in objects
        if source_id in (row.get("lineage_source_record_ids") or ())
    ]
    coverage = assess_dell_report_internal_chain_r3_packages(
        target_id="DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH",
        source_rows=[sources[1887 - 1], sources[1888 - 1]],
        object_rows=scoped_objects,
    )
    assert any(
        "factories can ship thousands" in row["material_sentence"]
        for row in coverage["coverage_gaps"]
    )
    assert len(objects) == 34198


def test_real_R2_final_pool_reconstructs_ASP_rank_15_16_and_supplier_rank_2(
    real_r38, bound_inputs
) -> None:
    sources, objects = real_r38
    by_target = {
        row["target_id"]: row for row in bound_inputs["r2_private"]["target_results"]
    }
    expected = {
        "DELL-RSQ-03A-TARGET-ASP": {15, 16},
        "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH": {2},
    }
    for target_id, expected_ranks in expected.items():
        rows = by_target[target_id]["private_union_assessments"]
        final_rank = {
            row["compiled_object_id"]: row["candidate_trace"][
                "minimum_final_output_rank"
            ]
            for row in rows
            if row["candidate_trace"]["minimum_final_output_rank"] is not None
        }
        result = assess_dell_report_internal_chain_r3_packages(
            target_id=target_id,
            source_rows=sources,
            object_rows=objects,
            selected_object_ids=final_rank,
            rank_by_object_id=final_rank,
        )
        actual_ranks = {
            row["completion_rank"]
            for row in result["compiled_packages"]
            if row["classification"] == "complete_bounded_target_package"
        }
        assert actual_ranks == expected_ranks


def _synthetic_compile_population(request_ids: list[str]) -> tuple[list[dict], list[dict]]:
    objects: list[dict] = []
    source_by_id: dict[str, dict] = {}
    for request_index, _ in enumerate(request_ids, start=1):
        for rank in range(1, 97):
            object_id = f"COBJ::{request_index:02d}::{rank:03d}"
            source_id = f"SRC::{object_id}"
            text = "Neutral current disclosure."
            ticker = "DELL"
            if request_index == 1 and rank == 1:
                source_id = "SRC::ASP-PACKAGE"
                text = "Dell quoted $757,231 including support and switches."
                ticker = "ORG::BUYER"
            elif request_index == 1 and rank == 16:
                source_id = "SRC::ASP-PACKAGE"
                text = "The two PowerEdge XE9680 AI server nodes are configured systems."
                ticker = "ORG::BUYER"
            objects.append(_object(object_id, source_id, text, ticker))
            if source_id not in source_by_id:
                source_by_id[source_id] = _source(source_id, text, ticker)
            elif source_id == "SRC::ASP-PACKAGE":
                source_by_id[source_id]["text"] += f" {text}"
    return list(source_by_id.values()), objects


def test_compile_derives_ASP_reranker_and_zero_authority_from_sealed_execution(
    bound_inputs, exact_execution
) -> None:
    request_ids, execution = exact_execution
    sources, objects = _synthetic_compile_population(request_ids)
    receipt = deepcopy(bound_inputs["receipt"])
    lineage = receipt["source_object_index_lineage"]
    lineage.update(
        {
            "compiled_object_count": len(objects),
            "source_record_count": len(sources),
            "compiled_lineage_source_record_count": len(sources),
            "all_source_records_lineage_bound": True,
            "compiled_lineage_ids_outside_bound_source_store": [],
            "source_records_missing_from_compiled_lineage": [],
        }
    )
    receipt["embedding_index"]["object_count"] = len(objects)
    policy = _r3_policy(bound_inputs)
    result = compile_dell_report_internal_chain_ceiling_r3_result(
        legacy_policy=bound_inputs["r1"],
        r3_policy=policy,
        residual_program=bound_inputs["residual"],
        runtime_registry=bound_inputs["registry"],
        runtime_binding_receipt=receipt,
        execution=execution,
        execution_sha256=hashlib.sha256(
            json.dumps(execution, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        source_rows=sources,
        object_rows=objects,
        recorded_at="2026-08-25T00:00:00+00:00",
        prepared_from_commit="d" * 40,
        input_bindings={},
    )
    by_id = {row["target_id"]: row for row in result["target_results"]}
    asp = by_id["DELL-RSQ-03A-TARGET-ASP"]
    assert asp["candidate_ceiling"]["complete_target_in_final_review_package_count"] == 1
    assert asp["candidate_ceiling"]["best_complete_package_final_completion_rank"] == 16
    assert asp["downstream_disposition"]["03D_same_pool_reranker_challenger_eligible"] is True
    assert asp["downstream_disposition"]["03C_external_route_required_for_complete_bounded_target"] is False
    assert all(result["summary"][field] == 0 for field in EXECUTION_CONTRACT if field.endswith("calls") or field in {"retries", "current_mutations", "candidate_promotions", "evidence_promotions", "gap_closures"})


def test_public_projection_excludes_raw_text_and_execution() -> None:
    private = {
        "status": "ok",
        "attempt_id": ATTEMPT_ID,
        "recorded_at": "x",
        "prepared_from_commit": "d" * 40,
        "case_key": "DELL",
        "input_bindings": {},
        "runtime_registry": {},
        "raw_execution_receipt": {"secret": "raw"},
        "raw_execution_sha256": "a" * 64,
        "raw_execution_projection_digest": "b" * 64,
        "validated_execution_digest": "c" * 64,
        "execution_summary": {},
        "target_results": [
            {
                "target_id": "x",
                "private_source_packages": [{"model_text": "secret"}],
                "private_source_to_object_coverage_gaps": [
                    {"material_sentence": "secret"}
                ],
                "public_top_bounded_packages": [],
            }
        ],
        "summary": {},
        "authority": {},
        "known_boundary": "bounded",
        "policy_digest": "p",
        "result_digest": "private",
    }
    public = build_dell_report_internal_chain_ceiling_r3_public_projection(
        private_result=private,
        private_ref=PRIVATE_REF,
        private_sha256="e" * 64,
    )
    serialized = json.dumps(public)
    assert "raw_execution_receipt" not in serialized
    assert "model_text" not in serialized
    assert "material_sentence" not in serialized
    assert "secret" not in serialized


def test_runner_rejects_alternate_or_same_outputs(runner_module, tmp_path, monkeypatch) -> None:
    private = tmp_path / "private" / "full.json"
    public = tmp_path / "public.json"
    receipt = tmp_path / "private" / "attempt.json"
    monkeypatch.setattr(runner_module, "DEFAULT_PRIVATE", private)
    monkeypatch.setattr(runner_module, "DEFAULT_PUBLIC", public)
    monkeypatch.setattr(runner_module, "ATTEMPT_RECEIPT", receipt)
    runner_module._validate_canonical_output_paths(private, public, receipt)
    with pytest.raises(ValueError, match="canonical_private"):
        runner_module._validate_canonical_output_paths(
            tmp_path / "alternate.json", public, receipt
        )
    monkeypatch.setattr(runner_module, "DEFAULT_PUBLIC", private)
    with pytest.raises(ValueError, match="paths_must_be_distinct"):
        runner_module._validate_canonical_output_paths(private, private, receipt)


def test_runner_atomic_pair_rolls_back_second_link_failure(
    runner_module, tmp_path, monkeypatch
) -> None:
    private = tmp_path / "private" / "full.json"
    public = tmp_path / "public" / "result.json"
    real_link = os.link
    calls = 0

    def fail_second(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise FileExistsError("attack")
        return real_link(source, destination)

    monkeypatch.setattr(runner_module.os, "link", fail_second)
    with pytest.raises(FileExistsError, match="attack"):
        runner_module._publish_atomic_pair(
            private_output=private,
            private_bytes=b"private",
            public_output=public,
            public_bytes=b"public",
        )
    assert not private.exists()
    assert not public.exists()
    assert not list(tmp_path.rglob("*.tmp"))


def test_runner_attempt_consumption_is_exclusive(runner_module, tmp_path) -> None:
    path = tmp_path / "attempt" / "attempt_consumed.json"
    result = runner_module._write_attempt_consumption_receipt(
        path=path,
        policy={"result_digest": "policy"},
        git_receipt={
            "head": "a" * 40,
            "head_tree": "b" * 40,
            "implementation_commit": "c" * 40,
            "implementation_tree": "d" * 40,
        },
        recorded_at="2026-08-25T00:00:00+00:00",
    )
    assert result["same_attempt_retry_authorized"] is False
    with pytest.raises(FileExistsError, match="already_consumed"):
        runner_module._write_attempt_consumption_receipt(
            path=path,
            policy={"result_digest": "policy"},
            git_receipt={},
            recorded_at="later",
        )


def test_runner_CLI_has_no_output_override(runner_module) -> None:
    with pytest.raises(SystemExit):
        runner_module.main(["--private-output", "alternate.json"])
