from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime import canonical_digest
from sec_agent.research.multi_agent_preview import SPECIALIST_AGENT_IDS
from sec_agent.research.multi_agent_report_authority import (
    compile_multi_agent_report_authority_catalog,
    compile_protected_report_messages,
    extend_multi_agent_report_authority_catalog,
    validate_protected_report_draft,
)
from sec_agent.research.source_bound_numeric_authority import (
    compile_source_bound_numeric_authority_program,
)


CURRENT_DYNAMIC_WRITER_PROTECTION_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_writer_protection_v1_0"
)
CURRENT_DYNAMIC_WRITER_ZERO_CALL_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_zero_call_v1_0"
)
CURRENT_DYNAMIC_WRITER_SCOPE_DECISION_SCHEMA_VERSION = (
    "fin_ia_s3_current_dynamic_multi_agent_protected_writer_scope_decision_v1_0"
)
CURRENT_DYNAMIC_WRITER_SCOPE_DECISION_STATUS = (
    "zero_call_R10_bound_protected_writer_successor_engineering_complete"
)
CURRENT_DYNAMIC_WRITER_RUN_SCOPE = (
    "one_capture_bound_R10_protected_writer_analysis_and_submission"
)

R10_ASSESSMENT_STATUS = (
    "R10_contract_pass_all_seven_material_findings_closed_independent_"
    "L1_L2_pass_writer_zero_call_gate_eligible"
)

_EXPECTED_MATERIAL_ISSUES = (
    "RC-S3-074-expense-bridge-contribution-share-misstated",
    "RC-S3-075-same-quarter-orders-and-revenue-promoted-to-cohort-conversion",
    "RC-S3-076-balance-sheet-stock-delta-promoted-to-cash-absorption",
    "RC-S3-077-cross-company-customer-structure-inferred-from-NVDA",
    "RC-S3-078-NVDA-export-control-risk-promoted-to-DELL-exposure",
    "RC-S3-079-company-gross-margin-used-as-necessary-test-of-product-pricing-power",
    "RC-S3-080-demand-context-promoted-to-definite-pull-forward-and-digestion",
)

_EXPECTED_WRITER_REQUIREMENTS = (
    "Preserve the exact same-quarter-versus-cohort boundary: USD 24.4B orders and USD 16.1B recognized revenue are parallel signals, not a proven same-order conversion.",
    "Preserve the USD 1.253B value only as a three-line balance-sheet working-capital proxy change; prohibit exact cash absorption and AI attribution.",
    "Rewrite slower guided growth as reducing the probability of further expense leverage, not making leverage narrowing arithmetically necessary.",
    "Omit unnormalized NVDA and MU absolute inventory balances unless a typed cross-company mechanism and comparable scale are provided.",
    "Preserve all issuer/source ownership, product-versus-company, pull-forward, typed-gap and not_inferable boundaries already accepted.",
)

_SOURCE_BOUND_DECISION_TARGETS: dict[
    str, tuple[tuple[str, int], ...]
] = {
    "dell_demand_ai_orders_actual": (("AGENT::DEMAND_QUALITY", 0),),
    "dell_demand_ai_server_revenue_actual": (
        ("AGENT::DEMAND_QUALITY", 0),
    ),
    "dell_demand_ai_backlog_actual": (("AGENT::DEMAND_QUALITY", 0),),
    "dell_demand_customer_count_threshold": (
        ("AGENT::DEMAND_QUALITY", 0),
    ),
    "dell_guidance_ai_server_revenue_approximation": (
        ("AGENT::OPERATING_PERFORMANCE", 3),
        ("AGENT::VALUE_CAPTURE", 5),
    ),
    "dell_guidance_q2_revenue_range": (
        ("AGENT::OPERATING_PERFORMANCE", 5),
        ("AGENT::VALUE_CAPTURE", 5),
    ),
    "nvda_counterevidence_hyperscaler_share_approximation": (
        ("AGENT::COUNTEREVIDENCE", 5),
    ),
}

_ENGLISH_SPELLED_NUMERIC_SURFACE = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
    r"twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
    r"million|billion|trillion|first|second|third|fourth|fifth|sixth|seventh|"
    r"eighth|ninth|tenth|point)\b",
    re.IGNORECASE,
)
_CHINESE_SPELLED_NUMERIC_SURFACE = re.compile(
    r"(?:百分之|千分之)[零〇一二三四五六七八九十百千万亿兆两点]+"
    r"|[零〇一二三四五六七八九十百千万亿兆两]+(?:点[零〇一二三四五六七八九]+)?"
    r"(?:美元|美金|亿元|万元|元|万|亿|兆|百分比|百分点|基点|家|台|笔|项|"
    r"季度|年|月|日)"
)


class CurrentDynamicWriterError(ValueError):
    """Fail-closed error for the R10-bound protected Writer successor."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CurrentDynamicWriterError(code)


def _canonical_object(value: Mapping[str, Any], *, digest_field: str) -> bool:
    body = deepcopy(dict(value))
    supplied = str(body.pop(digest_field, ""))
    return bool(supplied) and supplied == canonical_digest(body)


def expected_current_dynamic_writer_budget() -> dict[str, int]:
    """Maximum authority for one analysis and a bounded strict submission."""

    return {
        "maximum_new_model_calls": 3,
        "maximum_new_transport_attempts": 3,
        "writer_analysis_calls": 1,
        "maximum_writer_submission_attempts": 2,
        "maximum_new_writer_logical_nodes": 1,
        "maximum_new_s1_s2_requests": 0,
        "maximum_new_retrieval_rounds": 0,
        "maximum_external_source_network_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "candidate_promotions": 0,
        "current_product_pointer_mutations": 0,
    }


def compile_r10_report_contexts(
    *,
    r10_private: Mapping[str, Any],
    r9_private: Mapping[str, Any],
    r5_private: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Recover the exact authority views behind the six R10 workpapers.

    Five current contexts are preserved directly by the R9/R10 repair runs.
    Supply was byte-reused from R5 while only its submission-context identity was
    rebound.  For report compilation we project the unchanged R5 authority view
    onto that final context digest and emit an explicit no-authority-mutation
    receipt instead of pretending a new model context exists.
    """

    workpapers = [deepcopy(dict(row)) for row in r10_private.get("final_workpapers") or ()]
    _require(
        [str(row.get("agent_id") or "") for row in workpapers]
        == list(SPECIALIST_AGENT_IDS),
        "current_dynamic_writer_R10_workpaper_order_invalid",
    )
    by_workpaper = {str(row["agent_id"]): row for row in workpapers}
    r9_repairs = {
        str(row.get("agent_id") or ""): deepcopy(dict(row))
        for row in r9_private.get("repairs") or ()
    }
    contexts: dict[str, dict[str, Any]] = {}
    for agent_id in (
        "AGENT::OPERATING_PERFORMANCE",
        "AGENT::VALUE_CAPTURE",
        "AGENT::CASH_CONVERSION",
        "AGENT::COUNTEREVIDENCE",
    ):
        repair = r9_repairs.get(agent_id) or {}
        context = deepcopy(dict(repair.get("repair_context") or {}))
        _require(
            _canonical_object(context, digest_field="context_digest")
            and context.get("context_digest")
            == by_workpaper[agent_id].get("context_digest")
            and (context.get("agent") or {}).get("agent_id") == agent_id,
            "current_dynamic_writer_R9_context_invalid",
        )
        contexts[agent_id] = context

    demand_repair = deepcopy(dict(r10_private.get("repair") or {}))
    demand_context = deepcopy(dict(demand_repair.get("repair_context") or {}))
    _require(
        demand_repair.get("agent_id") == "AGENT::DEMAND_QUALITY"
        and _canonical_object(demand_context, digest_field="context_digest")
        and demand_context.get("context_digest")
        == by_workpaper["AGENT::DEMAND_QUALITY"].get("context_digest"),
        "current_dynamic_writer_R10_demand_context_invalid",
    )
    contexts["AGENT::DEMAND_QUALITY"] = demand_context

    supply_bundle = next(
        (
            deepcopy(dict(row))
            for row in r5_private.get("role_bundles") or ()
            if row.get("agent_id") == "AGENT::SUPPLY_RELATIONSHIP"
        ),
        None,
    )
    _require(supply_bundle is not None, "current_dynamic_writer_supply_bundle_missing")
    assert supply_bundle is not None
    source_context = deepcopy(dict(supply_bundle.get("workpaper_context") or {}))
    source_workpaper = deepcopy(dict(supply_bundle.get("workpaper") or {}))
    final_supply = by_workpaper["AGENT::SUPPLY_RELATIONSHIP"]
    _require(
        _canonical_object(source_context, digest_field="context_digest")
        and source_workpaper == final_supply
        and (source_context.get("agent") or {}).get("agent_id")
        == "AGENT::SUPPLY_RELATIONSHIP"
        and isinstance(source_context.get("cell_analysis_view"), Mapping),
        "current_dynamic_writer_supply_lineage_invalid",
    )
    projected_supply = deepcopy(source_context)
    projected_supply["context_digest"] = str(final_supply["context_digest"])
    contexts["AGENT::SUPPLY_RELATIONSHIP"] = projected_supply
    ordered_contexts = {
        agent_id: contexts[agent_id] for agent_id in SPECIALIST_AGENT_IDS
    }
    receipt_body = {
        "schema_version": (
            "fin_ia_s3_current_dynamic_multi_agent_report_context_projection_v1_0"
        ),
        "source_R5_supply_context_digest": source_context["context_digest"],
        "projected_R10_supply_context_digest": final_supply["context_digest"],
        "supply_workpaper_digest": final_supply["workpaper_digest"],
        "cell_analysis_view_digest": canonical_digest(
            source_context["cell_analysis_view"]
        ),
        "case_identity_digest": canonical_digest(source_context["case_identity"]),
        "source_workpaper_and_R10_workpaper_byte_equal": True,
        "evidence_numeric_relation_gap_and_case_authority_changed": False,
        "model_judgment_changed": False,
        "projection_is_report_compiler_only": True,
    }
    return ordered_contexts, {
        **receipt_body,
        "projection_receipt_digest": canonical_digest(receipt_body),
    }


def compile_r10_source_bound_numeric_review(
    *,
    base_authority_catalog: Mapping[str, Any],
    predecessor_review: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebind already-qualified source spans to the repaired R10 claim refs."""

    claims = {
        (str(row.get("agent_id") or ""), int(row.get("claim_index", -1))): row
        for row in base_authority_catalog.get("claims") or ()
    }
    predecessor_decisions = {
        str(row.get("decision_id") or ""): deepcopy(dict(row))
        for row in predecessor_review.get("decisions") or ()
    }
    _require(
        predecessor_review.get("status")
        == "qualified_engineering_source_bound_numeric_review"
        and set(_SOURCE_BOUND_DECISION_TARGETS).issubset(predecessor_decisions),
        "current_dynamic_writer_source_bound_predecessor_invalid",
    )
    decisions: list[dict[str, Any]] = []
    for decision_id, targets in _SOURCE_BOUND_DECISION_TARGETS.items():
        decision = predecessor_decisions[decision_id]
        bindings = []
        for agent_id, claim_index in targets:
            claim = claims.get((agent_id, claim_index))
            _require(
                claim is not None,
                "current_dynamic_writer_source_bound_claim_missing",
            )
            bindings.append(
                {"agent_id": agent_id, "claim_ref": str(claim["claim_ref"])}
            )
        decision["claim_bindings"] = bindings
        decisions.append(decision)

    temporal_rows = [
        deepcopy(dict(row))
        for row in predecessor_review.get("temporal_decisions") or ()
    ]
    _require(
        len(temporal_rows) == 1
        and temporal_rows[0].get("decision_id")
        == "dell_value_capture_mix_period_end",
        "current_dynamic_writer_source_bound_temporal_invalid",
    )
    value_mix_claim = claims.get(("AGENT::VALUE_CAPTURE", 3))
    _require(
        value_mix_claim is not None,
        "current_dynamic_writer_source_bound_value_mix_claim_missing",
    )
    temporal_rows[0]["claim_bindings"] = [
        {
            "agent_id": "AGENT::VALUE_CAPTURE",
            "claim_ref": str(value_mix_claim["claim_ref"]),
        }
    ]
    body = {
        "schema_version": predecessor_review["schema_version"],
        "status": "qualified_engineering_source_bound_numeric_review",
        "base_authority_catalog_digest": base_authority_catalog[
            "authority_catalog_digest"
        ],
        "case_identity": deepcopy(base_authority_catalog["case_identity"]),
        "decisions": decisions,
        "temporal_decisions": temporal_rows,
        "successor_lineage": {
            "predecessor_review_base_authority_catalog_digest": (
                predecessor_review.get("base_authority_catalog_digest")
            ),
            "review_semantics_changed": False,
            "claim_bindings_rebased_to_R10": True,
            "dropped_stale_or_unneeded_decision_ids": sorted(
                set(predecessor_decisions) - set(_SOURCE_BOUND_DECISION_TARGETS)
            ),
            "new_evidence_or_source_span_admitted": False,
        },
    }
    return {**body, "review_digest": canonical_digest(body)}


def compile_r10_writer_authority(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    specialist_contexts: Mapping[str, Mapping[str, Any]],
    predecessor_review: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    base = compile_multi_agent_report_authority_catalog(
        workpapers=workpapers,
        specialist_contexts=specialist_contexts,
    )
    review = compile_r10_source_bound_numeric_review(
        base_authority_catalog=base,
        predecessor_review=predecessor_review,
    )
    compiler_review = {
        key: deepcopy(value)
        for key, value in review.items()
        if key not in {"review_digest", "successor_lineage"}
    }
    program = compile_source_bound_numeric_authority_program(
        authority_catalog=base,
        specialist_contexts=specialist_contexts,
        review=compiler_review,
    )
    extended = extend_multi_agent_report_authority_catalog(
        authority_catalog=base,
        source_bound_program=program,
    )
    return review, program, extended


def _claim_by_agent_index(
    authority_catalog: Mapping[str, Any], agent_id: str, claim_index: int
) -> Mapping[str, Any]:
    matches = [
        row
        for row in authority_catalog.get("claims") or ()
        if row.get("agent_id") == agent_id
        and row.get("claim_index") == claim_index
    ]
    _require(len(matches) == 1, "current_dynamic_writer_claim_identity_invalid")
    return matches[0]


def compile_r10_writer_protection_contract(
    *,
    assessment: Mapping[str, Any],
    authority_catalog: Mapping[str, Any],
    source_bound_program: Mapping[str, Any],
) -> dict[str, Any]:
    dispositions = [
        deepcopy(dict(row))
        for row in assessment.get("original_finding_dispositions") or ()
    ]
    _require(
        assessment.get("status") == R10_ASSESSMENT_STATUS
        and assessment.get("material_residual_findings") == []
        and tuple(assessment.get("protected_writer_requirements") or ())
        == _EXPECTED_WRITER_REQUIREMENTS
        and tuple(str(row.get("issue_id") or "") for row in dispositions)
        == _EXPECTED_MATERIAL_ISSUES
        and (assessment.get("acceptance") or {}).get("independent_L1_pass") is True
        and (assessment.get("acceptance") or {}).get("independent_L2_pass") is True
        and (assessment.get("acceptance") or {}).get("writer_live_authorized")
        is False,
        "current_dynamic_writer_assessment_gate_invalid",
    )
    demand_claim = _claim_by_agent_index(
        authority_catalog, "AGENT::DEMAND_QUALITY", 0
    )
    cash_proxy_claim = _claim_by_agent_index(
        authority_catalog, "AGENT::CASH_CONVERSION", 5
    )
    counter_inventory_claim = _claim_by_agent_index(
        authority_catalog, "AGENT::COUNTEREVIDENCE", 8
    )
    receipts = {
        str(row.get("decision_id") or ""): str(row.get("authority_ref") or "")
        for row in source_bound_program.get("decision_receipts") or ()
    }
    order_ref = receipts.get("dell_demand_ai_orders_actual", "")
    revenue_ref = receipts.get("dell_demand_ai_server_revenue_actual", "")
    _require(
        order_ref.startswith("NUM::") and revenue_ref.startswith("NUM::"),
        "current_dynamic_writer_demand_authority_missing",
    )
    forbidden_authority = sorted(
        str(ref) for ref in counter_inventory_claim.get("authority_refs") or ()
    )
    _require(
        forbidden_authority
        == ["NUM::5EF59EBA7D876FB8", "NUM::8E720DA4B13E2279"],
        "current_dynamic_writer_counter_inventory_authority_drift",
    )
    body = {
        "schema_version": CURRENT_DYNAMIC_WRITER_PROTECTION_SCHEMA_VERSION,
        "assessment_status": assessment["status"],
        "material_issue_ids": list(_EXPECTED_MATERIAL_ISSUES),
        "assessment_writer_requirements": list(_EXPECTED_WRITER_REQUIREMENTS),
        "forbidden_claim_refs": [counter_inventory_claim["claim_ref"]],
        "forbidden_authority_refs": forbidden_authority,
        "global_forbidden_model_text_fragments": [
            "算术必然",
            "必然收窄",
            "必定收窄",
            "arithmetic necessity",
            "must narrow",
            "necessarily narrow",
            "inevitably narrow",
        ],
        "conditional_rules": [
            {
                "rule_id": "same_quarter_signals_not_cohort_conversion",
                "trigger_authority_refs_all": [order_ref, revenue_ref],
                "source_claim_ref": demand_claim["claim_ref"],
                "required_model_text_fragments_any": [
                    "并列",
                    "平行",
                    "同一订单",
                    "同批订单",
                    "cohort",
                    "parallel",
                ],
                "forbidden_model_text_fragments": [
                    "同季订单已转化",
                    "同季订单已经转化",
                    "已完成转化",
                    "same quarter orders converted",
                    "same-quarter orders converted",
                    "conversion occurred",
                ],
                "required_gap_refs": [],
            },
            {
                "rule_id": "cash_three_line_proxy_not_cash_or_AI_attribution",
                "trigger_source_claim_refs_any": [cash_proxy_claim["claim_ref"]],
                "required_model_text_fragments_any": ["代理", "proxy"],
                "forbidden_model_text_fragments": [
                    "精确现金吸收",
                    "实测现金吸收",
                    "人工智能归因",
                    "归因于人工智能",
                    "exact cash absorption",
                    "measured cash absorption",
                    "attributable to artificial intelligence",
                    "attributed to artificial intelligence",
                ],
                "required_gap_refs": ["GAP::EF4839B4BF55ADD0"],
            },
        ],
        "writer_rules": [
            "Use the same-quarter order and revenue authorities only as parallel signals unless an explicit cohort relation exists.",
            "Treat the three-line working-capital calculation only as a balance-sheet proxy and retain the product-attribution gap.",
            "State slower-growth expense leverage conditionally or omit it; never call narrowing an arithmetic necessity.",
            "The two unnormalized upstream inventory balance claims and their numeric authorities are unavailable to Writer.",
            "Preserve issuer ownership, company-versus-product, possible pull-forward, typed-gap and not-inferable boundaries.",
            "Do not spell out numeric or ordinal values in model text; all exact numeric and temporal surfaces must come from typed deterministic presentation authority.",
        ],
        "spelled_out_numeric_or_ordinal_model_surface_forbidden": True,
        "harness_authored_business_conclusion": False,
        "independent_post_writer_L1_L2_and_eight_dimension_review_required": True,
    }
    return {**body, "protection_digest": canonical_digest(body)}


def project_r10_writer_authority_catalog(
    *, authority_catalog: Mapping[str, Any], protection: Mapping[str, Any]
) -> dict[str, Any]:
    source = deepcopy(dict(authority_catalog))
    supplied_digest = str(source.pop("authority_catalog_digest", ""))
    _require(
        supplied_digest == canonical_digest(source)
        and protection.get("schema_version")
        == CURRENT_DYNAMIC_WRITER_PROTECTION_SCHEMA_VERSION,
        "current_dynamic_writer_authority_catalog_invalid",
    )
    forbidden_claims = set(protection.get("forbidden_claim_refs") or ())
    forbidden_authority = set(protection.get("forbidden_authority_refs") or ())
    claims = [
        deepcopy(dict(row))
        for row in source.get("claims") or ()
        if row.get("claim_ref") not in forbidden_claims
    ]
    _require(
        len(claims) + len(forbidden_claims) == len(source.get("claims") or ()),
        "current_dynamic_writer_forbidden_claim_missing",
    )
    used_evidence = {
        str(ref) for row in claims for ref in row.get("evidence_refs") or ()
    }
    used_authority = {
        str(ref) for row in claims for ref in row.get("authority_refs") or ()
    }
    _require(
        not (used_authority & forbidden_authority),
        "current_dynamic_writer_forbidden_authority_still_reachable",
    )
    source["claims"] = claims
    source["claim_refs_by_agent"] = {
        agent_id: sorted(
            str(row["claim_ref"])
            for row in claims
            if row.get("agent_id") == agent_id
        )
        for agent_id in sorted(source.get("claim_refs_by_agent") or {})
    }
    source["evidence_authority"] = [
        row
        for row in source.get("evidence_authority") or ()
        if row.get("evidence_ref") in used_evidence
    ]
    source["presentation_authority"] = [
        row
        for row in source.get("presentation_authority") or ()
        if row.get("authority_ref") in used_authority
    ]
    source["authority_boundary"] = {
        **deepcopy(dict(source.get("authority_boundary") or {})),
        "R10_writer_protection_projection_required": True,
        "forbidden_claim_or_authority_may_render": False,
        "research_estimates_granted_output_authority": False,
    }
    source["coverage_receipt"] = {
        **deepcopy(dict(source.get("coverage_receipt") or {})),
        "writer_admitted_claim_count": len(claims),
        "writer_forbidden_claim_count": len(forbidden_claims),
        "writer_forbidden_authority_count": len(forbidden_authority),
    }
    source["writer_protection_projection"] = {
        "protection_digest": protection["protection_digest"],
        "forbidden_claim_refs": sorted(forbidden_claims),
        "forbidden_authority_refs": sorted(forbidden_authority),
    }
    return {**source, "authority_catalog_digest": canonical_digest(source)}


def compile_r10_writer_evaluation(
    *,
    assessment: Mapping[str, Any],
    lead_decision: Mapping[str, Any],
    protection: Mapping[str, Any],
) -> dict[str, Any]:
    _require(
        lead_decision.get("next_state") == "proceed_to_evaluation"
        and lead_decision.get("lead_agent_id") == "AGENT::RESEARCH_LEAD"
        and assessment.get("status") == R10_ASSESSMENT_STATUS,
        "current_dynamic_writer_lead_or_assessment_invalid",
    )
    body = {
        "schema_version": (
            "fin_ia_s3_current_dynamic_multi_agent_writer_gate_v1_0"
        ),
        "status": "R10_independent_workpaper_gate_pass_writer_synthesis_only",
        "report_may_proceed": True,
        "lead_coordination_digest": lead_decision.get("coordination_digest"),
        "assessment_source_result_digest": assessment.get("source_result_digest"),
        "assessment_private_full_result_digest": assessment.get(
            "private_full_result_digest"
        ),
        "material_finding_dispositions": deepcopy(
            assessment.get("original_finding_dispositions") or []
        ),
        "non_blocking_findings": deepcopy(
            assessment.get("non_blocking_findings") or []
        ),
        "writer_protection_digest": protection["protection_digest"],
        "writer_live_authorized_by_this_gate": False,
        "final_report_accepted": False,
        "S3_accepted": False,
    }
    return {**body, "writer_gate_digest": canonical_digest(body)}


def compile_r10_protected_writer_messages(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    writer_gate: Mapping[str, Any],
    authority_catalog: Mapping[str, Any],
    protection: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    messages = [
        deepcopy(dict(row))
        for row in compile_protected_report_messages(
            workpapers=workpapers,
            evaluation=writer_gate,
            authority_catalog=authority_catalog,
        )
    ]
    import json

    visible = json.loads(messages[1]["content"])
    visible["R10_writer_protection_contract"] = deepcopy(dict(protection))
    messages[0]["content"] += (
        " The R10 protection contract is mandatory and locally validated; "
        "a fluent report that violates it is not a valid submission."
    )
    messages[1]["content"] = json.dumps(
        visible, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return tuple(messages)


def _draft_clauses(draft: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    clauses: list[Mapping[str, Any]] = []
    clauses.extend(draft.get("executive_thesis") or ())
    for section in draft.get("sections") or ():
        if isinstance(section, Mapping):
            clauses.extend(section.get("clauses") or ())
    clauses.extend(draft.get("remaining_gaps") or ())
    clauses.extend(draft.get("what_would_change") or ())
    confidence = draft.get("confidence")
    if isinstance(confidence, Mapping):
        clauses.append(confidence)
    return clauses


def _model_owned_texts(draft: Mapping[str, Any]) -> list[str]:
    texts = [str(draft.get("report_topic") or "")]
    for section in draft.get("sections") or ():
        if isinstance(section, Mapping):
            texts.append(str(section.get("heading") or ""))
    texts.extend(str(clause.get("model_text") or "") for clause in _draft_clauses(draft))
    return texts


def validate_r10_protected_writer_draft(
    payload: Mapping[str, Any],
    *,
    authority_catalog: Mapping[str, Any],
    protection: Mapping[str, Any],
) -> dict[str, Any]:
    for raw_text in _model_owned_texts(payload):
        _require(
            _ENGLISH_SPELLED_NUMERIC_SURFACE.search(raw_text) is None
            and _CHINESE_SPELLED_NUMERIC_SURFACE.search(raw_text) is None,
            "current_dynamic_writer_protected_surface_forbidden",
        )
    trusted = validate_protected_report_draft(
        payload, authority_catalog=authority_catalog
    )
    clauses = _draft_clauses(trusted)
    forbidden_claims = set(protection.get("forbidden_claim_refs") or ())
    forbidden_authority = set(protection.get("forbidden_authority_refs") or ())
    global_fragments = [
        str(value).casefold()
        for value in protection.get("global_forbidden_model_text_fragments") or ()
    ]
    _require(
        all(
            not any(fragment in text.casefold() for fragment in global_fragments)
            for text in _model_owned_texts(trusted)
        ),
        "current_dynamic_writer_protected_surface_forbidden",
    )
    for clause in clauses:
        text = str(clause.get("model_text") or "").casefold()
        _require(
            _ENGLISH_SPELLED_NUMERIC_SURFACE.search(text) is None
            and _CHINESE_SPELLED_NUMERIC_SURFACE.search(text) is None
            and not (set(clause.get("source_claim_refs") or ()) & forbidden_claims)
            and not (set(clause.get("authority_refs") or ()) & forbidden_authority),
            "current_dynamic_writer_protected_surface_forbidden",
        )

    triggered: list[str] = []
    for rule in protection.get("conditional_rules") or ():
        trigger_authority = set(rule.get("trigger_authority_refs_all") or ())
        trigger_claims = set(rule.get("trigger_source_claim_refs_any") or ())
        matching = []
        for clause in clauses:
            authority_refs = set(clause.get("authority_refs") or ())
            claim_refs = set(clause.get("source_claim_refs") or ())
            if (trigger_authority and trigger_authority.issubset(authority_refs)) or (
                trigger_claims and bool(trigger_claims & claim_refs)
            ):
                matching.append(clause)
        for clause in matching:
            text = str(clause.get("model_text") or "").casefold()
            required = [
                str(value).casefold()
                for value in rule.get("required_model_text_fragments_any") or ()
            ]
            forbidden = [
                str(value).casefold()
                for value in rule.get("forbidden_model_text_fragments") or ()
            ]
            required_gaps = set(rule.get("required_gap_refs") or ())
            _require(
                (not required or any(fragment in text for fragment in required))
                and not any(fragment in text for fragment in forbidden)
                and required_gaps.issubset(set(clause.get("gap_refs") or ())),
                "current_dynamic_writer_conditional_protection_invalid:"
                + str(rule.get("rule_id") or "unknown"),
            )
            triggered.append(str(rule.get("rule_id") or ""))
    body = deepcopy(trusted)
    body.pop("draft_digest", None)
    receipt = {
        "protection_digest": protection["protection_digest"],
        "global_forbidden_surface_pass": True,
        "forbidden_claim_and_authority_pass": True,
        "triggered_conditional_rule_ids": sorted(set(triggered)),
        "independent_semantic_review_still_required": True,
    }
    body["writer_protection_receipt"] = {
        **receipt,
        "receipt_digest": canonical_digest(receipt),
    }
    return {**body, "draft_digest": canonical_digest(body)}


__all__ = [
    "CURRENT_DYNAMIC_WRITER_PROTECTION_SCHEMA_VERSION",
    "CURRENT_DYNAMIC_WRITER_RUN_SCOPE",
    "CURRENT_DYNAMIC_WRITER_SCOPE_DECISION_SCHEMA_VERSION",
    "CURRENT_DYNAMIC_WRITER_SCOPE_DECISION_STATUS",
    "CURRENT_DYNAMIC_WRITER_ZERO_CALL_SCHEMA_VERSION",
    "CurrentDynamicWriterError",
    "compile_r10_protected_writer_messages",
    "compile_r10_report_contexts",
    "compile_r10_source_bound_numeric_review",
    "compile_r10_writer_authority",
    "compile_r10_writer_evaluation",
    "compile_r10_writer_protection_contract",
    "expected_current_dynamic_writer_budget",
    "project_r10_writer_authority_catalog",
    "validate_r10_protected_writer_draft",
]
