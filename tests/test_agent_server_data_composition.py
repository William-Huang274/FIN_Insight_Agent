from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any, Mapping

import pytest


pytest.importorskip("mcp", reason="agent-runtime optional dependency")

import sec_agent.agent_runtime.deepseek_structured_agents as deepseek_adapter

from sec_agent.agent_runtime.agent_server_data_composition import (
    APPROVED_DATA_SNAPSHOT_ID,
    APPROVED_RESEARCH_AS_OF,
    ApprovedDataComposition,
    ApprovedDataCompositionError,
    open_approved_data_composition,
)
from sec_agent.agent_runtime.research_graph_contracts import (
    BoundBranchTask,
    CaseFoundationBinding,
    ToolLaneResult,
    ToolLaneTask,
    canonical_sha256,
)
from sec_agent.agent_runtime.research_graph import (
    build_research_state_graph,
)
from sec_agent.research_foundation.contracts import (
    load_research_graph_foundation,
)


ROOT = Path(__file__).resolve().parents[1]


def test_task_cutoff_preserves_legacy_and_rejects_future_or_naive_time():
    from sec_agent.agent_runtime.agent_server_data_composition import task_research_as_of
    assert task_research_as_of({}) == APPROVED_RESEARCH_AS_OF
    assert task_research_as_of({'FINSIGHT_RESEARCH_AS_OF': '2026-09-10T23:00:00Z'}) == '2026-09-10T23:00:00Z'
    for value in ('9999-01-01T00:00:00Z', '2026-09-10T00:00:00'):
        with pytest.raises(ValueError):
            task_research_as_of({'FINSIGHT_RESEARCH_AS_OF': value})
FOUNDATION_PATH = (
    ROOT
    / "configs"
    / "research"
    / "reference_foundation.json"
)
EXPECTED_DECISION_DIGEST = (
    "739df0f5d2880af8e27a08b5f9e31e10e894f4900fb72681e7b02e065e89b204"
)
PHYSICAL_SELECTOR_KEYS = frozenset(
    {
        "issuer_ids",
        "fiscal_periods",
        "source_roles",
        "route_ids",
        "lanes",
        "domain_allowlist",
        "external_route_ref",
        "local_scope",
        "locator",
        "path",
    }
)
PHYSICAL_RESULT_SELECTOR_KEYS = frozenset(
    {"issuer_id", "fiscal_period", "source_role", "route_id", "lane", "branches"}
)
REVIEWED_TOPIC_REFS = (
    "capacity_inputs_execution",
    "capital_allocation_and_valuation",
    "cash_conversion_balance_sheet",
    "counterevidence_and_what_would_change",
    "demand_volume_quality",
    "management_outlook",
    "operating_performance",
    "pricing_mix_value_capture",
    "regulatory_policy_exposure",
    "relationship_attribution",
)


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return {
            *(str(key) for key in value),
            *(
                child_key
                for child in value.values()
                for child_key in _nested_keys(child)
            ),
        }
    if isinstance(value, (list, tuple)):
        return {
            child_key
            for child in value
            for child_key in _nested_keys(child)
        }
    return set()


def _foundation_binding(
    composition: ApprovedDataComposition,
) -> CaseFoundationBinding:
    foundation = load_research_graph_foundation(FOUNDATION_PATH)
    raw = composition.dependencies.foundation_binder(
        {
            "case_id": foundation.case_identity.case_id,
            "research_as_of": APPROVED_RESEARCH_AS_OF,
            "snapshot_id": APPROVED_DATA_SNAPSHOT_ID,
            "foundation_digest": canonical_sha256(foundation),
        }
    )
    # The binder deliberately returns ordinary JSON for Agent Server state.
    # Validate at that native boundary so strict tuple fields are reconstructed.
    return CaseFoundationBinding.model_validate_json(
        json.dumps(raw, ensure_ascii=False, allow_nan=False)
    )


def _route(
    composition: ApprovedDataComposition,
    *,
    branch_id: str,
    intent_kind: str,
    semantic_source_family_ref: str | None = None,
) -> Mapping[str, Any]:
    matches = [
        row
        for row in composition.dependencies.planner_source_route_catalog["routes"]
        if row["coverage_obligation_id"] == branch_id
        and row["intent_kind"] == intent_kind
        and (
            semantic_source_family_ref is None
            or tuple(row["semantic_source_family_refs"])
            == (semantic_source_family_ref,)
        )
    ]
    if intent_kind == "reviewed_evidence":
        matches = [row for row in matches if row["requirement"] == "required"]
    assert len(matches) == 1
    return matches[0]


def _reviewed_request(
    composition: ApprovedDataComposition,
) -> dict[str, Any]:
    route = _route(
        composition,
        branch_id="Q1_ISSUER_TRUTH",
        intent_kind="reviewed_evidence",
    )
    return {
        "minimum_route_obligation_id": route["minimum_route_obligation_id"],
        "intent": {
            "intent_kind": "reviewed_evidence",
            "query": "Dell AI optimized server orders revenue backlog",
            "purpose": "Retrieve reviewed Dell issuer evidence for issuer truth.",
            "entity_refs": [],
            "period_intents": [],
            "expected_information_gain": (
                "Resolve issuer performance using reviewed evidence."
            ),
            "limit": 12,
            "topic_refs": list(REVIEWED_TOPIC_REFS),
            "evidence_role_refs": [],
            "minimum_authority_tier": "reviewed",
        },
    }


def _local_request(
    composition: ApprovedDataComposition,
) -> dict[str, Any]:
    family = "F1_SEC_ISSUER_FACTS"
    route = _route(
        composition,
        branch_id="Q1_ISSUER_TRUTH",
        intent_kind="local_evidence",
        semantic_source_family_ref=family,
    )
    return {
        "minimum_route_obligation_id": route["minimum_route_obligation_id"],
        "intent": {
            "intent_kind": "local_evidence",
            "query": (
                "Dell FY2027 Q1 revenue gross profit operating income "
                "infrastructure solutions group servers"
            ),
            "purpose": (
                "Retrieve primary Dell filing candidate blocks for issuer truth."
            ),
            "entity_refs": [],
            "period_intents": [],
            "expected_information_gain": (
                "Locate structured filing sections relevant to operating performance."
            ),
            "limit": 6,
            "semantic_source_family_refs": [family],
            "source_role_intents": [],
            "content_surface_intents": ["prose", "table"],
        },
    }


def _external_request(
    composition: ApprovedDataComposition,
) -> dict[str, Any]:
    family = "F2_DELL_IR_EARNINGS"
    route = _route(
        composition,
        branch_id="Q1_ISSUER_TRUTH",
        intent_kind="external_source",
        semantic_source_family_ref=family,
    )
    return {
        "minimum_route_obligation_id": route["minimum_route_obligation_id"],
        "intent": {
            "intent_kind": "external_source",
            "query": "Dell fiscal 2027 second quarter AI server earnings release",
            "purpose": "Retrieve frozen Dell investor relations source candidate.",
            "entity_refs": [],
            "period_intents": [],
            "expected_information_gain": (
                "Locate the exact investor relations source without live web access."
            ),
            "limit": 2,
            "semantic_source_family_refs": [family],
            "domain_allowlist": [],
        },
    }


def _branch_task(
    composition: ApprovedDataComposition,
    *,
    label: str,
    evidence_request: Mapping[str, Any],
    fact_requests: tuple[dict[str, Any], ...] = (),
) -> BoundBranchTask:
    foundation = _foundation_binding(composition)
    method = next(
        row
        for row in foundation.branch_methods
        if row.branch_id == "Q1_ISSUER_TRUTH"
    )
    return BoundBranchTask(
        task_id=f"data-composition-test:{label}",
        case_id=foundation.case_id,
        branch_id=method.branch_id,
        revision=0,
        priority=method.priority,
        objective=method.objective,
        evidence_requests=(dict(evidence_request),),
        fact_requests=fact_requests,
        research_as_of=foundation.research_as_of,
        snapshot_id=foundation.snapshot_id,
        foundation_digest=foundation.foundation_digest,
        method_digest=method.method_digest,
        plan_digest=canonical_sha256({"test_task": label}),
    )


def _execute_evidence(
    composition: ApprovedDataComposition,
    *,
    label: str,
    request: Mapping[str, Any],
) -> ToolLaneResult:
    lane_task = ToolLaneTask(
        lane="evidence",
        task=_branch_task(
            composition,
            label=label,
            evidence_request=request,
        ),
    )
    raw = composition.dependencies.evidence_tool(lane_task.model_dump(mode="json"))
    return ToolLaneResult.model_validate_json(
        json.dumps(raw, ensure_ascii=False, allow_nan=False)
    )


def test_composition_fails_closed_when_repository_root_is_missing() -> None:
    with pytest.raises(
        ApprovedDataCompositionError,
        match="^approved_repository_root_missing$",
    ):
        with open_approved_data_composition(
            run_invocation_id="missing-root",
            environment={},
        ):
            pass


def test_composition_fails_closed_when_required_data_path_is_missing() -> None:
    with pytest.raises(
        ApprovedDataCompositionError,
        match=(
            "^approved_data_path_environment_missing:"
            "FINSIGHT_DELL_S1_NODES_PATH$"
        ),
    ):
        with open_approved_data_composition(
            run_invocation_id="missing-data-path",
            environment={"FIN_REPO_ROOT": str(ROOT)},
        ):
            pass
