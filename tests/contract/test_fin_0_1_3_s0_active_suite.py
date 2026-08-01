from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sec_agent.hermetic_test_runner import (
    _load_semantic_parity_contract,
    _policy_contract_paths,
    validate_host_current_program_projection,
)
from sec_agent.runtime_contract_governance import (
    validate_active_test_suite_manifest,
)
from sec_agent.runtime_resource_registry import load_runtime_resource_registry


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_REF = (
    "configs/releases/fin_ia_0_1_3_s0_active_test_suite_manifest_v1_0.json"
)
IMPLEMENTATION_REF = (
    "configs/releases/fin_ia_0_1_3_s0_t02_runtime_resource_registry_and_"
    "typed_environment_projection_minimum_zero_call_implementation_v1_0.json"
)
CURRENT_PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_2.json"
)
NEXT_ACTION = (
    "FIN-0.1.3-S0-HOST-IMPORT-COLLECT-RESOURCE-MUTATION-AND-THREE-CASE-"
    "FULL-FAKE-ZERO-CALL-PROOF"
)


def _load(ref: str) -> dict[str, Any]:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _sha256(ref: str) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def test_active_manifest_has_one_owner_per_proof_class_and_validates() -> None:
    manifest = _load(MANIFEST_REF)
    validate_active_test_suite_manifest(manifest)
    selected = [row for row in manifest["suites"] if row["selected"]]
    assert {row["proof_class"] for row in selected} == {
        "immutable_event",
        "current_projection",
        "current_runtime",
        "historical_audit",
        "release_gate",
    }
    assert len(selected) == 5
    assert manifest["next_action_on_T02_pass"] == NEXT_ACTION


def test_package_policy_compiles_registry_contract_and_projection_closure() -> None:
    manifest = _load(MANIFEST_REF)
    policy = manifest["hermetic_package_policy"]
    registry = load_runtime_resource_registry(
        ROOT,
        policy["runtime_resource_registry_ref"],
    )
    semantic, semantic_ref, _ = _load_semantic_parity_contract(ROOT, manifest)
    assert semantic is not None
    assert semantic_ref == policy["semantic_parity_contract_ref"]
    paths = {path.as_posix() for path in _policy_contract_paths(ROOT, policy)}
    assert {path.as_posix() for path in registry.package_paths()}.issubset(paths)
    assert policy["semantic_parity_contract_ref"] in paths
    assert validate_host_current_program_projection(
        ROOT,
        policy["host_current_program_projection_ref"],
    ).as_posix() == CURRENT_PROJECTION_REF


def test_T02_implementation_record_binds_current_files_and_zero_call_truth() -> None:
    record = _load(IMPLEMENTATION_REF)
    assert record["status"] == "engineering_pass_T02_complete_T03_ready_unexecuted"
    for binding in record["source_bindings"]:
        assert binding["sha256"] == _sha256(binding["ref"])
    assert record["runtime_resource_registry"]["resource_count"] == 29
    assert record["runtime_resource_registry"]["resource_bytes"] == 323829
    assert record["typed_environment_projection"]["typed_root_count"] == 8
    assert record["active_suite"]["manifest_ref"] == MANIFEST_REF
    assert record["budgets"]["implementation_bundles_consumed"] == 1
    assert record["budgets"]["engineering_proof_runs_consumed"] == 0
    assert record["budgets"]["formal_two_disposable_proof_packages_consumed"] == 0
    assert all(
        record["observed_counts"][key] == 0
        for key in (
            "credential_reads_or_probes",
            "model_calls",
            "provider_calls",
            "network_source_or_external_tool_calls",
            "new_admissions",
            "business_runs",
            "business_artifacts",
            "formal_two_disposable_proof_packages_created_or_executed",
        )
    )
    assert record["next_action"] == NEXT_ACTION


def test_T02_does_not_inflate_product_or_formal_proof_truth() -> None:
    record = _load(IMPLEMENTATION_REF)
    truth = record["product_truth"]
    assert truth["FIN_0_1_3_S0_T02"] == "engineering_pass"
    assert truth["FIN_0_1_3_S0_T03"] == "ready_not_started"
    assert truth["FIN_0_1_3_S0_T04"] == "locked"
    assert truth["FIN_0_1_3_S1"] == "not_started"
    assert truth["FIN_0_1_3_S2_entry"] is False
    assert truth["FIN_0_1_release_qualified"] is False
    assert truth["FIN_0_2_definition_changed"] is False


def test_current_projection_is_single_T02_state_owner() -> None:
    projection = _load(CURRENT_PROJECTION_REF)
    expectations = projection["expectations"]
    assert projection["status"] == (
        "current_host_validated_FIN_0_1_3_S0_T02_implementation_pass_T03_ready"
    )
    assert expectations["current_next_action"] == NEXT_ACTION
    assert expectations["FIN_0_1_3_S0_implementation_and_formal_proof_packages"] == [
        1,
        0,
    ]
    assert expectations["FIN_0_1_3_S0_T02"] == "engineering_pass"
    assert expectations["FIN_0_1_3_S0_T03"] == "ready_not_started"
    assert expectations["FIN_0_1_release_qualified"] is False
