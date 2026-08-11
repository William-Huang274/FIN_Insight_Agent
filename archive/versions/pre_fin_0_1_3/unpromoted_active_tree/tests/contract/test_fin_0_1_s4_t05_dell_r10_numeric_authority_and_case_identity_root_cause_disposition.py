from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    FactSupportAuthorityPolicy,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    build_s4_source_grounded_bounded_agent_input,
    resolve_s4_case_runtime_binding_for_admission,
)
from sec_agent.s4_case_runtime import load_s4_source_grounded_input_pack


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r10_numeric_authority_"
    "and_case_identity_false_negative_zero_call_root_cause_disposition_"
    "v1_0.json"
)
ASSESSMENT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r10_success_only_paired_"
    "assessment_and_owner_acceptance_decision_v1_0.json"
)
R10_ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r10_profile_aware_"
    "artifact_lineage_fresh_exact_admission_r10.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
EXECUTOR = ROOT / (
    "apps/workbench/backend/application/bounded_agent_executor.py"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _r10_input():
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load(R10_ADMISSION)
    )
    binding, overlay = resolve_s4_case_runtime_binding_for_admission(
        ROOT, admission
    )
    return build_s4_source_grounded_bounded_agent_input(
        binding,
        load_s4_source_grounded_input_pack(ROOT, "DELL"),
        case_id=str(admission.case_id),
        case_version=int(admission.case_version or 0),
        query="Zero-call R10 numeric-correspondence audit.",
        decision_surface_contract_ref="zero-call-R10-numeric-audit:v1",
        research_profile_overlay=overlay,
    )


def test_disposition_binds_R10_L1_failure_and_zero_call_scope() -> None:
    decision = _load(DECISION)

    assert decision["source_evidence"]["paired_assessment_sha256"] == (
        _sha256(ASSESSMENT)
    )
    assert decision["source_evidence"]["paired_L1_status"] == "fail"
    assert decision["source_evidence"]["owner_acceptance_eligible"] is False
    assert decision["authority"]["runtime_repair_transport_version_admission_or_execution_authorized"] is False
    assert all(value == 0 for value in decision["observed_counts"].values())
    assert decision["stage_acceptance"]["S4_T06"] == "not_entered"


def test_current_fact_policy_reproduces_numeric_value_false_negative() -> None:
    input_pack = _r10_input()
    cell = input_pack.cell_inputs[0]
    numeric_ref = str(cell["authority_refs"]["numeric_refs"][0])
    wrong_numeric_fact = {
        "fact_id": "zero_call_wrong_numeric_fact",
        "statement": "Q1 FY27 orders were USD 4.1 billion.",
        "support_type": "Numeric",
        "support_refs": [numeric_ref],
        "boundary": "zero-call audit only",
    }

    assert (
        FactSupportAuthorityPolicy.from_cell_input(cell).first_violation(
            [wrong_numeric_fact]
        )
        is None
    )
    surface = S3ThreeCellBoundedAgentExecutor._owner_grade_authority_surface(
        cell
    )
    assert surface["numeric_fact_scope_and_cannot_support"] == {}

    raw_row = cell["numeric_input"]["selected_financial_rows"][0]
    assert raw_row["numeric_ref"] == numeric_ref
    assert raw_row["value"]
    assert raw_row["comparison_operator"]
    projected_row = DeepSeekS3ThreeCellNodeExecutor._specialist_model_view(
        {"cell_input": cell}
    )["numeric_view"]["selected_financial_rows"][0]
    assert projected_row == {
        "scale_multiplier": raw_row["scale_multiplier"],
        "selector": {},
    }


def test_current_writer_path_preserves_legacy_NVDA_fallback_and_uses_bound_case_title() -> None:
    source = EXECUTOR.read_text(encoding="utf-8")

    assert (
        '"title_zh_cn": "NVDA 三单元内部研究备忘录"' in source
    )
    assert (
        'output.get("title_zh_cn") != "NVDA 三单元内部研究备忘录"'
        not in source
    )
    assert (
        '"title_zh_cn": "exactly NVDA 三单元内部研究备忘录"'
        in source
    )
    assert "expected_title_zh_cn=expected_title" in source
    assert "CaseDeliveryIdentityPolicy.from_projection" in source


def test_selected_contracts_keep_numeric_and_identity_in_L1() -> None:
    decision = _load(DECISION)
    selected = decision["selected_minimum_implementation_contracts"]
    numeric = selected["numeric_contract"]
    identity = selected["delivery_identity_contract"]

    assert numeric["contract_ref"] == (
        "fin01.s4.case_numeric_authority_projection_and_"
        "deterministic_rendering:v1"
    )
    assert numeric["provider_wire"][
        "provider_authored_material_numeric_values_currency_amounts_percentages_or_signs_in_free_narrative_allowed"
    ] is False
    assert numeric["independent_L1_validation"][
        "model_Verifier_is_not_the_numeric_truth_owner"
    ] is True
    assert identity["contract_ref"] == (
        "fin01.s4.case_delivery_identity_projection:v1"
    )
    assert identity["title_rule"] == (
        "{case_ticker} 三单元内部研究备忘录"
    )
    assert identity["provider_title_write_authority"] is False


def test_disposition_rejects_patch_loop_and_preserves_sequence_boundary() -> None:
    decision = _load(DECISION)
    alternatives = {
        row["option"]: row["decision"]
        for row in decision["rejected_and_deferred_alternatives"]
    }

    assert alternatives[
        "add_more_prompt_emphasis_that_numbers_must_match_refs"
    ] == "rejected"
    assert alternatives[
        "regex_compare_arbitrary_free_text_against_every_numeric_row_as_the_primary_contract"
    ] == "rejected_as_primary_owner"
    assert alternatives[
        "atomize_dependency_conflict_gap_WWC_and_every_other narrative structure in_T05"
    ] == "deferred_to_S4_T10_to_S5"
    assert decision["next_action"] == (
        "S4-T05-DELL-CASE-LOCAL-NUMERIC-ATOM-DETERMINISTIC-RENDERING-"
        "AND-DELIVERY-IDENTITY-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )


def test_backlogs_route_to_separately_authorized_implementation() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    task = next(
        row for row in detailed["tasks"] if row["item_id"] == "S4-T05"
    )

    assert program["next_action"]["item_id"] == decision["next_action"]
    assert detailed["current_next_action"] == decision["next_action"]
    assert task["RC_P36_067_disposition_sha256"] == _sha256(DECISION)
    assert task["RC_P36_068_disposition_sha256"] == _sha256(DECISION)
    assert task["R10_owner_acceptance"] == "not_eligible_while_L1_fails"
    assert task["R10_S4_T06_unblocked"] is False
