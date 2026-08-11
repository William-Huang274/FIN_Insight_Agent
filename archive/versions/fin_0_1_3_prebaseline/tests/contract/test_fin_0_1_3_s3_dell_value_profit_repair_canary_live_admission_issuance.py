from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s3_dell_value_profit_repair_canary import (  # noqa: E402
    compile_repair_canary_material,
    load_repair_canary_policy,
)
from sec_agent.s3_dell_value_profit_repair_canary_live import (  # noqa: E402
    LIVE_SCOPE,
    validate_live_canary_issuance,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
    "repair_canary_policy_v1_0.json"
)
DECISION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_repair_canary_"
    "live_value_cost_risk_authority_decision_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_"
    "clean_independent_proof_v1_0.json"
)
ISSUANCE_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_repair_canary_"
    "live_admission_issuance_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_issuance_is_canonical_fresh_unconsumed_and_not_execution_authority() -> None:
    issuance = _load(ISSUANCE_PATH)
    body = {
        key: value for key, value in issuance.items() if key != "issuance_digest"
    }
    assert issuance["issuance_digest"] == canonical_digest(body)
    assert issuance["status"] == "issued_unconsumed_execution_not_authorized"
    assert issuance["issuance_boundary"] == {
        "admission_issued": True,
        "admission_consumed": False,
        "execution_started": False,
        "provider_call_started": False,
        "model_call_started": False,
        "business_artifact_promotion": False,
    }
    assert issuance["observed_counts"]["provider_calls"] == 0
    assert issuance["observed_counts"]["model_calls"] == 0


def test_admission_binds_clean_implementation_and_exact_canary_identity() -> None:
    issuance = _load(ISSUANCE_PATH)
    authority = issuance["authority"]
    admission = issuance["admission"]
    assert authority["implementation_commit"] == (
        "1d29bc65b63560ac68b4f7344cc1fc8f10295c8d"
    )
    assert len(authority["source_bindings"]) == 10
    assert admission["run_scope"] == LIVE_SCOPE
    assert admission["run_id"] == (
        "fin013_s3_dell_value_profit_repair_canary_11a8bc7aa03045f7803a"
    )
    assert admission["case_key"] == "DELL"
    assert admission["node_id"] == (
        "dell_value_profit_current_pack_repair_adjudicator_v1"
    )
    assert admission["provider_calls_maximum"] == 1
    assert admission["model_calls_maximum"] == 1
    assert admission["retries"] == 0
    assert admission["fallbacks"] == 0
    assert admission["consumed"] is False


def test_issuance_revalidates_against_bound_sources_at_issued_time() -> None:
    policy = load_repair_canary_policy(POLICY_PATH, repo_root=ROOT)
    material = compile_repair_canary_material(policy=policy, repo_root=ROOT)
    issuance = _load(ISSUANCE_PATH)
    preflight = issuance["authority"]["project_os_preflight_snapshot"]
    validate_live_canary_issuance(
        issuance,
        decision=_load(DECISION_PATH),
        clean_proof=_load(PROOF_PATH),
        material=material,
        project_os_preflight=preflight,
        repo_root=ROOT,
        observed_at=issuance["admission"]["issued_at"],
    )
    assert issuance["authority"]["credential_preflight"] == {
        "credential_env_name": "DEEPSEEK_API_KEY",
        "credential_present": True,
        "credential_value_read_output_or_persisted": False,
    }
