from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
)
from scripts.releases.run_fin_ia_0_1_s2_t04_validate_live_artifacts import (
    T04ValidationError,
    validate_t04_artifacts,
)


RUN_ID = "run-t04-fixture"
ATTEMPT_ID = "attempt-t04-fixture"
INPUT_DIGEST = "d" * 64
CANDIDATE_ID = "candidate-t04-1"
RESULT_CONTRACT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s2_t04_live_artifact_validation_result_v1_0.json"
)


def _fixture_artifacts() -> dict[str, dict[str, Any]]:
    version_ids = {kind: f"artifact-{kind}:v1" for kind in BOUNDED_AGENT_ARTIFACT_TYPES}
    base: dict[str, dict[str, Any]] = {}
    for kind, version_id in version_ids.items():
        base[kind] = {
            "metadata": {
                "artifact_type": kind,
                "artifact_version_id": version_id,
                "producer_attempt_id": ATTEMPT_ID,
            },
            "payload": {
                "artifact_version_id": version_id,
                "research_run_id": RUN_ID,
                "artifact_manifest": version_ids,
            },
        }
    finding = {
        "candidate_id": CANDIDATE_ID,
        "supported_claim": "Reported-period demand is supported.",
        "boundary": "One filing period does not prove durability.",
    }
    specialist = {
        "thesis": "Reported-period demand is authentic.",
        "counter_thesis": "Durability remains uncertain.",
        "confidence": "medium",
        "evidence_findings": [finding],
        "unresolved_gaps": ["Cross-period durability is unresolved."],
    }
    lead = {
        "decision": "accept",
        "adjudicated_judgment": "Bounded judgment is suitable for internal review.",
        "confidence": "high",
        "evidence_refs": [CANDIDATE_ID],
        "remaining_gaps": ["Cross-period durability is unresolved."],
        "what_would_change": ["A later filing confirms durable conversion."],
    }
    base["bounded_agent_manifest"]["payload"].update(
        {
            "input_digest": INPUT_DIGEST,
            "observed_counts": {
                "model_calls": 4,
                "provider_calls": 4,
                "network_calls": 4,
                "source_network_calls": 0,
                "external_tool_calls": 0,
                "live_case_head_writes": 0,
                "evaluation_evidence_promotions": 1,
            },
            "hard_boundaries": {
                "candidate_is_evidence": 0,
                "graph_edge_is_evidence": 0,
                "writer_source_or_tool_calls": 0,
                "adapter_direct_canonical_writes": 0,
                "live_business_case_head_writes": 0,
                "release_admission": 0,
            },
        }
    )
    base["bounded_agent_evidence"]["payload"].update(
        {
            "status": "run_scoped_evaluation_evidence_version",
            "input_digest": INPUT_DIGEST,
            "candidate_refs": [CANDIDATE_ID],
            "findings": [finding],
            "live_evidence_head_promoted": False,
        }
    )
    base["bounded_agent_numeric"]["payload"].update(
        {
            "status": "typed_gap",
            "metric": "demand_sustainability",
            "value": None,
            "reason": "One cell cannot establish an exact metric.",
        }
    )
    base["bounded_agent_judgment"]["payload"].update(
        {"specialist_judgment": specialist, "lead_adjudication": lead}
    )
    base["bounded_agent_workpaper"]["payload"].update(
        {
            "evidence_ref": version_ids["bounded_agent_evidence"],
            "numeric_ref": version_ids["bounded_agent_numeric"],
            "judgment_ref": version_ids["bounded_agent_judgment"],
            "remaining_gaps": lead["remaining_gaps"],
        }
    )
    report = {
        "title_zh_cn": "需求真实性与持续性",
        "executive_summary_zh_cn": "需求真实，但持续性仍待验证。",
        "sections": [
            {
                "heading_zh_cn": "判断",
                "content_zh_cn": "报告期证据支持需求真实性。",
                "evidence_refs": [CANDIDATE_ID],
            }
        ],
        "limitations_zh_cn": ["单期证据不能证明长期持续性。"],
    }
    base["bounded_agent_report"]["payload"].update(
        {
            "mode": "model_no_source_internal_writer",
            "writer_source_calls": 0,
            "writer_tool_calls": 0,
            "report": report,
        }
    )
    base["bounded_agent_verification"]["payload"].update(
        {
            "deterministic_integrity": {
                "status": "pass",
                "exact_input_digest_bound": True,
                "evidence_refs_are_supplied_candidates": True,
                "writer_source_calls": 0,
                "writer_tool_calls": 0,
                "specialist_output_tool_calls": 0,
                "external_tool_executions": 0,
                "private_reasoning_persisted": False,
            },
            "semantic_fidelity": {"status": "pass", "score": 90, "issues": []},
            "financial_coherence": {"status": "pass", "score": 88, "issues": []},
            "visual_delivery": {
                "status": "pass",
                "title_present": True,
                "section_count": 1,
                "limitations_present": True,
            },
            "recommendation": "accept_for_internal_review",
        }
    )
    receipts = [
        {"stage": stage, "status": "ok", "transport_attempt_count": 1}
        for stage in (
            "bounded_specialist",
            "bounded_lead_adjudication",
            "bounded_writer_no_source",
            "bounded_semantic_financial_verifier",
        )
    ]
    base["bounded_agent_trace"]["payload"].update(
        {
            "input_digest": INPUT_DIGEST,
            "usage_receipts": receipts,
            "raw_provider_response_persisted": False,
            "private_reasoning_persisted": False,
            "specialist_external_tool_executed": False,
        }
    )
    base["agent_fallback_comparison"]["payload"].update(
        {
            "owner_review_status": "not_performed_in_t03",
            "material_gain_accepted": False,
        }
    )
    return base


def _validate(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return validate_t04_artifacts(
        artifacts,
        expected_input_digest=INPUT_DIGEST,
        expected_research_run_id=RUN_ID,
        expected_attempt_id=ATTEMPT_ID,
    )


def test_t04_accepts_exact_closed_live_artifact_shape() -> None:
    result = _validate(_fixture_artifacts())

    assert result["status"] == "pass"
    assert result["promotion"] == {
        "status": "pass_run_scoped_evaluation_evidence_version",
        "candidate_count": 1,
        "live_evidence_head_promoted": False,
    }
    assert result["numeric"]["status"] == "pass_typed_gap"
    assert result["four_layer_verifier"]["recommendation"] == (
        "accept_for_internal_review"
    )
    assert result["boundary"]["new_model_calls"] == 0
    assert result["boundary"]["T05_owner_review_performed"] is False


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda rows: rows["bounded_agent_evidence"]["payload"].update(
                {"live_evidence_head_promoted": True}
            ),
            "t04_live_evidence_head_promotion_forbidden",
        ),
        (
            lambda rows: rows["bounded_agent_numeric"]["payload"].update(
                {"value": 0.93}
            ),
            "t04_unsupported_numeric_precision_forbidden",
        ),
        (
            lambda rows: rows["bounded_agent_report"]["payload"]["report"][
                "sections"
            ][0].update({"evidence_refs": ["candidate-outside-promotion"]}),
            "t04_report_ref_outside_promoted_evidence",
        ),
        (
            lambda rows: rows["bounded_agent_verification"]["payload"][
                "financial_coherence"
            ].update({"status": "review_required"}),
            "t04_financial_verifier_failed",
        ),
    ],
)
def test_t04_fails_closed_on_promotion_numeric_writer_or_verifier_drift(
    mutate: Any, code: str
) -> None:
    artifacts = deepcopy(_fixture_artifacts())
    mutate(artifacts)

    with pytest.raises(T04ValidationError, match=code):
        _validate(artifacts)


def test_t04_result_contract_records_pass_without_claiming_t05() -> None:
    result = json.loads(RESULT_CONTRACT.read_text(encoding="utf-8"))

    assert result["status"] == "pass_read_only_exact_live_artifact_validation"
    assert result["validation"]["promotion"]["live_evidence_head_promoted"] is False
    assert result["validation"]["numeric"]["status"] == "pass_typed_gap"
    assert result["validation"]["four_layer_verifier"] == {
        "deterministic_integrity": "pass",
        "semantic_fidelity": "pass",
        "semantic_score": 100,
        "financial_coherence": "pass",
        "financial_score": 100,
        "visual_delivery": "pass",
        "recommendation": "accept_for_internal_review",
    }
    assert result["read_only_audit"]["new_model_calls"] == 0
    assert result["independent_review"]["T05_material_gain_or_owner_review_claimed"] is False
    assert result["stage_acceptance"]["S2_T04"] == "pass"
    assert result["stage_acceptance"]["S2_T05"] == (
        "ready_pending_separate_authorization"
    )
