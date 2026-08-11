"""Unit-only coverage for the M2-A1 assembly seam; no compiler/shadow call."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_audit_canary import M2A1AuditCanary
from sec_agent.canonical_runtime.m2_a1_audit_harness import (
    M2A1ActualExecutionNotAdmitted,
    M2A1AssemblyError,
    M2A1ActualRunner,
    assemble_compiler_input_contract,
)
from sec_agent.canonical_runtime.legacy_objective_adapter import (
    LegacyObjectiveAdapterError,
    adapt_legacy_research_objective,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.pack_registry import PlanningPackRegistry, PlanningPackRegistryPolicy, PlanningPackVersion
from sec_agent.canonical_runtime.pack_selection import PackSelectionEngine, PackSelectionIntent, PackSelectionPolicy


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "configs/engineering_handoff/point01_m2_a1_adversarial_input_corpus_v1_1.json"
RUNNER = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit.py"
CLEAN_CHILD = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child.py"


def _case(case_id: str = "m2-a1-ai-semis-input") -> dict:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    return next(copy.deepcopy(case) for case in corpus["cases"] if case["case_id"] == case_id)


def _mutate_case_delta_base_pack_ref(case: dict) -> None:
    version = next(version for version in case["pack_version_metadata"]["versions"] if version["scope_kind"] == "case_delta")
    payload = version["case_delta_payload"]
    payload["base_pack_refs"]["sector_pack_refs"] = ["pack-sector-saas:v3"]
    digest = canonical_digest({key: value for key, value in payload.items() if key != "payload_digest"})
    payload["payload_digest"] = digest
    version["payload_digest"] = digest


def test_explicit_legacy_adapter_plus_seed_pack_merge_is_strict_and_deterministic() -> None:
    assembled, proof = assemble_compiler_input_contract(
        _case(),
        compiler_policy_ref="point01-m2-1-compiler-policy-v1",
        pack_registry_policy_ref="point01-m2-3-pack-registry-policy-v1",
    )
    assert assembled.case_id == "m2-a1-ai-semis-input"
    assert proof.required_cell_count == 10
    assert proof.adapter_output_pack_selection_empty is True
    assert assembled.pack_selection.sector_pack_refs == ("pack-sector-ai-semis:v3",)
    assert assembled.pack_selection.case_delta_pack_refs == ("pack-case-m2-a1-ai-semis-no-override:v1",)
    assert proof.case_delta_pack_refs == assembled.pack_selection.case_delta_pack_refs
    assert proof.case_delta_payload_digest == "71d9a25e7973db55ec0a99295e90d51d9acb2ed87c988b548d4e8089d00d28b9"
    assert proof.compiler_or_shadow_fixture_runs == 0
    assert proof.model_calls == proof.network_requests == proof.store_writes == 0


def test_ai_semis_case_delta_no_override_pack_is_exactly_resolved_from_seed_lineage() -> None:
    case = _case()
    assembled, _ = assemble_compiler_input_contract(
        case,
        compiler_policy_ref="point01-m2-1-compiler-policy-v1",
        pack_registry_policy_ref="point01-m2-3-pack-registry-policy-v1",
    )
    registry_raw = json.loads((ROOT / "configs/engineering_handoff/point01_m2_3_pack_registry_policy_v1_0.json").read_text(encoding="utf-8"))
    selection_raw = json.loads((ROOT / "configs/engineering_handoff/point01_m2_4_pack_selection_policy_v1_0.json").read_text(encoding="utf-8"))
    registry = PlanningPackRegistry(PlanningPackRegistryPolicy.model_validate({key: value for key, value in registry_raw.items() if key not in {"policy_version", "authority_boundary"}}))
    for raw_version in case["pack_version_metadata"]["versions"]:
        version = PlanningPackVersion.model_validate(raw_version)
        if version.supersedes_pack_version_id:
            registry.publish(
                version.model_copy(
                    update={
                        "pack_version": version.pack_version - 1,
                        "pack_version_id": version.supersedes_pack_version_id,
                        "supersedes_pack_version_id": None,
                    }
                )
            )
        registry.publish(version)
    selection = PackSelectionEngine(
        registry,
        PackSelectionPolicy.model_validate({key: value for key, value in selection_raw.items() if key not in {"policy_version", "authority_boundary"}}),
    ).select(
        PackSelectionIntent(
            query=assembled.query,
            sector=case["compiler_input_seed"]["sector"],
            report_type=case["compiler_input_seed"]["report_type"],
            case_id=assembled.case_id,
            as_of=assembled.as_of,
        )
    )
    assert selection.status == "selected"
    assert selection.resolution is not None
    assert selection.resolution.case_delta_pack_refs == assembled.pack_selection.case_delta_pack_refs
    assert selection.resolution.case_delta_pack_refs == ("pack-case-m2-a1-ai-semis-no-override:v1",)
    assert any(reason.code == "versioned_pack_resolution_selected" for reason in selection.reasons)


def test_legacy_adapter_derives_only_canonical_forbidden_substitution_defaults() -> None:
    case = _case()
    scope = case["case_scope"]
    inputs = adapt_legacy_research_objective(
        case["legacy_research_objective"]["payload"],
        tenant_id=scope["tenant_id"],
        project_id=scope["project_id"],
        case_id=scope["case_id"],
        compiler_policy_ref="point01-m2-1-compiler-policy-v1",
    )
    by_role = {cell.evidence_slots[0].evidence_role: cell.evidence_slots[0].forbidden_substitutions for cell in inputs.required_cells}
    assert by_role["issuer_metric"] == ("relationship_graph_only",)
    assert by_role["relationship_signal"] == ("issuer_metric_substitute",)

    unsupported = copy.deepcopy(case["legacy_research_objective"]["payload"])
    unsupported["required_items"][0]["evidence_role"] = "unbounded_unknown_role"
    with pytest.raises(LegacyObjectiveAdapterError, match="forbidden_substitutions_unresolved"):
        adapt_legacy_research_objective(
            unsupported,
            tenant_id=scope["tenant_id"],
            project_id=scope["project_id"],
            case_id=scope["case_id"],
            compiler_policy_ref="point01-m2-1-compiler-policy-v1",
        )


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda case: case["compiler_input_seed"].update({"universe": ["WRONG"]}), "seed_legacy_field_mismatch:universe"),
        (lambda case: case["compiler_input_seed"]["pack_selection"].update({"sector_pack_refs": ["pack-sector-saas:v3"]}), "pack_selection_ref_not_in_metadata:sector"),
        (lambda case: case["compiler_input_seed"]["pack_selection"].update({"case_delta_pack_refs": []}), "case_delta_pack_lineage_cardinality_invalid"),
        (lambda case: case["pack_version_metadata"].update({"registry_policy_ref": "wrong"}), "pack_registry_policy_ref_mismatch"),
        (lambda case: next(version for version in case["pack_version_metadata"]["versions"] if version["scope_kind"] == "case_delta").pop("case_delta_payload"), "case_delta_payload_missing"),
        (lambda case: next(version for version in case["pack_version_metadata"]["versions"] if version["scope_kind"] == "case_delta")["case_delta_payload"].update({"case_id": "wrong-case"}), "case_delta_payload_case_id_mismatch"),
        (_mutate_case_delta_base_pack_ref, "case_delta_payload_base_pack_refs_mismatch"),
        (lambda case: next(version for version in case["pack_version_metadata"]["versions"] if version["scope_kind"] == "case_delta")["case_delta_payload"].update({"decision_source_ref": ""}), "case_delta_payload_decision_source_missing"),
        (lambda case: next(version for version in case["pack_version_metadata"]["versions"] if version["scope_kind"] == "case_delta")["case_delta_payload"].update({"payload_digest": "0" * 64}), "case_delta_payload_digest_mismatch"),
    ],
)
def test_assembly_rejects_seed_or_metadata_shortcuts(mutate, expected: str) -> None:
    case = _case()
    mutate(case)
    with pytest.raises(M2A1AssemblyError, match=expected):
        assemble_compiler_input_contract(case, compiler_policy_ref="point01-m2-1-compiler-policy-v1", pack_registry_policy_ref="point01-m2-3-pack-registry-policy-v1")


def test_actual_runner_pre_receipt_assembly_and_probe_entrypoints_remain_fail_closed(tmp_path: Path) -> None:
    canary = M2A1AuditCanary(allowed_temporary_roots=(tmp_path,))
    runner = M2A1ActualRunner(
        corpus_case=_case("m2-a1-banks-input"),
        compiler_policy_ref="point01-m2-1-compiler-policy-v1",
        pack_registry_policy_ref="point01-m2-3-pack-registry-policy-v1",
        temporary_root=tmp_path / "isolated",
        canary=canary,
    )
    # v2.3 forbids even adapter/pack assembly before an existing receipt was
    # atomically consumed by the separate executor lifecycle.
    with pytest.raises(M2A1ActualExecutionNotAdmitted, match="m2_a1_preflight_assembly_requires_exact_admission_and_single_use_receipt"):
        runner.preflight_assembly()
    with pytest.raises(M2A1ActualExecutionNotAdmitted, match="m2_a1_actual_probes_not_authorized"):
        runner.execute_actual_probes()
    assert canary.snapshot()["counts"]["store_open_attempt_count"] == 0


def test_actual_runner_has_no_oracle_evaluator_import_or_constructor_parameter() -> None:
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert "sec_agent.canonical_runtime.m2_a1_audit_oracle" not in imported
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert "build_preflight_runner" not in names
    source = RUNNER.read_text(encoding="utf-8")
    assert '"-I"' in source
    assert "import sec_agent" not in source
    child_source = CLEAN_CHILD.read_text(encoding="utf-8")
    assert "m2_a1_audit_oracle" not in child_source
    assert child_source.index("open_existing") < child_source.index("consume_before_run") < child_source.index("reverify_current_execution_tree") < child_source.index("verify_consumption_grant_before_runtime") < child_source.index("materialize_runtime_after_consumption") < child_source.index("m2_a1_audit_canary") < child_source.index("m2_a1_audit_harness")
