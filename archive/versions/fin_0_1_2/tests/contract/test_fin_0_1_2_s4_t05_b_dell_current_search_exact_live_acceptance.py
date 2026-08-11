from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RESULT = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_search_"
    "exact_live_result_and_acceptance_v1_0.json"
)
PROJECTION = Path(
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_54.json"
)
NEXT = (
    "FIN-0.1.2-S4-T05-B-DELL-CURRENT-EVIDENCE-PACK-AND-"
    "AGENT-EXACT-INPUT-COMPILATION"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def test_exact_live_result_preserves_search_only_success_truth() -> None:
    result = _json(RESULT)
    assert result["terminal"]["status"] == "success"
    assert result["terminal"]["code"] == (
        "three_request_current_evidence_candidate_pack_ready"
    )
    assert result["observed_counts"] == {
        "requests": 3,
        "source_calls": 1,
        "live_source_network_calls": 1,
        "local_retrieval_or_tool_invocations": 6,
        "fallbacks": 0,
        "same_target_retries": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "paid_api_cost_usd": 0.0,
        "accepted_candidates": 18,
        "rejected_candidates": 12,
        "business_artifacts": 0,
        "capture_objects": 8,
    }
    assert [
        (row["accepted"], row["rejected"]) for row in result["cell_results"]
    ] == [(6, 9), (6, 0), (6, 3)]
    assert result["source_acceptance"]["response_persisted_before_parse"] is True
    assert result["source_acceptance"][
        "credential_cookie_authorization_present"
    ] is False
    assert result["independent_acceptance"]["entity_exact_DELL"] is True
    assert result["independent_acceptance"]["writer_citable_in_search"] is False
    assert result["independent_acceptance"][
        "domain_judgment_eligible_in_search"
    ] is False
    assert result["stage_acceptance"]["DELL_current_R2"] is False
    assert result["next_action"] == NEXT


def test_projection_advances_only_to_evidence_and_agent_input_compilation() -> None:
    result = _json(RESULT)
    projection = _json(PROJECTION)
    acceptance = projection["T05_B_DELL_search_acceptance"]
    assert acceptance["result_ref"] == RESULT.as_posix()
    assert acceptance["result_sha256"] == _sha(RESULT)
    assert acceptance["terminal_digest"] == result["terminal"]["digest"]
    assert projection["current_truth"]["S4_T05_B_DELL_Search"] == (
        "pass_live_current_evidence_candidate_pack_ready"
    )
    assert projection["current_truth"]["S4_T05_B_DELL_Agent"] == "not_started"
    assert projection["current_truth"]["DELL_current_R2"] is False
    assert projection["acceptance_boundary"][
        "DELL_writer_citable_Evidence_promoted"
    ] is False
    assert projection["acceptance_boundary"][
        "DELL_Agent_admission_or_live_authorized"
    ] is False
    assert projection["current_truth"]["current_next_action"] == NEXT
