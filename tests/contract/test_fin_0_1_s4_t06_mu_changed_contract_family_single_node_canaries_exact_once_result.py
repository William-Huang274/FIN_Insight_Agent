from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.models import canonical_digest


AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_"
    "single_node_natural_output_canaries_authority_decision_v1_0.json"
)
RUNNER = ROOT / (
    "scripts/releases/run_fin_ia_0_1_s4_t06_mu_changed_contract_family_"
    "single_node_natural_output_canaries.py"
)
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_"
    "single_node_natural_output_canaries_exact_once_execution_result_v1_0.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_exact_once_result_is_bound_and_stops_after_claim_failure() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["authority_sha256"] == _sha256(AUTHORITY)
    assert result["runner_ref"] == str(RUNNER.relative_to(ROOT)).replace(
        "\\", "/"
    )
    assert result["status"] == "terminal_failed_no_retry"
    assert result["completed_families"] == [
        "specialist_fact_atoms",
        "claim_candidate_atoms",
    ]
    assert result["skipped_after_first_failure"] == [
        "what_would_change_atoms"
    ]
    assert result["first_credible_failure"] == (
        "s4_compiled_claim_atom_no_valid_scope_compatible_subset"
    )
    assert result["totals"]["model_calls"] == 2
    assert result["totals"]["provider_calls"] == 2
    assert result["totals"]["network_calls"] == 2
    assert result["totals"]["transport_attempts"] == 2
    assert result["totals"]["captures"] == 2
    assert result["totals"]["total_tokens"] == 7643
    assert result["totals"]["estimated_cost_usd"] == 0.0034813
    assert result["budget"][
        "retry_fallback_replay_provider_hopping"
    ] == [0, 0, 0, 0]
    assert result["canonical_work_unit_attempt_run_or_artifact_writes"] == 0
    assert result["business_artifact_promotions"] == 0
    assert result["R7_admission_or_exact_live"] is False


def test_fact_pass_claim_fail_and_capture_v2_readback() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    fact, claim = result["family_results"]
    assert fact["family_id"] == "specialist_fact_atoms"
    assert fact["status"] == "pass"
    assert fact["validation"]["provider_item_count"] == 5
    assert fact["validation"]["compiled_wire_pass"] is True
    assert fact["validation"]["local_deterministic_assembly_pass"] is True
    assert claim["family_id"] == "claim_candidate_atoms"
    assert claim["status"] == "terminal_failed"
    assert claim["provider_status"] == "ok"
    assert claim["finish_reason"] == "stop"
    assert claim["failure_code"] == (
        "s4_compiled_claim_atom_no_valid_scope_compatible_subset"
    )
    for row in (fact, claim):
        capture_path = ROOT / row["capture_ref"]
        capture = json.loads(capture_path.read_text(encoding="utf-8"))
        assert canonical_digest(capture) == row["capture_digest"]
        assert capture["capture_policy_ref"] == (
            "fin01.runtime.provider_interaction_audit_capture:v2"
        )
        assert capture["assistant_output_present"] is True
        assert capture["raw_request_envelope_included"] is False
        assert capture["raw_provider_response_included"] is False
        assert capture["private_reasoning_included"] is False
        assert capture["credentials_included"] is False


def test_result_contains_no_raw_output_or_business_promotion() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    serialized = json.dumps(result, ensure_ascii=False)
    assert "assistant_output_text" not in serialized
    assert "model_visible_request" not in serialized
    assert "raw_response" not in serialized
    assert result["paired_assessment_or_owner_acceptance"] is False
    assert result["next_action"] == (
        "S4-T06-MU-CHANGED-CONTRACT-FAMILY-SINGLE-NODE-NATURAL-OUTPUT-"
        "CANARIES-POST-RESULT-DISPOSITION-DECISION"
    )
