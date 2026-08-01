from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sec_agent.runtime_contract_governance import validate_active_test_suite_manifest


ROOT = Path(__file__).resolve().parents[2]
CLOSEOUT_REF = (
    "configs/releases/fin_ia_0_1_3_s0_t03_host_zero_call_engineering_"
    "proof_terminal_honest_block_closeout_v1_0.json"
)
ACTIVE_MANIFEST_REF = (
    "configs/releases/fin_ia_0_1_3_s0_active_test_suite_manifest_v1_1.json"
)
CURRENT_PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_3.json"
)
FROZEN_T02_ACTIVE_MANIFEST_REF = (
    "configs/releases/fin_ia_0_1_3_s0_active_test_suite_manifest_v1_0.json"
)
FROZEN_T02_CURRENT_TEST = (
    "tests/contract/test_fin_0_1_3_s0_active_suite.py"
)
NEXT_ACTION = (
    "FIN-0.1.3-S0-T03-TERMINAL-HONEST-BLOCK-AND-REFERENCE-ROLE-"
    "TAXONOMY-OWNER-VERSION-DISPOSITION-DECISION"
)


def _load(ref: str) -> dict[str, Any]:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _sha256(ref: str) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def _load_jsonl(ref: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (ROOT / ref).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_T03_closeout_preserves_immutable_failure_snapshot_bindings() -> None:
    closeout = _load(CLOSEOUT_REF)
    assert closeout["status"] == (
        "terminal_failed_unique_T03_engineering_proof_consumed_T04_blocked"
    )
    bindings = {
        binding["role"]: (binding["ref"], binding["sha256"])
        for binding in closeout["source_bindings"]
    }
    assert bindings["repository_closure_compiler"] == (
        "src/sec_agent/hermetic_test_runner.py",
        "5e1f06ede2bde8893aaac7e704741e3fcc390bf050428dc9e57145746e99478f",
    )
    for role in (
        "immutable_T01_stage_plan",
        "T02_implementation_record",
        "T03_execution_manifest",
        "T02_active_suite_manifest",
        "T03_host_proof_runner",
        "first_failure_resource",
    ):
        ref, digest = bindings[role]
        assert digest == _sha256(ref)
    assert _sha256("src/sec_agent/hermetic_test_runner.py") != bindings[
        "repository_closure_compiler"
    ][1]
    failure = closeout["first_credible_failure"]
    assert failure == {
        "phase": (
            "host_compiled_repository_inventory_before_application_import_"
            "collect_or_pytest"
        ),
        "error_type": "HermeticTestRunnerError",
        "error_code": "hermetic_repository_reference_classification_missing",
        "field": "followup_ref",
        "value": "official quarterly cohort/definition bridge",
        "resource_id": "s4.source_grounded_input.dell",
        "resource_ref": (
            "configs/releases/fin_ia_0_1_s4_t04_dell_source_grounded_"
            "input_pack_v1_0.json"
        ),
        "resource_line": 1169,
        "application_modules_imported": 0,
        "active_tests_collected": 0,
        "active_tests_executed": 0,
        "diagnostic_artifacts_created": 0,
    }
    assert closeout["proof_evidence"]["verification_sha256"] == (
        "80d0250334c37bb881eecd63e191e183c47a149c9287a6bd75df41416e631538"
    )
    assert _sha256(FROZEN_T02_ACTIVE_MANIFEST_REF) == (
        "ec3be712618a03e5792984e46054954571c98c52a767cab0aa261bb31ef614be"
    )


def test_collect_all_diagnostic_exposes_structural_taxonomy_gap_only() -> None:
    diagnostic = _load(CLOSEOUT_REF)["read_only_collect_all_diagnostic"]
    assert diagnostic["status"] == (
        "nonpromotable_hypothetical_classification_only"
    )
    assert diagnostic["registered_resource_ref_values_scanned"] == 507
    assert diagnostic["registered_resource_classification_counts"] == {
        "semantic": 440,
        "external": 58,
        "repository_path": 8,
        "unclassified_path_reference": 1,
    }
    assert diagnostic["hypothetical_reference_field_count_before_closure_completed"] == 47
    assert len(diagnostic["hypothetical_reference_fields"]) == 47
    assert len(set(diagnostic["hypothetical_reference_fields"])) == 47
    assert diagnostic["hypothetical_reference_value_families"] == {
        "business_semantic_followup": 1,
        "ignored_codex_runtime_audit_lineage": 44,
        "tracked_model_run_report_lineage": 2,
    }
    assert diagnostic["hypothetical_closure"] == {
        "path_count": 1218,
        "tracked_path_count": 1218,
        "explicit_allowlist_path_count": 0,
        "recursive_reference_path_count": 527,
        "semantic_or_external_reference_count": 2566,
        "closure_digest": (
            "c54b6131565049b3dbd68726d8f0f7aa246034937f0a2a5fa4fd9030cab771c9"
        ),
    }
    assert diagnostic["does_not_reinterpret_or_pass_T03"] is True
    assert diagnostic["repository_mutation_or_runtime_patch"] is False


def test_T03_budget_and_product_truth_stop_before_T04() -> None:
    closeout = _load(CLOSEOUT_REF)
    assert closeout["budgets"] == {
        "maximum_implementation_bundles": 1,
        "implementation_bundles_consumed": 1,
        "maximum_T03_engineering_proof_runs": 1,
        "T03_engineering_proof_runs_consumed": 1,
        "maximum_formal_two_disposable_proof_packages": 1,
        "formal_two_disposable_proof_packages_consumed": 0,
        "second_T03_or_T04_authorized": False,
    }
    assert all(value == 0 for value in closeout["observed_counts"].values())
    truth = closeout["product_truth"]
    assert truth["FIN_0_1_3_S0_T03"] == "terminal_failed_unique_run_consumed"
    assert truth["FIN_0_1_3_S0_T04"] == "blocked_not_executed"
    assert truth["FIN_0_1_3_S1"] == "not_started"
    assert truth["FIN_0_1_3_S2_entry"] is False
    assert truth["FIN_0_1_release_qualified"] is False
    assert truth["FIN_0_2_definition_changed"] is False
    assert closeout["next_action"] == NEXT_ACTION


def test_terminal_active_manifest_replaces_stale_T02_current_owner() -> None:
    manifest = _load(ACTIVE_MANIFEST_REF)
    validate_active_test_suite_manifest(manifest)
    assert manifest["status"] == (
        "S0_T03_terminal_failed_unique_engineering_proof_consumed_T04_blocked"
    )
    selected_paths = {
        path
        for suite in manifest["suites"]
        if suite["selected"]
        for path in suite["test_paths"]
    }
    assert FROZEN_T02_CURRENT_TEST not in selected_paths
    assert manifest["fixed_budget"]["engineering_proof_runs_consumed"] == 1
    assert manifest["fixed_budget"][
        "formal_two_disposable_proof_packages_consumed"
    ] == 0
    assert manifest["fixed_budget"]["automatic_second_T03_or_T04"] is False
    assert manifest["next_action_on_T03_failure"] == NEXT_ACTION


def test_frozen_T03_projection_preserves_the_terminal_event_snapshot() -> None:
    projection = _load(CURRENT_PROJECTION_REF)
    expectations = projection["expectations"]
    sources = projection["source_paths"]
    assert projection["status"] == (
        "current_FIN_0_1_3_S0_T03_terminal_failed_unique_run_consumed_"
        "T04_blocked"
    )
    assert expectations["current_next_action"] == NEXT_ACTION
    assert expectations["FIN_0_1_3_S0_T03_engineering_proof_runs"] == [1, 1]
    assert expectations["FIN_0_1_3_S0_T04"] == "blocked_not_executed"
    assert expectations["FIN_0_1_release_qualified"] is False
    assert all(
        (ROOT / value).is_file()
        for value in sources.values()
    )
    assert expectations["active_slice"] == (
        "FIN_0_1_3_S0_TERMINAL_HONEST_BLOCK_REFERENCE_ROLE_TAXONOMY_"
        "DISPOSITION"
    )
    assert expectations["capability_stage_acceptance"]["FIN_0_1_3_S0_T03"] == (
        "terminal_failed_unique_engineering_proof_consumed"
    )
    assert expectations["pattern_status"] == (
        "FIN_0_1_3_S0_T03_terminal_failed_typed_reference_role_taxonomy_"
        "missing"
    )
