from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

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
    bind_dynamic_evidence_responses_to_research_input,
    compile_dynamic_claim_authority_policy,
    compile_dynamic_claim_surface_policy,
    compile_dynamic_evidence_responses,
    compile_dynamic_reviewed_pack_view,
)


def compile_dynamic_research_input_projection(
    *,
    truth_spine_policy: Mapping[str, Any],
    consumer_policy: Mapping[str, Any],
    controlled_plan: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
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
    "compile_dynamic_claim_surface_projection",
    "compile_dynamic_research_input_projection",
]
