from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest


DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_deepseek_exact_admission_issuance_decision_v1_0.json"
)
REPAIR = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t09_deepseek_transport_exact_input_preflight_repair_v1_0.json"
)
BACKLOG = ROOT / "configs" / "releases" / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _decision() -> dict[str, object]:
    return json.loads(DECISION.read_text(encoding="utf-8"))


def test_decision_recommends_but_does_not_issue_or_execute() -> None:
    decision = _decision()
    assert decision["status"] == (
        "pass_issue_recommended_pending_separate_exact_admission_issuance_authority"
    )
    assert decision["decision"] == {
        "exact_admission_may_be_issued_after_separate_authority": True,
        "issue_exact_admission_now": False,
        "consume_or_execute_exact_admission_now": False,
        "reason": (
            "The exact Case, DecisionSurface, as-of, input digest, fresh canonical "
            "identities, six-node adapter, schema, budget, credential presence and "
            "zero-call boundaries all pass. Issuance remains a separate authority "
            "and execution remains a later independent boundary."
        ),
    }
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["next_action"] == (
        "S3-T09-EXACT-THREE-CELL-DEEPSEEK-ADMISSION-ISSUANCE"
    )


def test_prospective_admission_payload_is_exact_and_factory_admissible() -> None:
    prospective = _decision()["prospective_admission"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        prospective["payload"]
    )
    admission.assert_profile_admissible()
    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=lambda **_: {}
    )
    assert canonical_digest(admission.digest_payload()) == prospective[
        "admission_digest"
    ]
    assert prospective["admission_digest"] == (
        "ca7af62de613dcaa274cc8a0780658ef16e72082de54a8e1038eeeb6a4bfba3f"
    )


def test_decision_input_binding_matches_repair_and_budget_is_coherent() -> None:
    decision = _decision()
    repair = json.loads(REPAIR.read_text(encoding="utf-8"))
    evidence = decision["input_evidence"]
    repaired = repair["exact_input_preflight_repair"]
    assert evidence["prepared_case_id"] == repaired["case_id"]
    assert evidence["prepared_case_version"] == repaired["case_version"]
    assert evidence["accepted_decision_surface_contract_ref"] == repaired[
        "decision_surface_contract_ref"
    ]
    assert evidence["input_digest"] == repaired["input_digest"]
    assert evidence["preparation_digest"] == repaired["preparation_digest"]
    budget = decision["budget_review"]
    assert budget["maximum_output_tokens_total"] == 7800
    assert budget["output_only_cost_ceiling_usd"] == 0.006786
    assert budget["remaining_cost_for_input_usd_at_full_output_ceiling"] == 0.093214
    assert budget["maximum_transport_attempts_per_call"] == 1
    assert budget["retry_budget"] == 0


def test_environment_and_backlog_boundaries_remain_fail_closed() -> None:
    decision = _decision()
    review = decision["independent_preissuance_review"]
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    assert review["credential_present"] is True
    assert review["credential_value_read_output_or_persisted"] is False
    assert review["provider_health_probe_performed"] is False
    assert review["transport_retry_environment_currently_zero"] is False
    assert review["transport_retry_environment_requirement"] == (
        "must_equal_0_before_any_execution_command"
    )
    assert decision["next_action"] == (
        "S3-T09-EXACT-THREE-CELL-DEEPSEEK-ADMISSION-ISSUANCE"
    )
    assert backlog["next_action"]["S3_T09_admission_issuance_decision_ref"] == (
        "configs/releases/"
        "fin_ia_0_1_s3_t09_deepseek_exact_admission_issuance_decision_v1_0.json"
    )
    assert backlog["next_action"]["S3_T09_admission_issuance_decision_authorized"] is True
    assert backlog["next_action"]["S3_T09_admission_issuance_authorized"] is True
    assert backlog["next_action"]["S3_T09_execution_authorized"] is True
    assert backlog["next_action"]["source_network_or_external_tool_execution_authorized"] is False
    assert backlog["next_action"][
        "S3_T09_specialist_model_view_and_output_budget_repair_execution_authorized"
    ] is True
    assert backlog["next_action"]["replacement_admission_or_execution_authorized"] is False
