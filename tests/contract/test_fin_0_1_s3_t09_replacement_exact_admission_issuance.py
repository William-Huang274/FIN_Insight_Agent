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
    / "fin_ia_0_1_s3_t09_three_cell_deepseek_segmented_output_v2_exact_admission_v1_0.json"
)
ISSUANCE = RELEASES / "fin_ia_0_1_s3_t09_replacement_exact_admission_issuance_v1_0.json"
DECISION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_replacement_exact_admission_issuance_decision_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_issued_payload_exactly_matches_reviewed_output_v2_payload() -> None:
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
    assert admission.output_contract_ref == "fin01.s3.bounded_agent_three_cell_output:v2"
    assert admission.specialist_max_output_tokens == 2200


def test_issuance_is_unconsumed_and_preserves_zero_call_boundary() -> None:
    issuance = _load(ISSUANCE)
    assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert issuance["issued_admission"]["fresh_identity"] is True
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    counts = issuance["observed_counts"]
    assert counts["new_admissions"] == 1
    assert counts["admission_consumptions"] == 0
    assert all(value == 0 for key, value in counts.items() if key != "new_admissions")


def test_exact_binding_budget_and_execution_preconditions_are_frozen() -> None:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    evidence = decision["input_evidence"]
    binding = issuance["exact_binding"]
    assert binding["input_digest"] == evidence["input_digest"]
    assert binding["preparation_digest"] == evidence["preparation_digest"]
    assert binding["predicted_work_unit_id"] == evidence["predicted_work_unit_id"]
    assert binding["predicted_attempt_id"] == evidence["predicted_attempt_id"]
    assert binding["predicted_research_run_id"] == evidence["predicted_research_run_id"]
    envelope = issuance["execution_envelope"]
    assert envelope["maximum_output_tokens_total"] == 10200
    assert envelope["specialist_max_output_tokens"] == 2200
    assert envelope["retry_budget"] == 0
    preflight = issuance["zero_call_preflight"]
    assert preflight["fresh_predicted_work_unit_attempt_run_absent"] is True
    assert preflight["credential_present"] is True
    assert preflight["credential_value_read_output_or_persisted"] is False
    assert preflight["provider_health_probe_performed"] is False


def test_backlog_preserves_issuance_and_records_later_exact_execution() -> None:
    backlog = _load(BACKLOG)
    next_action = backlog["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["fresh_v3_agent_proof_decision_authorized"] is True
    assert next_action["fresh_v3_exact_admission_issuance_authorized"] is True
    assert next_action["fresh_v3_exact_admission_issued"] is True
    assert next_action["fresh_v3_exact_live_execution_authorized"] is True
    assert next_action["S3_T09_replacement_exact_admission_issuance_authorized"] is True
    assert next_action["S3_T09_replacement_exact_admission_issued"] is True
    assert next_action["S3_T09_replacement_exact_admission_consumed"] is True
    assert next_action["S3_T09_replacement_exact_live_execution_authorized"] is True
    assert next_action[
        "S3_T09_replacement_artifact_paired_baseline_validation_authorized"
    ] is True
    assert next_action["deterministic_baseline_materialization_authorized"] is True
    assert next_action["replacement_admission_or_execution_authorized"] is False
    assert next_action["source_network_or_external_tool_execution_authorized"] is False
    assert next_action["release_or_production_authorized"] is False


def test_issuance_artifacts_do_not_contain_plaintext_credentials() -> None:
    rendered = ADMISSION.read_text(encoding="utf-8") + ISSUANCE.read_text(
        encoding="utf-8"
    )
    assert "DEEPSEEK_API_KEY" in rendered
    assert "sk-" not in rendered.lower()
    assert "fixture-secret" not in rendered.lower()
