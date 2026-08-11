from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s2_selected_evidence_numeric_cocompilation import (  # noqa: E402
    canonical_digest,
)


DECISION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "live_value_cost_risk_authority_decision_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "clean_independent_proof_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_decision_is_zero_call_and_does_not_execute_live() -> None:
    decision = _load(DECISION_PATH)
    assert decision["scope"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "retries": 0,
        "live_scope_registered": False,
        "live_runner_implemented": False,
        "live_admission_issued": False,
        "live_execution_authorized_by_this_record": False,
        "dell_full_chain_authorized": False,
        "business_artifact_promotion": False,
    }


def test_decision_is_bound_to_clean_r2_and_exact_request() -> None:
    decision = _load(DECISION_PATH)
    proof = _load(PROOF_PATH)
    basis = decision["immutable_basis"]
    assert basis["clean_proof"]["expected_result_digest"] == proof["result_digest"]
    assert basis["compiled_input_digest"] == proof["compiled_canary"][
        "compiled_input_digest"
    ]
    assert basis["request_digest"] == proof["compiled_canary"]["request_digest"]
    assert basis["request_characters"] == proof["compiled_canary"][
        "request_characters"
    ]


def test_selected_option_is_one_pro_call_not_full_report_or_model_ab() -> None:
    decision = _load(DECISION_PATH)
    selected = [
        row for row in decision["option_assessment"] if row["decision"] == "selected"
    ]
    assert [row["option_id"] for row in selected] == [
        "A_authorize_one_bounded_Pro_live_canary_path"
    ]
    budget = decision["future_live_budget_if_separately_executed"]
    assert budget["provider_calls_maximum"] == budget["model_calls_maximum"] == 1
    assert budget["source_calls"] == budget["network_tool_calls"] == 0
    assert budget["retries"] == budget["fallbacks"] == 0
    assert budget["business_artifact_promotion"] is False


def test_only_live_path_and_admission_issuance_are_authorized_next() -> None:
    next_step = _load(DECISION_PATH)["authorized_next_implementation"]
    assert next_step["implement_live_admission_validation"] is True
    assert next_step["issue_one_fresh_admission_after_clean_synced_preflight"] is True
    assert next_step["execute_provider_call"] is False
    assert next_step["automatic_execution_after_issuance"] is False


def test_decision_digest_is_canonical() -> None:
    decision = _load(DECISION_PATH)
    body = {key: value for key, value in decision.items() if key != "decision_digest"}
    assert decision["decision_digest"] == canonical_digest(body)
