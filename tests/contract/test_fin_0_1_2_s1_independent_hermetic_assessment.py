from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.runtime_contract_governance import (
    validate_active_test_suite_manifest,
)


CAPSULE = ROOT / "configs/releases/fin_ia_0_1_2_s1_stage_capsule_v1_0.json"
STAGE_PLAN = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_realistic_three_case_"
    "deterministic_vertical_stage_plan_v1_0.json"
)
ASSESSMENT_MANIFEST = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_t04_independent_"
    "assessment_manifest_v1_0.json"
)
STAGE_ASSESSMENT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_stage_assessment_v1_0.json"
)
STAGE_CLOSEOUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s1_stage_closeout_v1_0.json"
)
FROZEN_STAGE_PLAN_SHA256 = (
    "a51d241e56417ad6005ca1fecb4495a9b899945d8f50bfb595045934d88a77b7"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_t03_failure_is_retained_and_classified_before_runtime_execution() -> None:
    capsule = _load(CAPSULE)
    proof = capsule["t03_hermetic_proof_package"]
    assert proof["status"] == "failed_collection_no_tests_executed"
    assert proof["failure_class"] == (
        "hermetic_dependency_inventory_incomplete"
    )
    assert proof["missing_module"] == "retrieval"
    assert proof["missing_repository_prefix"] == "src"
    assert proof["disposable_runtime_count"] == 2
    assert proof["disposable_failure_parity"] is True
    assert proof["tests_collected"] == 0
    assert proof["runtime_L1_failure_established"] is False
    assert proof["model_or_provider_fault_established"] is False
    assert proof["business_output_promotable"] is False
    assert proof["automatic_T03_reproof_forbidden"] is True
    for field in (
        "package_manifest_sha256",
        "verification_sha256",
        "disposable_a_terminal_result_sha256",
        "disposable_b_terminal_result_sha256",
    ):
        assert len(proof[field]) == 64


def test_T04_manifest_closes_full_src_dependency_and_binds_T03_evidence() -> None:
    manifest = _load(ASSESSMENT_MANIFEST)
    validate_active_test_suite_manifest(manifest)
    prefixes = {
        row["path"]: set(row["suffixes"])
        for row in manifest["hermetic_package_policy"][
            "repository_prefixes"
        ]
    }
    assert prefixes["src"] == {".py"}
    assert "src/sec_agent" not in prefixes
    bindings = manifest["hermetic_package_policy"][
        "external_read_only_bindings"
    ]
    assert len(bindings) == 1
    assert bindings[0]["binding_object_field"] == (
        "t03_hermetic_proof_package"
    )
    assert len(bindings[0]["files"]) == 4


def test_T04_budget_is_consumed_and_S1_is_closed_honest_block() -> None:
    capsule = _load(CAPSULE)
    assert capsule["status"] == (
        "S1_closed_honest_block_G2_not_proven_S2_entry_blocked"
    )
    assert capsule["next_action"] == (
        "FIN-0.1.2-S1-TO-S2-HERMETIC-FIXTURE-RESOURCE-"
        "BLOCKER-DISPOSITION"
    )
    events = {row["task_id"]: row for row in capsule["stage_events"]}
    assert events["S1-T03"]["status"] == (
        "failed_hermetic_collection_no_tests_executed"
    )
    assert events["S1-T04"]["status"] == (
        "failed_current_gate_hermetic_resource_closure_incomplete"
    )
    assert hashlib.sha256(STAGE_PLAN.read_bytes()).hexdigest() == (
        FROZEN_STAGE_PLAN_SHA256
    )
    assert capsule["immutable_stage_plan"]["rewritten"] is False
    truth = capsule["product_truth"]
    assert not truth["DELL_R2"]
    assert not truth["MU_R2"]
    assert not truth["post_transfer_NVDA_exact_product"]
    assert not truth["NVDA_R3"]
    assert not truth["FIN_0_1_release_qualified"]
    assert truth["S1_closed_honest_block"] is True
    assert truth["S2_entry_authorized"] is False


def test_T04_failure_is_complete_and_does_not_inflate_runtime_or_model_fault() -> None:
    capsule = _load(CAPSULE)
    package = capsule["t04_independent_assessment_package"]
    assert package["status"] == "failed_current_gate"
    assert package["tests_passed_each"] == 25
    assert package["tests_failed_each"] == 11
    assert package["collection_errors_each"] == 0
    assert package["identical_failure_nodeids"] is True
    assert package["complete_per_test_and_process_output_content_addressed"] is True
    assert package["repository_unchanged"] is True
    assert package["runtime_L1_failure_established"] is False
    assert package["model_or_provider_fault_established"] is False
    assert package["business_output_promotable"] is False
    assert package["automatic_T04_reproof_forbidden"] is True


def test_assessment_and_closeout_bind_the_honest_block_boundary() -> None:
    capsule = _load(CAPSULE)
    assessment = _load(STAGE_ASSESSMENT)
    closeout = _load(STAGE_CLOSEOUT)
    assert hashlib.sha256(STAGE_ASSESSMENT.read_bytes()).hexdigest() == (
        capsule["stage_assessment"]["sha256"]
    )
    assert hashlib.sha256(STAGE_CLOSEOUT.read_bytes()).hexdigest() == (
        capsule["stage_closeout"]["sha256"]
    )
    assert assessment["status"] == "honest_block_G2_not_hermetically_proven"
    assert assessment["fixed_budget_consumption"]["remaining_S1_packages"] == 0
    assert assessment["failure_classification"][
        "runtime_L1_failure_established"
    ] is False
    assert closeout["status"] == (
        "closed_honest_block_G2_not_proven_S2_entry_blocked"
    )
    assert closeout["scope_boundary"]["S1_T05_exists"] is False
    assert closeout["blocking_truth"]["S2_entry"] is False


def test_S1_remains_zero_call_and_NVDA_fixture_boundary_is_explicit() -> None:
    capsule = _load(CAPSULE)
    assert all(value == 0 for value in capsule["observed_counts"].values())
    manifest = _load(ASSESSMENT_MANIFEST)
    historical = next(
        row
        for row in manifest["suites"]
        if row["proof_class"] == "historical_audit"
    )
    assert historical["gates_current_release"] is False
    assert "NVDA_compatibility_fixture_boundary" in historical[
        "assertion_surfaces"
    ]
