from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


RELEASES = ROOT / "configs" / "releases"
DECISION = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_v3_"
    "fresh_agent_proof_decision_v1_0.json"
)
ADMISSION = RELEASES / (
    "fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_"
    "specialist_v5_research_lead_v3_exact_admission_v1_0.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_v3_"
    "fresh_exact_admission_issuance_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_issued_admission_exactly_matches_frozen_payload_and_digest() -> None:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    payload = _load(ADMISSION)
    assert payload == decision["prospective_admission"]["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    admission.assert_profile_admissible()
    assert admission.transport_ref == (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF
    )
    assert admission.research_lead_transport_ref == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF
    )
    assert admission.provider_output_capture_policy_ref == (
        S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF
    )
    digest = canonical_digest(admission.digest_payload())
    assert digest == decision["prospective_admission"]["admission_digest"]
    assert digest == issuance["issued_admission"]["admission_digest"]


def test_issuance_loads_in_runner_without_provider_or_execution_call() -> None:
    target = load_execution_target(ISSUANCE)
    assert target.research_run_id == "research_run_fin01_e418d7086d4a1d253e9b2c9b"
    assert target.maximum_output_tokens == 16800
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(_load(ADMISSION))
    callback_calls = 0

    def _must_not_call_provider(**_: object) -> dict[str, object]:
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("provider_callback_forbidden")

    build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=_must_not_call_provider
    )
    assert callback_calls == 0


def test_issuance_budget_truth_table_and_authority_remain_closed() -> None:
    decision = _load(DECISION)
    issuance = _load(ISSUANCE)
    assert decision["freshness_and_nonreuse"]["prior_research_run_count"] == 10
    envelope = issuance["execution_envelope"]
    assert [
        envelope["maximum_semantic_model_calls"],
        envelope["maximum_provider_calls"],
        envelope["maximum_network_calls"],
    ] == [12, 12, 12]
    assert envelope["maximum_output_tokens_total"] == 16800
    assert envelope["retry_budget"] == 0
    assert envelope["automatic_retry_repair_fallback_or_rerun_allowed"] is False
    contract = issuance["research_lead_v3_contract"]
    assert set(contract["fact_presence_truth_table"].values()) == {
        "facts_present",
        "no_facts_present",
        "mixed_fact_presence",
    }
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False
    assert issuance["authority"][
        "admission_consumption_or_exact_once_execution_authorized"
    ] is False
    assert issuance["zero_call_preflight"][
        "transport_retry_environment_currently_zero"
    ] is False
    assert set(
        value
        for key, value in issuance["observed_counts"].items()
        if key != "new_admissions"
    ) == {0}


def test_issuance_historically_advanced_to_execution_and_backlog_records_consumption() -> None:
    issuance = _load(ISSUANCE)
    backlog = _load(BACKLOG)
    historical_next = (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-FRESH-EXACT-"
        "LIVE-EXECUTION"
    )
    assert issuance["next_action"] == historical_next
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-WRITER-CLAIM-SURFACE-"
        "AND-ORPHANED-RUN-ZERO-CALL-ROOT-CAUSE-DECISION"
    )
    next_action = backlog["next_action"]
    assert next_action[
        "research_lead_v3_fresh_exact_admission_issuance_authorized"
    ] is True
    assert next_action["research_lead_v3_fresh_exact_admission_issued"] is True
    assert next_action["research_lead_v3_fresh_exact_admission_consumed"] is True
    assert next_action[
        "research_lead_v3_fresh_exact_live_execution_authorized"
    ] is True
    assert next_action["agent_execution_authorized"] is False
    assert next_action["agent_rerun_authorized"] is False


def test_issuance_contracts_do_not_persist_plaintext_credentials() -> None:
    rendered = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (DECISION, ADMISSION, ISSUANCE)
    )
    assert "DEEPSEEK_API_KEY" in rendered
    assert "sk-" not in rendered.lower()
