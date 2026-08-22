from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from sec_agent.canonical_runtime.session import canonical_digest
from sec_agent.research.actionable_research_evaluation import (
    evaluate_actionable_research_state,
)
from sec_agent.research.claim_authority import (
    compile_claim_authority_research_input,
)
from sec_agent.research.claim_surface_authority import (
    compile_claim_surface_authority_research_input,
)
from sec_agent.research.current_consumer import (
    compile_current_research_input,
)
from sec_agent.research.dynamic_truth_spine import (
    DYNAMIC_RESEARCH_INPUT_SCHEMA_VERSION,
    bind_dynamic_evidence_responses_to_research_input,
    compile_dynamic_claim_authority_policy,
    compile_dynamic_claim_surface_policy,
    compile_dynamic_evidence_responses,
    compile_dynamic_reviewed_pack_view,
)


DYNAMIC_RESEARCH_CONTROL_CONTEXT_SCHEMA_VERSION = (
    "fin_ia_dynamic_research_control_context_v1_0"
)


def bind_actionable_research_control_context(
    *,
    dynamic_research_input: Mapping[str, Any],
    actionable_research_state: Mapping[str, Any],
    quantitative_authority: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind current typed feedback and quantitative kinds to a dynamic S3 input.

    This is deliberately a consuming seam rather than another planning artifact.
    It validates the current-data state, annotates the NumericFact cards already
    present in the S3 input, and exposes only typed actions/receipts to downstream
    research nodes.  It never promotes a retrieval candidate or invents a gap.
    """

    current = deepcopy(dict(dynamic_research_input))
    state = deepcopy(dict(actionable_research_state))
    quantitative = deepcopy(dict(quantitative_authority))
    case_key = str(current.get("case_identity", {}).get("case_key") or "")
    if (
        current.get("schema_version") != DYNAMIC_RESEARCH_INPUT_SCHEMA_VERSION
        or not case_key
        or state.get("case_key") != case_key
        or quantitative.get("case_key") != case_key
        or state.get("quantitative_authority_ref")
        != quantitative.get("quantitative_authority_digest")
    ):
        raise ValueError("dynamic_research_control_context_case_binding_invalid")
    evaluation = evaluate_actionable_research_state(
        state=state,
        quantitative_authority=quantitative,
    )
    if evaluation.get("status") != "pass":
        raise ValueError("dynamic_research_control_context_evaluation_failed")

    quantitative_kind_by_ref = {
        str(row.get("authority_ref") or ""): str(
            row.get("quantitative_kind") or ""
        )
        for lane in (
            "reported_facts",
            "deterministic_derived_metrics",
            "research_estimates",
            "scenarios",
        )
        for row in quantitative.get(lane) or ()
        if row.get("authority_ref")
    }
    current.pop("research_input_digest", None)
    for card in current.get("numeric_fact_cards") or ():
        source_refs = [
            str(value) for value in card.get("source_numeric_fact_ids") or ()
        ]
        kinds = sorted(
            {
                quantitative_kind_by_ref[ref]
                for ref in source_refs
                if ref in quantitative_kind_by_ref
            }
        )
        if not kinds:
            raise ValueError(
                "dynamic_research_control_context_numeric_kind_binding_missing"
            )
        card["quantitative_kinds"] = kinds
        card["reported_fact_authority"] = kinds == ["reported_fact"]

    actions = [deepcopy(dict(row)) for row in state.get("research_actions") or ()]
    action_ids = {str(row.get("action_id") or "") for row in actions}
    for cell in current.get("cells") or ():
        slots = {
            str(cell.get("primary_slot_id") or ""),
            *(str(value) for value in cell.get("supplemental_context_slot_ids") or ()),
        }
        facets = {str(value) for value in cell.get("selected_planner_facets") or ()}
        cell["allowed_research_action_refs"] = sorted(
            str(row["action_id"])
            for row in actions
            if str(row.get("slot_id") or "") in slots
            or str(row.get("facet_id") or "") in facets
        )
        if not set(cell["allowed_research_action_refs"]).issubset(action_ids):
            raise ValueError(
                "dynamic_research_control_context_action_binding_invalid"
            )

    source_snapshot = dict(state.get("source_portfolio_snapshot") or {})
    checkpoint = dict(state.get("context_checkpoint") or {})
    token_basis = dict(state.get("next_natural_node_token_budget_basis") or {})
    context_body = {
        "schema_version": DYNAMIC_RESEARCH_CONTROL_CONTEXT_SCHEMA_VERSION,
        "status": "current_action_feedback_checkpoint_bound_to_dynamic_input",
        "case_key": case_key,
        "actionable_state_ref": state.get("actionable_state_digest"),
        "evaluation_ref": evaluation.get("evaluation_digest"),
        "actionable_uncertainties": deepcopy(
            state.get("actionable_uncertainties") or []
        ),
        "research_actions": actions,
        "feedback_receipts": deepcopy(state.get("feedback_receipts") or []),
        "accepted_plan_delta": deepcopy(state.get("accepted_plan_delta") or {}),
        "accepted_plan": deepcopy(state.get("accepted_plan") or {}),
        "graph_delta": deepcopy(state.get("graph_delta") or {}),
        "stop_decision": deepcopy(state.get("stop_decision") or {}),
        "checkpoint_resume": {
            "checkpoint_id": checkpoint.get("checkpoint_id"),
            "checkpoint_digest": checkpoint.get("checkpoint_digest"),
            "open_gap_refs": deepcopy(checkpoint.get("open_gap_refs") or []),
            "unresolved_feedback_refs": deepcopy(
                checkpoint.get("unresolved_feedback_refs") or []
            ),
            "resume_receipt": deepcopy(state.get("resume_receipt") or {}),
        },
        "source_portfolio": {
            "current_source_count": source_snapshot.get("current_source_count"),
            "source_class_counts": deepcopy(
                source_snapshot.get("source_class_counts") or {}
            ),
            "rights_axes": deepcopy(source_snapshot.get("rights_axes") or []),
            "portfolio_boundary": deepcopy(
                source_snapshot.get("portfolio_boundary") or {}
            ),
        },
        "quantitative_authority": {
            "quantitative_authority_ref": quantitative.get(
                "quantitative_authority_digest"
            ),
            "summary": deepcopy(quantitative.get("summary") or {}),
            "authority_boundary": deepcopy(
                quantitative.get("authority_boundary") or {}
            ),
        },
        "next_natural_node_token_budget_basis": token_basis,
        "authority": {
            "candidate_text_exposed": False,
            "candidate_promotion_authority": False,
            "public_information_gap_authority": False,
            "reported_fact_and_derived_metric_are_distinct": True,
            "pending_action_is_not_completed_research": True,
            "natural_agent_consumption_proven_by_this_binding": False,
        },
    }
    current["research_control_context"] = {
        **context_body,
        "control_context_digest": canonical_digest(context_body),
    }
    current["known_boundary"] = (
        str(current.get("known_boundary") or "")
        + " Current typed FeedbackReceipt, PlanDelta, StopDecision and checkpoint "
        "state are bound for downstream consumption. This zero-model binding proves "
        "the runtime seam, not natural-agent reflection quality."
    )
    return {**current, "research_input_digest": canonical_digest(current)}


def compile_dynamic_research_input_projection(
    *,
    truth_spine_policy: Mapping[str, Any],
    consumer_policy: Mapping[str, Any],
    controlled_plan: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    include_actionable_control_context: bool = False,
) -> dict[str, Any]:
    """Compile the shared EvidenceResponse -> dynamic research-input path.

    The function deliberately has no Provider, network, filesystem or service
    dependency.  Both deterministic proofs and natural live runners must feed
    the same already-materialized plan and reviewed Pack through this path.
    """

    responses = compile_dynamic_evidence_responses(
        policy=truth_spine_policy,
        controlled_plan=controlled_plan,
        evidence_pack=evidence_pack,
    )
    reviewed_view: dict[str, Any] = {}
    dynamic_input: dict[str, Any] = {}
    if responses["accepted_evidence_item_digests"]:
        reviewed_view = compile_dynamic_reviewed_pack_view(
            evidence_pack=evidence_pack,
            evidence_responses=responses,
        )
        base_input = compile_current_research_input(
            policy=consumer_policy,
            evidence_pack=reviewed_view,
            controlled_plan=controlled_plan,
        )
        dynamic_input = bind_dynamic_evidence_responses_to_research_input(
            research_input=base_input,
            evidence_responses=responses,
        )
        if include_actionable_control_context:
            actionable_state = evidence_pack.get("actionable_research_state")
            quantitative_authority = evidence_pack.get("quantitative_authority")
            if not isinstance(actionable_state, Mapping) or not isinstance(
                quantitative_authority, Mapping
            ):
                raise ValueError(
                    "dynamic_research_control_context_runtime_surface_missing"
                )
            dynamic_input = bind_actionable_research_control_context(
                dynamic_research_input=dynamic_input,
                actionable_research_state=actionable_state,
                quantitative_authority=quantitative_authority,
            )
    return {
        "evidence_responses": responses,
        "reviewed_pack_view": reviewed_view,
        "dynamic_research_input": dynamic_input,
        "candidate_promotions": 0,
    }


def compile_dynamic_claim_surface_projection(
    *,
    dynamic_research_input: Mapping[str, Any],
    claim_authority_template: Mapping[str, Any],
    claim_surface_template: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one dynamic input through claim and narrative authority layers."""

    dynamic_claim_policy = compile_dynamic_claim_authority_policy(
        research_input=dynamic_research_input,
        template_policy=claim_authority_template,
    )
    claim_input = compile_claim_authority_research_input(
        dynamic_research_input,
        policy=dynamic_claim_policy,
    )
    dynamic_surface_policy = compile_dynamic_claim_surface_policy(
        claim_authority_input=claim_input,
        template_policy=claim_surface_template,
    )
    surface_input = compile_claim_surface_authority_research_input(
        claim_input,
        policy=dynamic_surface_policy,
    )
    return {
        "dynamic_claim_authority_policy": deepcopy(dynamic_claim_policy),
        "claim_authority_research_input": claim_input,
        "dynamic_claim_surface_policy": deepcopy(dynamic_surface_policy),
        "claim_surface_research_input": surface_input,
        "candidate_promotions": 0,
    }


__all__ = [
    "DYNAMIC_RESEARCH_CONTROL_CONTEXT_SCHEMA_VERSION",
    "bind_actionable_research_control_context",
    "compile_dynamic_claim_surface_projection",
    "compile_dynamic_research_input_projection",
]
