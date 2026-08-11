from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

RELEASES = ROOT / "configs" / "releases"
DECISION = (
    RELEASES
    / "fin_ia_0_1_s3_t09_owner_grade_v3_fresh_agent_proof_decision_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_issue(issue_id: str) -> dict[str, object]:
    latest: dict[str, dict[str, object]] = {}
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[str(row["issue_id"])] = row
    return latest[issue_id]


def test_decision_freezes_fresh_v3_identity_without_issuance_or_execution() -> None:
    decision = _load(DECISION)
    assert decision["status"] == (
        "pass_fresh_v3_exact_proof_contract_decided_"
        "admission_issuance_pending_separate_authority"
    )
    authority = decision["authority"]
    assert authority["fresh_v3_agent_proof_decision_authorized"] is True
    assert authority["admission_issuance_authorized"] is False
    assert authority["model_provider_network_execution_authorized"] is False
    assert set(decision["observed_counts"].values()) == {0}
    identity = decision["fresh_identity"]
    assert identity["research_run_id"] == (
        "research_run_fin01_b939a453b921cb5bcf3c2edf"
    )
    assert identity["input_digest"] == (
        "dba3d25144edfd0f7411d638b964deba8bab70406fb33b3bfca7c16be6bcf06e"
    )


def test_fresh_identity_is_distinct_and_baseline_body_is_blinded() -> None:
    decision = _load(DECISION)
    fresh = decision["fresh_identity"]["research_run_id"]
    nonreuse = decision["freshness_and_nonreuse"]
    assert fresh not in {
        nonreuse["distinct_from_prior_failed_agent_run"],
        nonreuse["distinct_from_prior_output_v2_succeeded_agent_run"],
        nonreuse["distinct_from_exact_deterministic_baseline_run"],
    }
    assert nonreuse["consumed_identity_reuse_allowed"] is False
    assert nonreuse["baseline_output_body_exposed_to_agent"] is False
    assert nonreuse["baseline_body_or_artifact_is_provider_input"] is False


def test_provider_route_does_not_overclaim_server_side_strictness() -> None:
    decision = _load(DECISION)
    route = decision["provider_route_review"]
    prospective = decision["prospective_admission"]
    assert route["decision"] == "retain_deepseek_to_isolate_output_v3_contract_effect"
    assert route["server_side_strict_json_schema_claimed"] is False
    assert route["provider_transport_guarantee_used"] == "json_object_only"
    assert "local_output_v3" in route["strict_contract_owner"]
    assert prospective["output_contract_ref"] == (
        "fin01.s3.bounded_agent_three_cell_output:v3"
    )
    assert prospective["admission_digest"] == (
        "5f8db7ff2eef2b8ea06c8c95b21c32dec57432b34888a9cf6c5990af3d4b4459"
    )
    assert prospective["admission_issued"] is False


def test_budget_and_stop_contract_is_exact_and_runtime_precondition_is_explicit() -> None:
    decision = _load(DECISION)
    budget = decision["budget_and_stop_contract"]
    assert (
        budget["maximum_semantic_model_calls"],
        budget["maximum_provider_calls"],
        budget["maximum_network_calls"],
    ) == (6, 6, 6)
    assert budget["aggregate_max_output_tokens"] == 10200
    assert budget["maximum_total_cost_usd"] == 0.1
    assert budget["retry_budget"] == 0
    assert budget["automatic_repair_fallback_or_rerun"] is False
    assert budget["execution_environment_precondition"] == (
        "LLM_GATEWAY_TRANSPORT_RETRIES=0"
    )
    assert budget["current_environment_precondition_satisfied"] is False


def test_historical_decision_and_current_issuance_progress_keep_rc_blocking() -> None:
    decision = _load(DECISION)
    backlog = _load(BACKLOG)
    assert decision["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-FRESH-EXACT-ADMISSION-ISSUANCE"
    )
    next_action = backlog["next_action"]
    assert next_action["item_id"] == (
        "S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V5-RESEARCH-LEAD-OUTPUT-TRUNCATION-RESULT-AND-ROOT-CAUSE-DECISION"
    )
    assert next_action["fresh_v3_agent_proof_decision_authorized"] is True
    assert next_action["fresh_v3_exact_admission_issuance_authorized"] is True
    assert next_action["fresh_v3_exact_admission_issued"] is True
    assert next_action["fresh_v3_exact_admission_consumed"] is True
    assert next_action["fresh_v3_exact_live_execution_authorized"] is True
    issue = _latest_issue(
        "RC-P36-037-s3-owner-grade-semantic-actionability-and-verifier-false-negative-gap"
    )
    assert issue["status"] == (
            "semantic_repair_and_transport_v5_assembly_live_proven_lead_truncation_"
            "no_complete_artifact_proof"
    )
    assert issue["full_chain_blocker"] is True
