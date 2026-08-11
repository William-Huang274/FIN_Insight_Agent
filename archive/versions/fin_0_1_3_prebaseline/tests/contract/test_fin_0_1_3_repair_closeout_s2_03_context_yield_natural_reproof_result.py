from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_context_yield_program import validate_compact_provider_output


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_context_yield_natural_reproof_result_v1_0.json"
)
PROGRAM = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_context_yield_and_capacity_zero_call_v1_0.json"
)
ACTIVE = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_active_test_suite_successor_v1_1.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_result_is_digest_bound_and_closes_only_s2_03() -> None:
    result = _load(RESULT)
    body = {key: value for key, value in result.items() if key != "record_digest"}
    assert result["record_digest"] == canonical_digest(body)
    assert result["disposition"]["S2_03"] == "pass_closed"
    assert result["stage_boundary"]["S3_to_S5"] == "not_started"
    assert result["stage_boundary"]["eight_dimension_research_quality"] is False
    assert result["stage_boundary"]["full_chain_authorized"] is False


def test_natural_output_is_request_local_and_revalidates_compact_contract() -> None:
    result = _load(RESULT)
    program = _load(PROGRAM)
    compiled = next(
        row for row in program["role_scoped_contexts"] if row["request_id"] == result["request_id"]
    )
    output = result["natural_reproof"]["provider_output"]
    validate_compact_provider_output(output, compiled=compiled)
    assert result["request_id"] == "FIN013-S2-NVDA-demand_authenticity_and_sustainability"
    assert output["mechanism_alias"] == "NVDA_M_DURABILITY_REQUIRES_REPEAT_EVIDENCE"
    assert output["support_aliases"] == [f"NVDA_E0{i}" for i in range(1, 7)]
    assert set(output["what_would_change_aliases"]) == {
        "NVDA_W_REPEAT_DEPLOYMENT",
        "NVDA_W_DEMAND_DIGESTION",
    }


def test_exact_once_usage_and_capacity_are_preserved() -> None:
    result = _load(RESULT)
    natural = result["natural_reproof"]
    assert natural["status"] == "terminal_succeeded_exact_once"
    assert natural["finish_reason"] == "stop"
    assert natural["usage"] == {
        "input_tokens": 927,
        "output_tokens": 149,
        "total_tokens": 1076,
        "transport_attempt_count": 1,
    }
    assert natural["retry_count"] == natural["fallback_count"] == 0
    assert result["capacity"]["aggregate_character_reduction_ratio"] == 0.397684
    assert result["semantic_retention"]["evidence_alias_retention_ratio"] == 1.0


def test_public_result_and_active_suite_exclude_private_capture_refs() -> None:
    result = _load(RESULT)
    active = _load(ACTIVE)
    serialized = json.dumps({"result": result, "active": active}, ensure_ascii=False)
    for forbidden in (
        "data/workbench_private",
        '"capture_ref":',
        "Authorization",
        "Cookie",
        "C:\\Users\\",
    ):
        assert forbidden not in serialized
    active_body = {key: value for key, value in active.items() if key != "suite_digest"}
    assert active["suite_digest"] == canonical_digest(active_body)
    assert active["decision_sha256"] == hashlib.sha256(RESULT.read_bytes()).hexdigest()
    assert active["observed_result"] == "195 passed / 1 historical event-time assertion deselected"
