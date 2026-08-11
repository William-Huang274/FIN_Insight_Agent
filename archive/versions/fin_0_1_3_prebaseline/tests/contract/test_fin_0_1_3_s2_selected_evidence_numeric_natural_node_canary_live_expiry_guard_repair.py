from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
RELEASES = ROOT / "configs/releases"
R1_ISSUANCE = RELEASES / (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_admission_issuance_v1_0.json"
)
R1_DISPOSITION = RELEASES / (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_admission_issuance_r1_expiry_guard_gap_disposition_v1_0.json"
)
REPAIR = RELEASES / (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_expiry_guard_repair_v1_0.json"
)


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _canonical_digest(value: dict, digest_key: str) -> str:
    from sec_agent.s2_selected_evidence_numeric_cocompilation import canonical_digest

    body = {key: item for key, item in value.items() if key != digest_key}
    return canonical_digest(body)


def test_r1_issuance_is_canonical_unconsumed_and_zero_call() -> None:
    issuance = _load(R1_ISSUANCE)
    assert issuance["issuance_digest"] == _canonical_digest(
        issuance, "issuance_digest"
    )
    assert issuance["admission"]["consumed"] is False
    assert issuance["issuance_boundary"]["execution_started"] is False
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
    assert issuance["authority"]["credential_preflight"] == {
        "credential_env_name": "DEEPSEEK_API_KEY",
        "credential_present": True,
        "credential_value_read_output_or_persisted": False,
    }


def test_r1_disposition_is_canonical_and_forbids_reuse() -> None:
    disposition = _load(R1_DISPOSITION)
    assert disposition["disposition_digest"] == _canonical_digest(
        disposition, "disposition_digest"
    )
    assert disposition["r1_issuance"]["issuance_digest"] == _load(R1_ISSUANCE)[
        "issuance_digest"
    ]
    assert disposition["disposition"]["r1_may_be_executed"] is False
    assert disposition["disposition"]["r1_may_be_relabelled_or_reused"] is False
    assert disposition["safety_observation"]["provider_calls"] == 0


def test_repair_result_is_canonical_and_stops_before_live() -> None:
    repair = _load(REPAIR)
    assert repair["result_digest"] == _canonical_digest(repair, "result_digest")
    assert repair["implementation"]["valid_window_rule"] == (
        "issued_at <= observed_at < expires_at"
    )
    assert repair["stage_acceptance"]["fresh_v1_1_admission_issued"] is False
    assert repair["stage_acceptance"]["natural_model_canary"] is False
    assert repair["observed_calls"]["provider_calls"] == 0


def test_issuer_and_runner_only_target_replacement_v1_1() -> None:
    issuer = (
        ROOT
        / "scripts/releases/issue_fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_live_admission.py"
    ).read_text(encoding="utf-8")
    runner = (
        ROOT
        / "scripts/releases/run_fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_live.py"
    ).read_text(encoding="utf-8")
    assert '"live_admission_issuance_v1_1.json"' in issuer
    assert '"live_admission_issuance_v1_1.json"' in runner
    assert "observed_at=observed_at" in runner
