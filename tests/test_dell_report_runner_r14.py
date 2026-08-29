from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest
import retrieval.dell_report_runner_r14 as runner_module

from retrieval.dell_report_decision_vector_rebuilder_r14 import (
    rebuild_decision_vector_r14,
)
from retrieval.dell_report_population_manifest_r14 import (
    build_input_population_manifest_r14,
    build_population_commitment_r14,
)
from retrieval.dell_report_r14_common import (
    DellReportR14ContractError,
    canonical_json_bytes,
    domain_rows_digest,
    sha256_bytes,
    with_result_digest,
)
from retrieval.dell_report_r14_contracts import (
    TARGET_IDS,
    load_and_validate_r14_contracts,
)
from retrieval.dell_report_runner_r14 import compile_manifest_lane_r14
from retrieval.dell_report_runner_r14 import (
    bind_preformal_evidence_for_formal_r14,
    build_formal_compiler_input_envelope_r14,
    build_full_program_r14,
    build_program_artifact_payloads_r14,
    run_formal_recompute_and_compare_r14,
)
from retrieval.dell_report_reconciliation_r14 import (
    build_planned_program_artifact_contracts_r14,
    formal_compare_contract_r14,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bundle():
    return load_and_validate_r14_contracts(root=ROOT)


def _source(source_id: str, text: str) -> dict:
    return {
        "evidence_id": source_id,
        "text": text,
        "metadata": {"source_page_record_id": f"FAMILY-{source_id}"},
    }


def _object(object_id: str, source_id: str, text: str) -> dict:
    return {
        "compiled_object_id": object_id,
        "model_text": text,
        "object_kind": "sentence",
        "lineage_source_record_ids": [source_id],
        "base_object_view": {
            "source_record_id": source_id,
            "source_lineage": {"source_page_record_id": f"FAMILY-{source_id}"},
            "surface_text": text,
            "focus_binding": {
                "mode": "exact_text",
                "char_start": 0,
                "char_end": len(text),
            },
        },
    }


def _manifest(sources: list[dict], objects: list[dict]) -> dict:
    return build_input_population_manifest_r14(
        source_rows=sources,
        object_rows=objects,
        source_ref="private/source.jsonl",
        source_sha256="a" * 64,
        object_ref="private/object.jsonl",
        object_sha256="b" * 64,
        implementation_identity="TEST::R14::RUNNER",
        changed_path_digest="c" * 64,
        recorded_at="2026-08-29T00:00:00+08:00",
    )


def _synthetic_preformal_commitment(preview, population_commitment) -> dict:
    reconciliation = preview.reconciliation
    payloads = build_program_artifact_payloads_r14(preview)
    planned = build_planned_program_artifact_contracts_r14(
        payloads=payloads,
        program_receipt=preview.program_receipt,
        reconciliation=reconciliation,
    )
    return with_result_digest(
        {
            "schema_version": "fin_ia_dell_03B_R14_preformal_decision_commitment_v1_0",
            "implementation_commit": "1" * 40,
            "implementation_tree": "2" * 40,
            "implementation_parent": "3" * 40,
            "population_manifest_result_digest": reconciliation["manifest_result_digest"],
            "population_manifest_root": reconciliation["manifest_root"],
            "population_commitment_result_digest": population_commitment["result_digest"],
            "parser_version": "parser_v1",
            "target_topology_digest": "3" * 64,
            "transformation_version": "transformation_v1",
            "vector_bindings": [
                {key: (dict(row[key]) if key == "outcome_counts" else row[key]) for key in ("target_id", "lane", "vector_root", "detail_root", "outcome_counts", "receipt_result_digest")}
                for row in reconciliation["target_lane_rows"]
            ],
            "receipt_binding_root": reconciliation["receipt_binding_root"],
            "reconciliation_result_digest": reconciliation["result_digest"],
            "program_receipt_result_digest": preview.program_receipt["result_digest"],
            "package_root": preview.program_receipt["package_root"],
            "event_root": preview.program_receipt["event_root"],
            "coverage_root": preview.program_receipt["coverage_root"],
            "family_root": preview.program_receipt["family_root"],
            "rank_root": preview.program_receipt["rank_root"],
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
            "resource_stage_bytes": sum(row["exact_bytes"] for row in planned),
            "canonical_serializer_identity": "canonical_json_v1",
            "planned_artifacts": planned,
            "planned_artifact_bytes": {row["relative_path"]: row["exact_bytes"] for row in planned},
            "planned_artifact_total_bytes": sum(
                row["exact_bytes"] for row in planned
            ),
            "private_artifact_contract_root": domain_rows_digest(b"FIN_IA_R14_PRIVATE_ARTIFACT_CONTRACT_V1\0", (canonical_json_bytes(planned[0]),)),
            "public_artifact_contract_root": domain_rows_digest(b"FIN_IA_R14_PUBLIC_ARTIFACT_CONTRACT_V1\0", (canonical_json_bytes(planned[1]),)),
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


def test_r14_runner_compiles_each_input_once_into_six_rebuildable_vectors(bundle) -> None:
    sources = [
        _source("S-PRICE", "Dell offered PowerEdge at $100."),
        _source("S-NONE", "The weather remained calm."),
        _source("S-SUPPLY", "Micron supplied HBM to Dell in 2026."),
    ]
    objects = [
        _object("O-PRICE", "S-PRICE", sources[0]["text"]),
        _object("O-NONE", "S-NONE", sources[1]["text"]),
        _object("O-SUPPLY", "S-SUPPLY", sources[2]["text"]),
    ]
    manifest = _manifest(sources, objects)
    compiled = compile_manifest_lane_r14(
        manifest=manifest, raw_rows=sources, lane="source", bundle=bundle
    )

    assert compiled.compiled_input_count == 3
    assert compiled.model_provider_calls == 0
    assert tuple(row["target_id"] for row in compiled.receipts) == TARGET_IDS
    for receipt in compiled.receipts:
        rebuilt = rebuild_decision_vector_r14(
            manifest=manifest,
            receipt=receipt,
            details=compiled.details_by_target[receipt["target_id"]],
        )
        assert rebuilt["status"] == "PASS_INDEPENDENT_REBUILD"
        assert rebuilt["length"] == 3

    asp = next(
        row
        for row in compiled.receipts
        if row["target_id"] == "DELL-RSQ-03A-TARGET-ASP"
    )
    capacity = next(
        row
        for row in compiled.receipts
        if row["target_id"] == "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE"
    )
    assert asp["outcome_counts"]["C"] == 1
    assert capacity["outcome_counts"]["C"] == 0
    assert capacity["outcome_counts"]["P"] == 1


def test_r14_runner_rejects_raw_population_or_digest_substitution(bundle) -> None:
    sources = [_source("S1", "Dell offered PowerEdge at $100.")]
    objects = [_object("O1", "S1", sources[0]["text"])]
    manifest = _manifest(sources, objects)

    with pytest.raises(
        DellReportR14ContractError, match="R14_runner_source_raw_population_mismatch"
    ):
        compile_manifest_lane_r14(
            manifest=manifest, raw_rows=[], lane="source", bundle=bundle
        )

    changed = deepcopy(sources)
    changed[0]["text"] = "substituted"
    with pytest.raises(
        DellReportR14ContractError, match="R14_runner_source_input_digest_mismatch"
    ):
        compile_manifest_lane_r14(
            manifest=manifest, raw_rows=changed, lane="source", bundle=bundle
        )


def test_r14_runner_source_has_no_preview_result_or_provider_dependency() -> None:
    path = ROOT / "src/retrieval/dell_report_runner_r14.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }

    assert "preview_vector" not in source
    assert "preview_result" not in source
    assert "R13" not in source
    assert "openai" not in source.casefold()
    assert "requests" not in source.casefold()
    assert "raw_text" not in attributes


def test_r14_full_program_runs_both_lanes_lineage_and_transformations(
    bundle,
) -> None:
    sources = [
        _source("S-PRICE", "Dell offered PowerEdge at $100."),
        _source("S-SUPPLY", "Micron supplied HBM to Dell in 2026."),
    ]
    objects = [
        _object("O-PRICE", "S-PRICE", sources[0]["text"]),
        _object("O-SUPPLY", "S-SUPPLY", sources[1]["text"]),
    ]
    manifest = _manifest(sources, objects)
    routes = {target_id: "03C_AFTER_R14" for target_id in TARGET_IDS}
    result = build_full_program_r14(
        manifest=manifest,
        source_rows=sources,
        object_rows=objects,
        bundle=bundle,
        route_registry=routes,
    )

    assert result.source_lane.compiled_input_count == 2
    assert result.compiled_lane.compiled_input_count == 2
    assert len(result.transformation_receipts) == 2
    assert result.reconciliation["transformation_status_counts"] == {
        "PASS_PRESERVATION": 2
    }
    assert result.program_receipt["logical_decision_count"] == 24
    assert result.program_receipt["model_provider_calls"] == 0


def test_r14_full_program_requires_independent_population_rebuild(
    bundle, monkeypatch
) -> None:
    sources = [_source("S1", "Dell offered PowerEdge at $100.")]
    objects = [_object("O1", "S1", sources[0]["text"])]
    manifest = _manifest(sources, objects)
    routes = {target_id: "03C_AFTER_R14" for target_id in TARGET_IDS}
    original_rebuilder = runner_module.rebuild_input_population_r14

    def mismatching_rebuilder(**kwargs):
        rebuilt = original_rebuilder(**kwargs)
        return {**rebuilt, "parent_document_receipt_root": "f" * 64}

    monkeypatch.setattr(
        runner_module,
        "rebuild_input_population_r14",
        mismatching_rebuilder,
    )
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_runner_independent_population_rebuild_mismatch",
    ):
        build_full_program_r14(
            manifest=manifest,
            source_rows=sources,
            object_rows=objects,
            bundle=bundle,
            route_registry=routes,
        )


def test_r14_formal_recomputes_raw_program_before_commitment_comparison(bundle) -> None:
    sources = [_source("S-PRICE", "Dell offered PowerEdge at $100.")]
    objects = [_object("O-PRICE", "S-PRICE", sources[0]["text"])]
    manifest = _manifest(sources, objects)
    routes = {target_id: "03C_AFTER_R14" for target_id in TARGET_IDS}
    preview = build_full_program_r14(
        manifest=manifest,
        source_rows=sources,
        object_rows=objects,
        bundle=bundle,
        route_registry=routes,
    )
    private_bytes = canonical_json_bytes(manifest)
    population_commitment = build_population_commitment_r14(
        manifest,
        private_sha256=sha256_bytes(private_bytes),
        private_bytes=len(private_bytes),
    )
    commitment = _synthetic_preformal_commitment(preview, population_commitment)
    formal_envelope = build_formal_compiler_input_envelope_r14(
        manifest=manifest,
        source_rows=sources,
        object_rows=objects,
        bundle=bundle,
        route_registry=routes,
        preformal_commitment=commitment,
        bound_preformal_evidence=bind_preformal_evidence_for_formal_r14(
            commitment
        ),
    )
    formal = run_formal_recompute_and_compare_r14(
        input_envelope=formal_envelope
    )
    assert formal.program_receipt == preview.program_receipt

    forged = deepcopy(commitment)
    forged["vector_bindings"][0]["vector_root"] = "f" * 64
    forged = with_result_digest(forged)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_formal_commitment_mismatch:vector_bindings",
    ):
        run_formal_recompute_and_compare_r14(
            manifest=manifest,
            source_rows=sources,
            object_rows=objects,
            bundle=bundle,
            route_registry=routes,
            preformal_commitment=forged,
            bound_preformal_evidence=bind_preformal_evidence_for_formal_r14(
                forged
            ),
        )


@pytest.mark.parametrize("forbidden_key", ["preview_vector", "preview_output"])
def test_r14_formal_compiler_consumed_envelope_rejects_preview_injection(
    bundle, monkeypatch, forbidden_key
) -> None:
    sources = [_source("S-PRICE", "Dell offered PowerEdge at $100.")]
    objects = [_object("O-PRICE", "S-PRICE", sources[0]["text"])]
    manifest = _manifest(sources, objects)
    routes = {target_id: "03C_AFTER_R14" for target_id in TARGET_IDS}
    preview = build_full_program_r14(
        manifest=manifest,
        source_rows=sources,
        object_rows=objects,
        bundle=bundle,
        route_registry=routes,
    )
    manifest_bytes = canonical_json_bytes(manifest)
    population_commitment = build_population_commitment_r14(
        manifest,
        private_sha256=sha256_bytes(manifest_bytes),
        private_bytes=len(manifest_bytes),
    )
    commitment = _synthetic_preformal_commitment(preview, population_commitment)
    envelope = build_formal_compiler_input_envelope_r14(
        manifest=manifest,
        source_rows=sources,
        object_rows=objects,
        bundle=bundle,
        route_registry=routes,
        preformal_commitment=commitment,
        bound_preformal_evidence=bind_preformal_evidence_for_formal_r14(
            commitment
        ),
    )
    injected = dict(envelope)
    injected[forbidden_key] = {"forged": True}

    def compiler_must_not_run(**_kwargs):
        raise AssertionError("formal compiler ran before envelope preflight")

    monkeypatch.setattr(
        runner_module,
        "build_full_program_r14",
        compiler_must_not_run,
    )
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_formal_compiler_input_envelope_forbidden_preview_input",
    ):
        run_formal_recompute_and_compare_r14(input_envelope=injected)


def test_r14_formal_compiler_envelope_rejects_unknown_or_missing_key(bundle) -> None:
    sources = [_source("S-PRICE", "Dell offered PowerEdge at $100.")]
    objects = [_object("O-PRICE", "S-PRICE", sources[0]["text"])]
    manifest = _manifest(sources, objects)
    routes = {target_id: "03C_AFTER_R14" for target_id in TARGET_IDS}
    preview = build_full_program_r14(
        manifest=manifest,
        source_rows=sources,
        object_rows=objects,
        bundle=bundle,
        route_registry=routes,
    )
    manifest_bytes = canonical_json_bytes(manifest)
    population_commitment = build_population_commitment_r14(
        manifest,
        private_sha256=sha256_bytes(manifest_bytes),
        private_bytes=len(manifest_bytes),
    )
    commitment = _synthetic_preformal_commitment(preview, population_commitment)
    envelope = build_formal_compiler_input_envelope_r14(
        manifest=manifest,
        source_rows=sources,
        object_rows=objects,
        bundle=bundle,
        route_registry=routes,
        preformal_commitment=commitment,
        bound_preformal_evidence=bind_preformal_evidence_for_formal_r14(
            commitment
        ),
    )
    missing = dict(envelope)
    missing.pop("source_rows")
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_formal_compiler_input_envelope_keyset_invalid",
    ):
        run_formal_recompute_and_compare_r14(input_envelope=missing)
    unknown = dict(envelope)
    unknown["alternate_compiler_input"] = ()
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_formal_compiler_input_envelope_keyset_invalid",
    ):
        run_formal_recompute_and_compare_r14(input_envelope=unknown)
