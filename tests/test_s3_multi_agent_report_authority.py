from __future__ import annotations

from copy import deepcopy

import pytest

from sec_agent.research.multi_agent_report_authority import (
    MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
    MultiAgentReportAuthorityError,
    audit_legacy_report_protected_surfaces,
    compile_multi_agent_report_authority_catalog,
    protected_report_draft_tool,
    render_protected_report,
    validate_protected_report_draft,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest


def _fixtures(ticker: str = "DELL"):
    identity = {
        "case_key": ticker,
        "research_as_of": "2026-08-06",
        "subject_legal_name": f"{ticker} Holdings Inc.",
        "subject_ticker": ticker,
    }
    agents = [f"AGENT::ROLE_{letter}" for letter in "ABCD"]
    workpapers = []
    contexts = {}
    for index, agent_id in enumerate(agents, start=1):
        evidence_ref = f"EV::{ticker}{index:014d}"
        gap_ref = f"GAP::{ticker}{index:013d}"
        numeric_ref = f"NUM::{ticker}{index:013d}" if index == 1 else ""
        relation_ref = f"REL::{ticker}{index:013d}" if index == 1 else ""
        context_digest = canonical_digest(
            {"ticker": ticker, "agent_id": agent_id, "index": index}
        )
        numeric_catalog = []
        relation_catalog = []
        if numeric_ref:
            numeric_catalog.append(
                {
                    "numeric_ref": numeric_ref,
                    "ticker": ticker,
                    "metric_id": "revenue",
                    "value_decimal": "43842000000",
                    "unit": "USD",
                    "period_start": "2026-02-01",
                    "period_end": "2026-05-01",
                    "fiscal_year": 2027,
                    "fiscal_period": "Q1",
                    "authority_mode": "reported_exact",
                    "formula_trace": None,
                }
            )
            numeric_catalog.append(
                {
                    "numeric_ref": f"NUM::{ticker}PRIOR00000001",
                    "ticker": ticker,
                    "metric_id": "revenue",
                    "value_decimal": "23378000000",
                    "unit": "USD",
                    "period_start": "2025-02-01",
                    "period_end": "2025-05-02",
                    "fiscal_year": 2026,
                    "fiscal_period": "Q1",
                    "authority_mode": "reported_exact",
                    "formula_trace": None,
                }
            )
            relation_catalog.append(
                {
                    "numeric_relation_ref": relation_ref,
                    "ticker": ticker,
                    "metric_id": "revenue",
                    "current_numeric_ref": numeric_ref,
                    "comparison_numeric_ref": f"NUM::{ticker}PRIOR00000001",
                    "current_period_end": "2026-05-01",
                    "comparison_period_end": "2025-05-02",
                    "fiscal_period": "Q1",
                    "relation_type": "year_over_year",
                    "direction": "increase",
                    "unit": "USD",
                    "absolute_change_decimal": "20464000000",
                    "percent_change_decimal": "87.5352895885",
                    "percentage_point_change_decimal": None,
                    "authority_mode": "deterministic_relation",
                }
            )
        contexts[agent_id] = {
            "agent_id": agent_id,
            "context_digest": context_digest,
            "cell_analysis_view": {
                "case_identity": deepcopy(identity),
                "evidence_fact_catalog": [
                    {
                        "evidence_ref": evidence_ref,
                        "evidence_owner_ticker": ticker,
                        "source_type": "10-Q",
                        "source_tier": "official_primary",
                        "publication_date": "2026-05-28",
                        "source_reporting_period_end": "2026-05-01",
                        "relationship_directions": ["subject_self_disclosure"],
                        "source_visible_fact_excerpt": (
                            "A source-visible amount of $99B is deliberately not "
                            "typed and must not become output authority."
                        ),
                    }
                ],
                "numeric_fact_catalog": numeric_catalog,
                "numeric_relation_catalog": relation_catalog,
                "cell": {
                    "cell_id": f"CELL::{index}",
                    "residual_gap_cards": [
                        {
                            "gap_ref": gap_ref,
                            "gap_code": "metric_not_disclosed",
                            "slot_id": f"slot_{index}",
                            "facet_id": f"facet_{index}",
                            "business_reason_zh": "缺少直接披露。",
                            "supplement_direction_zh": "继续查找官方资料。",
                        }
                    ],
                },
            },
        }
        claim = {
            "claim": "Observed evidence supports a bounded research statement.",
            "authority": "fact_supported",
            "evidence_refs": [evidence_ref],
            "numeric_refs": [numeric_ref] if numeric_ref else [],
            "numeric_relation_refs": [relation_ref] if relation_ref else [],
        }
        workpaper = {
            "agent_id": agent_id,
            "context_digest": context_digest,
            "sourced_claims": [claim],
            "remaining_gap_refs": [gap_ref],
        }
        workpaper["workpaper_digest"] = canonical_digest(workpaper)
        workpapers.append(workpaper)
    return workpapers, contexts


def _clause(
    *,
    agent_id: str,
    claim_ref: str = "",
    evidence_ref: str = "",
    authority_ref: str = "",
    gap_ref: str = "",
    text: str = "The evidence supports a bounded conclusion with material uncertainty.",
):
    return {
        "model_text": text,
        "source_workpaper_agent_ids": [agent_id],
        "source_claim_refs": [claim_ref] if claim_ref else [],
        "evidence_refs": [evidence_ref] if evidence_ref else [],
        "authority_refs": [authority_ref] if authority_ref else [],
        "gap_refs": [gap_ref] if gap_ref else [],
    }


def _payload(catalog):
    claims = catalog["claims"]
    by_agent = {row["agent_id"]: row for row in claims}
    agents = sorted(by_agent)
    first = by_agent[agents[0]]
    first_gap = next(
        row["gap_refs"][0]
        for row in catalog["workpaper_gap_bindings"]
        if row["agent_id"] == agents[0]
    )
    authority_ref = catalog["presentation_authority"][0]["authority_ref"]
    executive = _clause(
        agent_id=agents[0],
        claim_ref=first["claim_ref"],
        evidence_ref=first["evidence_refs"][0],
        authority_ref=authority_ref,
    )
    sections = []
    for agent_id in agents:
        claim = by_agent[agent_id]
        sections.append(
            {
                "heading": f"Research role {agent_id.split('_')[-1].lower()} perspective",
                "clauses": [
                    _clause(
                        agent_id=agent_id,
                        claim_ref=claim["claim_ref"],
                        evidence_ref=claim["evidence_refs"][0],
                    )
                ],
            }
        )
    return {
        "schema_version": MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
        "report_topic": "Demand quality, value capture and cash conversion",
        "executive_thesis": [executive],
        "sections": sections,
        "remaining_gaps": [
            _clause(
                agent_id=agents[0],
                gap_ref=first_gap,
                text="Direct disclosure remains unavailable after the bounded search routes.",
            )
        ],
        "what_would_change": [
            _clause(
                agent_id=agents[0],
                claim_ref=first["claim_ref"],
                gap_ref=first_gap,
                text="A direct issuer disclosure would materially narrow this uncertainty.",
            ),
            _clause(
                agent_id=agents[0],
                claim_ref=first["claim_ref"],
                text="A verified reversal in the operating mechanism would change the judgment.",
            ),
        ],
        "confidence": _clause(
            agent_id=agents[0],
            claim_ref=first["claim_ref"],
            text="Confidence is moderate because the core fact is typed but attribution remains bounded.",
        ),
    }


@pytest.mark.parametrize("ticker", ["DELL", "MU", "NVDA", "ORCL"])
def test_protected_report_contract_is_case_neutral_and_renders_typed_surfaces(
    ticker: str,
) -> None:
    workpapers, contexts = _fixtures(ticker)
    catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    payload = _payload(catalog)
    trusted = validate_protected_report_draft(
        payload,
        authority_catalog=catalog,
    )
    rendered = render_protected_report(trusted, authority_catalog=catalog)

    assert rendered["case_identity"]["case_key"] == ticker
    assert "$43.842B" in rendered["executive_thesis"]
    assert "2026-08-06" in rendered["report_title"]
    assert rendered["rendering_authority"][
        "case_identity_period_numeric_and_citations_harness_rendered"
    ] is True
    assert all(
        "$99B" not in row["display_surface"]
        for row in catalog["presentation_authority"]
    )


def test_catalog_and_rendering_are_stable_under_input_permutation() -> None:
    workpapers, contexts = _fixtures()
    first = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    second = compile_multi_agent_report_authority_catalog(
        workpapers=list(reversed(workpapers)),
        specialist_contexts=dict(reversed(list(contexts.items()))),
    )
    assert first["authority_catalog_digest"] == second["authority_catalog_digest"]
    assert render_protected_report(
        _payload(first), authority_catalog=first
    )["rendered_report_digest"] == render_protected_report(
        _payload(second), authority_catalog=second
    )["rendered_report_digest"]


def test_model_owned_numeric_surface_fails_closed() -> None:
    workpapers, contexts = _fixtures()
    catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    payload = _payload(catalog)
    payload["executive_thesis"][0]["model_text"] = (
        "Revenue reached $43.842B and therefore the conclusion is stronger."
    )
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_model_text_unprotected_surface",
    ):
        validate_protected_report_draft(payload, authority_catalog=catalog)


def test_cross_claim_authority_ref_fails_closed() -> None:
    workpapers, contexts = _fixtures()
    catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    payload = _payload(catalog)
    claims = {row["agent_id"]: row for row in catalog["claims"]}
    second_agent = sorted(claims)[1]
    payload["executive_thesis"][0] = _clause(
        agent_id=second_agent,
        claim_ref=claims[second_agent]["claim_ref"],
        evidence_ref=claims[second_agent]["evidence_refs"][0],
        authority_ref=catalog["presentation_authority"][0]["authority_ref"],
    )
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_clause_reference_scope_invalid",
    ):
        validate_protected_report_draft(payload, authority_catalog=catalog)


def test_legacy_free_prose_report_is_a_negative_replay() -> None:
    audit = audit_legacy_report_protected_surfaces(
        {
            "report_title": "Issuer Q1 FY27 research report",
            "executive_thesis": "Revenue reached $43.842B as of 2026-05-01.",
            "sections": [],
            "remaining_gaps": [],
            "what_would_change": [],
            "confidence_statement": "Confidence is medium.",
        }
    )
    assert audit["status"] == "hard_fail"
    assert audit["local_surface_gate_pass"] is False
    assert {row["field_path"] for row in audit["findings"]} == {
        "report_title",
        "executive_thesis",
    }


def test_tool_contract_exposes_refs_but_not_raw_evidence_numeric_surface() -> None:
    workpapers, contexts = _fixtures()
    catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    tool = protected_report_draft_tool(authority_catalog=catalog)
    serialized = str(tool)
    assert "submit_protected_report_draft" in serialized
    assert "NUM::" in serialized
    assert "$99B" not in serialized
