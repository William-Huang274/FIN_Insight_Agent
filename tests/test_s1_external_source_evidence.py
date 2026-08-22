from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from retrieval.external_source_evidence import (
    EXTERNAL_SOURCE_EVIDENCE_PLAN_SCHEMA_VERSION,
    EXTERNAL_SOURCE_REVIEW_PLAN_SCHEMA_VERSION,
    ExternalSourceEvidenceError,
    adjudicate_external_source_evidence,
    compile_external_source_candidate_review,
)
from retrieval.public_context_source import PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION
from retrieval.query_plan import canonical_digest
from retrieval.source_use_policy import SourceUsePolicy


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "configs/retrieval/fin_ia_0_1_3_s1_source_strength_and_claim_use_policy_v1_0.json"


def _policy() -> SourceUsePolicy:
    return SourceUsePolicy.from_mapping(json.loads(POLICY.read_text(encoding="utf-8")))


def _source(
    *,
    source_id: str,
    speaker: str,
    ticker: str | None,
    source_class: str,
    url: str,
    text: str,
) -> dict:
    body = {
        "schema_version": PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION,
        "status": "captured_public_source_compiled_not_evidence",
        "source_id": source_id,
        "case_key": "DELL",
        "speaker_entity": speaker,
        "speaker_ticker": ticker,
        "source_class": source_class,
        "source_role": "review_fixture",
        "source_type": "PUBLIC_WEB",
        "relationship_directions": ["speaker_to_dell_context"],
        "publication_date": "2026-03-01",
        "research_as_of": "2026-08-06",
        "source_url": url,
        "title": "review fixture",
        "capture_ref": "private/capture.json",
        "capture_sha256": "a" * 64,
        "body_sha256": "b" * 64,
        "segments": [
            {
                "segment_id": "SEG::" + canonical_digest(text)[:12],
                "segment_index": 1,
                "text": text,
                "text_digest": canonical_digest(text),
                "candidate_not_evidence": True,
                "numeric_authority": False,
            }
        ],
        "authority": {
            "candidate_not_evidence": True,
            "source_strength_does_not_prove_claim": True,
            "speaker_is_not_target_company_unless_identity_matches": True,
            "exact_target_numeric_authority": False,
        },
    }
    return {**body, "source_object_digest": canonical_digest(body)}


def _proposal(*, source: dict, proposition: str, excerpt: str) -> dict:
    body = {
        "source_id": source["source_id"],
        "source_object_digest": source["source_object_digest"],
        "segment_id": source["segments"][0]["segment_id"],
        "proposition_id": proposition,
        "query_unit_id": "QUERY::" + proposition,
        "query_tier_id": "official",
        "expected_output_ids": ["expected"],
        "excerpt": excerpt,
        "scope_anchor_hits": ["dell"],
        "material_signal_hits": ["server"],
        "query_term_overlap": ["dell", "server"],
        "deterministic_locator_relevance": 5.0,
        "selection_method": "fixture",
        "candidate_not_evidence": True,
        "candidate_decision_required": True,
    }
    return {**body, "candidate_proposal_digest": canonical_digest(body)}


def _terminal(sources: list[dict], proposals: list[dict]) -> dict:
    body = {
        "schema_version": "fin_ia_s1_dell_external_source_ladder_private_result_v1_1",
        "status": "dell_external_source_ladder_exact_once_complete",
        "original_compilation_result": {
            "source_objects": sources,
            "candidate_proposals": proposals,
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


def _review_fixture() -> tuple[dict, dict]:
    issuer_text = (
        "Dell PowerEdge XE9680L integrated racks support up to 96 GPUs per rack."
    )
    market_text = (
        "Industry AI server shipments are forecast to grow, but this does not "
        "establish Dell unit volume."
    )
    issuer = _source(
        source_id="SOURCE::DELL",
        speaker="Dell Technologies Inc.",
        ticker="DELL",
        source_class="issuer_regulator_or_government_primary",
        url="https://www.dell.com/example",
        text=issuer_text,
    )
    market = _source(
        source_id="SOURCE::MARKET",
        speaker="Industry Tracker",
        ticker=None,
        source_class="official_market_or_industry_primary",
        url="https://tracker.example.org/report",
        text=market_text,
    )
    issuer_proposal = _proposal(
        source=issuer,
        proposition="DELL-PROP-PRICE-CONFIGURATION",
        excerpt=issuer_text,
    )
    market_proposal = _proposal(
        source=market,
        proposition="DELL-PROP-UNIT-VOLUME",
        excerpt=market_text,
    )
    terminal = _terminal([issuer, market], [issuer_proposal, market_proposal])
    plan_body = {
        "schema_version": EXTERNAL_SOURCE_REVIEW_PLAN_SCHEMA_VERSION,
        "status": "approved_internal_engineering_candidate_review",
        "plan_id": "REVIEW-1",
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "ladder_terminal_result_digest": terminal["result_digest"],
        "original_proposal_dispositions": [
            {
                "candidate_proposal_digest": issuer_proposal[
                    "candidate_proposal_digest"
                ],
                "action": "accept_as_reviewed_candidate",
                "review_candidate_key": "dell-config",
                "reason_zh": "发行人直接产品配置。",
            },
            {
                "candidate_proposal_digest": market_proposal[
                    "candidate_proposal_digest"
                ],
                "action": "accept_as_reviewed_candidate",
                "review_candidate_key": "market-volume",
                "reason_zh": "行业销量语境。",
            },
        ],
        "reviewed_candidate_specs": [
            {
                "review_candidate_key": "dell-config",
                "source_id": issuer["source_id"],
                "proposition_id": issuer_proposal["proposition_id"],
                "excerpt_source_kind": "original_proposal",
                "origin_candidate_proposal_digests": [
                    issuer_proposal["candidate_proposal_digest"]
                ],
                "claim_use": "target_company_exact_fact",
                "speaker_bound": True,
                "subject_bound": True,
                "corroborating_source_ids": [],
                "business_reason_zh": "保留 Dell 自己披露的产品配置。",
            },
            {
                "review_candidate_key": "market-volume",
                "source_id": market["source_id"],
                "proposition_id": market_proposal["proposition_id"],
                "excerpt_source_kind": "original_proposal",
                "origin_candidate_proposal_digests": [
                    market_proposal["candidate_proposal_digest"]
                ],
                "claim_use": "industry_exact_fact",
                "speaker_bound": True,
                "subject_bound": True,
                "corroborating_source_ids": [],
                "business_reason_zh": "保留行业出货语境但不归因给 Dell。",
            },
        ],
    }
    return terminal, {**plan_body, "plan_digest": canonical_digest(plan_body)}


def _evidence_plan(compiled: dict) -> dict:
    decisions = []
    for candidate in compiled["candidates"]:
        direct = candidate["claim_use"] == "target_company_exact_fact"
        decisions.append(
            {
                "candidate_id": candidate["candidate_id"],
                "candidate_digest": candidate["candidate_digest"],
                "source_object_digest": candidate["source_object_digest"],
                "proposition_id": candidate["proposition_id"],
                "action": "accept_as_evidence",
                "slot_bindings": [
                    {
                        "slot_id": (
                            "pricing_mix_value_capture"
                            if direct
                            else "demand_volume_quality"
                        ),
                        "facet_ids": ["configuration" if direct else "industry_units"],
                        "requirement_ids": [],
                        "business_meaning_zh": "可用于当前研究命题。",
                        "claim_boundary_zh": (
                            "只证明 Dell 产品配置。"
                            if direct
                            else "只证明行业语境，不证明 Dell 单位量。"
                        ),
                    }
                ],
                "gap_ids_narrowed": [],
                "gap_ids_satisfied": [],
                "numeric_use_boundary_zh": "不生成新的 NumericFact。",
                "causal_attribution_authorized": False,
            }
        )
    body = {
        "schema_version": EXTERNAL_SOURCE_EVIDENCE_PLAN_SCHEMA_VERSION,
        "status": "approved_internal_engineering_evidence_gate",
        "plan_id": "EVIDENCE-1",
        "case_key": "DELL",
        "research_as_of": "2026-08-06",
        "compiled_result_digest": compiled["result_digest"],
        "qualified_human_review": False,
        "S1_qualification_authorized": False,
        "product_publication_authorized": False,
        "decisions": decisions,
    }
    return {**body, "plan_digest": canonical_digest(body)}


def test_external_review_and_gate_preserve_direct_and_context_roles() -> None:
    terminal, review_plan = _review_fixture()
    compiled = compile_external_source_candidate_review(
        ladder_terminal=terminal,
        plan=review_plan,
        source_use_policy=_policy(),
    )
    evidence = adjudicate_external_source_evidence(
        compiled_result=compiled,
        plan=_evidence_plan(compiled),
    )

    assert compiled["summary"]["original_proposal_count"] == 2
    assert compiled["summary"]["candidate_evidence_promotions"] == 0
    assert {row["disposition"] for row in evidence["accepted_evidence_items"]} == {
        "accepted_direct_source_evidence",
        "accepted_bounded_context_evidence",
    }
    direct = next(
        row
        for row in evidence["accepted_evidence_items"]
        if row["disposition"] == "accepted_direct_source_evidence"
    )
    assert direct["evidence_role"] == "issuer_direct_source"
    assert direct["target_company_exact_numeric_authority"] is False
    bounded = next(
        row
        for row in evidence["accepted_evidence_items"]
        if row["disposition"] == "accepted_bounded_context_evidence"
    )
    assert bounded["evidence_role"] == "counterparty_or_ecosystem_readthrough"


def test_external_review_requires_every_original_proposal_disposition() -> None:
    terminal, plan = _review_fixture()
    mutated = deepcopy(plan)
    mutated.pop("plan_digest")
    mutated["original_proposal_dispositions"].pop()
    mutated["plan_digest"] = canonical_digest(mutated)

    with pytest.raises(
        ExternalSourceEvidenceError,
        match="external_source_review_proposal_disposition_coverage_invalid",
    ):
        compile_external_source_candidate_review(
            ladder_terminal=terminal,
            plan=mutated,
            source_use_policy=_policy(),
        )


def test_external_review_accepts_digest_bound_capture_replay_terminal() -> None:
    terminal, plan = _review_fixture()
    replay_body = dict(terminal)
    replay_body.pop("result_digest")
    replay_body["schema_version"] = (
        "fin_ia_s1_dell_external_capture_replay_private_result_v1_0"
    )
    replay_body["status"] = "dell_external_capture_replay_complete"
    replay = {**replay_body, "result_digest": canonical_digest(replay_body)}
    rebound = deepcopy(plan)
    rebound.pop("plan_digest")
    rebound["ladder_terminal_result_digest"] = replay["result_digest"]
    rebound["plan_digest"] = canonical_digest(rebound)

    compiled = compile_external_source_candidate_review(
        ladder_terminal=replay,
        plan=rebound,
        source_use_policy=_policy(),
    )

    assert compiled["summary"]["original_proposal_count"] == 2
    assert compiled["ladder_terminal_result_digest"] == replay["result_digest"]


def test_external_evidence_cannot_close_gap_without_separate_receipt() -> None:
    terminal, review_plan = _review_fixture()
    compiled = compile_external_source_candidate_review(
        ladder_terminal=terminal,
        plan=review_plan,
        source_use_policy=_policy(),
    )
    plan = _evidence_plan(compiled)
    mutated = deepcopy(plan)
    mutated.pop("plan_digest")
    mutated["decisions"][0]["gap_ids_satisfied"] = ["dell-gap-pricing-asp"]
    mutated["plan_digest"] = canonical_digest(mutated)

    with pytest.raises(
        ExternalSourceEvidenceError,
        match="external_source_evidence_gap_closure_requires_separate_receipt",
    ):
        adjudicate_external_source_evidence(
            compiled_result=compiled,
            plan=mutated,
        )
