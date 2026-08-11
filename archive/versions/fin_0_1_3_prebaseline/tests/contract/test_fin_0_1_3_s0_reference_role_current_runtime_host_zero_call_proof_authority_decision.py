from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases/fin_ia_0_1_3_s0_reference_role_taxonomy_and_current_runtime_host_zero_call_engineering_proof_authority_decision_v1_0.json"
PROJECTION = ROOT / "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_6.json"
PROGRAM = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
S4 = ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
CAPABILITY = ROOT / "docs/project_os/capability_status_ledger.jsonl"
ROOT_CAUSE = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
EXTERNAL = ROOT / "docs/project_os/external_pattern_registry.jsonl"
CONTEXT = ROOT / "docs/project_os/current_context_pack.zh-CN.md"
NEXT = "FIN-0.1.3-S0-REFERENCE-ROLE-TAXONOMY-AND-CURRENT-RUNTIME-HOST-ZERO-CALL-ENGINEERING-PROOF"
AUTHORITY_SHA = "e1ab2dbfea350f309a19981fb9b625bfbff3892f6b1510e6bb3d6841d69486e8"
ISSUES = {
    "RC-P36-090-fin-0-1-2-pre-s2-t03-disposable-self-introspection-git-inventory-dependency",
    "RC-P36-091-fin-0-1-2-hermetic-package-recursive-json-ref-admits-ignored-runtime-state",
    "RC-P36-092-fin-0-1-2-code-declared-static-runtime-resource-missing-from-hermetic-inventory",
    "RC-P36-093-fin-0-1-2-hermetic-semantic-parity-untyped-host-python-traceback-path",
    "RC-P36-094-fin-0-1-3-hermetic-reference-role-taxonomy-conflates-semantic-audit-and-repository-paths",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_authority_is_single_future_host_proof_and_not_execution() -> None:
    decision = _load(DECISION)
    authority = decision["authority"]

    assert decision["status"] == "pass_authorize_one_future_v2_host_zero_call_engineering_proof_not_executed"
    assert decision["decision_label"] == "authorize_one_future_v2_host_zero_call_engineering_proof_only"
    assert authority["future_proof_execution_scope"] == NEXT
    assert authority["future_host_zero_call_engineering_proof_authorized"] is True
    assert authority["proof_executed_in_this_decision"] is False
    assert authority["maximum_future_host_proof_runs"] == 1
    assert authority["formal_two_disposable_proof_authorized"] is False
    assert authority["old_T03_rerun_or_reinterpretation_authorized"] is False
    assert authority["runtime_contract_resource_reference_or_environment_repair_during_proof"] is False
    assert authority["credential_model_provider_network_source_external_tool_admission_business_run_artifact_authorized"] is False
    assert set(decision["observed_counts_this_decision"].values()) == {0}
    assert decision["fixed_budget"]["v2_observed_after_this_authority_decision"] == [1, 0, 0]
    assert decision["next_action"] == NEXT


def test_authority_binds_exact_implementation_sources_and_clean_preflight() -> None:
    decision = _load(DECISION)
    assert _sha(DECISION) == AUTHORITY_SHA
    immutable_snapshot_roles = {
        "owner_exit_contract_v2_decision",
        "completed_v2_implementation",
        "immutable_implementation_snapshot_manifest",
        "six_role_reference_authority",
        "pre_decision_current_projection",
    }
    for binding in decision["source_bindings"]:
        path = ROOT / binding["ref"]
        assert path.is_file(), binding["ref"]
        assert len(binding["sha256"]) == 64
        if binding["role"] in immutable_snapshot_roles:
            assert _sha(path) == binding["sha256"], binding["ref"]

    preflight = decision["project_os_preflight"]
    assert preflight["status"] == "pass"
    assert preflight["missing_files"] == 0
    assert preflight["missing_capabilities"] == 0
    assert preflight["open_full_chain_blockers_for_this_authorized_scope"] == 0
    assert preflight["packaged_or_business_promotable"] is False
    assert decision["clean_head_precondition"]["head"] == decision["clean_head_precondition"]["upstream_head"]
    assert decision["clean_head_precondition"]["worktree_clean"] is True
    assert decision["clean_head_precondition"]["independent_zero_call_matrix"].startswith("83_passed")


def test_proof_contract_forbids_inline_repair_retry_and_promotion() -> None:
    decision = _load(DECISION)
    package = decision["future_proof_packaging_contract"]
    stop = decision["success_and_stop_rules"]

    assert package["new_execution_manifest_required"] is True
    assert package["orchestration_only_runner_may_be_created"] is True
    assert package["shared_runtime_or_contract_source_change_allowed"] is False
    assert package["implementation_snapshot_manifest_v1_2_mutation_allowed"] is False
    assert package["network_socket_blocked"] is True
    assert package["provider_credential_environment_scrubbed"] is True
    assert package["repository_readback_before_after_equal"] is True
    assert package["failed_package_business_promotable"] is False
    assert stop["host_success_automatically_closes_RC_P36_090_through_094"] is False
    assert stop["host_success_automatically_authorizes_formal_proof"] is False
    assert "terminal_stop_no_patch_retry_replacement" in stop["failure_behavior"]


def test_authority_projection_is_an_immutable_authorized_not_executed_snapshot() -> None:
    projection = _load(PROJECTION)

    assert projection["host_proof_authority_binding"]["sha256"] == AUTHORITY_SHA
    assert projection["expectations"]["current_next_action"] == NEXT
    assert projection["expectations"]["FIN_0_1_3_S0_v2_observed_implementation_host_formal"] == [1, 0, 0]
    assert projection["expectations"]["FIN_0_1_3_S0_v2_host_proof_executed"] is False
    assert projection["expectations"]["capability_stage_acceptance"]["FIN_0_1_3_S0_v2_host_proof"] == "authorized_not_executed"


def test_authority_projection_remains_a_valid_historical_event() -> None:
    projection = _load(PROJECTION)

    assert projection["host_proof_authority_binding"]["sha256"] == AUTHORITY_SHA
    assert projection["expectations"]["current_next_action"] == NEXT
    assert projection["expectations"]["FIN_0_1_3_S0_v2_host_proof_executed"] is False


def test_project_os_records_the_authority_event_without_rewriting_issues() -> None:
    capability = next(
        row
        for row in _jsonl(CAPABILITY)
        if row.get("capability_id")
        == "fin_0_1_3_S0_reference_role_and_current_runtime_host_zero_call_proof_authority"
    )
    assert capability["capability_id"] == "fin_0_1_3_S0_reference_role_and_current_runtime_host_zero_call_proof_authority"
    assert capability["status"] == "pass_authorize_one_future_v2_host_zero_call_engineering_proof_not_executed"
    assert capability["current_next"] == NEXT

    authority_rows: dict[str, dict] = {}
    for row in _jsonl(ROOT_CAUSE):
        if row.get("issue_id") in ISSUES and row.get("recorded_at") == "2026-08-01T21:00:00+08:00":
            authority_rows[row["issue_id"]] = row
    assert set(authority_rows) == ISSUES
    for row in authority_rows.values():
        assert row["status"] == "open"
        assert row["full_chain_blocker"] is True
        assert row["allowed_run_scopes"] == [NEXT, "restricted_audit_evidence_review", "repository_and_git_hygiene"]
        assert row["verification"]["host_proof_authorized"] is True
        assert row["verification"]["host_proof_executed"] is False

    pattern = next(
        row
        for row in _jsonl(EXTERNAL)
        if row.get("status")
        == "FIN_0_1_3_S0_v2_host_zero_call_engineering_proof_authorized_not_executed"
    )
    assert pattern["status"] == "FIN_0_1_3_S0_v2_host_zero_call_engineering_proof_authorized_not_executed"
    assert pattern["verification"]["host_proof_executed"] is False
    assert "v2 host zero-call engineering proof 已获单次授权、尚未执行" in CONTEXT.read_text(encoding="utf-8")


def test_old_t03_is_immutable_and_authority_records_no_proof_execution() -> None:
    decision = _load(DECISION)
    assert decision["fixed_budget"]["old_T03_engineering_proof_runs"] == [1, 1]
    assert decision["fixed_budget"]["old_T04_formal_packages"] == [0, 1]
    assert decision["authority"]["proof_executed_in_this_decision"] is False
    assert decision["observed_counts_this_decision"]["host_proof_runs"] == 0
