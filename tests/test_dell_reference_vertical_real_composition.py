from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


pytest.importorskip("mcp", reason="agent-runtime optional dependency")

from sec_agent.agent_runtime.dell_agent_server_data_composition import (
    DELL_APPROVED_DATA_SNAPSHOT_ID,
    DELL_APPROVED_RESEARCH_AS_OF,
    DellApprovedDataCompositionError,
    open_dell_approved_data_composition,
)
from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
    BoundBranchTask,
    CaseFoundationBinding,
    ToolLaneResult,
    ToolLaneTask,
    canonical_sha256,
)
from sec_agent.agent_runtime.dell_reference_vertical_graph import (
    build_dell_reference_vertical_state_graph,
)
from sec_agent.agent_runtime.dell_zero_model_graph_qualification import (
    ZERO_MODEL_EXECUTION_PROFILE,
)
from sec_agent.research_foundation.contracts import (
    load_dell_reference_vertical_foundation,
)


ROOT = Path(__file__).resolve().parents[1]
FOUNDATION_PATH = (
    ROOT
    / "configs/research/fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
)
STRUCTURED_NODES_PATH = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/rag_mature_stack/"
    "retrieval_qualification/dell_rag_full_stack_preview_attempt_20260902_03/"
    "retrieval_nodes.jsonl"
)
REVIEWED_BASE_PACK_PATH = (
    ROOT
    / "data/workbench_private/fin_0_1_3_s1_dell_direct_source_evidence/"
    "r4/successor/pack.json"
)
REVIEWED_OVERLAY_PATH = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/evidence_overlay/"
    "attempts/20260902T051005+0800-dell-fy27q2-sec-ex99-review-a01/"
    "reviewed-evidence-case-projection.json"
)
S2_DIRECTORY = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/s2/"
    "s2_exact_period_contract_successor_20260902_r1"
)
S2_RESULT_PATH = S2_DIRECTORY / "company_financial_fact_mart_result.json"
S2_MART_PATH = S2_DIRECTORY / "company_financial_facts.sqlite"
EXTERNAL_MANIFEST_PATH = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
    "external_exact_url_qualification/"
    "dell_external_exact_url_zero_model_20260902_r12/manifest.json"
)
RUN_INVOCATION_ID = "test:dell-owner-approved-real-composition"
PLAN_DIGEST = canonical_sha256(
    {"test": "owner-approved semantic compiler and MCP composition"}
)

RUNTIME_ENVIRONMENT = {
    "FIN_REPO_ROOT": str(ROOT),
    "FINSIGHT_DELL_S1_NODES_PATH": str(STRUCTURED_NODES_PATH),
    "FINSIGHT_DELL_REVIEWED_BASE_PACK_PATH": str(REVIEWED_BASE_PACK_PATH),
    "FINSIGHT_DELL_REVIEWED_OVERLAY_PATH": str(REVIEWED_OVERLAY_PATH),
    "FINSIGHT_DELL_S2_RESULT_PATH": str(S2_RESULT_PATH),
    "FINSIGHT_COMPANY_FINANCIAL_FACT_MART_PATH": str(S2_MART_PATH),
    "FINSIGHT_DELL_EXTERNAL_MANIFEST_PATH": str(EXTERNAL_MANIFEST_PATH),
}

pytestmark = pytest.mark.local_data_integration


def _catalog_route(
    catalog: Mapping[str, Any],
    route_id: str,
) -> dict[str, Any]:
    matches = [
        dict(row)
        for row in catalog["routes"]
        if row["minimum_route_obligation_id"] == route_id
    ]
    assert len(matches) == 1
    return matches[0]


def _semantic_request(
    route: Mapping[str, Any],
    *,
    query: str,
) -> dict[str, Any]:
    intent_kind = str(route["intent_kind"])
    shared = {
        "intent_kind": intent_kind,
        "query": query,
        "purpose": "Exercise one exact Owner-approved semantic source route.",
        "entity_refs": [],
        "period_intents": [],
        "expected_information_gain": (
            "Determine whether the frozen data plane can serve the exact route."
        ),
        "limit": 3,
    }
    if intent_kind == "reviewed_evidence":
        intent = {
            **shared,
            "entity_refs": ["DELL"],
            "topic_refs": ["operating_performance"],
            "evidence_role_refs": [],
            "minimum_authority_tier": "reviewed",
        }
    elif intent_kind == "local_evidence":
        intent = {
            **shared,
            "semantic_source_family_refs": list(
                route["semantic_source_family_refs"]
            ),
            "source_role_intents": [],
            "content_surface_intents": ["prose", "table"],
        }
    elif intent_kind == "external_source":
        intent = {
            **shared,
            "semantic_source_family_refs": list(
                route["semantic_source_family_refs"]
            ),
            "domain_allowlist": [],
            "published_not_before": None,
            "published_not_after": None,
        }
    else:  # pragma: no cover - catalog validation owns this invariant
        raise AssertionError(f"unexpected semantic intent kind: {intent_kind}")
    return {
        "minimum_route_obligation_id": route[
            "minimum_route_obligation_id"
        ],
        "intent": intent,
    }


def _foundation_binding(dependencies: Any) -> CaseFoundationBinding:
    foundation = load_dell_reference_vertical_foundation(FOUNDATION_PATH)
    request = {
        "case_id": foundation.case_identity.case_id,
        "research_as_of": DELL_APPROVED_RESEARCH_AS_OF,
        "snapshot_id": DELL_APPROVED_DATA_SNAPSHOT_ID,
        "foundation_digest": canonical_sha256(foundation),
    }
    return CaseFoundationBinding.model_validate_json(
        json.dumps(dependencies.foundation_binder(request))
    )


def _lane_task(
    *,
    binding: CaseFoundationBinding,
    lane: str,
    branch_id: str,
    evidence_requests: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    method = next(
        row for row in binding.branch_methods if row.branch_id == branch_id
    )
    task = BoundBranchTask(
        task_id=f"task:{branch_id}:{lane}:real-composition",
        case_id=binding.case_id,
        branch_id=branch_id,
        revision=0,
        priority=method.priority,
        objective="Exercise frozen semantic compilation through the MCP lane.",
        evidence_requests=evidence_requests,
        fact_requests=(
            {
                "ticker": "DELL",
                "metric_ids": ["revenue"],
                "granularity": "quarter_discrete",
                "period_start": None,
                "period_end": None,
                "selection_mode": "latest_on_or_before",
                "fiscal_years": [],
                "requested_unit": "reported_source_unit",
                "unit_family": None,
            },
        ),
        research_as_of=binding.research_as_of,
        snapshot_id=binding.snapshot_id,
        foundation_digest=binding.foundation_digest,
        method_digest=method.method_digest,
        plan_digest=PLAN_DIGEST,
    )
    return ToolLaneTask(lane=lane, task=task).model_dump(mode="json")


def _assert_runtime_assets_present() -> None:
    missing = [
        str(path)
        for path in (
            FOUNDATION_PATH,
            STRUCTURED_NODES_PATH,
            REVIEWED_BASE_PACK_PATH,
            REVIEWED_OVERLAY_PATH,
            S2_RESULT_PATH,
            S2_MART_PATH,
            EXTERNAL_MANIFEST_PATH,
        )
        if not path.is_file()
    ]
    assert not missing, f"Owner-approved local integration assets missing: {missing}"


def test_owner_approved_semantic_compiler_and_mcp_real_composition() -> None:
    """Prove the frozen data plane without a local graph or model execution."""

    _assert_runtime_assets_present()
    with open_dell_approved_data_composition(
        run_invocation_id=RUN_INVOCATION_ID,
        environment=RUNTIME_ENVIRONMENT,
    ) as composition:
        assert composition.reviewed_evidence_count == 56
        assert composition.s2_observation_count == 1_319
        assert composition.external_route_count == 12
        assert composition.local_candidate_count == 890
        assert composition.model_calls_authorized is False
        assert composition.network_calls_authorized is False
        assert composition.paid_calls_authorized is False

        dependencies = composition.dependencies
        catalog = dependencies.planner_source_route_catalog
        assert catalog["catalog_digest"] == composition.source_route_catalog_digest
        assert catalog["physical_selectors_exposed"] is False
        assert catalog["answer_free"] is True
        serialized_catalog = json.dumps(catalog, ensure_ascii=False)
        for physical_key in (
            '"source_route"',
            '"issuer_ids"',
            '"route_ids"',
            '"lanes"',
            '"domain_allowlist"',
            '"external_route_ref"',
        ):
            assert physical_key not in serialized_catalog

        routes = tuple(catalog["routes"])
        required_reviewed = [
            row
            for row in routes
            if row["requirement"] == "required"
            and row["intent_kind"] == "reviewed_evidence"
        ]
        assert len(required_reviewed) == 9
        route_ids = {
            row["minimum_route_obligation_id"] for row in routes
        }
        assert "route:Q3_UNITS_ASP_PVM:F3_DELL_PRODUCT_SUPPORT:local" not in route_ids
        assert (
            "route:Q4_ARCHITECTURE_RAMP:F4_CUSTOMER_CAPEX_DEPLOYMENT:local"
            not in route_ids
        )
        assert not any(
            row["coverage_obligation_id"] == "Q9_COUNTEREVIDENCE_WWC"
            and row["intent_kind"] == "external_source"
            for row in routes
        )

        reviewed_route = _catalog_route(
            catalog, "route:Q1_ISSUER_TRUTH:required-reviewed"
        )
        local_route = _catalog_route(
            catalog, "route:Q1_ISSUER_TRUTH:F2_DELL_IR_EARNINGS:local"
        )
        external_route = _catalog_route(
            catalog, "route:Q1_ISSUER_TRUTH:F2_DELL_IR_EARNINGS:external"
        )
        semantic_requests = (
            _semantic_request(
                reviewed_route,
                query="Dell operating performance and infrastructure demand",
            ),
            _semantic_request(
                local_route,
                query="Dell earnings infrastructure demand commentary",
            ),
            _semantic_request(
                external_route,
                query="Dell investor relations infrastructure demand update",
            ),
        )
        assert all("intent" in request for request in semantic_requests)
        assert all("source_route" not in request for request in semantic_requests)

        binding = _foundation_binding(dependencies)
        evidence = ToolLaneResult.model_validate_json(
            json.dumps(
                dependencies.evidence_tool(
                    _lane_task(
                        binding=binding,
                        lane="evidence",
                        branch_id="Q1_ISSUER_TRUTH",
                        evidence_requests=semantic_requests,
                    )
                )
            )
        )
        finance = ToolLaneResult.model_validate_json(
            json.dumps(
                dependencies.finance_tool(
                    _lane_task(
                        binding=binding,
                        lane="finance",
                        branch_id="Q1_ISSUER_TRUTH",
                        evidence_requests=(semantic_requests[0],),
                    )
                )
            )
        )

        assert evidence.status == "success", evidence.model_dump(mode="json")
        assert {
            "reviewed_evidence",
            "retrieval_candidate",
            "captured_source_candidate",
        }.issubset(evidence.result_states)
        assert finance.status == "success"
        assert "numeric_fact" in finance.result_states
        assert any(
            item.get("writer_citable") is True
            for item in evidence.items
            if item.get("result_state") == "reviewed_evidence"
        )
        assert any(
            item.get("structured_document_tree") is True
            for item in evidence.items
            if item.get("result_state") == "retrieval_candidate"
        )
        captured = next(
            item
            for item in evidence.items
            if item.get("result_state") == "captured_source_candidate"
        )
        assert captured["captured_candidate_is_not_evidence"] is True
        assert captured["admission_required_before_citation"] is True
        assert captured["source_capture_authority"] is False
        assert captured["citation_eligible"] is False
        assert all(
            item.get("numeric_fact_authority") is True
            for item in finance.items
            if item.get("result_state") == "numeric_fact"
        )

        compilation_receipts = {
            receipt["receipt_digest"]: receipt
            for item in evidence.items
            for receipt in item.get("mcp_receipt_chain", [])
            if receipt.get("contract_version") == "1.2"
            and "receipt_digest" in receipt
        }
        assert {
            receipt["intent_kind"]
            for receipt in compilation_receipts.values()
        } == {"reviewed_evidence", "local_evidence", "external_source"}
        assert all(
            receipt["tool_call_authorized"] is True
            for receipt in compilation_receipts.values()
        )

        serialized_results = json.dumps(
            {
                "evidence": evidence.model_dump(mode="json"),
                "finance": finance.model_dump(mode="json"),
            },
            ensure_ascii=False,
        )
        assert "Z:/" not in serialized_results
        assert "Z:\\" not in serialized_results
        assert "D:/" not in serialized_results
        assert "D:\\" not in serialized_results

        with pytest.raises(
            DellApprovedDataCompositionError,
            match="model_execution_not_authorized",
        ):
            dependencies.planner_agent({})


def test_real_composition_runs_zero_model_graph_to_interrupt_and_resume() -> None:
    """Exercise the real bounded graph/MCP path without any model-owned port."""

    _assert_runtime_assets_present()
    foundation = load_dell_reference_vertical_foundation(FOUNDATION_PATH)
    run_id = "test:dell-zero-model-real-graph"
    with open_dell_approved_data_composition(
        run_invocation_id=f"{RUN_INVOCATION_ID}:zero-model-graph",
        environment=RUNTIME_ENVIRONMENT,
    ) as composition:
        graph = build_dell_reference_vertical_state_graph(
            dependencies=composition.dependencies,
            execution_profile=ZERO_MODEL_EXECUTION_PROFILE,
        ).compile(
            checkpointer=InMemorySaver(),
            name="dell_zero_model_real_composition_test",
        )
        config = {"configurable": {"thread_id": run_id}}
        interrupted = graph.invoke(
            {
                "run_id": run_id,
                "case_id": foundation.case_identity.case_id,
                "research_question": (
                    foundation.case_identity.top_level_question_zh
                ),
                "research_as_of": DELL_APPROVED_RESEARCH_AS_OF,
                "snapshot_id": DELL_APPROVED_DATA_SNAPSHOT_ID,
                "foundation_digest": canonical_sha256(foundation),
            },
            config,
        )

        assert interrupted["phase"] == "zero_model_mcp_qualified"
        assert "__interrupt__" in interrupted
        summary = interrupted["zero_model_qualification_summary"]
        assert summary["tool_lane_execution_count"] == 2
        assert summary["mcp_call_count"] > 0
        assert summary["mcp_error_call_count"] == 0
        assert sum(summary["mcp_tool_call_counts"].values()) == summary[
            "mcp_call_count"
        ]
        assert summary["model_call_count"] == 0
        assert summary["live_external_research_call_count"] == 0
        assert summary["paid_call_count"] == 0
        safe_summary = json.dumps(summary, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "bounded_excerpt",
            "source_url",
            "value_decimal",
            "citation_urls",
            "Z:/",
            "Z:\\",
            "D:/",
            "D:\\",
            "/run/fin-insight",
            "postgres://",
            "redis://",
        ):
            assert forbidden not in safe_summary

        completed = graph.invoke(
            Command(
                resume={
                    "action": "complete_zero_model_qualification",
                    "reason": "real composition checkpoint verified",
                }
            ),
            config,
        )

        assert completed["phase"] == "zero_model_control_plane_completed"
        assert completed["zero_model_qualification_summary"] == summary
        assert completed["final_report"] is None


def test_compiler_backed_real_composition_rejects_legacy_physical_request() -> None:
    """A real data composition must never fall back to the legacy provider surface."""

    _assert_runtime_assets_present()
    with open_dell_approved_data_composition(
        run_invocation_id=f"{RUN_INVOCATION_ID}:legacy-negative",
        environment=RUNTIME_ENVIRONMENT,
    ) as composition:
        binding = _foundation_binding(composition.dependencies)
        physical_request = {
            "query": "Dell operating performance",
            "purpose": "This legacy request must not reach any data reader.",
            "issuer_ids": ["DELL"],
            "source_roles": ["issuer_management_disclosure"],
            "source_route": "reviewed_first",
            "limit": 3,
            "capture_limit": 1,
        }
        result = ToolLaneResult.model_validate_json(
            json.dumps(
                composition.dependencies.evidence_tool(
                    _lane_task(
                        binding=binding,
                        lane="evidence",
                        branch_id="Q1_ISSUER_TRUTH",
                        evidence_requests=(physical_request,),
                    )
                )
            )
        )

    assert result.status == "tool_failure"
    assert result.failure is not None
    assert result.failure.code == "mcp_legacy_physical_evidence_request_forbidden"
    assert result.result_states == ("tool_failure",)
