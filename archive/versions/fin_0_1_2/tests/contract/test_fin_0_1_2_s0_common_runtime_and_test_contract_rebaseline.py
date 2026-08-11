from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from sec_agent.runtime_contract_governance import (
    ContractGovernanceError,
    LOCAL_TRUTH_FIELDS,
    ProofClass,
    REQUIRED_COMPILED_CONSUMERS,
    canonical_digest,
    compile_runtime_contract_source,
    validate_active_test_suite_manifest,
    validate_runtime_contract_source,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "configs" / "runtime" / "fin_ia_0_1_2_common_runtime_contract_family_source_v1_0.json"
MANIFEST = ROOT / "configs" / "releases" / "fin_ia_0_1_2_s0_active_test_suite_manifest_v1_0.json"
DECISION = ROOT / "configs" / "releases" / "fin_ia_0_1_2_s0_common_runtime_and_test_contract_rebaseline_v1_0.json"
S1_STAGE_PLAN = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_2_s1_realistic_three_case_deterministic_"
    "vertical_stage_plan_v1_0.json"
)
S1_STAGE_CAPSULE = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_2_s1_stage_capsule_v1_0.json"
)
PRE_S2_DISPOSITION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_2_s1_to_s2_hermetic_fixture_resource_"
    "blocker_disposition_v1_0.json"
)
PRE_S2_IMPLEMENTATION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_2_pre_s2_hermetic_fixture_resource_rebaseline_"
    "minimum_zero_call_implementation_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_runtime_source_compiles_deterministically_to_all_consumers() -> None:
    source = _load(SOURCE)
    validate_runtime_contract_source(source)
    compiled = compile_runtime_contract_source(source)
    assert compiled == compile_runtime_contract_source(deepcopy(source))
    assert compiled["source_digest"] == canonical_digest(source)
    assert tuple(row["consumer_id"] for row in compiled["compiled_consumers"]) == REQUIRED_COMPILED_CONSUMERS
    assert {row["source_digest"] for row in compiled["compiled_consumers"]} == {compiled["source_digest"]}
    assert tuple(compiled["local_truth_fields"]) == LOCAL_TRUTH_FIELDS


def test_runtime_source_rejects_truth_owner_and_consumer_drift() -> None:
    source = _load(SOURCE)
    mutated = deepcopy(source)
    mutated["truth_ownership"]["material_number"] = "provider"
    with pytest.raises(ContractGovernanceError, match="runtime_truth_owner_not_local:material_number"):
        validate_runtime_contract_source(mutated)

    mutated = deepcopy(source)
    mutated["compiled_consumers"] = [
        row for row in mutated["compiled_consumers"] if row["consumer_id"] != "renderer"
    ]
    with pytest.raises(ContractGovernanceError, match="runtime_compiled_consumer_surface_incomplete"):
        validate_runtime_contract_source(mutated)

    mutated = deepcopy(source)
    mutated["compiled_consumers"][0].pop("implementation_owner")
    with pytest.raises(ContractGovernanceError, match="runtime_compiled_consumer_implementation_owner_missing"):
        validate_runtime_contract_source(mutated)


def test_active_manifest_has_one_selected_suite_per_proof_class() -> None:
    manifest = _load(MANIFEST)
    validate_active_test_suite_manifest(manifest)
    selected = [row for row in manifest["suites"] if row["selected"]]
    assert {row["proof_class"] for row in selected} == {item.value for item in ProofClass}
    assert manifest["runner_policy"]["runner_migration_completed"] is True
    package = manifest["hermetic_package_policy"]
    assert package["disposable_runtime_count"] == 2
    assert package["complete_per_test_stdout_stderr_required"] is True
    assert package["capture_plugin_path"] in package["required_runner_files"]
    for suite in selected:
        for path in suite["test_paths"]:
            assert (ROOT / path).is_file()


def test_active_manifest_rejects_mutable_event_and_historical_gate_mutations() -> None:
    manifest = _load(MANIFEST)
    mutated = deepcopy(manifest)
    event = next(row for row in mutated["suites"] if row["proof_class"] == "immutable_event")
    event["assertion_surfaces"].append("current_next_action")
    with pytest.raises(ContractGovernanceError, match="immutable_event_asserts_mutable_projection"):
        validate_active_test_suite_manifest(mutated)

    mutated = deepcopy(manifest)
    historical = next(row for row in mutated["suites"] if row["proof_class"] == "historical_audit")
    historical["gates_current_release"] = True
    with pytest.raises(ContractGovernanceError, match="historical_audit_cannot_gate_current_release"):
        validate_active_test_suite_manifest(mutated)

    mutated = deepcopy(manifest)
    mutated["hermetic_package_policy"]["required_runner_files"].remove(
        mutated["hermetic_package_policy"]["capture_plugin_path"]
    )
    with pytest.raises(ContractGovernanceError, match="test_manifest_capture_plugin_not_packaged"):
        validate_active_test_suite_manifest(mutated)


def test_s0_decision_bindings_and_gates_are_honest() -> None:
    decision = _load(DECISION)
    for binding in decision["source_bindings"]:
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert len(binding["sha256"]) == 64
        if binding["ref"].startswith("configs/"):
            assert _sha256(path) == binding["sha256"]
    gates = decision["S0_gates"]
    assert gates["G1_truth_ownership_and_provider_envelope"]["verdict"].startswith("pass")
    assert gates["G2_single_source_compiled_consumers"]["live_runtime_family_migration_complete"] is False
    assert gates["G3_test_semantics_and_active_manifest"]["active_suite_runner_migration_complete"] is True
    assert gates["G4_hermetic_package_and_complete_failure_output"]["verdict"].startswith("pass_")
    assert gates["G4_hermetic_package_and_complete_failure_output"][
        "complete_content_addressed_stdout_stderr_proven"
    ] is True
    assert gates["G4_hermetic_package_and_complete_failure_output"][
        "disposable_runtime_parity_proven"
    ] is True
    assert gates["G5_current_active_suite_all_green"]["verdict"].startswith("pass_")
    assert gates["G6_S1_entry"]["S1_started"] is False
    assert decision["implementation_truth"]["S0_closed"] is True
    assert set(decision["observed_counts"].values()) == {0}


def test_historical_sequence_preserves_s0_handoff_and_S1_honest_close() -> None:
    decision = _load(DECISION)
    stage_plan = _load(S1_STAGE_PLAN)
    stage_capsule = _load(S1_STAGE_CAPSULE)
    disposition = _load(PRE_S2_DISPOSITION)
    implementation = _load(PRE_S2_IMPLEMENTATION)
    assert decision["next_action"] == (
        "FIN-0.1.2-S1-REALISTIC-THREE-CASE-DETERMINISTIC-VERTICAL-STAGE-PLAN"
    )
    assert stage_plan["status"] == (
        "S1_stage_plan_G0_pass_implementation_not_started"
    )
    assert stage_capsule["status"] == (
        "S1_closed_honest_block_G2_not_proven_S2_entry_blocked"
    )
    assert stage_capsule["next_action"] == (
        "FIN-0.1.2-S1-TO-S2-HERMETIC-FIXTURE-RESOURCE-BLOCKER-DISPOSITION"
    )
    assert disposition["next_action"] == (
        "FIN-0.1.2-PRE-S2-HERMETIC-FIXTURE-RESOURCE-REBASELINE-"
        "MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    assert implementation["next_action"] == (
        "FIN-0.1.2-PRE-S2-RB-T03-INDEPENDENT-TWO-DISPOSABLE-"
        "REPLACEMENT-HERMETIC-PROOF"
    )
    assert stage_capsule["product_truth"]["S2_entry_authorized"] is False
    assert disposition["product_truth"]["S2_entry"] is False
    assert implementation["product_truth"]["S2_entry"] is False
