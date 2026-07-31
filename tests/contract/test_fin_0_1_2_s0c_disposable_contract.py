from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sec_agent.runtime_contract_governance import (
    validate_active_test_suite_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s0c_t02_hermetic_test_topology_and_"
    "allowlisted_package_closure_minimum_zero_call_implementation_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v1_0.json"
)
MANIFEST = ROOT / (
    "configs/releases/fin_ia_0_1_2_s0c_t03_corrective_"
    "hermetic_proof_manifest_v1_0.json"
)
NEXT = (
    "FIN-0.1.2-S0C-T03-INDEPENDENT-TWO-DISPOSABLE-CORRECTIVE-"
    "HERMETIC-PROOF-AND-CLOSEOUT"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_S0C_decision_and_T02_event_are_bound_without_rewrite() -> None:
    implementation = _load(IMPLEMENTATION)
    parent = implementation["immutable_parent_decision"]
    assert parent["path"].endswith(
        "s0c_hermetic_test_topology_and_allowlisted_package_closure_"
        "scope_decision_v1_0.json"
    )
    assert len(parent["sha256"]) == 64
    assert parent["historical_event_rewritten"] is False
    assert implementation["status"] == (
        "pass_S0C_T02_zero_call_implementation_host_matrix_green_"
        "T03_corrective_proof_ready"
    )
    assert implementation["authority"]["implementation_bundles_consumed"] == 1
    assert implementation["authority"]["corrective_proof_packages_consumed"] == 0


def test_disposable_consumes_only_the_host_validated_projection_snapshot() -> None:
    implementation = _load(IMPLEMENTATION)
    projection = _load(PROJECTION)
    binding = implementation["current_projection_binding"]
    assert binding["ref"] == str(PROJECTION.relative_to(ROOT)).replace("\\", "/")
    assert binding["sha256"] == _sha256(PROJECTION)
    assert projection["expectations"]["current_next_action"] == NEXT
    assert projection["expectations"][
        "implementation_and_corrective_proof_packages"
    ] == [1, 0]
    assert projection["expectations"]["S2_entry_authorized"] is False
    assert projection["package_governance"]["host_sources_packaged"] is False
    assert projection["package_governance"]["disposable_git_required"] is False


def test_T03_manifest_uses_strict_closure_and_excludes_host_only_gates() -> None:
    manifest = _load(MANIFEST)
    validate_active_test_suite_manifest(manifest)
    policy = manifest["hermetic_package_policy"]
    reference_policy = policy["repository_reference_policy"]
    selected_paths = {
        path
        for suite in manifest["suites"]
        if suite["selected"]
        for path in suite["test_paths"]
    }
    assert manifest["status"] == "S0C_T03_ready_unexecuted_after_T02_pass"
    assert reference_policy["explicit_allowlist"] == []
    assert ".codex_runtime" in reference_policy["forbidden_prefixes"]
    assert reference_policy["untracked_or_ignored_reference_behavior"] == (
        "fail_closed"
    )
    assert policy["disposable_git_subprocess_calls_allowed"] == 0
    assert policy["ignored_or_untracked_repository_paths_packaged_maximum"] == 0
    assert (
        "tests/contract/test_fin_0_1_2_current_program_projection.py"
        not in selected_paths
    )
    assert (
        "tests/contract/test_fin_0_1_2_s0c_hermetic_topology_and_"
        "allowlisted_package_closure.py"
        not in selected_paths
    )
    assert (
        "tests/contract/test_fin_0_1_2_pre_s2_hermetic_fixture_resource_"
        "rebaseline_minimum_zero_call_implementation.py"
        not in selected_paths
    )


def test_T02_does_not_inflate_product_or_release_truth() -> None:
    implementation = _load(IMPLEMENTATION)
    truth = implementation["product_truth"]
    assert truth["S0C_T02"] == "engineering_pass"
    assert truth["S0C_T03"] == "ready_not_started"
    assert truth["S2_entry"] is False
    assert truth["DELL_R2"] is False
    assert truth["MU_R2"] is False
    assert truth["post_transfer_NVDA_exact_product"] is False
    assert truth["NVDA_R3"] is False
    assert truth["FIN_0_1_release_qualified"] is False
    assert implementation["next_action"] == NEXT
