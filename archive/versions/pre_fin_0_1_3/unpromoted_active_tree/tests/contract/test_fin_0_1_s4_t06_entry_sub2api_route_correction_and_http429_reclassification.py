from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEEPSEEK_MAINLINE = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
)
DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_sub2api_route_correction_and_"
    "http429_reclassification_program_disposition_v1_0.json"
)
RESULT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_openai_credential_requalified_"
    "fresh_strict_schema_canary_exact_once_execution_result_v1_0.json"
)
METADATA = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_openai_credential_requalification_"
    "exact_once_metadata_probe_result_v1_0.json"
)
RUNNER = ROOT / (
    "scripts/releases/"
    "run_fin_ia_0_1_s4_t06_entry_single_node_strict_schema_canary.py"
)
NEXT = (
    "S4-T06-ENTRY-SUB2API-PROVIDER-ROUTE-AND-CAPABILITY-"
    "CONTRACT-REBASELINE-DECISION"
)
PROGRESSED = "S4-T06-ENTRY-SUB2API-SECURE-TRANSPORT-ENDPOINT-CONFIRMATION"
CURRENT = (
    "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
    "CANARY-POST-RESULT-PROGRAM-DISPOSITION"
)


def _latest_issue(issue_id: str) -> dict:
    rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [row for row in rows if row["issue_id"] == issue_id][-1]


def test_decision_reclassifies_wrong_route_without_mutating_evidence() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))

    assert decision["decision_label"] == (
        "retract_official_platform_quota_diagnosis_and_rebaseline_sub2api_route"
    )
    assert decision["user_correction"]["intended_provider"] == (
        "self_hosted_Sub2API"
    )
    assert decision["immutable_historical_evidence"]["canary_result_sha256"] == (
        hashlib.sha256(RESULT.read_bytes()).hexdigest()
    )
    assert result["provider_contract"]["base_url"] == "https://api.openai.com/v1"
    assert metadata["provider_contract"]["base_url"] == "https://api.openai.com/v1"
    reclassification = decision["reclassification"]
    assert reclassification["official_openai_http429_remains_valid_historical_fact"]
    assert not reclassification["official_openai_http429_proves_sub2api_rate_limit"]
    assert not reclassification["official_openai_http429_proves_sub2api_quota_exhaustion"]
    assert reclassification["intended_sub2api_rate_or_quota_state"] == (
        "not_evaluated"
    )


def test_route_audit_proves_sub2api_was_never_contacted() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    audit = decision["zero_call_route_audit"]
    runner_source = RUNNER.read_text(encoding="utf-8")

    assert audit["runner_hardcodes_official_openai_base_url"]
    assert not audit["sub2api_route_bound_in_current_authority"]
    assert not audit["sub2api_route_contacted_by_historical_probe_or_canary"]
    assert audit["model_provider_network_calls"] == [0, 0, 0]
    assert not audit["credential_read_or_write"]
    assert "https://api.openai.com/v1" in runner_source
    assert "OPENAI_BASE_URL" not in runner_source


def test_backlogs_and_latest_root_causes_point_only_to_zero_call_rebaseline() -> None:
    decision_sha256 = hashlib.sha256(DECISION.read_bytes()).hexdigest()
    program = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
        ).read_text(encoding="utf-8")
    )
    s4 = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    for state in (program["next_action"], s4["T06_entry_program_scope_replace"]):
        assert state["Sub2API_route_correction_disposition_sha256"] == (
            decision_sha256
        )
        assert state["intended_provider_family"] == "self_hosted_Sub2API"
        assert state["intended_provider_base_url"] == (
            "http://43.135.174.27:8080"
        )
        assert not state["historical_canary_route_matches_intended_provider"]
        assert not state["official_OpenAI_HTTP_429_applies_to_intended_Sub2API"]
        assert state["Sub2API_route_rebaseline_authorized"]
    assert program["next_action"]["item_id"] in {
        CURRENT,
        DEEPSEEK_MAINLINE,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    assert s4["current_next_action"] == program["next_action"]["item_id"]

    rc_070 = _latest_issue(
        "RC-P36-070-s4-t06-strict-schema-unsupported-uniqueItems"
    )
    rc_072 = _latest_issue(
        "RC-P36-072-s4-t06-openai-http-429-rate-or-quota-subtype-unknown"
    )
    rc_073 = _latest_issue(
        "RC-P36-073-s4-t06-provider-route-authority-mismatch-sub2api-unbound"
    )
    expected_scope = [
        "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
        "post_result_program_disposition",
        "repository_and_git_hygiene",
    ]
    if program["next_action"]["item_id"] in {
        DEEPSEEK_MAINLINE,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }:
        expected_scope = [
            "S4_T06_MU_DeepSeek_fresh_exact_admission_preparation_and_"
            "zero_call_proof",
            "repository_and_git_hygiene",
        ]
    assert rc_070["allowed_run_scopes"] == expected_scope
    assert not rc_072["full_chain_blocker"]
    assert rc_072["blocking_run_scopes"] == []
    assert rc_073["full_chain_blocker"] is False
    assert rc_073["owned_by_project"]
    assert rc_073["allowed_run_scopes"] == expected_scope


def test_decision_contains_no_credential_material_and_authorizes_no_call() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    text = DECISION.read_text(encoding="utf-8")
    assert decision["next_action"] == NEXT
    assert not decision["next_action_authorized"]
    assert decision["next_action_preconditions"][
        "user_supplies_or_confirms_non_secret_sub2api_base_url"
    ]
    assert decision["next_action_preconditions"][
        "no_model_or_provider_call_in_rebaseline_decision"
    ]
    assert "sk-" not in text
    assert "Authorization" not in text
