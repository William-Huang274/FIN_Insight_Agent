from __future__ import annotations

from copy import deepcopy

import pytest

from sec_agent.research.multi_agent_report_authority import (
    MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
    MultiAgentReportAuthorityError,
    compile_multi_agent_report_authority_catalog,
    extend_multi_agent_report_authority_catalog,
    render_protected_report,
    validate_protected_report_draft,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.research.source_bound_numeric_authority import (
    SOURCE_BOUND_NUMERIC_REVIEW_SCHEMA_VERSION,
    SourceBoundNumericAuthorityError,
    compile_source_bound_numeric_authority_program,
)


def _fixtures(ticker: str = "DELL"):
    agent_id = "AGENT::DEMAND_QUALITY"
    evidence_ref = f"EV::{ticker}SOURCEBOUND01"
    numeric_ref = f"NUM::{ticker}ARCURRENT001"
    gap_ref = f"GAP::{ticker}SOURCEBOUND01"
    identity = {
        "case_key": ticker,
        "research_as_of": "2026-08-06",
        "subject_legal_name": f"{ticker} Holdings Inc.",
        "subject_ticker": ticker,
    }
    context_digest = canonical_digest({"ticker": ticker, "agent": agent_id})
    context = {
        "agent_id": agent_id,
        "context_digest": context_digest,
        "cell_analysis_view": {
            "case_identity": deepcopy(identity),
            "evidence_fact_catalog": [
                {
                    "evidence_ref": evidence_ref,
                    "evidence_owner_ticker": ticker,
                    "source_type": "EARNINGS_CALL_TRANSCRIPT",
                    "source_tier": "official_primary",
                    "publication_date": "2026-05-28",
                    "source_reporting_period_end": "2026-05-01",
                    "relationship_directions": ["subject_self_disclosure"],
                    "source_visible_fact_excerpt": (
                        "In the quarter, we booked $24.4 billion in AI orders and "
                        "our customer count surpassed 5,000. Guidance expected "
                        "between $44.0 billion and $45.0 billion."
                    ),
                }
            ],
            "numeric_fact_catalog": [
                {
                    "numeric_ref": numeric_ref,
                    "ticker": ticker,
                    "metric_id": "accounts_receivable",
                    "value_decimal": "25854000000",
                    "unit": "USD",
                    "period_start": None,
                    "period_end": "2026-05-01",
                    "fiscal_year": 2027,
                    "fiscal_period": "Q1",
                    "authority_mode": "source_bound_company_reported_numeric_fact",
                    "formula_trace": None,
                }
            ],
            "numeric_relation_catalog": [],
            "cell": {
                "cell_id": "CELL::demand",
                "residual_gap_cards": [
                    {
                        "gap_ref": gap_ref,
                        "gap_code": "conversion_bridge_not_disclosed",
                        "slot_id": "slot_demand",
                        "facet_id": "order_conversion",
                        "business_reason_zh": "缺少转化桥。",
                        "supplement_direction_zh": "继续查找发行人披露。",
                    }
                ],
            },
        },
    }
    workpaper = {
        "agent_id": agent_id,
        "context_digest": context_digest,
        "sourced_claims": [
            {
                "claim": (
                    "Orders were $24.4B, customer count exceeded 5,000, guidance "
                    "was $44.0B to $45.0B, and AR was $25,854M."
                ),
                "authority": "fact_supported",
                "evidence_refs": [evidence_ref],
                "numeric_refs": [],
                "numeric_relation_refs": [],
            }
        ],
        "remaining_gap_refs": [gap_ref],
    }
    workpaper["workpaper_digest"] = canonical_digest(workpaper)
    base = compile_multi_agent_report_authority_catalog(
        workpapers=[workpaper], specialist_contexts={agent_id: context}
    )
    claim_ref = base["claims"][0]["claim_ref"]
    review = {
        "schema_version": SOURCE_BOUND_NUMERIC_REVIEW_SCHEMA_VERSION,
        "status": "qualified_engineering_source_bound_numeric_review",
        "base_authority_catalog_digest": base["authority_catalog_digest"],
        "case_identity": deepcopy(identity),
        "decisions": [
            {
                "decision_id": "bind_current_ar",
                "decision": "bind_existing_numeric_fact",
                "claim_bindings": [
                    {"agent_id": agent_id, "claim_ref": claim_ref}
                ],
                "numeric_ref": numeric_ref,
                "claim_value_surface": "$25,854M",
                "reason_code": "typed_fact_was_visible_but_workpaper_ref_was_omitted",
            },
            {
                "decision_id": "admit_ai_orders",
                "decision": "admit_exact_numeric_fact",
                "claim_bindings": [
                    {"agent_id": agent_id, "claim_ref": claim_ref}
                ],
                "evidence_ref": evidence_ref,
                "source_quote": "we booked $24.4 billion in AI orders",
                "source_value_surfaces": ["$24.4 billion"],
                "semantic_metric_key": "ai_orders",
                "fact_status": "management_reported_actual",
                "value_kind": "exact_scalar",
                "unit": "USD",
                "source_scale": "",
                "period": {
                    "period_start": None,
                    "period_end": "2026-05-01",
                    "fiscal_year": 2027,
                    "fiscal_period": "Q1",
                    "period_role": "quarter_discrete",
                },
                "claim_boundary": "Orders are not revenue or cash.",
                "qualifier": "management-reported",
                "point_estimate_forbidden": False,
                "normalized_values": ["24400000000"],
            },
            {
                "decision_id": "admit_customer_threshold",
                "decision": "admit_bounded_presentation",
                "claim_bindings": [
                    {"agent_id": agent_id, "claim_ref": claim_ref}
                ],
                "evidence_ref": evidence_ref,
                "source_quote": "our customer count surpassed 5,000",
                "source_value_surfaces": ["5,000"],
                "semantic_metric_key": "ai_customer_count",
                "fact_status": "management_threshold",
                "value_kind": "greater_than",
                "unit": "count",
                "source_scale": "",
                "period": {
                    "period_start": None,
                    "period_end": "2026-05-01",
                    "fiscal_year": 2027,
                    "fiscal_period": "Q1",
                    "period_role": "instant",
                },
                "claim_boundary": "Customer count does not establish concentration.",
                "qualifier": "surpassed",
                "point_estimate_forbidden": True,
                "normalized_values": ["5000"],
            },
            {
                "decision_id": "admit_guidance_range",
                "decision": "admit_bounded_presentation",
                "claim_bindings": [
                    {"agent_id": agent_id, "claim_ref": claim_ref}
                ],
                "evidence_ref": evidence_ref,
                "source_quote": (
                    "Guidance expected between $44.0 billion and $45.0 billion"
                ),
                "source_value_surfaces": ["$44.0 billion", "$45.0 billion"],
                "semantic_metric_key": "revenue_guidance",
                "fact_status": "company_guidance",
                "value_kind": "closed_range",
                "unit": "USD",
                "source_scale": "",
                "period": {
                    "period_start": None,
                    "period_end": "2026-08-01",
                    "fiscal_year": 2027,
                    "fiscal_period": "Q2",
                    "period_role": "forward_guidance",
                },
                "claim_boundary": "Guidance is not a realized result.",
                "qualifier": "company guidance",
                "point_estimate_forbidden": True,
                "normalized_values": ["44000000000", "45000000000"],
            },
        ],
        "temporal_decisions": [
            {
                "decision_id": "bind_source_period_end",
                "decision": "admit_source_reporting_period_end",
                "claim_bindings": [
                    {"agent_id": agent_id, "claim_ref": claim_ref}
                ],
                "evidence_ref": evidence_ref,
                "date": "2026-05-01",
                "reason_code": "reviewed_source_period_is_material_to_the_claim",
            }
        ],
    }
    return base, {agent_id: context}, review, agent_id, claim_ref, gap_ref


def _payload(catalog, *, agent_id: str, claim_ref: str, gap_ref: str):
    claim = next(row for row in catalog["claims"] if row["claim_ref"] == claim_ref)
    refs = claim["authority_refs"]
    return {
        "schema_version": MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
        "report_topic": "Demand quality and value capture",
        "executive_thesis": [
            {
                "model_text": "Demand is substantial but conversion remains bounded.",
                "source_workpaper_agent_ids": [agent_id],
                "source_claim_refs": [claim_ref],
                "evidence_refs": claim["evidence_refs"],
                "authority_refs": refs,
                "gap_refs": [],
            }
        ],
        "sections": [
            {
                "heading": heading,
                "clauses": [
                    {
                        "model_text": "The disclosed stack requires distinct fact states.",
                        "source_workpaper_agent_ids": [agent_id],
                        "source_claim_refs": [claim_ref],
                        "evidence_refs": claim["evidence_refs"],
                        "authority_refs": [],
                        "gap_refs": [],
                    }
                ],
            }
            for heading in (
                "Demand perspective",
                "Conversion perspective",
                "Risk perspective",
                "Monitoring perspective",
            )
        ],
        "remaining_gaps": [
            {
                "model_text": "The direct conversion bridge remains unavailable.",
                "source_workpaper_agent_ids": [agent_id],
                "source_claim_refs": [],
                "evidence_refs": [],
                "authority_refs": [],
                "gap_refs": [gap_ref],
            }
        ],
        "what_would_change": [
            {
                "model_text": "A direct conversion bridge would narrow uncertainty.",
                "source_workpaper_agent_ids": [agent_id],
                "source_claim_refs": [claim_ref],
                "evidence_refs": [],
                "authority_refs": [],
                "gap_refs": [],
            },
            {
                "model_text": "A verified reversal in the disclosed demand would change the judgment.",
                "source_workpaper_agent_ids": [agent_id],
                "source_claim_refs": [claim_ref],
                "evidence_refs": [],
                "authority_refs": [],
                "gap_refs": [],
            },
        ],
        "confidence": {
            "model_text": "Confidence is moderate because attribution is incomplete.",
            "source_workpaper_agent_ids": [agent_id],
            "source_claim_refs": [claim_ref],
            "evidence_refs": [],
            "authority_refs": [],
            "gap_refs": [],
        },
    }


@pytest.mark.parametrize("ticker", ["DELL", "MU", "NVDA", "ORCL"])
def test_source_bound_program_is_case_neutral_and_renders_exact_bounded_and_temporal(
    ticker: str,
) -> None:
    base, contexts, review, agent_id, claim_ref, gap_ref = _fixtures(ticker)
    program = compile_source_bound_numeric_authority_program(
        authority_catalog=base,
        specialist_contexts=contexts,
        review=review,
    )
    extended = extend_multi_agent_report_authority_catalog(
        authority_catalog=base,
        source_bound_program=program,
    )
    payload = _payload(
        extended, agent_id=agent_id, claim_ref=claim_ref, gap_ref=gap_ref
    )
    trusted = validate_protected_report_draft(payload, authority_catalog=extended)
    rendered = render_protected_report(trusted, authority_catalog=extended)

    text = rendered["executive_thesis"]
    assert "$24.4B" in text
    assert "$25.854B" in text
    assert "more than 5,000" in text
    assert "$44B–$45B" in text
    assert "source reporting period ended 2026-05-01" in text
    assert extended["authority_boundary"][
        "source_presence_bypasses_typed_admission"
    ] is False
    assert program["coverage_receipt"][
        "admitted_exact_or_existing_numeric_count"
    ] == 2


def test_program_is_stable_under_decision_and_context_permutation() -> None:
    base, contexts, review, _, _, _ = _fixtures()
    first = compile_source_bound_numeric_authority_program(
        authority_catalog=base,
        specialist_contexts=contexts,
        review=review,
    )
    mutated = deepcopy(review)
    mutated["decisions"] = list(reversed(mutated["decisions"]))
    second = compile_source_bound_numeric_authority_program(
        authority_catalog=base,
        specialist_contexts=dict(reversed(list(contexts.items()))),
        review=mutated,
    )
    assert first["program_digest"] == second["program_digest"]


def test_source_value_mismatch_fails_closed() -> None:
    base, contexts, review, _, _, _ = _fixtures()
    mutated = deepcopy(review)
    mutated["decisions"][1]["normalized_values"] = ["2440000000"]
    with pytest.raises(
        SourceBoundNumericAuthorityError,
        match="source_bound_admission_surface_value_mismatch",
    ):
        compile_source_bound_numeric_authority_program(
            authority_catalog=base,
            specialist_contexts=contexts,
            review=mutated,
        )


def test_cross_claim_or_case_binding_fails_closed() -> None:
    base, contexts, review, _, _, _ = _fixtures()
    mutated = deepcopy(review)
    mutated["decisions"][1]["claim_bindings"][0]["agent_id"] = "AGENT::OTHER"
    with pytest.raises(
        SourceBoundNumericAuthorityError,
        match="source_bound_numeric_binding_agent_mismatch",
    ):
        compile_source_bound_numeric_authority_program(
            authority_catalog=base,
            specialist_contexts=contexts,
            review=mutated,
        )


def test_source_visible_number_not_in_review_never_enters_authority() -> None:
    base, contexts, review, _, _, _ = _fixtures()
    review["decisions"] = review["decisions"][:1]
    program = compile_source_bound_numeric_authority_program(
        authority_catalog=base,
        specialist_contexts=contexts,
        review=review,
    )
    extended = extend_multi_agent_report_authority_catalog(
        authority_catalog=base,
        source_bound_program=program,
    )
    surfaces = "\n".join(
        str(row["display_surface"]) for row in extended["presentation_authority"]
    )
    assert "$24.4B" not in surfaces
    assert "$44B" not in surfaces
    assert "5,000" not in surfaces


def test_raw_numeric_writer_prose_still_fails_after_extension() -> None:
    base, contexts, review, agent_id, claim_ref, gap_ref = _fixtures()
    program = compile_source_bound_numeric_authority_program(
        authority_catalog=base,
        specialist_contexts=contexts,
        review=review,
    )
    extended = extend_multi_agent_report_authority_catalog(
        authority_catalog=base,
        source_bound_program=program,
    )
    payload = _payload(
        extended, agent_id=agent_id, claim_ref=claim_ref, gap_ref=gap_ref
    )
    payload["executive_thesis"][0]["model_text"] += " Orders were $24.4B."
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_model_text_unprotected_surface",
    ):
        validate_protected_report_draft(payload, authority_catalog=extended)
