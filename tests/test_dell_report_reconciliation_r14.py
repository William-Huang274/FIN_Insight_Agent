from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
import retrieval.dell_report_reconciliation_r14 as reconciliation_module

from retrieval.dell_report_decision_vector_r14 import (
    build_decision_vector_receipt_r14,
)
from retrieval.dell_report_population_manifest_r14 import (
    build_input_population_manifest_r14,
    build_population_commitment_r14,
)
from retrieval.dell_report_r14_common import (
    DellReportR14ContractError,
    TARGET_IDS,
    canonical_digest,
    canonical_json_bytes,
    domain_rows_digest,
    sha256_bytes,
    with_result_digest,
)
from retrieval.dell_report_reconciliation_r14 import (
    build_reconciliation_summary_r14,
    formal_compare_contract_r14,
    project_public_reconciliation_r14,
    validate_public_reconciliation_projection_r14,
    validate_reconciliation_summary_r14,
)
from retrieval.dell_report_r14_contracts import load_and_validate_r14_contracts
from retrieval.dell_report_structural_graph_r14 import (
    build_event_argument_graph_r14,
    build_price_attachment_graph_r14,
)
from retrieval.dell_report_target_compiler_r14 import build_target_graph_view_r14
from retrieval.dell_report_transformation_r14 import (
    build_graph_transformation_receipt_r14,
)


ROOT = Path(__file__).resolve().parents[1]

def _source() -> dict:
    return {
        "evidence_id": "PRIVATE-SOURCE-ID",
        "text": "private model text",
        "metadata": {"source_page_record_id": "PRIVATE-FAMILY"},
    }


def _object() -> dict:
    return {
        "compiled_object_id": "PRIVATE-OBJECT-ID",
        "model_text": "private model text",
        "object_kind": "sentence",
        "lineage_source_record_ids": ["PRIVATE-SOURCE-ID"],
        "base_object_view": {
            "source_record_id": "PRIVATE-SOURCE-ID",
            "source_lineage": {"source_page_record_id": "PRIVATE-FAMILY"},
            "surface_text": "private model text",
            "focus_binding": {
                "mode": "exact_text",
                "char_start": 0,
                "char_end": len("private model text"),
            },
        },
    }


def _artifacts():
    manifest = build_input_population_manifest_r14(
        source_rows=[_source()],
        object_rows=[_object()],
        source_ref="private/sources.jsonl",
        source_sha256="a" * 64,
        object_ref="private/objects.jsonl",
        object_sha256="b" * 64,
        implementation_identity="TEST::R14::I",
        changed_path_digest="c" * 64,
        recorded_at="2026-08-29T00:00:00+08:00",
    )
    receipts = []
    details = {}
    for target_id in TARGET_IDS:
        for lane in ("source", "compiled"):
            entry_key = (
                "source_canonical_order"
                if lane == "source"
                else "object_canonical_order"
            )
            entry = manifest[entry_key][0]
            outcome = (
                "C"
                if target_id == TARGET_IDS[0] and lane == "source"
                else "P"
                if target_id == TARGET_IDS[0] and lane == "compiled"
                else "N"
            )
            detail = (
                {
                    "accepted_event_ids": ["EVENT::R14::ACCEPTED"],
                    "target_topology_digest": "d" * 64,
                    "package_digest": "e" * 64,
                }
                if outcome == "C"
                else {
                    "candidate_proof_ids": ["PROOF::R14::CANDIDATE"],
                    "limitations": ["missing_role"],
                    "graph_digest": "f" * 64,
                }
                if outcome == "P"
                else {}
            )
            receipt, detail_rows = build_decision_vector_receipt_r14(
                manifest=manifest,
                target_id=target_id,
                lane=lane,
                cells=[
                    {
                        "manifest_index": 0,
                        "input_digest": entry["input_digest"],
                        "target_id": target_id,
                        "lane": lane,
                        "outcome": outcome,
                        "detail": detail,
                    }
                ],
                parser_version="parser_v1",
                target_topology_digest="1" * 64,
                price_graph_version="price_v1",
            )
            receipts.append(receipt)
            details[(target_id, lane)] = detail_rows
    route_registry = {
        target_id: "03C_EXTERNAL_LADDER_AFTER_R14" for target_id in TARGET_IDS
    }
    bundle = load_and_validate_r14_contracts(root=ROOT)
    event_graph = build_event_argument_graph_r14(
        text="Dell offered PowerEdge at USD 100.", bundle=bundle
    )
    price_graph = build_price_attachment_graph_r14(
        graph=event_graph, bundle=bundle
    )
    view = build_target_graph_view_r14(
        event_graph=event_graph, price_graph=price_graph
    )
    transformation = build_graph_transformation_receipt_r14(
        source_view=view,
        compiled_view=view,
        source_manifest_index=manifest["source_canonical_order"][0][
            "manifest_index"
        ],
        compiled_manifest_index=manifest["object_canonical_order"][0][
            "manifest_index"
        ],
        source_record_id=manifest["source_canonical_order"][0][
            "source_record_id"
        ],
        compiled_object_id=manifest["object_canonical_order"][0][
            "compiled_object_id"
        ],
        source_input_digest=manifest["source_canonical_order"][0]["input_digest"],
        source_slice_mode=manifest["object_canonical_order"][0]["source_slice_mode"],
        source_slice_digest=manifest["object_canonical_order"][0]["source_slice_digest"],
        source_slice_binding_digest=manifest["object_canonical_order"][0][
            "source_slice_binding_digest"
        ],
        compiled_input_digest=manifest["object_canonical_order"][0]["input_digest"],
        canonical_source_family_id=manifest["object_canonical_order"][0][
            "canonical_source_family_id"
        ],
        compiled_lineage_source_record_ids=tuple(
            manifest["object_canonical_order"][0]["lineage_source_record_ids"]
        ),
        compiled_lineage_source_keyset_digest=manifest[
            "object_canonical_order"
        ][0]["lineage_source_keyset_digest"],
        source_extraction_receipt_digest="8" * 64,
        compiled_extraction_receipt_digest="9" * 64,
        source_extraction_passed=True,
        compiled_extraction_passed=True,
    )
    reconciliation = build_reconciliation_summary_r14(
        manifest=manifest,
        receipts=receipts,
        details_by_target_lane=details,
        transformation_receipts=(transformation,),
        route_registry=route_registry,
    )
    private_bytes = canonical_json_bytes(manifest)
    population_commitment = build_population_commitment_r14(
        manifest,
        private_sha256=sha256_bytes(private_bytes),
        private_bytes=len(private_bytes),
    )
    planned_rows = [
        {
            "relative_path": "private/result.json",
            "exact_bytes": 7,
            "sha256": sha256_bytes(b"private"),
            "semantic_root": "5" * 64,
        },
        {
            "relative_path": "public/result.json",
            "exact_bytes": 6,
            "sha256": sha256_bytes(b"public"),
            "semantic_root": "6" * 64,
        },
    ]
    commitment = with_result_digest(
        {
            "schema_version": "fin_ia_dell_03B_R14_preformal_decision_commitment_v1_0",
            "implementation_commit": "1" * 40,
            "implementation_tree": "2" * 40,
            "implementation_parent": "3" * 40,
            "population_manifest_result_digest": reconciliation["manifest_result_digest"],
            "population_manifest_root": reconciliation["manifest_root"],
            "population_commitment_result_digest": population_commitment["result_digest"],
            "parser_version": "parser_v1",
            "target_topology_digest": "1" * 64,
            "transformation_version": "transformation_v1",
            "vector_bindings": [
                {
                    "target_id": row["target_id"],
                    "lane": row["lane"],
                    "vector_root": row["vector_root"],
                    "detail_root": row["detail_root"],
                    "outcome_counts": dict(row["outcome_counts"]),
                    "receipt_result_digest": row["receipt_result_digest"],
                }
                for row in reconciliation["target_lane_rows"]
            ],
            "receipt_binding_root": reconciliation["receipt_binding_root"],
            "reconciliation_result_digest": reconciliation["result_digest"],
            "program_receipt_result_digest": "0" * 64,
            "package_root": "1" * 64,
            "event_root": "2" * 64,
            "coverage_root": "3" * 64,
            "family_root": "4" * 64,
            "rank_root": "5" * 64,
            "aggregate_outcome_counts": dict(reconciliation["aggregate_outcome_counts"]),
            "aggregate_candidate_ceiling": reconciliation["aggregate_candidate_ceiling"],
            "transformation_root": reconciliation["transformation_root"],
            "route_registry_digest": reconciliation["route_registry_digest"],
            "r13_delta_receipt_result_digest": "6" * 64,
            "r13_delta_root": "7" * 64,
            "performance_receipt_result_digest": "8" * 64,
            "performance_status": "PASS",
            "peak_memory_bytes": 1,
            "elapsed_ms": 1,
            "performance_warning_limit_ms": 600000,
            "performance_hard_limit_ms": 1800000,
            "performance_hard_memory_limit_bytes": 4 * 1024**3,
            "resource_gate_receipt_result_digest": "9" * 64,
            "resource_gate_status": "PASS",
            "required_free_bytes": 536870912,
            "observed_free_bytes": 1073741824,
            "durability_probe_receipt_digest": "a" * 64,
            "resource_planned_artifact_root": "b" * 64,
            "resource_stage_bytes": sum(row["exact_bytes"] for row in planned_rows),
            "canonical_serializer_identity": "canonical_json_v1",
            "planned_artifacts": planned_rows,
            "planned_artifact_bytes": {row["relative_path"]: row["exact_bytes"] for row in planned_rows},
            "planned_artifact_total_bytes": 13,
            "private_artifact_contract_root": domain_rows_digest(
                b"FIN_IA_R14_PRIVATE_ARTIFACT_CONTRACT_V1\0",
                (canonical_json_bytes(planned_rows[0]),),
            ),
            "public_artifact_contract_root": domain_rows_digest(
                b"FIN_IA_R14_PUBLIC_ARTIFACT_CONTRACT_V1\0",
                (canonical_json_bytes(planned_rows[1]),),
            ),
            "critical_mutation_manifest_sha256": "a" * 64,
            "critical_mutation_manifest_root": "b" * 64,
            "critical_mutation_kill_receipt_sha256": "c" * 64,
            "critical_mutation_execution_root": "d" * 64,
            "critical_mutation_observation_root": "e" * 64,
            "critical_mutation_status": "PASS_100_PERCENT_KILLED",
            "property_manifest_sha256": "f" * 64,
            "property_operator_version": "property_operator_v1",
            "property_seed": "property_seed_v1",
            "property_matrix_root": "0" * 64,
            "property_receipt_sha256": "1" * 64,
            "property_result_root": "2" * 64,
            "property_status": "PASS",
            "formal_compare_contract": list(formal_compare_contract_r14()),
            "preview_output_is_compiler_input": False,
            "model_provider_calls": 0,
        }
    )
    return manifest, receipts, details, transformation, reconciliation, commitment


def test_r14_reconciliation_is_full_population_derived_and_candidate_ceiling_exact() -> None:
    _, _, _, _, reconciliation, _ = _artifacts()

    assert len(reconciliation["target_lane_rows"]) == 12
    assert reconciliation["aggregate_outcome_counts"] == {
        "C": 1,
        "P": 1,
        "N": 10,
        "E": 0,
    }
    assert reconciliation["aggregate_candidate_ceiling"] == 2
    assert reconciliation["transformation_non_vacuous_count"] == 1


def test_r14_reconciliation_rejects_missing_receipt_or_detail_lane() -> None:
    manifest, receipts, details, _, _, _ = _artifacts()
    removed = receipts[:-1]
    removed_details = dict(details)
    removed_details.pop((TARGET_IDS[-1], "compiled"))

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_reconciliation_receipt_population_invalid",
    ):
        build_reconciliation_summary_r14(
            manifest=manifest,
            receipts=removed,
            details_by_target_lane=removed_details,
            transformation_receipts=(),
            route_registry={target_id: "route" for target_id in TARGET_IDS},
        )


def test_r14_reconciliation_rejects_resigned_same_source_slice_rebind() -> None:
    manifest, receipts, details, transformation, _, _ = _artifacts()
    forged = deepcopy(transformation)
    forged["source_slice_digest"] = "a" * 64
    forged = with_result_digest(forged)

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_reconciliation_transformation_population_rebind",
    ):
        build_reconciliation_summary_r14(
            manifest=manifest,
            receipts=receipts,
            details_by_target_lane=details,
            transformation_receipts=(forged,),
            route_registry={
                target_id: "03C_EXTERNAL_LADDER_AFTER_R14"
                for target_id in TARGET_IDS
            },
        )


def test_r14_projector_rejects_recomputed_private_summary_not_bound_by_commitment() -> None:
    _, _, _, _, reconciliation, commitment = _artifacts()
    mutated = deepcopy(reconciliation)
    rebound_target = mutated["target_lane_rows"][0]["target_id"]
    for row in mutated["target_lane_rows"]:
        if row["target_id"] == rebound_target:
            row["route_disposition"] = "AUTHOR_REBOUND_ROUTE"
    route_registry = {
        row["target_id"]: row["route_disposition"]
        for row in mutated["target_lane_rows"]
    }
    mutated["route_registry_digest"] = canonical_digest(
        dict(sorted(route_registry.items()))
    )
    mutated["receipt_binding_root"] = domain_rows_digest(
        b"FIN_IA_R14_RECONCILIATION_BINDINGS_V1\0",
        (canonical_json_bytes(row) for row in mutated["target_lane_rows"]),
    )
    mutated = with_result_digest(mutated)

    with pytest.raises(
        DellReportR14ContractError,
        match="R14_projector_commitment_mismatch",
    ):
        project_public_reconciliation_r14(
            reconciliation=mutated, commitment=commitment
        )


def test_r14_public_projection_is_bounded_and_private_safe() -> None:
    _, _, _, _, reconciliation, commitment = _artifacts()
    public = project_public_reconciliation_r14(
        reconciliation=reconciliation, commitment=commitment
    )
    surface = json.dumps(public, sort_keys=True)

    assert "PRIVATE-SOURCE-ID" not in surface
    assert "PRIVATE-OBJECT-ID" not in surface
    assert "private source text" not in surface
    assert "private model text" not in surface
    assert "outcome_bytes_hex" not in surface
    assert '"detail":' not in surface
    assert public["privacy_contract"]["creates_reader_citation"] is False


def test_r14_public_projector_invokes_production_validator_before_return(
    monkeypatch,
) -> None:
    _, _, _, _, reconciliation, commitment = _artifacts()
    original_signer = reconciliation_module.with_result_digest

    def inject_unknown_private_key(body):
        projected = original_signer(body)
        projected["private_source_id"] = "PRIVATE-SOURCE-ID"
        return original_signer(projected)

    monkeypatch.setattr(
        reconciliation_module,
        "with_result_digest",
        inject_unknown_private_key,
    )
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_public_projection_keyset_invalid",
    ):
        project_public_reconciliation_r14(
            reconciliation=reconciliation,
            commitment=commitment,
        )


@pytest.mark.parametrize(
    ("injection", "failure_code"),
    [
        (
            ("top", "private_source_id", "PRIVATE-SOURCE-ID"),
            "R14_public_projection_keyset_invalid",
        ),
        (
            ("row", "source_record_id", "PRIVATE-SOURCE-ID"),
            "R14_public_projection_row_keyset_invalid",
        ),
        (
            ("route", "route_disposition", "D:/private/source.json"),
            "R14_public_projection_private_locator_detected",
        ),
        (
            (
                "route",
                "route_disposition",
                "Dell offered PowerEdge at $100.",
            ),
            "R14_public_projection_raw_text_detected",
        ),
    ],
)
def test_r14_public_projection_validator_rejects_private_surface_injection(
    injection, failure_code
) -> None:
    _, _, _, _, reconciliation, commitment = _artifacts()
    projected = project_public_reconciliation_r14(
        reconciliation=reconciliation,
        commitment=commitment,
    )
    mutated = deepcopy(projected)
    location, key, value = injection
    if location == "top":
        mutated[key] = value
    elif location == "row":
        mutated["target_lane_rows"][0][key] = value
    else:
        mutated["target_lane_rows"][0]["route_disposition"] = value
    mutated = with_result_digest(mutated)
    with pytest.raises(DellReportR14ContractError, match=failure_code):
        validate_public_reconciliation_projection_r14(
            mutated,
            reconciliation=reconciliation,
            commitment=commitment,
        )


def test_r14_public_projection_validator_rejects_noncanonical_or_stale_digest() -> None:
    _, _, _, _, reconciliation, commitment = _artifacts()
    projected = project_public_reconciliation_r14(
        reconciliation=reconciliation,
        commitment=commitment,
    )
    stale_digest = deepcopy(projected)
    stale_digest["aggregate_candidate_ceiling"] += 1
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_public_projection_result_digest_mismatch",
    ):
        validate_public_reconciliation_projection_r14(
            stale_digest,
            reconciliation=reconciliation,
            commitment=commitment,
        )

    noncanonical = deepcopy(projected)
    noncanonical["target_lane_rows"] = tuple(noncanonical["target_lane_rows"])
    noncanonical = with_result_digest(noncanonical)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_public_projection_not_canonical_value",
    ):
        validate_public_reconciliation_projection_r14(
            noncanonical,
            reconciliation=reconciliation,
            commitment=commitment,
        )


def test_r14_reconciliation_validator_rejects_resigned_row_drop() -> None:
    _, _, _, _, reconciliation, _ = _artifacts()
    mutated = deepcopy(reconciliation)
    mutated["target_lane_rows"] = mutated["target_lane_rows"][:-1]
    mutated = with_result_digest(mutated)

    with pytest.raises(DellReportR14ContractError, match="R14_reconciliation_rows"):
        validate_reconciliation_summary_r14(mutated)
