from __future__ import annotations

from copy import deepcopy

import pytest

from sec_agent.research.multi_agent_report_authority import (
    MULTI_AGENT_REPORT_QUALITY_POLICY_LEGACY_VERSION,
    MULTI_AGENT_PROTECTED_REPORT_DRAFT_LEGACY_SCHEMA_VERSION,
    MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
    MULTI_AGENT_PROTECTED_REPORT_REFERENCE_PATCH_SCHEMA_VERSION,
    MultiAgentReportAuthorityError,
    apply_protected_report_reference_patch,
    audit_legacy_report_protected_surfaces,
    audit_protected_report_draft,
    compile_protected_report_remap_messages,
    compile_protected_report_reference_patch_messages,
    compile_protected_report_reference_patch_receipt,
    compile_multi_agent_report_authority_catalog,
    protected_report_draft_tool,
    protected_report_reference_patch_tool,
    render_protected_report,
    validate_protected_report_draft,
    validate_protected_report_remap_draft,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.research.report_boundary import (
    compile_report_boundary_disposition_register,
)


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


def test_current_dynamic_catalog_projects_identity_estimates_and_operand_relations() -> None:
    workpapers, contexts = _fixtures()
    first_agent, second_agent = sorted(contexts)[:2]
    for context in contexts.values():
        view = context["cell_analysis_view"]
        context["case_identity"] = view.pop("case_identity")

    first_view = contexts[first_agent]["cell_analysis_view"]
    current = first_view["numeric_fact_catalog"][0]
    current["formula_trace"] = {
        "expression": "issuer_value",
        "input_numeric_fact_ids": ["NF::ROLE_A"],
    }
    duplicate = deepcopy(current)
    duplicate["formula_trace"]["input_numeric_fact_ids"] = ["NF::ROLE_B"]
    contexts[second_agent]["cell_analysis_view"]["numeric_fact_catalog"].append(
        duplicate
    )
    estimate_ref = "ESTIMATE::RESEARCH_ONLY_01"
    first_view["numeric_fact_catalog"].append(
        {
            "estimate_id": estimate_ref,
            "metric_id": "non_issuer_research_estimate",
            "value_decimal": "27.5",
            "unit": "percent",
            "numeric_fact_authority": False,
        }
    )
    workpapers[0]["sourced_claims"][0]["numeric_refs"].append(estimate_ref)
    workpapers[0].pop("workpaper_digest")
    workpapers[0]["workpaper_digest"] = canonical_digest(workpapers[0])
    relation = first_view["numeric_relation_catalog"][0]
    relation["absolute_change_decimal"] = None
    relation["percent_change_decimal"] = None
    relation["percentage_point_change_decimal"] = None

    catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )

    presentations = {
        row["authority_ref"]: row for row in catalog["presentation_authority"]
    }
    numeric = presentations[current["numeric_ref"]]
    relation_presentation = presentations[relation["numeric_relation_ref"]]
    assert numeric["presentation_receipt"]["formula_trace"][
        "input_numeric_fact_ids"
    ] == ["NF::ROLE_A", "NF::ROLE_B"]
    assert "+87.54%" in relation_presentation["display_surface"]
    assert relation_presentation["presentation_receipt"]["authority_mode"] == (
        "deterministically_hydrated_numeric_relation"
    )
    assert estimate_ref in catalog["claims"][0]["research_estimate_refs"]
    assert estimate_ref not in presentations
    assert catalog["coverage_receipt"][
        "research_estimates_granted_output_authority"
    ] is False


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


def test_terminal_remap_preserves_source_topology_and_agent_order() -> None:
    workpapers, contexts = _fixtures()
    evaluation = {"report_may_proceed": True}
    catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    payload = _payload(catalog)
    source = {
        "report_digest": "legacy-report-digest",
        "report_title": "DELL Q1 FY27 report",
        "executive_thesis": "Revenue was $1B.",
        "sections": [
            {
                "heading": f"Section {index + 1}",
                "body": "Revenue was $1B.",
                "source_workpaper_agent_ids": [row["agent_id"]],
                "evidence_refs": [],
                "numeric_refs": [],
            }
            for index, row in enumerate(workpapers[:4])
        ],
        "remaining_gaps": ["Gap is $1B."],
        "what_would_change": ["Change $1B.", "Change $2B."],
        "confidence_statement": "Medium confidence.",
        "workpaper_digests": catalog["workpaper_digests"],
    }
    payload["sections"] = [
        {
            "heading": "Research section " + chr(65 + index),
            "clauses": [
                {
                    **payload["sections"][0]["clauses"][0],
                    "source_workpaper_agent_ids": [row["agent_id"]],
                    "source_claim_refs": [
                        next(
                            claim["claim_ref"]
                            for claim in catalog["claims"]
                            if claim["agent_id"] == row["agent_id"]
                        )
                    ],
                    "evidence_refs": [],
                    "authority_refs": [],
                }
            ],
        }
        for index, row in enumerate(workpapers[:4])
    ]
    payload["remaining_gaps"] = payload["remaining_gaps"][:1]
    payload["what_would_change"] = payload["what_would_change"][:2]
    messages = compile_protected_report_remap_messages(
        source_report=source,
        evaluation=evaluation,
        authority_catalog=catalog,
    )
    assert "terminal contract remap" in messages[0]["content"]
    trusted = validate_protected_report_remap_draft(
        payload,
        authority_catalog=catalog,
        source_report=source,
    )
    assert trusted["remap_receipt"]["section_agent_order_preserved"] is True

    drift = deepcopy(payload)
    drift["sections"][0]["clauses"][0]["source_workpaper_agent_ids"] = [
        workpapers[1]["agent_id"]
    ]
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_clause_claim_agent_scope_invalid|multi_agent_report_remap_section_agent_order_drift",
    ):
        validate_protected_report_remap_draft(
            drift,
            authority_catalog=catalog,
            source_report=source,
        )


def test_narrative_density_is_a_quality_finding_below_safety_capacity() -> None:
    workpapers, contexts = _fixtures()
    catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    payload = _payload(catalog)
    payload["executive_thesis"][0]["model_text"] = "A" * 1200

    audit = audit_protected_report_draft(payload, authority_catalog=catalog)
    trusted = validate_protected_report_draft(
        payload, authority_catalog=catalog
    )

    assert audit["hard_finding_count"] == 0
    assert audit["quality_finding_count"] == 1
    assert audit["quality_findings"][0]["field_path"] == (
        "executive_thesis[0].model_text"
    )
    assert trusted["surface_contract_receipt"][
        "recommended_narrative_density_pass"
    ] is False

    overflow = deepcopy(payload)
    overflow["executive_thesis"][0]["model_text"] = "A" * 2401
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_model_text_safety_capacity_exceeded",
    ) as caught:
        validate_protected_report_draft(overflow, authority_catalog=catalog)
    finding = caught.value.details["contract_finding_receipt"]["hard_findings"][0]
    assert finding["field_path"] == "executive_thesis[0].model_text"
    assert finding["details"]["safety_maximum_characters"] == 2400


def test_boundary_inventory_repetition_is_quality_not_truth_failure() -> None:
    workpapers, contexts = _fixtures()
    catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    payload = _payload(catalog)
    gap_ref = payload["remaining_gaps"][0]["gap_refs"][0]
    payload["executive_thesis"][0]["gap_refs"] = [gap_ref]
    payload["sections"][0]["clauses"][0]["gap_refs"] = [gap_ref]
    payload["confidence"]["gap_refs"] = [gap_ref]

    audit = audit_protected_report_draft(payload, authority_catalog=catalog)
    trusted = validate_protected_report_draft(payload, authority_catalog=catalog)
    codes = {row["finding_code"] for row in audit["quality_findings"]}

    assert audit["hard_finding_count"] == 0
    assert "multi_agent_report_confidence_repeats_gap_inventory" in codes
    assert "multi_agent_report_gap_repeated_across_surface_groups" in codes
    assert trusted["surface_contract_receipt"][
        "recommended_narrative_density_pass"
    ] is False


def test_legacy_quality_policy_preserves_immutable_reference_patch_proof() -> None:
    workpapers, contexts = _fixtures()
    catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    payload = _payload(catalog)
    gap_ref = payload["remaining_gaps"][0]["gap_refs"][0]
    payload["executive_thesis"][0]["gap_refs"] = [gap_ref]
    payload["sections"][0]["clauses"][0]["gap_refs"] = [gap_ref]
    payload["confidence"]["gap_refs"] = [gap_ref]

    current = audit_protected_report_draft(payload, authority_catalog=catalog)
    legacy = audit_protected_report_draft(
        payload,
        authority_catalog=catalog,
        quality_policy_version=MULTI_AGENT_REPORT_QUALITY_POLICY_LEGACY_VERSION,
    )

    assert len(current["quality_findings"]) > len(legacy["quality_findings"])
    assert all(
        finding["finding_code"]
        != "multi_agent_report_gap_repeated_across_surface_groups"
        for finding in legacy["quality_findings"]
    )


def test_pre_report_operational_boundary_blocks_customer_report() -> None:
    workpapers, contexts = _fixtures()
    catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    payload = _payload(catalog)
    register = compile_report_boundary_disposition_register(
        case_key="DELL",
        source_report_ref="config://candidate-report",
        source_report_digest="a" * 64,
        rows=[
            {
                "boundary_id": "BOUNDARY::STALE-EVALUATION",
                "claim_area": "cash_conversion",
                "surface_paths": ["sections[0]"],
                "owner_plane": "harness_control",
                "owner_stage": "S2_to_S3",
                "information_state": "source_visible_numeric_authority_stale_downstream",
                "root_cause_zh": "旧评审没有被新权威废止。",
                "artifact_refs": ["config://authority"],
                "customer_surface_disposition": "resolve_before_customer_report",
                "next_action_zh": "刷新 Writer 视图。",
                "true_information_boundary": False,
            }
        ],
        recorded_at="2026-08-22T00:00:00+08:00",
    )

    audit = audit_protected_report_draft(
        payload,
        authority_catalog=catalog,
        boundary_disposition_register=register,
    )

    assert audit["contract_valid"] is False
    assert audit["hard_findings"][-1]["finding_code"] == (
        "multi_agent_report_pre_report_boundary_unresolved"
    )
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_pre_report_boundary_unresolved",
    ):
        validate_protected_report_draft(
            payload,
            authority_catalog=catalog,
            boundary_disposition_register=register,
        )


def test_reference_patch_preserves_model_text_and_only_repairs_failed_paths() -> None:
    workpapers, contexts = _fixtures()
    catalog = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=contexts,
    )
    valid = _payload(catalog)
    base = deepcopy(valid)
    base["schema_version"] = (
        MULTI_AGENT_PROTECTED_REPORT_DRAFT_LEGACY_SCHEMA_VERSION
    )
    base["executive_thesis"][0]["model_text"] = "A" * 1200
    claims = {row["agent_id"]: row for row in catalog["claims"]}
    second_agent = sorted(claims)[1]
    second_claim = claims[second_agent]
    base["executive_thesis"][0].update(
        {
            "source_workpaper_agent_ids": [second_agent],
            "source_claim_refs": [second_claim["claim_ref"]],
            "evidence_refs": [second_claim["evidence_refs"][0]],
            "authority_refs": [
                catalog["presentation_authority"][0]["authority_ref"]
            ],
        }
    )
    base["remaining_gaps"][0]["gap_refs"] = []
    source = {
        "report_digest": "legacy-report-digest",
        "sections": [
            {
                "source_workpaper_agent_ids": list(
                    section["clauses"][0]["source_workpaper_agent_ids"]
                )
            }
            for section in valid["sections"]
        ],
        "remaining_gaps": ["legacy gap"] * len(valid["remaining_gaps"]),
        "what_would_change": ["legacy route"]
        * len(valid["what_would_change"]),
    }
    receipt = compile_protected_report_reference_patch_receipt(
        base, authority_catalog=catalog
    )
    assert receipt["target_paths"] == [
        "executive_thesis[0]",
        "remaining_gaps[0]",
    ]
    assert len(receipt["quality_findings_preserved_for_later_assessment"]) == 1
    messages = compile_protected_report_reference_patch_messages(
        base_payload=base,
        patch_receipt=receipt,
        authority_catalog=catalog,
    )
    tool = protected_report_reference_patch_tool(
        patch_receipt=receipt,
        authority_catalog=catalog,
    )
    assert "Preserve every word" in messages[0]["content"]
    assert tool["function"]["name"] == "submit_protected_report_reference_patch"

    patch = {
        "schema_version": MULTI_AGENT_PROTECTED_REPORT_REFERENCE_PATCH_SCHEMA_VERSION,
        "base_payload_digest": receipt["base_payload_digest"],
        "patches": [
            {
                "field_path": "executive_thesis[0]",
                "source_claim_refs": [second_claim["claim_ref"]],
                "evidence_refs": [second_claim["evidence_refs"][0]],
                "authority_refs": [],
                "gap_refs": [],
            },
            {
                "field_path": "remaining_gaps[0]",
                "source_claim_refs": list(
                    base["remaining_gaps"][0]["source_claim_refs"]
                ),
                "evidence_refs": list(
                    base["remaining_gaps"][0]["evidence_refs"]
                ),
                "authority_refs": [],
                "gap_refs": list(valid["remaining_gaps"][0]["gap_refs"]),
            },
        ],
    }
    trusted = apply_protected_report_reference_patch(
        patch,
        base_payload=base,
        patch_receipt=receipt,
        authority_catalog=catalog,
        source_report=source,
    )
    assert trusted["reference_patch_receipt"]["model_text_unchanged"] is True
    assert trusted["reference_patch_receipt"][
        "source_workpaper_agent_ids_unchanged"
    ] is True
    assert trusted["reference_patch_receipt"]["patched_paths"] == receipt[
        "target_paths"
    ]
    assert trusted["surface_contract_receipt"][
        "recommended_narrative_density_pass"
    ] is False

    prose_patch = deepcopy(patch)
    prose_patch["patches"][0]["model_text"] = "Harness-authored replacement"
    with pytest.raises(
        MultiAgentReportAuthorityError,
        match="multi_agent_report_reference_patch_fields_invalid",
    ):
        apply_protected_report_reference_patch(
            prose_patch,
            base_payload=base,
            patch_receipt=receipt,
            authority_catalog=catalog,
            source_report=source,
        )
