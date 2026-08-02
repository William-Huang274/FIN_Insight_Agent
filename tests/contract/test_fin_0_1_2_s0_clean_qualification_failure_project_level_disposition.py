from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sec_agent.hermetic_test_runner import (
    validate_host_current_program_projection,
)


ROOT = Path(__file__).resolve().parents[2]
DECISION_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_2_s0_clean_qualification_failure_"
    "project_level_disposition_v1_0.json"
)
TERMINAL_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_2_s0_fresh_clean_environment_qualification_"
    "terminal_failure_and_project_level_disposition_required_v1_0.json"
)
PROJECTION_REF = Path(
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_3.json"
)
PROGRAM_REF = Path(
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_REF = Path(
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
CAPABILITY_REF = Path("docs/project_os/capability_status_ledger.jsonl")
ISSUE_REF = Path("docs/project_os/root_cause_issue_ledger.jsonl")
PATTERN_REF = Path("docs/project_os/external_pattern_registry.jsonl")
PRODUCT_PLAN_REF = Path(
    "docs/product/"
    "FIN_0_1_2_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260802.zh-CN.md"
)
S0_PLAN_REF = Path(
    "docs/architecture/repository/"
    "FIN_0_1_2_S0_CURRENT_BASELINE_AND_CLEAN_ENVIRONMENT_"
    "QUALIFICATION_PLAN_20260802.zh-CN.md"
)
NEXT = (
    "FIN-0.1.2-S0-PHASE-AWARE-TEST-TOPOLOGY-AND-TYPED-TEST-"
    "DEPENDENCY-COMPILER-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _load(path: Path) -> dict[str, Any]:
    return json.loads(
        (ROOT / path).read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line, object_pairs_hook=_strict_object)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def test_decision_binds_terminal_failure_and_changes_no_product_version() -> None:
    decision = _load(DECISION_REF)
    assert decision["status"] == (
        "pass_keep_FIN_0_1_2_in_S0_select_phase_aware_test_topology_"
        "and_typed_test_dependency_compiler_implementation_pending"
    )
    assert decision["product_truth"]["current_product_version"] == "FIN_0_1_2"
    assert decision["product_truth"]["current_stage"] == "S0"
    assert decision["product_truth"]["S1_through_S5"] == (
        "not_started_under_consolidated_baseline"
    )
    assert decision["product_truth"]["FIN_0_2_definition_changed"] is False
    sources = {row["role"]: row for row in decision["source_bindings"]}
    terminal = sources["immutable_clean_qualification_terminal_failure"]
    assert terminal["ref"] == TERMINAL_REF.as_posix()
    assert terminal["sha256"] == _sha256(TERMINAL_REF)


def test_selected_phase_contract_separates_gating_and_historical_truth() -> None:
    decision = _load(DECISION_REF)
    phases = decision["selected_contract"]["execution_phases"]
    assert [row["phase"] for row in phases] == [
        "contract_compile",
        "host_preflight",
        "disposable_current_gate",
        "historical_audit",
        "post_run_attestation",
    ]
    assert {
        row["phase"]
        for row in phases
        if row["gates_current_candidate"]
    } == {
        "contract_compile",
        "host_preflight",
        "disposable_current_gate",
        "post_run_attestation",
    }
    historical = next(
        row for row in phases if row["phase"] == "historical_audit"
    )
    assert historical["gates_current_candidate"] is False
    ownership = decision["selected_contract"]["module_ownership_rules"]
    assert ownership["one_selected_test_module_has_exactly_one_execution_phase"]
    assert ownership["mixed_phase_modules_must_be_split_before_selection"]
    assert ownership["gating_role_is_derived_from_phase_not_duplicated_per_suite"]


def test_typed_dependency_and_environment_contract_forbid_observed_file_patches() -> None:
    decision = _load(DECISION_REF)
    compiler = decision["selected_contract"]["typed_dependency_compiler"]
    assert compiler["dependency_bundle_resolver_types"] == [
        "python_import_closure",
        "runtime_resource_registry_closure",
        "reference_role_repository_closure",
        "current_projection_binding_and_source_paths_closure",
        "immutable_event_root_closure",
        "tracked_fixture_prefix",
    ]
    assert compiler["per_observed_file_exception_list_forbidden"] is True
    assert compiler["git_and_codex_runtime_never_enter_disposable_package"] is True
    environment = decision["selected_contract"][
        "environment_and_capture_contract"
    ]
    assert environment["uri_is_parsed_before_filesystem_absolute_path_detection"]
    assert environment["raw_stdout_stderr_detail_collection_and_terminal_content_remain_byte_preserved"]
    assert environment["unknown_host_absolute_paths_after_typed_projection_fail_closed"]


def test_iteration_policy_allows_local_repair_without_blind_formal_retry() -> None:
    policy = _load(DECISION_REF)["iteration_and_proof_policy"]
    assert policy[
        "local_unit_contract_fixture_and_mutation_runs_are_normal_implementation_verification"
    ]
    assert policy["local_zero_call_test_iteration_is_not_a_product_version_or_formal_attempt"]
    assert policy["formal_clean_qualification_authorized_now"] is False
    assert policy["future_formal_qualification_requires_separate_authority_after_engineering_pass"]
    assert policy["one_formal_qualification_per_committed_candidate"]
    assert policy["same_candidate_blind_retry"] is False
    assert policy["new_candidate_after_documented_root_cause_fix_keeps_FIN_0_1_2_in_S0"]
    assert policy["failure_automatically_creates_product_version"] is False


def test_current_projection_and_backlogs_share_the_new_implementation_entry() -> None:
    projection = _load(PROJECTION_REF)
    assert validate_host_current_program_projection(
        ROOT, PROJECTION_REF.as_posix()
    ) == PROJECTION_REF
    assert projection["decision_binding"] == {
        "ref": DECISION_REF.as_posix(),
        "sha256": _sha256(DECISION_REF),
        "binding_role": (
            "current_project_level_disposition_and_selected_S0_"
            "structural_implementation_contract"
        ),
    }
    assert projection["lifecycle_state"] == "in_progress"
    assert projection["current_truth"]["current_next_action"] == NEXT
    assert projection["execution_authority"]["focused_s0_repair_authorized"] is False
    assert projection["execution_authority"]["clean_environment_acceptance_authorized"] is False

    program = _load(PROGRAM_REF)
    s4 = _load(S4_REF)
    assert program["current_version_rebaseline"]["projection_ref"] == (
        PROJECTION_REF.as_posix()
    )
    assert program["next_action"]["item_id"] == NEXT
    assert program["next_action"]["current_project_disposition_sha256"] == (
        _sha256(DECISION_REF)
    )
    assert s4["current_next_action"] == NEXT


def test_ledgers_keep_only_live_open_issues_and_external_pattern_is_advisory() -> None:
    capability = _jsonl(CAPABILITY_REF)[-1]
    assert capability["status"] == (
        "project_disposition_pass_structural_implementation_pending"
    )
    assert capability["current_next"] == NEXT

    issues = _jsonl(ISSUE_REF)
    latest = {
        number: [
            row
            for row in issues
            if f"RC-P36-{number:03d}" in row.get("issue_id", "")
        ][-1]
        for number in range(90, 98)
    }
    assert {number for number, row in latest.items() if row["status"] == "closed"} == {
        92,
        96,
    }
    assert {number for number, row in latest.items() if row["status"] == "open"} == {
        90,
        91,
        93,
        94,
        95,
        97,
    }
    for number in (90, 91, 93, 94, 95, 97):
        assert latest[number]["allowed_run_scopes"][0] == NEXT

    pattern = _jsonl(PATTERN_REF)[-1]
    assert pattern["pattern_id"] == (
        "hermetic_tests_need_phase_ownership_and_declared_runtime_data_dependencies"
    )
    assert pattern["status"].endswith("implementation_pending")
    assert pattern["verification"]["implementation_executed"] is False


def test_living_product_and_s0_plans_name_the_same_bounded_next_action() -> None:
    product = (ROOT / PRODUCT_PLAN_REF).read_text(encoding="utf-8")
    s0 = (ROOT / S0_PLAN_REF).read_text(encoding="utf-8")
    assert NEXT in product
    assert NEXT in s0
    assert "S1–S5、模型/Provider、真实业务链和产品 Artifact 均未授权" in product
    assert "新 formal qualification attempt" in s0
