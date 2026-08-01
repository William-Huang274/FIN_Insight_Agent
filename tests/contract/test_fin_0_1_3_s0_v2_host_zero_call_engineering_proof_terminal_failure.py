from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLOSEOUT = ROOT / "configs/releases/fin_ia_0_1_3_s0_v2_host_zero_call_engineering_proof_terminal_failure_and_project_level_disposition_required_v1_0.json"
PROJECTION = ROOT / "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_7.json"
PROGRAM = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
S4 = ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
CAPABILITY = ROOT / "docs/project_os/capability_status_ledger.jsonl"
ROOT_CAUSE = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
EXTERNAL = ROOT / "docs/project_os/external_pattern_registry.jsonl"
CONTEXT = ROOT / "docs/project_os/current_context_pack.zh-CN.md"
ACTIVE = ROOT / "configs/releases/fin_ia_0_1_3_s0_v2_host_zero_call_engineering_proof_active_suite_manifest_v1_0.json"
COMPILER = ROOT / "src/sec_agent/hermetic_test_runner.py"
NEXT = "FIN-0.1.3-S0-V2-HOST-PROOF-FIRST-CREDIBLE-FAILURE-PROJECT-LEVEL-DISPOSITION-DECISION"
CLOSEOUT_SHA = "5e452fdef23b8492feeabef994731a2997c3eee11b9ed0865ff6ec584d57f6b1"
PROJECTION_SHA = "67f7a75058b1d65be27cc99debab05d35ec266c0fea61e3b05ba3575249d2d0d"
ISSUE = "RC-P36-095-fin-0-1-3-v2-host-proof-manifest-policy-enum-contract-drift"
PRIOR_ISSUES = {
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


def test_terminal_failure_consumes_the_only_host_run_without_retry_or_formal_proof() -> None:
    closeout = _load(CLOSEOUT)

    assert _sha(CLOSEOUT) == CLOSEOUT_SHA
    assert closeout["status"] == "terminal_failed_unique_v2_host_proof_consumed_project_level_disposition_required"
    assert closeout["budgets"]["v2_maximum_implementation_host_formal"] == [1, 1, 1]
    assert closeout["budgets"]["v2_observed_after_terminal_failure"] == [1, 1, 0]
    assert closeout["authority"]["patch_retry_replacement_or_second_host_run_authorized"] is False
    assert closeout["authority"]["formal_two_disposable_proof_authorized_or_consumed"] is False
    assert set(closeout["stop_rule_enforcement"].values()) == {False}
    assert closeout["next_action"] == NEXT


def test_first_failure_is_proof_packaging_policy_drift_before_runtime_behavior() -> None:
    closeout = _load(CLOSEOUT)
    failure = closeout["first_credible_failure"]
    root_cause = closeout["root_cause"]
    manifest = _load(ACTIVE)
    compiler = COMPILER.read_text(encoding="utf-8")

    assert failure["error_code"] == "hermetic_repository_reference_policy_boundary_invalid"
    assert failure["active_manifest_value"] == "fail_closed_collect_all"
    assert failure["shared_compiler_required_value"] == "fail_closed"
    assert [
        failure["application_modules_imported"],
        failure["active_tests_collected"],
        failure["active_tests_executed"],
        failure["diagnostic_artifacts_created"],
    ] == [0, 0, 0, 0]
    assert root_cause["owned_by_project"] is True
    assert root_cause["model_or_provider_fault_established"] is False
    assert root_cause["financial_runtime_L1_failure_established"] is False
    assert root_cause["reference_role_behavior_failure_established"] is False
    assert manifest["hermetic_package_policy"]["repository_reference_policy"]["unknown_reference_behavior"] == "fail_closed_collect_all"
    assert '"unknown_reference_behavior": "fail_closed"' in compiler


def test_internal_source_bindings_are_immutable_and_exact() -> None:
    closeout = _load(CLOSEOUT)
    for binding in closeout["source_bindings"]:
        path = ROOT / binding["ref"]
        assert path.is_file(), binding["ref"]
        assert _sha(path) == binding["sha256"], binding["ref"]

    evidence = closeout["proof_evidence"]
    assert evidence["verification_sha256"] == "dd8b9eef8e95b56f61519cd3ca8cd92266b18e302f777c45d456583d0416f667"
    assert evidence["all_content_addressed_object_hashes_match"] is True
    assert evidence["file_count"] == 6
    assert evidence["total_bytes"] == 766661
    assert closeout["pre_failure_integrity"]["tracked_repository_file_count"] == 4316
    assert closeout["pre_failure_integrity"]["repository_mutated_by_proof"] is False


def test_current_projection_and_mutable_backlogs_expose_terminal_truth() -> None:
    projection = _load(PROJECTION)
    program = _load(PROGRAM)
    s4 = _load(S4)

    assert _sha(PROJECTION) == PROJECTION_SHA
    assert projection["host_proof_terminal_failure_binding"]["sha256"] == CLOSEOUT_SHA
    assert projection["expectations"]["current_next_action"] == NEXT
    assert projection["expectations"]["FIN_0_1_3_S0_v2_observed_implementation_host_formal"] == [1, 1, 0]
    assert projection["expectations"]["FIN_0_1_3_S0_v2_host_proof_executed"] is True
    assert projection["expectations"]["FIN_0_1_3_S0_v2_host_proof_passed"] is False
    assert set(projection["expectations"]["open_issue_ids"]) == PRIOR_ISSUES | {ISSUE}
    assert program["active_slice"] == projection["expectations"]["active_slice"]
    assert program["next_action"]["item_id"] == NEXT
    assert program["next_action"]["FIN_0_1_3_current_projection_sha256"] == PROJECTION_SHA
    assert program["next_action"]["FIN_0_1_3_S0_v2_host_proof_terminal_closeout_sha256"] == CLOSEOUT_SHA
    assert s4["current_next_action"] == NEXT
    stage = s4["FIN_0_1_3_S0_hermetic_runtime_dependency_and_semantic_parity"]
    assert stage["current_projection_sha256"] == PROJECTION_SHA
    assert stage["host_proof_terminal_closeout_sha256"] == CLOSEOUT_SHA
    assert stage["exit_contract_v2_observed"] == [1, 1, 0]
    assert stage["stage_plan_sha256"] == _sha(ROOT / stage["stage_plan_ref"])
    assert stage["canonical_S0_to_S5_plan_sha256"] == _sha(ROOT / stage["canonical_S0_to_S5_plan_ref"])
    assert program["next_action"]["FIN_0_1_3_S0_stage_plan_sha256"] == stage["stage_plan_sha256"]
    assert program["next_action"]["FIN_0_1_3_canonical_S0_to_S5_plan_sha256"] == stage["canonical_S0_to_S5_plan_sha256"]


def test_project_os_records_new_issue_and_keeps_prior_blockers_open() -> None:
    capabilities = _jsonl(CAPABILITY)
    issues = _jsonl(ROOT_CAUSE)
    patterns = _jsonl(EXTERNAL)

    capability = next(
        row
        for row in capabilities
        if row.get("capability_id") == "fin_0_1_3_S0_v2_host_zero_call_engineering_proof_terminal_failure"
    )
    assert capability["status"] == "terminal_failed_unique_v2_host_proof_consumed_project_level_disposition_required"
    assert capability["current_next"] == NEXT

    current_issue_rows = {
        row["issue_id"]: row
        for row in issues
        if row.get("recorded_at") == "2026-08-01T18:20:00+08:00"
        and row.get("issue_id") in PRIOR_ISSUES | {ISSUE}
    }
    assert set(current_issue_rows) == PRIOR_ISSUES | {ISSUE}
    for row in current_issue_rows.values():
        assert row["status"] == "open"
        assert row["full_chain_blocker"] is True
        assert row["allowed_run_scopes"] == [NEXT, "restricted_audit_evidence_review", "repository_and_git_hygiene"]
        assert row["model_or_provider_fault_established"] is False
        assert row["runtime_L1_failure_established"] is False

    pattern = next(
        row
        for row in patterns
        if row.get("pattern_id") == "fixed_budget_proof_must_cross_exact_earliest_execution_boundary_before_consumption"
    )
    assert pattern["status"] == "FIN_0_1_3_S0_v2_host_proof_terminal_failed_pre_execution_boundary"
    assert "v2 host zero-call engineering proof 已终态失败" in CONTEXT.read_text(encoding="utf-8")


def test_product_truth_does_not_inflate_failure_into_runtime_or_release_evidence() -> None:
    closeout = _load(CLOSEOUT)
    truth = closeout["product_truth"]
    counts = closeout["observed_counts"]

    assert truth["user_visible_financial_research_capability_delta"] == "none"
    assert truth["FIN_0_1_3_S0"] == "blocked"
    assert truth["FIN_0_1_3_S1"] == "not_started"
    assert truth["FIN_0_1_release_qualified"] is False
    assert truth["FIN_0_2_definition_changed"] is False
    assert [
        counts["credential_reads_or_probes"],
        counts["model_calls"],
        counts["provider_calls"],
        counts["network_source_or_external_tool_calls"],
        counts["new_admissions"],
        counts["business_runs"],
        counts["business_artifacts"],
    ] == [0, 0, 0, 0, 0, 0, 0]
