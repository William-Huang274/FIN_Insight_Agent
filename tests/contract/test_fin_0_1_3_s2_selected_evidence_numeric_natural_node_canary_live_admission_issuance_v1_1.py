from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s2_selected_evidence_numeric_cocompilation import (  # noqa: E402
    canonical_digest,
)
from sec_agent.s2_selected_evidence_numeric_natural_node_canary import (  # noqa: E402
    compile_canary_material,
    load_canary_policy,
)
from sec_agent.s2_selected_evidence_numeric_natural_node_canary_live import (  # noqa: E402
    LIVE_SCOPE,
    validate_live_canary_issuance,
)


RELEASES = ROOT / "configs/releases"
POLICY = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "policy_v1_0.json"
)
DECISION = RELEASES / (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_value_cost_risk_authority_decision_v1_0.json"
)
PROOF = RELEASES / (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "clean_independent_proof_v1_0.json"
)
ISSUANCE = RELEASES / (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_admission_issuance_v1_1.json"
)
R1_DISPOSITION = RELEASES / (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_admission_issuance_r1_expiry_guard_gap_disposition_v1_0.json"
)
PREFLIGHT_RESULT = RELEASES / (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_admission_v1_1_clean_preflight_result_v1_0.json"
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_v1_1_issuance_validates_against_current_contract_and_window() -> None:
    issuance = _load(ISSUANCE)
    material = compile_canary_material(
        policy=load_canary_policy(POLICY, repo_root=ROOT), repo_root=ROOT
    )
    preflight = run_project_os_preflight(ROOT, run_scope=LIVE_SCOPE)
    validate_live_canary_issuance(
        issuance,
        decision=_load(DECISION),
        clean_proof=_load(PROOF),
        material=material,
        project_os_preflight=preflight,
        repo_root=ROOT,
        observed_at=issuance["authority"]["issued_at"],
    )
    body = {
        key: value for key, value in issuance.items() if key != "issuance_digest"
    }
    assert issuance["issuance_digest"] == canonical_digest(body)


def test_v1_1_is_24_hour_unconsumed_zero_call_and_not_execution_authority() -> None:
    issuance = _load(ISSUANCE)
    issued_at = datetime.fromisoformat(
        issuance["authority"]["issued_at"].replace("Z", "+00:00")
    )
    expires_at = datetime.fromisoformat(
        issuance["authority"]["expires_at"].replace("Z", "+00:00")
    )
    assert (expires_at - issued_at).total_seconds() == 24 * 60 * 60
    assert issuance["status"] == "issued_unconsumed_execution_not_authorized"
    assert issuance["admission"]["consumed"] is False
    assert issuance["admission"]["execution_enabled_by_issuance"] is False
    assert issuance["authority"]["execution_authorized_by_this_authority"] is False
    assert issuance["observed_counts"] == {
        "admission_consumptions": 0,
        "fallbacks": 0,
        "model_calls": 0,
        "network_calls": 0,
        "new_admissions": 1,
        "provider_calls": 0,
        "retries": 0,
        "source_calls": 0,
    }


def test_v1_1_binds_repaired_commit_and_boolean_only_credential_state() -> None:
    issuance = _load(ISSUANCE)
    assert issuance["authority"]["implementation_commit"] == (
        "dd035eb5d62776e0a3d1118f1c439add42814c45"
    )
    assert len(issuance["authority"]["source_bindings"]) == 9
    assert issuance["authority"]["credential_preflight"] == {
        "credential_env_name": "DEEPSEEK_API_KEY",
        "credential_present": True,
        "credential_value_read_output_or_persisted": False,
    }


def test_v1_1_does_not_rehabilitate_or_reuse_r1() -> None:
    issuance = _load(ISSUANCE)
    disposition = _load(R1_DISPOSITION)
    assert issuance["issuance_digest"] != disposition["r1_issuance"][
        "issuance_digest"
    ]
    assert issuance["admission"]["admission_digest"] != disposition[
        "r1_issuance"
    ]["admission_digest"]
    assert disposition["disposition"]["r1_may_be_executed"] is False
    assert disposition["disposition"]["r1_may_be_relabelled_or_reused"] is False


def test_v1_1_clean_preflight_result_is_canonical_and_stops_before_execution() -> None:
    result = _load(PREFLIGHT_RESULT)
    body = {key: value for key, value in result.items() if key != "result_digest"}
    assert result["result_digest"] == canonical_digest(body)
    assert result["v1_1_issuance"]["issuance_digest"] == _load(ISSUANCE)[
        "issuance_digest"
    ]
    assert result["clean_preflight"]["status"] == (
        "preflight_pass_execution_not_authorized"
    )
    assert result["clean_preflight"]["separate_execution_authority_present"] is False
    assert result["stage_acceptance"]["fresh_v1_1_clean_preflight"] is True
    assert result["stage_acceptance"]["natural_model_canary"] is False
    assert result["observed_calls"]["provider_calls"] == 0
