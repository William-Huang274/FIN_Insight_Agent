from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases/fin_ia_0_1_3_s0_v2_host_proof_first_credible_failure_project_level_disposition_and_exit_contract_v3_decision_v1_0.json"
PROJECTION = ROOT / "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_8.json"
PROGRAM = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
S4 = ROOT / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
CAPABILITY = ROOT / "docs/project_os/capability_status_ledger.jsonl"
ROOT_CAUSE = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
EXTERNAL = ROOT / "docs/project_os/external_pattern_registry.jsonl"
CONTEXT = ROOT / "docs/project_os/current_context_pack.zh-CN.md"
PRODUCT_PLAN = ROOT / "docs/product/FIN_0_1_3_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260801.zh-CN.md"
TECHNICAL_PLAN = ROOT / "docs/architecture/repository/FIN_0_1_3_S0_HERMETIC_RUNTIME_DEPENDENCY_AND_SEMANTIC_PARITY_STAGE_PLAN_20260801.zh-CN.md"
VERSION_PLAN = ROOT / "docs/product/FIN_0_1_1_0_1_2_VERSION_LINEAGE_AND_RELEASE_CADENCE_DECISION_20260731.zh-CN.md"

DECISION_SHA = "273e0383c133fa6530205357beb722453830f9e6aff03564f8e5765a962fdc30"
PROJECTION_SHA = "9413590a956ea5290672d8af494ac759c29e9eab05c6b0a033761ef4775c816a"
PRODUCT_PLAN_SHA = "a522a5006b95e9668df13871f0d6d096bf8a9580b63e079b9d204040abe6b25c"
NEXT = "FIN-0.1.3-S0-EXIT-CONTRACT-V3-PROOF-POLICY-SINGLE-SOURCE-AND-PRE-CONSUMPTION-BOUNDARY-MINIMUM-ZERO-CALL-IMPLEMENTATION"
ISSUES = {
    "RC-P36-090-fin-0-1-2-pre-s2-t03-disposable-self-introspection-git-inventory-dependency",
    "RC-P36-091-fin-0-1-2-hermetic-package-recursive-json-ref-admits-ignored-runtime-state",
    "RC-P36-092-fin-0-1-2-code-declared-static-runtime-resource-missing-from-hermetic-inventory",
    "RC-P36-093-fin-0-1-2-hermetic-semantic-parity-untyped-host-python-traceback-path",
    "RC-P36-094-fin-0-1-3-hermetic-reference-role-taxonomy-conflates-semantic-audit-and-repository-paths",
    "RC-P36-095-fin-0-1-3-v2-host-proof-manifest-policy-enum-contract-drift",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_project_disposition_selects_only_bounded_v3_without_version_churn() -> None:
    decision = _load(DECISION)

    assert _sha(DECISION) == DECISION_SHA
    selected = [name for name, option in decision["options"].items() if option["selected"]]
    assert selected == ["keep_FIN_0_1_3_and_select_bounded_S0_exit_contract_v3"]
    version = decision["version_and_stage_disposition"]
    assert version["FIN_0_1_3"] == "sole_current_mainline_S0_blocked_exit_contract_v3_selected"
    assert version["FIN_0_1_4"] == "not_created_not_implied"
    assert version["FIN_0_2"] == "original_Earnings_Review_Alpha_definition_preserved"
    assert version["FIN_0_1_3_exit_contract_revision_ceiling"] == "v3_no_v4_within_FIN_0_1_3"
    assert decision["next_action"] == NEXT


def test_v3_separates_policy_semantics_and_moves_exact_boundary_before_consumption() -> None:
    v3 = _load(DECISION)["exit_contract_v3"]

    assert v3["contract_id"] == "fin_0_1_3.S0.exit_contract:v3"
    assert "unknown_reference_behavior_equals_fail_closed" in v3["required_contract_surfaces"]
    assert "unknown_reference_reporting_equals_collect_all_typed_envelope_as_a_separate_semantic" in v3["required_contract_surfaces"]
    before = v3["consumption_boundary"]["before_host_run_consumption"]
    assert "compile_repository_inventory_on_the_exact_active_manifest" in before
    assert "content_addressed_eligibility_attestation_readback" in before
    assert v3["consumption_boundary"]["host_run_consumption_begins"].startswith("only_after_a_matching_eligibility_attestation")
    assert v3["fixed_budget"]["maximum_proof_control_plane_implementation_bundles"] == 1
    assert v3["fixed_budget"]["maximum_clean_head_eligibility_attestations"] == 1
    assert v3["fixed_budget"]["maximum_host_engineering_proof_runs"] == 1
    assert v3["fixed_budget"]["maximum_formal_two_disposable_proof_packages"] == 1
    assert v3["fixed_budget"]["observed_implementation_eligibility_host_formal"] == [0, 0, 0, 0]
    assert v3["fixed_budget"]["automatic_exit_contract_v4_or_version_bump"] == 0


def test_decision_preserves_immutable_sources_and_marks_living_snapshots_honestly() -> None:
    bindings = _load(DECISION)["source_bindings"]
    immutable_modes = {"immutable_source", "immutable_snapshot", "immutable_event_summary"}

    for binding in bindings:
        path = ROOT / binding["ref"]
        assert path.is_file(), binding["ref"]
        if binding["binding_mode"] in immutable_modes:
            assert _sha(path) == binding["sha256"], binding["ref"]

    living = [binding for binding in bindings if binding["binding_mode"] == "decision_time_living_document_snapshot"]
    assert len(living) == 3
    assert all(_sha(ROOT / binding["ref"]) != binding["sha256"] for binding in living)


def test_current_projection_and_mutable_backlogs_follow_v3() -> None:
    projection = _load(PROJECTION)
    program = _load(PROGRAM)
    s4 = _load(S4)
    stage = s4["FIN_0_1_3_S0_hermetic_runtime_dependency_and_semantic_parity"]

    assert _sha(PROJECTION) == PROJECTION_SHA
    assert projection["v3_disposition_binding"]["sha256"] == DECISION_SHA
    assert projection["expectations"]["active_slice"] == program["active_slice"]
    assert projection["expectations"]["current_next_action"] == program["next_action"]["item_id"] == s4["current_next_action"] == NEXT
    assert program["next_action"]["FIN_0_1_3_current_projection_sha256"] == PROJECTION_SHA
    assert stage["current_projection_sha256"] == PROJECTION_SHA
    assert stage["exit_contract_v2_observed"] == [1, 1, 0]
    assert stage["exit_contract_v3_observed"] == [0, 0, 0, 0]
    assert stage["exit_contract_v4_authorized"] is False
    assert stage["canonical_S0_to_S5_plan_sha256"] == _sha(PRODUCT_PLAN) == PRODUCT_PLAN_SHA
    assert program["next_action"]["FIN_0_1_3_canonical_S0_to_S5_plan_sha256"] == PRODUCT_PLAN_SHA


def test_project_os_records_v3_and_keeps_all_six_blockers_open() -> None:
    capabilities = _jsonl(CAPABILITY)
    issues = _jsonl(ROOT_CAUSE)
    patterns = _jsonl(EXTERNAL)

    capability = next(row for row in reversed(capabilities) if row.get("capability_id") == "fin_0_1_3_S0_v2_failure_project_disposition_and_exit_contract_v3")
    assert capability["current_next"] == NEXT
    assert capability["authority"]["v3_implementation_eligibility_host_formal_observed"] == [0, 0, 0, 0]

    current = {
        row["issue_id"]: row
        for row in issues
        if row.get("recorded_at") == "2026-08-01T18:40:00+08:00" and row.get("issue_id") in ISSUES
    }
    assert set(current) == ISSUES
    for row in current.values():
        assert row["status"] == "open"
        assert row["full_chain_blocker"] is True
        assert row["allowed_run_scopes"] == [NEXT, "restricted_audit_evidence_review", "repository_and_git_hygiene"]
        assert row["model_or_provider_fault_established"] is False
        assert row["runtime_L1_failure_established"] is False

    pattern = next(row for row in reversed(patterns) if row.get("pattern_id") == "fixed_budget_proof_must_cross_exact_earliest_execution_boundary_before_consumption")
    assert pattern["status"] == "FIN_0_1_3_S0_exit_contract_v3_proof_control_plane_implementation_pending"


def test_living_docs_and_product_truth_do_not_inflate_decision_into_execution() -> None:
    decision = _load(DECISION)
    truth = decision["product_truth"]
    authority = decision["authority"]

    assert truth["user_visible_financial_research_capability_delta"] == "none"
    assert truth["new_Runtime_or_reference_role_implementation"] is False
    assert truth["new_proof_or_eligibility_execution"] is False
    assert truth["model_provider_network_calls"] == [0, 0, 0]
    assert truth["business_runs_artifacts"] == [0, 0]
    assert truth["FIN_0_1_release_qualified"] is False
    assert authority["implementation_executed_in_this_decision"] is False
    assert authority["eligibility_attestation_executed_in_this_decision"] is False
    assert authority["host_or_formal_proof_executed_in_this_decision"] is False
    assert "exit contract v3" in CONTEXT.read_text(encoding="utf-8").lower()
    assert "exit-contract v3" in PRODUCT_PLAN.read_text(encoding="utf-8").lower()
    assert "exit contract v3" in TECHNICAL_PLAN.read_text(encoding="utf-8").lower()
    assert "exit contract v3" in VERSION_PLAN.read_text(encoding="utf-8").lower()
