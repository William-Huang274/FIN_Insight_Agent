from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s2_selected_evidence_numeric_natural_node_canary_live import (
    LIVE_EXECUTION_AUTHORITY_SCHEMA,
    LIVE_SCOPE,
    validate_live_execution_authority,
)


AUTHORITY = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_live_"
    "execution_authority_decision_v1_0.json"
)
ISSUANCE = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_live_"
    "admission_issuance_v1_1.json"
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_execution_authority_is_canonical_and_exactly_bound() -> None:
    authority = _load(AUTHORITY)
    issuance = _load(ISSUANCE)
    body = {
        key: value
        for key, value in authority.items()
        if key != "execution_authority_digest"
    }

    assert authority["schema_version"] == LIVE_EXECUTION_AUTHORITY_SCHEMA
    assert authority["execution_authority_digest"] == canonical_digest(body)
    validate_live_execution_authority(authority, issuance=issuance)
    assert authority["issuance_digest"] == issuance["issuance_digest"]
    assert authority["admission_digest"] == issuance["admission"]["admission_digest"]


def test_decision_is_zero_call_and_precedes_execution() -> None:
    authority = _load(AUTHORITY)
    counts = authority["decision_boundary"]

    assert authority["status"] == "authorized_single_exact_once_live_canary_execution"
    assert counts["credential_presence_checks"] == 1
    assert set(
        value
        for key, value in counts.items()
        if key != "credential_presence_checks"
    ) == {0}
    assert authority["pre_execution_verification"]["admission_consumed"] is False
    assert authority["pre_execution_verification"]["execution_started"] is False
    assert authority["stage_acceptance"]["natural_model_canary"] is False


def test_authority_is_one_pro_atom_with_no_scope_expansion() -> None:
    authority = _load(AUTHORITY)
    binding = authority["execution_binding"]

    assert binding["run_scope"] == LIVE_SCOPE
    assert binding["case_key"] == "DELL"
    assert binding["node_id"] == (
        "dell_demand_authenticity_numeric_view_atom_canary_v1"
    )
    assert binding["model"] == "deepseek-v4-pro"
    assert authority["provider_calls_maximum"] == 1
    assert authority["model_calls_maximum"] == 1
    assert authority["retries"] == 0
    assert authority["fallbacks"] == 0
    assert authority["business_artifact_promotion"] is False
    assert binding["network_tool_calls"] == 0
    assert binding["source_calls"] == 0
    assert not authority["authority"]["full_dell_report_or_other_case_execution_authorized"]
    assert not authority["authority"]["automatic_second_call_retry_fallback_replay_or_relaunch_authorized"]


def test_decision_time_is_inside_exact_admission_window() -> None:
    authority = _load(AUTHORITY)
    binding = authority["execution_binding"]
    decided_at = datetime.fromisoformat(authority["decided_at"].replace("Z", "+00:00"))
    issued_at = datetime.fromisoformat(binding["issued_at"].replace("Z", "+00:00"))
    expires_at = datetime.fromisoformat(binding["expires_at"].replace("Z", "+00:00"))

    assert issued_at <= decided_at < expires_at


def test_source_decision_and_preflight_digests_remain_bound() -> None:
    authority = _load(AUTHORITY)
    source = authority["source_authority"]
    decision = _load(ROOT / source["value_cost_risk_decision_ref"])
    proof = _load(ROOT / source["clean_independent_proof_ref"])
    implementation = _load(ROOT / source["live_implementation_ref"])
    repair = _load(ROOT / source["expiry_guard_repair_ref"])
    preflight = _load(ROOT / source["clean_preflight_ref"])

    assert source["value_cost_risk_decision_digest"] == decision["decision_digest"]
    assert source["clean_independent_proof_digest"] == proof["result_digest"]
    assert source["live_implementation_digest"] == implementation["result_digest"]
    assert source["expiry_guard_repair_digest"] == repair["result_digest"]
    assert source["clean_preflight_digest"] == preflight["result_digest"]
