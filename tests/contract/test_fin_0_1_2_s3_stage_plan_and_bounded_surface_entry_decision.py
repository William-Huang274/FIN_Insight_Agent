from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STAGE_PLAN = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s3_nvda_product_anchor_and_bounded_model_surface_"
    "stage_plan_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_21.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
S2_BINDING = ROOT / (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_binding_v1_2.json"
)
EXECUTOR = ROOT / "apps/workbench/backend/application/bounded_agent_executor.py"
ROOT_CAUSE_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
CAPABILITY_LEDGER = ROOT / "docs/project_os/capability_status_ledger.jsonl"
PATTERN_LEDGER = ROOT / "docs/project_os/external_pattern_registry.jsonl"

EXPECTED_STAGE_PLAN_SHA256 = (
    "5e4a5bc8abd4b1b0c39c435e1aa65b23b34c5d6b1ef1c56cd0f9a6fa3e0131dd"
)
EXPECTED_PROJECTION_SHA256 = (
    "c9381ce81007d0404bd64571bc62268232fccb532c218664f432197964b5973c"
)
ISSUE_ID = (
    "RC-P36-105-fin-0-1-2-s3-s2-selected-surface-not-bound-to-"
    "production-runtime-and-current-nvda-product-input"
)
NEXT_ACTION = (
    "FIN-0.1.2-S3-T02-NVDA-BOUNDED-SURFACE-PRODUCTION-RUNTIME-"
    "INTEGRATION-AND-ZERO-CALL-PRODUCT-READINESS-IMPLEMENTATION"
)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line, object_pairs_hook=_strict_object)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stage_plan_bindings_preserve_immutable_content_and_code_baseline() -> None:
    plan = _load(STAGE_PLAN)
    assert _sha256(STAGE_PLAN) == EXPECTED_STAGE_PLAN_SHA256
    assert _sha256(PROJECTION) == EXPECTED_PROJECTION_SHA256

    for binding in plan["bindings"]:
        bound = ROOT / binding["ref"]
        assert bound.is_file(), binding["ref"]
        if binding["role"] == "current_production_executor_audit_snapshot":
            # This digest is the immutable T01 audit baseline. T02 is
            # explicitly authorized to evolve the implementation file.
            assert len(binding["sha256"]) == 64
            assert all(
                character in "0123456789abcdef"
                for character in binding["sha256"]
            )
        else:
            assert _sha256(bound) == binding["sha256"], binding["ref"]


def test_entry_audit_preserves_the_known_production_topology_gap() -> None:
    plan = _load(STAGE_PLAN)
    binding = _load(S2_BINDING)
    executor_text = EXECUTOR.read_text(encoding="utf-8")

    assert binding["compatibility"]["S2_paired_canary_only"] is True
    for segment in (
        "facts_explanation_and_terminal",
        "owner_grade_claim_cards",
        "actionable_what_would_change_tasks",
    ):
        assert segment in executor_text

    assert [item["finding_id"] for item in plan["read_only_audit_findings"]] == [
        "S3-F01",
        "S3-F02",
        "S3-F03",
        "S3-F04",
    ]
    issue = plan["entry_issue"]
    assert issue["issue_id"] == ISSUE_ID
    assert issue["earliest_owner"] == "S3-T02"
    assert issue["model_or_provider_fault_established"] is False
    assert issue["does_not_reopen"] == ["S0", "S1", "S2"]


def test_model_and_local_authority_are_bounded_without_silent_fallback() -> None:
    authority = _load(STAGE_PLAN)["model_and_local_authority_matrix"]
    selected = authority["selected_model"]

    assert selected["model_ref"] == "deepseek:deepseek-v4-pro"
    assert selected["lifecycle"] == "preview_historical_control_selected_by_S2"
    assert selected["automatic_fallback"] is False
    assert authority["retained_bounded_model_surfaces"] == [
        "specialist_Claim_request_local_aliases_and_closed_judgment_enums",
        "specialist_WWC_request_local_aliases_closed_enums_and_bound_date_aliases",
    ]
    assert any("specialist_Fact" in item for item in authority["local_L1_truth_owners"])
    assert "Provider_authored_Fact_segment" in authority["forbidden"]
    assert set(authority["conditionally_retained_historical_model_surfaces"]) == {
        "Research_Lead_cross_cell_judgment_synthesis",
        "Memo_Writer_non_authoritative_narrative_shell",
        "Verifier_findings",
    }
    assert "may not create alter or repair L1 truth" in authority[
        "condition_for_historical_surfaces"
    ]


def test_S3_topology_and_task_boundary_are_fixed_without_rewriting_history() -> None:
    plan = _load(STAGE_PLAN)
    topology = plan["S3_product_call_topology"]

    assert topology == {
        "logical_node_count": 6,
        "logical_interaction_count": 12,
        "local_Fact_interaction_count": 3,
        "model_specialist_Claim_WWC_call_count": 6,
        "model_Lead_Writer_Verifier_call_count": 3,
        "maximum_model_provider_call_count": 9,
        "expected_model_capture_count": 9,
        "expected_local_Fact_receipt_count": 3,
        "required_business_Artifact_count": 9,
        "historical_S1_6_12_12_9_rewritten": False,
        "S3_shape_reason": (
            "Fact model authority was revoked by S2, so S3 preserves twelve "
            "logical interactions while replacing three Provider calls with "
            "deterministic local receipts."
        ),
    }
    tasks = plan["fixed_tasks"]
    assert [task["task_id"] for task in tasks] == [
        "S3-T01",
        "S3-T02",
        "S3-T03",
        "S3-T04",
    ]
    assert tasks[0]["status"] == "pass"
    assert tasks[1]["status"] == "pending_separate_user_continuation"
    assert tasks[2]["primary_formal_attempt_maximum"] == 1
    assert tasks[3]["model_calls"] == 0


def test_budget_stop_rules_and_stage_exit_prevent_patch_loop_inflation() -> None:
    plan = _load(STAGE_PLAN)
    budget = plan["hard_budget"]
    policy = plan["failure_and_repair_policy"]

    assert budget["primary_exact_live_model_calls"] == 9
    assert budget["maximum_input_tokens"] == 60000
    assert budget["maximum_output_tokens"] == 10000
    assert budget["maximum_total_cost_usd"] == 0.06
    assert budget["maximum_wall_clock_seconds"] == 900
    assert policy["automatic_repair_or_rerun"] is False
    assert policy["field_by_field_prompt_patch_series"] is False
    assert (
        policy[
            "maximum_consolidated_project_owned_structural_repair_bundles_after_primary_live"
        ]
        == 1
    )
    assert policy["maximum_replacement_exact_live_attempts_after_structural_repair"] == 1
    assert policy["new_L1_after_replacement"] == (
        "S3_honest_block_no_third_exact_attempt"
    )
    assert plan["stage_exit"]["failure_version_effect"] == (
        "no_automatic_FIN_0_1_3_or_new_stage"
    )
    assert plan["observed_counts"] == {
        "runtime_code_changes": 0,
        "credential_reads_or_probes": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "execution_network_calls": 0,
        "business_runs": 0,
        "business_artifacts": 0,
    }


def test_projection_backlog_and_project_os_agree_on_current_next() -> None:
    plan = _load(STAGE_PLAN)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)

    assert plan["next_action"] == NEXT_ACTION
    assert projection["implementation_binding"] == {
        "ref": str(STAGE_PLAN.relative_to(ROOT)).replace("\\", "/"),
        "sha256": EXPECTED_STAGE_PLAN_SHA256,
        "binding_role": (
            "S3_stage_plan_entry_call_topology_failure_budget_and_bounded_surface_scope"
        ),
    }
    assert projection["current_truth"]["stage"] == (
        "S3_entered_T01_pass_T02_not_started"
    )
    assert projection["current_truth"]["current_next_action"] == NEXT_ACTION
    assert projection["execution_authority"]["S3_T02_implementation_executed"] is False

    rebaseline = backlog["current_version_rebaseline"]
    next_action = backlog["next_action"]
    # This file proves the immutable T01 entry projection. The global backlog
    # is intentionally allowed to advance through T02/T03 and must not be
    # treated as part of that historical snapshot. Its current authority must
    # therefore agree with the backlog's live pointer, not stay pinned to v2.22.
    assert rebaseline["current_projection_is_authority"] is True
    assert rebaseline["projection_ref"] == next_action["current_projection_ref"]
    current_projection = ROOT / rebaseline["projection_ref"]
    assert current_projection.exists()
    assert next_action["current_projection_sha256"] == _sha256(current_projection)
    assert rebaseline["current_product_version"] == "FIN_0_1_2"
    assert next_action["item_id"] != NEXT_ACTION
    assert next_action["S3_stage_plan_sha256"] == EXPECTED_STAGE_PLAN_SHA256
    assert next_action["S3_model_provider_call_topology"] == [6, 12, 9, 9, 3, 9]
    assert next_action["S3_T01_completed"] is True
    assert next_action["S3_T02_started"] is True
    assert next_action["S3_T02_completed"] is True

    issue = next(
        row
        for row in _load_jsonl(ROOT_CAUSE_LEDGER)
        if row["issue_id"] == ISSUE_ID and row["status"] == "open"
    )
    capability = next(
        row
        for row in _load_jsonl(CAPABILITY_LEDGER)
        if row["capability_id"]
        == "fin_0_1_2_S3_T01_NVDA_product_anchor_and_bounded_model_surface_stage_plan"
    )
    pattern = next(
        row
        for row in _load_jsonl(PATTERN_LEDGER)
        if row["pattern_id"]
        == "model_surface_disposition_must_change_production_call_topology_before_product_live"
    )
    assert issue["issue_id"] == ISSUE_ID
    assert issue["status"] == "open"
    assert issue["allowed_run_scopes"][0] == NEXT_ACTION
    assert capability["capability_id"] == (
        "fin_0_1_2_S3_T01_NVDA_product_anchor_and_bounded_model_surface_stage_plan"
    )
    assert capability["current_next"] == NEXT_ACTION
    assert pattern["pattern_id"] == (
        "model_surface_disposition_must_change_production_call_topology_before_product_live"
    )
    assert pattern["verification"]["runtime_injected"] is False
