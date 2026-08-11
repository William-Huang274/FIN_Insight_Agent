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


RELEASES = ROOT / "configs" / "releases"
ADMISSION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_three_cell_deepseek_segmented_exact_admission_v1_0.json"
)
ISSUANCE = RELEASES / "fin_ia_0_1_s3_t09_deepseek_exact_admission_issuance_v1_0.json"
DECISION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_deepseek_exact_admission_issuance_decision_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_issued_payload_exactly_matches_reviewed_prospective_payload() -> None:
    decision = _load(DECISION)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    assert payload == decision["prospective_admission"]["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=lambda **_: {}
    )
    digest = canonical_digest(admission.digest_payload())
    assert digest == decision["prospective_admission"]["admission_digest"]
    assert digest == issuance["issued_admission"]["admission_digest"]


def test_issuance_is_unconsumed_and_preserves_zero_call_boundary() -> None:
    issuance = _load(ISSUANCE)
    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert issuance["issued_admission"]["fresh_identity"] is True
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    counts = issuance["observed_counts"]
    assert counts["new_admissions"] == 1
    assert counts["admission_consumptions"] == 0
    assert all(
        counts[key] == 0
        for key in (
            "work_units_created",
            "attempts_created",
            "research_runs_created",
            "artifacts_created",
            "model_calls",
            "provider_calls",
            "execution_network_calls",
            "source_network_calls",
            "external_tool_calls",
            "live_business_writes",
            "human_review_writes",
            "paid_runs",
        )
    )


def test_exact_binding_and_execution_precondition_are_frozen() -> None:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    evidence = decision["input_evidence"]
    binding = issuance["exact_binding"]
    assert binding["case_id"] == evidence["prepared_case_id"]
    assert binding["decision_surface_contract_ref"] == evidence[
        "accepted_decision_surface_contract_ref"
    ]
    assert binding["input_digest"] == evidence["input_digest"]
    assert binding["preparation_digest"] == evidence["preparation_digest"]
    assert binding["predicted_work_unit_id"] == evidence["predicted_work_unit_id"]
    assert binding["predicted_attempt_id"] == evidence["predicted_attempt_id"]
    assert binding["predicted_research_run_id"] == evidence[
        "predicted_research_run_id"
    ]
    preflight = issuance["zero_call_preflight"]
    assert preflight["credential_present"] is True
    assert preflight["credential_value_read_output_or_persisted"] is False
    assert preflight["provider_health_probe_performed"] is False
    assert preflight["transport_retry_environment_currently_zero"] is False
    assert preflight["transport_retry_environment_requirement"] == (
        "must_equal_0_before_any_execution_command"
    )


def test_backlog_retains_issuance_and_records_later_consumed_execution() -> None:
    backlog = _load(BACKLOG)
    issuance = _load(ISSUANCE)
    s3 = next(row for row in backlog["slices"] if row["slice_id"] == "S3")
    t09 = next(row for row in s3["items"] if row["item_id"] == "S3-T09")
    assert t09["exact_admission_issued"] is True
    assert t09["exact_admission_consumed"] is True
    assert t09["live_execution_performed"] is True
    assert issuance["next_action"] == "S3-T09-EXACT-THREE-CELL-DEEPSEEK-LIVE-EXECUTION"
    assert backlog["next_action"]["S3_T09_admission_issuance_ref"] == (
        "configs/releases/fin_ia_0_1_s3_t09_deepseek_exact_admission_issuance_v1_0.json"
    )
    assert backlog["next_action"]["S3_T09_admission_issued"] is True
    assert backlog["next_action"]["S3_T09_admission_issuance_authorized"] is True
    assert backlog["next_action"]["S3_T09_execution_authorized"] is True
    assert backlog["next_action"]["source_network_or_external_tool_execution_authorized"] is False
    assert backlog["next_action"][
        "S3_T09_specialist_model_view_and_output_budget_repair_execution_authorized"
    ] is True
    assert backlog["next_action"]["replacement_admission_or_execution_authorized"] is False


def test_issuance_artifacts_do_not_contain_plaintext_credentials() -> None:
    rendered = ADMISSION.read_text(encoding="utf-8") + ISSUANCE.read_text(
        encoding="utf-8"
    )
    assert "DEEPSEEK_API_KEY" in rendered
    assert "sk-" not in rendered.lower()
    assert "fixture-secret" not in rendered.lower()
