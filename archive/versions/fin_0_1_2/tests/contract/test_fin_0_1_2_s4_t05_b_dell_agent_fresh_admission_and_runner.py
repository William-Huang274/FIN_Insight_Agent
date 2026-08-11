from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "src"),
    str(ROOT / "tests" / "contract"),
]

from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentInputPack,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_b_agent_exact_execution import (
    Fin012S4T05BAgentExecutionError,
    prepare_t05_b_dell_agent_execution,
)
from scripts.releases.prepare_and_issue_fin_ia_0_1_2_s4_t05_b_dell_agent_fresh_exact_admission import (
    ADMISSION_REF,
    AGENT_INPUT_REF,
    DECISION_REF,
    EVIDENCE_PACK_REF,
    ISSUANCE_REF,
    _fake,
    build_proof,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (
    _principal,
)
from scripts.releases.run_fin_ia_0_1_2_s4_t05_b_dell_agent_exact_live import (
    EXECUTION_IDENTITY,
    execute_exact_once,
    load_exact_target,
    zero_call_preflight,
)
from sec_agent.canonical_runtime.models import canonical_digest


def _load(ref: Path) -> dict[str, object]:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def test_fresh_proof_admission_and_issuance_are_exact_and_capacity_bound() -> None:
    tracked_decision = _load(DECISION_REF)
    decision, admission, issuance = build_proof(
        recorded_at=str(tracked_decision["recorded_at"])
    )
    assert decision == tracked_decision
    assert admission == _load(ADMISSION_REF)
    assert issuance == _load(ISSUANCE_REF)
    assert decision["decision_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "decision_digest"}
    )
    assert issuance["issuance_digest"] == canonical_digest(
        {key: value for key, value in issuance.items() if key != "issuance_digest"}
    )
    assert decision["capacity_proof"]["aggregate_estimated_input_tokens"] == 86688
    assert decision["capacity_proof"]["maximum_input_tokens"] == 108000
    assert decision["capacity_proof"]["input_token_headroom"] == 21312
    assert decision["fresh_proof"]["topology_each"] == [9, 3, 9]
    assert issuance["issued_admission"]["consumed"] is False
    assert issuance["issued_admission"]["execution_started"] is False


def test_exact_runner_preflight_and_full_fake_reach_nine_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preflight = zero_call_preflight()
    assert preflight["status"] == (
        "pass_exact_input_admission_transport_wiring_zero_call"
    )
    assert preflight["execution_identity"] == EXECUTION_IDENTITY
    assert preflight["aggregate_estimated_input_tokens"] == 86688
    assert preflight["input_token_headroom"] == 21312
    assert preflight["provider_callback_calls"] == 0
    assert preflight["model_provider_network_calls"] == [0, 0, 0]

    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    runtime = tmp_path / "runtime"
    result = execute_exact_once(runtime, completion=_fake())
    assert result["status"] == "success"
    assert [
        len(result["capture_objects"]),
        len(result["terminal"]["local_fact_receipts"]),
        len(result["artifacts"]),
    ] == [9, 3, 9]
    assert result["business_promotable"] is True
    with pytest.raises(ValueError, match="runtime_identity_already_exists"):
        execute_exact_once(runtime, completion=_fake())


def test_agent_input_identity_mutation_fails_before_execution() -> None:
    _, _, input_pack, evidence_pack = load_exact_target()
    payload = input_pack.model_dump(mode="json")
    payload["case_id"] = "fin012-s4-t05-mu-current-evidence-mutated"
    payload["input_digest"] = canonical_digest(
        {key: value for key, value in payload.items() if key != "input_digest"}
    )
    changed = S3ThreeCellBoundedAgentInputPack.model_validate(payload)
    with pytest.raises(
        Fin012S4T05BAgentExecutionError,
        match="s4_t05_b_agent_exact_input_binding_invalid",
    ):
        prepare_t05_b_dell_agent_execution(
            changed,
            deepcopy(evidence_pack),
            principal=_principal(),
            execution_identity="mutation-must-fail",
        )
