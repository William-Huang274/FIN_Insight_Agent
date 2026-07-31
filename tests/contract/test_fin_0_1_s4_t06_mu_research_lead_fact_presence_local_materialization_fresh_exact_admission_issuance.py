from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY,
    research_lead_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
)
from scripts.releases.issue_fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_fresh_exact_admission import (
    ADMISSION,
    ISSUANCE,
    NEXT_ACTION,
    PROOF_DECISION,
    verify_issued_admission,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _load_admission,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest


PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
ROOT_CAUSE_LEDGER = (
    ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
)
AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_"
    "local_materialization_r2_exact_live_execution_and_success_only_"
    "paired_assessment_authority_decision_v1_0.json"
)
EXPECTED_DIGEST = (
    "55fb08cac25b3a03109b13ae645d858b90b2074873f5355e6ed47ac93c6cd65c"
)
EXPECTED_PROOF_SHA256 = (
    "25178880022a502fad3e368033f009c852f7e503d032365e5c8b7a08f46f30f5"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_issue(issue_id: str) -> dict:
    return [
        json.loads(line)
        for line in ROOT_CAUSE_LEDGER.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and json.loads(line)["issue_id"] == issue_id
    ][-1]


def test_issued_R2_admission_is_exact_frozen_payload() -> None:
    proof = _load(PROOF_DECISION)
    payload = _load(ADMISSION)
    issuance = _load(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)

    admission.assert_profile_admissible()
    assert payload == proof["prospective_admission"]["payload"]
    assert canonical_digest(admission.digest_payload()) == EXPECTED_DIGEST
    assert admission.research_lead_transport_ref == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
    )
    assert (
        research_lead_transport_contract(
            admission.research_lead_transport_ref
        ).conflict_fact_presence_materialization_policy_ref
        == S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY
        .policy_ref
    )
    assert _sha256(PROOF_DECISION) == EXPECTED_PROOF_SHA256
    assert issuance["source_proof_decision_sha256"] == (
        EXPECTED_PROOF_SHA256
    )


def test_issuance_verifier_proves_unconsumed_zero_call_state() -> None:
    later_success = ROOT / (
        "configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_"
        "fact_presence_local_materialization_r2_exact_live_"
        "execution_success_result_v1_0.json"
    )
    if later_success.exists():
        issuance = _load(ISSUANCE)
        assert issuance["status"] == "issued_unconsumed_zero_call_preflight_pass"
        assert issuance["issued_admission"]["admission_digest"] == EXPECTED_DIGEST
        assert issuance["issuance_boundary"]["admission_consumed"] is False
        return

    result = verify_issued_admission()
    assert result["status"] == "issued_unconsumed_zero_call_preflight_pass"
    assert result["admission_digest"] == EXPECTED_DIGEST
    assert result["fresh_identity_absent"] is True
    assert result["provider_calls"] == 0
    assert result["next_action"] == NEXT_ACTION


def test_runner_loads_exact_R2_admission_without_execution() -> None:
    target = load_execution_target(ISSUANCE)
    admission = _load_admission(ADMISSION, target)
    proof = _load(PROOF_DECISION)

    assert target.admission_digest == EXPECTED_DIGEST
    assert target.work_unit_id == proof["fresh_identity"]["work_unit_id"]
    assert target.attempt_id == proof["fresh_identity"]["attempt_id"]
    assert target.research_run_id == proof["fresh_identity"][
        "research_run_id"
    ]
    assert target.maximum_output_tokens == 16800
    assert admission.admission_id == target.admission_id


def test_issuance_boundary_excludes_execution_and_deferred_work() -> None:
    issuance = _load(ISSUANCE)
    authority = issuance["authority"]
    boundary = issuance["issuance_boundary"]
    counts = issuance["observed_counts"]

    assert authority["fresh_exact_admission_issuance_authorized"] is True
    assert authority[
        "admission_consumption_or_exact_live_execution_authorized"
    ] is False
    assert authority[
        "paired_assessment_or_Human_review_authorized"
    ] is False
    assert authority["S4_T07_or_later_authorized"] is False
    assert authority["strict_schema_transport_authorized"] is False
    assert boundary["admission_issued"] is True
    assert boundary["admission_consumed"] is False
    assert boundary["execution_started"] is False
    assert boundary["strict_schema_transport_reentered"] is False
    assert counts["new_admissions"] == 1
    assert set(
        value for key, value in counts.items() if key != "new_admissions"
    ) == {0}


def test_project_state_advances_only_to_R2_execution_authority() -> None:
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    t06 = next(
        item for item in detailed["tasks"] if item["item_id"] == "S4-T06"
    )
    issue = _latest_issue(
        "RC-P36-078-s4-t06-mu-research-lead-deterministic-"
        "fact-presence-summary-model-ownership-recurrence"
    )

    current_next = program["next_action"]["item_id"]
    assert detailed["current_next_action"] == current_next
    assert program["next_action"][
        "fact_presence_materialization_fresh_R2_admission_issued"
    ] is True
    assert program["next_action"][
        "fact_presence_materialization_fresh_R2_admission_consumed"
    ] is True
    assert t06["fresh_R2_admission_issued"] is True
    assert t06["fresh_R2_admission_consumed"] is True
    assert issue["status"] == (
        "closed_exact_live_Lead_v7_local_materialization_proven"
    )
    assert issue["allowed_run_scopes"] == [
        (
            "S4_T06_MU_R2_L1_numeric_authority_and_case_identity_"
            "live_recurrence_root_cause_or_scope_disposition_decision"
        ),
        "repository_and_git_hygiene",
    ]
