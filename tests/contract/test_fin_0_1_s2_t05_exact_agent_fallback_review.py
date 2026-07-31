from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "releases"))

from run_fin_ia_0_1_s2_t05_exact_agent_fallback_review import (
    T05ValidationError,
    assess_exact_pair,
)


AGENT_RUN_ID = "research_run_agent"
AGENT_ATTEMPT_ID = "attempt_agent"
BASELINE_RUN_ID = "research_run_baseline"
INPUT_DIGEST = "a" * 64
CANDIDATES = ["candidate-1", "candidate-2", "candidate-3"]


def _agent_artifacts() -> dict:
    manifest = {
        "bounded_agent_manifest": "artifact-manifest:v1",
        "bounded_agent_evidence": "artifact-evidence:v1",
        "bounded_agent_numeric": "artifact-numeric:v1",
        "bounded_agent_judgment": "artifact-judgment:v1",
        "bounded_agent_workpaper": "artifact-workpaper:v1",
        "bounded_agent_report": "artifact-report:v1",
        "bounded_agent_trace": "artifact-trace:v1",
        "bounded_agent_verification": "artifact-verification:v1",
        "agent_fallback_comparison": "artifact-comparison:v1",
    }
    baseline = {
        "run_kind": "deterministic_paired_baseline",
        "analysis_digest": "analysis-digest",
        "judgment": {
            "evidence_refs": CANDIDATES,
            "remaining_gaps": ["one broad gap"],
            "what_would_change_en": "one broad condition",
        },
        "workpaper_section": {"evidence_refs": CANDIDATES},
        "writer_sections": [{"content_zh_cn": "baseline"}],
        "observed_calls": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "external_tool_calls": 0,
        },
    }
    payloads = {
        "bounded_agent_manifest": {
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
        },
        "bounded_agent_evidence": {
            "input_digest": INPUT_DIGEST,
            "status": "run_scoped_evaluation_evidence_version",
            "live_evidence_head_promoted": False,
            "candidate_refs": CANDIDATES,
            "findings": [
                {
                    "candidate_id": ref,
                    "supported_claim": f"claim {ref}",
                    "boundary": "company filing boundary",
                }
                for ref in CANDIDATES
            ],
        },
        "bounded_agent_numeric": {
            "status": "typed_gap",
            "metric": "demand_sustainability",
            "value": None,
            "reason": "not supported",
        },
        "bounded_agent_judgment": {
            "specialist_judgment": {
                "thesis": "authentic but durability uncertain",
                "counter_thesis": "capacity, energy and supply constraints",
                "evidence_findings": [
                    {
                        "candidate_id": ref,
                        "supported_claim": f"claim {ref}",
                        "boundary": "company filing boundary",
                    }
                    for ref in CANDIDATES
                ],
            },
            "lead_adjudication": {
                "decision": "accept",
                "evidence_refs": CANDIDATES,
                "remaining_gaps": ["gap 1", "gap 2", "gap 3"],
                "what_would_change": ["wwc 1", "wwc 2", "wwc 3"],
            },
        },
        "bounded_agent_workpaper": {
            "evidence_ref": manifest["bounded_agent_evidence"],
            "numeric_ref": manifest["bounded_agent_numeric"],
            "judgment_ref": manifest["bounded_agent_judgment"],
            "remaining_gaps": ["gap 1", "gap 2", "gap 3"],
        },
        "bounded_agent_report": {
            "mode": "model_no_source_internal_writer",
            "writer_source_calls": 0,
            "writer_tool_calls": 0,
            "report": {
                "title_zh_cn": "title",
                "executive_summary_zh_cn": "summary",
                "sections": [
                    {
                        "heading_zh_cn": f"heading {i}",
                        "content_zh_cn": f"content {i}",
                        "evidence_refs": [CANDIDATES[i]],
                    }
                    for i in range(3)
                ],
                "limitations_zh_cn": ["limit 1", "limit 2", "limit 3"],
            },
        },
        "bounded_agent_trace": {
            "input_digest": INPUT_DIGEST,
            "raw_provider_response_persisted": False,
            "private_reasoning_persisted": False,
            "specialist_external_tool_executed": False,
            "usage_receipts": [
                {
                    "stage": stage,
                    "status": "ok",
                    "transport_attempt_count": 1,
                }
                for stage in (
                    "bounded_specialist",
                    "bounded_lead_adjudication",
                    "bounded_writer_no_source",
                    "bounded_semantic_financial_verifier",
                )
            ],
        },
        "bounded_agent_verification": {
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
            "semantic_fidelity": {"status": "pass", "score": 100, "issues": []},
            "financial_coherence": {"status": "pass", "score": 100, "issues": []},
            "visual_delivery": {
                "status": "pass",
                "title_present": True,
                "section_count": 3,
                "limitations_present": True,
            },
            "recommendation": "accept_for_internal_review",
        },
        "agent_fallback_comparison": {
            "paired_input_digest": INPUT_DIGEST,
            "runs_must_be_distinct": True,
            "deterministic_baseline": baseline,
            "owner_review_status": "not_performed_in_t03",
            "material_gain_accepted": False,
        },
    }
    result = {}
    for artifact_type, payload in payloads.items():
        payload.update(
            {
                "artifact_manifest": manifest,
                "artifact_version_id": manifest[artifact_type],
                "research_run_id": AGENT_RUN_ID,
            }
        )
        result[artifact_type] = {
            "metadata": {
                "artifact_type": artifact_type,
                "artifact_version_id": manifest[artifact_type],
                "producer_attempt_id": AGENT_ATTEMPT_ID,
            },
            "payload": payload,
        }
    return result


def _baseline() -> dict:
    embedded = _agent_artifacts()["agent_fallback_comparison"]["payload"][
        "deterministic_baseline"
    ]
    return {
        "run": {"research_run_id": BASELINE_RUN_ID},
        "artifact_metadata": {"artifact_version_id": "artifact-baseline:v1"},
        "artifact_payload": {"case_id": "case-1"},
        "input_pack": {"case_id": "case-1"},
        "reconstructed_baseline": embedded,
        "agent_artifacts_unchanged": True,
    }


def test_t05_exact_pair_yields_bounded_material_gain_candidate() -> None:
    result = assess_exact_pair(
        _agent_artifacts(),
        _baseline(),
        expected_agent_run_id=AGENT_RUN_ID,
        expected_agent_attempt_id=AGENT_ATTEMPT_ID,
        expected_input_digest=INPUT_DIGEST,
    )
    assert result["status"] == "technical_comparison_pass_owner_review_required"
    assert result["lineage"]["runs_are_distinct"] is True
    assert result["independent_product_review"]["disposition"] == "material_gain_candidate"
    assert result["owner_product_review"]["status"] == "awaiting_user_owner_decision"
    assert result["dimensions"]["numeric_bridge"]["result"].startswith("no_new_numeric_gain")


def test_t05_rejects_same_agent_and_baseline_run() -> None:
    baseline = _baseline()
    baseline["run"]["research_run_id"] = AGENT_RUN_ID
    with pytest.raises(
        T05ValidationError, match="t05_agent_and_baseline_runs_must_be_distinct"
    ):
        assess_exact_pair(
            _agent_artifacts(),
            baseline,
            expected_agent_run_id=AGENT_RUN_ID,
            expected_agent_attempt_id=AGENT_ATTEMPT_ID,
            expected_input_digest=INPUT_DIGEST,
        )


def test_t05_rejects_embedded_baseline_not_backed_by_canonical_run() -> None:
    baseline = _baseline()
    baseline["reconstructed_baseline"] = deepcopy(
        baseline["reconstructed_baseline"]
    )
    baseline["reconstructed_baseline"]["judgment"]["remaining_gaps"] = [
        "different baseline"
    ]
    with pytest.raises(
        T05ValidationError, match="t05_comparison_baseline_payload_mismatch"
    ):
        assess_exact_pair(
            _agent_artifacts(),
            baseline,
            expected_agent_run_id=AGENT_RUN_ID,
            expected_agent_attempt_id=AGENT_ATTEMPT_ID,
            expected_input_digest=INPUT_DIGEST,
        )
