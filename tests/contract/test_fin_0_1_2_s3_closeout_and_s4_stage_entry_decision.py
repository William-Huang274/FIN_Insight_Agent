from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OWNER_DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t04_owner_stage_boundary_"
    "realignment_and_s3_closeout_v1_0.json"
)
S4_PLAN = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_evidence_to_workbench_stage_"
    "entry_and_t01_plan_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_35.json"
)
CURRENT_PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_38.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
PRIOR_REJECTION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t04_nvda_paired_assessment_"
    "owner_rejection_and_s3_closeout_v1_0.json"
)
EXACT_RESULT = ROOT / (
    ".codex_runtime/fin012-s3-t03-nvda-replacement-r2/execution-result.json"
)
NEXT = (
    "FIN-0.1.2-S4-T01-NATURAL-CASE-ENTRY-AND-EXACT-BINDING-"
    "ZERO-CALL-IMPLEMENTATION"
)
T02_NEXT = (
    "FIN-0.1.2-S4-T02-THREE-CASE-RETRIEVAL-EVIDENCE-"
    "DETERMINISTIC-READINESS-ZERO-CALL-IMPLEMENTATION"
)
T03_NEXT = (
    "FIN-0.1.2-S4-T03-NVDA-EXECUTABLE-SEARCH-REQUEST-ROUTE-ADAPTER-"
    "CAPTURE-FIRST-CONTROLLED-SUCCESSOR-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_owner_decision_preserves_evidence_and_product_acceptance_truth() -> None:
    decision = _load(OWNER_DECISION)

    assert decision["accepted_stage_meaning"]["S3"] == (
        "pass_closed_bounded_frozen_input_runtime_and_verified_delivery_anchor"
    )
    assert decision["accepted_stage_meaning"]["owner_scope_acceptance"] is True
    assert decision["accepted_stage_meaning"]["owner_product_acceptance"] is False
    assert decision["accepted_stage_meaning"]["current_NVDA_R2"] is False
    assert decision["evidence_gap_disposition"]["promoted_evidence_cells"] == [0, 3]
    assert decision["evidence_gap_disposition"]["candidate_metadata_promoted"] is False
    assert decision["evidence_gap_disposition"]["assigned_stage_tasks"] == [
        "S4-T02",
        "S4-T03",
        "S4-T04",
    ]
    assert decision["next_action"] == NEXT
    assert all(value == 0 for value in decision["observed_counts"].values())


def test_owner_decision_immutable_bindings_recompute() -> None:
    decision = _load(OWNER_DECISION)
    for binding in decision["immutable_bindings"]:
        path = ROOT / binding["ref"]
        assert path.exists()
        assert binding["sha256"] == _sha256(path)
    assert _sha256(EXACT_RESULT) == (
        "7f430356295c558f5158898d069905c3ce6d02b2585e87676c9252ebd5a3568c"
    )
    assert _load(PRIOR_REJECTION)["owner_decision"]["decision"] == (
        "reject_current_NVDA_R2_product_acceptance"
    )


def test_s4_plan_enters_t01_without_claiming_t01_pass_or_later_execution() -> None:
    plan = _load(S4_PLAN)
    assert plan["status"] == (
        "S4_entered_T01_zero_call_implementation_pending_T02_T08_not_started"
    )
    assert [task["id"] for task in plan["tasks"]] == [
        f"S4-T{number:02d}" for number in range(1, 9)
    ]
    assert plan["tasks"][0]["status"] == "started_zero_call_implementation_pending"
    assert all(
        task["status"].startswith("not_started_blocked_by_")
        for task in plan["tasks"][1:]
    )
    assert plan["stage_objective"]["current_NVDA_R2_at_entry"] is False
    assert plan["historical_S4_policy"][
        "historical_task_pass_counts_as_FIN_0_1_2_current_proof"
    ] is False
    assert all(value == 0 for value in plan["observed_counts"].values())
    assert plan["next_action"] == NEXT


def test_projection_and_backlog_have_one_current_authority() -> None:
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)
    next_action = backlog["next_action"]
    rebaseline = backlog["current_version_rebaseline"]

    assert projection["current_truth"]["S3"] == (
        "pass_closed_bounded_anchor_not_source_grounded_NVDA_R2"
    )
    assert projection["current_truth"]["S4"] == (
        "entered_T01_started_implementation_pending"
    )
    assert projection["current_truth"]["current_NVDA_R2"] is False
    assert projection["current_truth"]["current_next_action"] == NEXT
    assert projection["S4_entry"]["stage_plan_sha256"] == _sha256(S4_PLAN)
    assert rebaseline["projection_ref"] == str(
        CURRENT_PROJECTION.relative_to(ROOT)
    ).replace("\\", "/")
    assert next_action["current_projection_sha256"] == _sha256(CURRENT_PROJECTION)
    assert next_action["item_id"] == T03_NEXT
    assert next_action["S4_T01_started"] is True
    assert next_action["S4_T01_completed"] is True
    assert next_action["S4_T02_started"] is True
    assert next_action["S4_T02_completed"] is True
    assert next_action["S4_T02_T03_authorized"] is False


def test_t01_contract_is_zero_call_and_does_not_contain_evidence_payload() -> None:
    plan = _load(S4_PLAN)
    contract = plan["S4_T01_contract"]
    assert contract["future_contract_ref"] == (
        "fin_0_1_2.S4.natural_case_entry_and_exact_binding:v1"
    )
    assert contract[
        "S4_T01_model_provider_execution_network_source_network_external_tool_business_artifact_counts"
    ] == [0, 0, 0, 0, 0, 0]
    assert "S4T01EntryReceipt_without_Evidence_content" in contract["required_outputs"]
    assert "current_runtime_consumer_readback" in contract[
        "required_zero_call_matrix"
    ]
