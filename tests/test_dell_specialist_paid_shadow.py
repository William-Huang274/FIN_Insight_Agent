from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
    canonical_sha256,
)
from sec_agent.agent_runtime.dell_specialist_paid_shadow import (
    DellQ1SpecialistPaidShadowAuthority,
    DellSpecialistPaidShadowError,
    build_public_model_audit_sink,
    require_runtime_authority_binding,
)


def _authority(tmp_path: Path) -> DellQ1SpecialistPaidShadowAuthority:
    execution_id = "20260904-dell-q1-specialist-paid-shadow-r1"
    body: dict[str, Any] = {
        "schema_version": (
            "fin_ia_dell_q1_specialist_paid_shadow_authority_v1_0"
        ),
        "decision_id": "decision:q1-paid-shadow-r1",
        "decision_status": "authorized_once",
        "qualification_only": True,
        "paid_full_chain_execution_id": execution_id,
        "agent_session_id": "session:q1-paid-shadow-r1",
        "fin_thread_id": "thread:q1-paid-shadow-r1",
        "research_run_id": "run:q1-paid-shadow-r1",
        "run_invocation_id": "invocation:q1-paid-shadow-r1",
        "graph_id": "dell_reference_vertical",
        "serving_mode": "q1_specialist_paid_shadow_v1",
        "branch_id": "Q1_ISSUER_TRUTH",
        "node_id": "specialist:Q1_ISSUER_TRUTH",
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "research_as_of": "2026-09-02T00:00:00Z",
        "implementation_commit": "a" * 40,
        "deepseek_config_sha256": "b" * 64,
        "owner_data_gate_decision_digest": "c" * 64,
        "inventory_snapshot_digest": "d" * 64,
        "source_route_catalog_digest": "e" * 64,
        "max_model_turns": 8,
        "max_tool_actions": 12,
        "max_input_characters_per_turn": 160_000,
        "max_output_tokens_per_turn": 10_000,
        "timeout_seconds_per_turn": 240.0,
        "max_transport_attempts_per_turn": 1,
        "retry_policy": "none",
        "fallback_policy": "none",
        "truncation_behavior": "fail_closed_no_partial_promotion",
        "unknown_outcome_behavior": "stop_and_require_human_review",
        "node_purpose": "Run exactly one bounded Q1 Specialist research shadow.",
        "input_scale_basis": "Three replay turns remained below the configured input ceiling.",
        "required_outputs": (
            "one legal action",
            "one terminal workpaper or stop",
        ),
        "schema_burden": "One closed action union is validated on every provider turn.",
        "materiality_quality_risk": "Wrong sources or periods must fail before acceptance.",
        "comparable_run_evidence": "A three-turn zero-transport replay used the same graph and tools.",
        "reasoning_profile": "Thinking disabled and one structured action returned per turn.",
        "cost_and_latency_estimate": "Expected three to five turns; eight is the anomaly ceiling.",
        "live_external_calls_authorized": False,
        "evidence_admission_authorized": False,
        "s2_write_authorized": False,
        "other_model_nodes_authorized": False,
        "artifact_root_container": (
            f"/run/fin-insight/paid-shadow/{execution_id}"
        ),
        "model_audit_filename": "model-call-events.jsonl",
    }
    return DellQ1SpecialistPaidShadowAuthority.model_validate(
        {**body, "decision_digest": canonical_sha256(body)}
    )


def test_authority_binds_exact_runtime_identity_and_research_snapshot(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)

    require_runtime_authority_binding(
        authority,
        agent_session_id=authority.agent_session_id,
        research_run_id=authority.research_run_id,
        run_invocation_id=authority.run_invocation_id,
        implementation_commit=authority.implementation_commit,
    )
    assert authority.research_as_of == "2026-09-02T00:00:00Z"

    with pytest.raises(
        DellSpecialistPaidShadowError,
        match="paid_shadow_runtime_authority_binding_invalid",
    ):
        require_runtime_authority_binding(
            authority,
            agent_session_id="session:wrong",
            research_run_id=authority.research_run_id,
            run_invocation_id=authority.run_invocation_id,
            implementation_commit=authority.implementation_commit,
        )


def test_authority_rejects_artifact_root_not_bound_to_execution(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)
    body = authority.model_dump(mode="json", exclude={"decision_digest"})
    body["artifact_root_container"] = (
        "/run/fin-insight/paid-shadow/a-different-execution"
    )

    with pytest.raises(ValidationError, match="artifact_execution_binding"):
        DellQ1SpecialistPaidShadowAuthority.model_validate_json(
            json.dumps(
                {**body, "decision_digest": canonical_sha256(body)},
                ensure_ascii=False,
            )
        )


def test_public_audit_persists_digests_and_rejects_private_payloads(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path).model_copy(
        update={
            "artifact_root_container": str(
                tmp_path / "paid-shadow" / "20260904-dell-q1-specialist-paid-shadow-r1"
            )
        }
    )
    # model_copy intentionally bypasses the container-path validator for this local sink test.
    sink = build_public_model_audit_sink(authority)
    sink(
        {
            "schema_version": "fin_ia_model_call_audit_event_v1_0",
            "event": "outcome",
            "status": "success",
            "action_digest": "f" * 64,
        }
    )

    audit_path = Path(authority.artifact_root_container) / authority.model_audit_filename
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["paid_execution_id"] == authority.paid_full_chain_execution_id
    assert rows[0]["authority_decision_digest"] == authority.decision_digest
    assert rows[0]["audit_event_digest"] == canonical_sha256(
        {key: value for key, value in rows[0].items() if key != "audit_event_digest"}
    )

    with pytest.raises(
        DellSpecialistPaidShadowError,
        match="paid_shadow_private_model_payload_forbidden",
    ):
        sink({"event": "outcome", "nested": {"raw_response": "private"}})
