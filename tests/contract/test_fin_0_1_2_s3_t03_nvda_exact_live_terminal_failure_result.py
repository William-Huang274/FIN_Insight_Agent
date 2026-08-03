from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_execution_"
    "terminal_failure_result_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_29.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_fresh_exact_admission_r1.json"
)
HISTORICAL_LEAD_V7_SUCCESS = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_"
    "local_materialization_r2_exact_live_execution_success_result_v1_0.json"
)
NEXT = (
    "FIN-0.1.2-S3-T03-NVDA-RESEARCH-LEAD-LOCAL-FACT-PRESENCE-AND-"
    "CLAIM-ALIAS-SEMANTIC-OWNERSHIP-REGRESSION-DISPOSITION-DECISION"
)
ISSUE = (
    "RC-P36-108-fin-0-1-2-s3-t03-research-lead-deterministic-fact-"
    "presence-and-claim-alias-semantic-ownership-regression"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_terminal_failure_is_exact_once_quarantined_and_inside_budget() -> None:
    result = _load(RESULT)

    assert result["status"].startswith("terminal_failed_first_credible")
    assert result["authority"]["admission_consumed"] is True
    assert result["authority"][
        "automatic_retry_fallback_replay_relaunch_or_replacement"
    ] == [0, 0, 0, 0, 0]
    assert result["authority"][
        "paired_assessment_owner_acceptance_or_S3_T04_performed"
    ] is False
    assert result["typed_terminal"]["phase"] == "research_lead"
    assert result["typed_terminal"]["code"] == (
        "s3_bounded_research_lead_v3_semantic_fact_presence_summary_mismatch"
    )
    assert result["typed_terminal"]["failed_output_quarantined"] is True
    assert result["typed_terminal"]["business_promotable"] is False
    assert result["typed_terminal"]["credential_value_persisted"] is False
    assert result["typed_terminal"]["private_reasoning_persisted"] is False
    assert result["typed_terminal"]["raw_provider_response_persisted"] is False
    observed = result["observed_execution"]
    assert (
        observed["local_fact_receipts"],
        observed["provider_calls"],
        observed["restricted_captures"],
        observed["business_artifacts"],
    ) == (3, 7, 7, 0)
    assert (
        observed["input_tokens"],
        observed["output_tokens"],
        observed["total_tokens"],
    ) == (37107, 2310, 39417)
    assert observed["estimated_cost_usd"] == 0.01815124
    assert observed["budget_exceeded"] is False


def test_failure_analysis_preserves_model_error_and_project_regression() -> None:
    result = _load(RESULT)
    analysis = result["first_failure_analysis"]

    assert analysis["provider_transport_or_json_failure"] is False
    assert analysis["direct_model_semantic_error_observed"] is True
    assert analysis["project_contract_regression_observed"] is True
    assert analysis["claim_alias_support_truth"] == {
        "C001": "no_direct_support_facts",
        "C002": "no_direct_support_facts",
        "C003": "three_direct_support_facts",
        "C004": "no_direct_support_facts",
    }
    mismatches = [
        row
        for row in analysis["observed_conflict_rows"]
        if row["provider_summary"] != row["deterministic_expected_summary"]
    ]
    assert len(mismatches) == 2
    assert all(row["provider_narrative_also_treated_C002_as_fact_supported"] for row in mismatches)
    assert result["issue"]["issue_id"] == ISSUE
    assert result["issue"]["S0_S1_or_S2_reopened"] is False


def test_current_admission_regressed_from_live_proven_lead_v7_to_v6() -> None:
    admission = _load(ADMISSION)
    historical = _load(HISTORICAL_LEAD_V7_SUCCESS)

    assert admission["research_lead_transport_ref"].endswith(":v6")
    assert historical["status"].startswith("terminal_succeeded_exact_once")
    assert historical["provider_execution"]["research_lead_transport_ref"].endswith(
        ":v7"
    )
    assert historical["provider_execution"][
        "research_lead_fact_presence_materialization_policy_ref"
    ] == "fin01.s3.research_lead.conflict_fact_presence_local_materialization:v1"
    assert historical["canonical_terminal_truth"]["artifact_count"] == 9


def test_projection_backlog_and_project_os_stop_before_any_replacement() -> None:
    result = _load(RESULT)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)["next_action"]

    assert projection["decision_binding"]["sha256"] == _sha256(RESULT)
    assert projection["decision_binding"]["bytes"] == RESULT.stat().st_size
    assert projection["current_truth"]["current_next_action"] == NEXT
    assert projection["execution_policy"]["primary_exact_attempts_consumed"] == 1
    assert projection["execution_policy"][
        "automatic_retry_replay_relaunch_or_replacement_authorized"
    ] is False
    assert projection["execution_policy"]["new_admission_or_execution_authorized"] is False
    assert backlog["item_id"] == NEXT
    assert backlog["current_projection_sha256"] == _sha256(PROJECTION)
    assert backlog["S3_T03_fresh_admission_consumed"] is True
    assert backlog["S3_T03_primary_exact_attempts_remaining"] == 0
    assert backlog["S3_T03_execution_result_sha256"] == _sha256(RESULT)
    assert result["next_action_authorized"] is False
    root_rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if ISSUE in line
    ]
    assert root_rows[-1]["status"].startswith("open_first_credible")
    assert root_rows[-1]["full_chain_blocker"] is True
    assert root_rows[-1]["allowed_run_scopes"][0] == NEXT
    capability_rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/project_os/capability_status_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if "fin_0_1_2_S3_T03_NVDA_primary_exact_live_terminal_failure" in line
    ]
    assert capability_rows[-1]["current_next"] == NEXT


def test_local_runtime_evidence_hashes_match_when_restricted_root_is_present() -> None:
    result = _load(RESULT)
    runtime = ROOT / result["execution_identity"]["runtime_root"]
    supervision = ROOT / result["execution_identity"]["supervision_root"]
    if not runtime.exists() and not supervision.exists():
        return

    assert runtime.exists() and supervision.exists()
    terminal = result["typed_terminal"]
    supervisor = result["supervision_result"]
    assert _sha256(runtime / "execution-result.json") == terminal[
        "execution_result_sha256"
    ]
    assert _sha256(runtime / "execution-state.json") == terminal[
        "execution_state_sha256"
    ]
    assert _sha256(runtime / "capture-index.json") == terminal[
        "capture_index_sha256"
    ]
    assert _sha256(supervision / "launch-receipt.json") == supervisor[
        "launch_receipt_sha256"
    ]
    assert _sha256(supervision / "exit-receipt.json") == supervisor[
        "exit_receipt_sha256"
    ]
