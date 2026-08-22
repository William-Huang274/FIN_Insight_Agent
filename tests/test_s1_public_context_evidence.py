from __future__ import annotations

from copy import deepcopy

import pytest

from retrieval.public_context_evidence import (
    PUBLIC_CONTEXT_EVIDENCE_PLAN_SCHEMA_VERSION,
    PublicContextEvidenceError,
    adjudicate_public_context_evidence,
)
from retrieval.public_context_source import (
    PUBLIC_CONTEXT_CANDIDATE_SCHEMA_VERSION,
    PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest


def _fixture() -> tuple[dict, dict]:
    source_body = {
        "schema_version": PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION,
        "status": "captured_public_source_compiled_not_evidence",
        "source_id": "PUBLIC::MSFT::TEST",
        "case_key": "DELL",
        "speaker_entity": "Microsoft Corporation",
        "speaker_ticker": "MSFT",
        "source_class": "named_counterparty_or_standards_primary",
        "source_role": "hyperscaler_demand_primary_context",
        "source_type": "EARNINGS_CALL_TRANSCRIPT",
        "relationship_directions": ["hyperscaler_demand_to_target_context"],
        "publication_date": "2026-04-29",
        "research_as_of": "2026-08-06",
        "source_url": "https://example.test/msft",
        "capture_ref": "private/msft.json",
        "capture_sha256": "a" * 64,
        "body_sha256": "b" * 64,
        "segments": [],
        "authority": {"candidate_not_evidence": True},
    }
    source = {**source_body, "source_object_digest": canonical_digest(source_body)}
    use_body = {
        "schema_version": "fin_ia_s1_source_claim_use_decision_v1_0",
        "policy_id": "POLICY",
        "source_class": source["source_class"],
        "claim_use": "speaker_attributed_mechanism",
        "customer_use_mode": "exact_fact_and_citation",
        "internalization_mode": "versioned_source_object",
        "target_company_exact_numeric_fact_allowed": False,
        "disposition": "admit_as_exact_or_speaker_attributed_candidate",
        "blockers": [],
        "evidence_promotion_allowed": True,
        "source_strength_is_not_claim_truth": True,
        "ranking_score_is_not_evidence_authority": True,
    }
    use = {**use_body, "decision_digest": canonical_digest(use_body)}
    candidate_body = {
        "schema_version": PUBLIC_CONTEXT_CANDIDATE_SCHEMA_VERSION,
        "candidate_id": "PUBCAND::TEST",
        "case_key": "DELL",
        "source_id": source["source_id"],
        "source_object_digest": source["source_object_digest"],
        "proposition_id": "PROP::DELL::HYPERSCALER_DEMAND",
        "excerpt": "We are adding capacity aligned to demand signals.",
        "excerpt_digest": canonical_digest(
            "We are adding capacity aligned to demand signals."
        ),
        "segment_ids": ["SEG-1"],
        "speaker_entity": source["speaker_entity"],
        "source_class": source["source_class"],
        "source_role": source["source_role"],
        "publication_date": source["publication_date"],
        "relationship_directions": source["relationship_directions"],
        "claim_use": "speaker_attributed_mechanism",
        "source_use_decision": use,
        "candidate_not_evidence": True,
        "evidence_admission_required": True,
        "target_company_exact_numeric_authority": False,
    }
    candidate = {
        **candidate_body,
        "candidate_digest": canonical_digest(candidate_body),
    }
    compiled_body = {
        "schema_version": "fin_ia_s1_public_context_admission_result_v1_0",
        "status": "public_context_candidates_compiled_evidence_admission_pending",
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "source_objects": [source],
        "candidates": [candidate],
    }
    compiled = {
        **compiled_body,
        "result_digest": canonical_digest(compiled_body),
    }
    plan_body = {
        "schema_version": PUBLIC_CONTEXT_EVIDENCE_PLAN_SCHEMA_VERSION,
        "status": "approved_internal_engineering_adjudication",
        "plan_id": "PLAN-1",
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "compiled_result_digest": compiled["result_digest"],
        "qualified_human_review": False,
        "S1_qualification_authorized": False,
        "product_publication_authorized": False,
        "decisions": [
            {
                "candidate_id": candidate["candidate_id"],
                "candidate_digest": candidate["candidate_digest"],
                "source_object_digest": source["source_object_digest"],
                "proposition_id": candidate["proposition_id"],
                "action": "accept_as_bounded_context",
                "slot_bindings": [
                    {
                        "slot_id": "demand_volume_quality",
                        "facet_ids": ["hyperscaler_demand_signal"],
                        "requirement_ids": [],
                        "business_meaning_zh": "客户侧需求语境。",
                        "claim_boundary_zh": "不证明 Dell 订单。",
                    }
                ],
                "gap_ids_narrowed": [],
                "gap_ids_satisfied": [],
                "numeric_use_boundary_zh": "不授予 Dell 数字权威。",
                "causal_attribution_authorized": False,
            }
        ],
    }
    return compiled, {**plan_body, "plan_digest": canonical_digest(plan_body)}


def test_public_context_evidence_preserves_speaker_and_target_boundary() -> None:
    compiled, plan = _fixture()

    result = adjudicate_public_context_evidence(
        compiled_result=compiled,
        plan=plan,
    )

    assert result["evidence_qualified"] is True
    assert result["gap_ids_satisfied"] == []
    assert len(result["accepted_evidence_items"]) == 1
    item = result["accepted_evidence_items"][0]
    assert item["case_key"] == "DELL"
    assert item["speaker_entity"] == "Microsoft Corporation"
    assert item["disposition"] == "accepted_bounded_context_evidence"
    assert item["evidence_role"] == "counterparty_or_ecosystem_readthrough"
    assert item["causal_attribution_authorized"] is False
    assert result["source_materials"][0]["evidence_owner_ticker"] == "MSFT"
    assert result["authority"]["target_company_exact_numeric_authority"] is False


def test_public_context_cannot_close_dell_gap() -> None:
    compiled, plan = _fixture()
    mutated = deepcopy(plan)
    mutated["decisions"][0]["gap_ids_satisfied"] = ["dell-gap-pricing-asp"]
    unsigned = dict(mutated)
    unsigned.pop("plan_digest")
    mutated["plan_digest"] = canonical_digest(unsigned)

    with pytest.raises(
        PublicContextEvidenceError,
        match="public_context_evidence_target_gap_closure_forbidden",
    ):
        adjudicate_public_context_evidence(
            compiled_result=compiled,
            plan=mutated,
        )
