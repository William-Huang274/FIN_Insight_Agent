from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json

import pytest


pytest.importorskip("mcp", reason="agent-runtime optional dependency")

import sec_agent.agent_runtime.dell_reference_vertical_mcp_tools as mcp_tools_module

from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
    BoundBranchTask,
    EvidenceRequest,
    ToolLaneResult,
    ToolLaneTask,
    canonical_sha256,
)
from sec_agent.agent_runtime.deepseek_structured_agents import (
    PlannerSemanticPayload,
)
from sec_agent.agent_runtime.dell_source_family_compiler import SourceFamilyCompiler
from sec_agent.agent_runtime.dell_reference_vertical_mcp_tools import (
    DellMCPToolLaneAdapter,
    compose_dell_mcp_graph_run,
)
from sec_agent.agent_runtime.dell_reference_vertical_graph import _validate_tool_result
from sec_agent.research_foundation.mcp_server import (
    CAPTURE_EXTERNAL_SOURCE_TOOL,
    GET_RESEARCH_METHOD_TOOL,
    QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_BY_ID_TOOL,
    SEARCH_EXTERNAL_SOURCES_TOOL,
    SEARCH_LOCAL_KNOWLEDGE_TOOL,
    SEARCH_REVIEWED_EVIDENCE_TOOL,
)
from sec_agent.research_foundation.contracts import (
    load_dell_reference_vertical_foundation,
    project_dell_research_method,
)
from test_dell_research_mcp import _build_server
from test_dell_source_family_compiler import (
    baseline as _compiler_baseline_fixture,
    inventory as _compiler_inventory_fixture,
)


_BRANCH = "Q1_ISSUER_TRUTH"
_BRANCHES = (_BRANCH, "Q2_DEMAND_QUALITY")
_CASE = "DELL_AI_INFRA_REFERENCE_VERTICAL"
_SNAPSHOT = "DELL-MCP-TEST-SNAPSHOT-01"
_PLAN_DIGEST = "c" * 64
_AS_OF = datetime(2026, 9, 2, 2, 0, tzinfo=timezone.utc).isoformat()
_FOUNDATION = load_dell_reference_vertical_foundation()
_COMPOSITION = compose_dell_mcp_graph_run(
    _FOUNDATION,
    branch_ids=_BRANCHES,
    research_as_of=_AS_OF,
    snapshot_id=_SNAPSHOT,
    execution_attempt_id="DELL-MCP-ADAPTER-A01",
)
_FOUNDATION_DIGEST = _COMPOSITION.foundation_binding.foundation_digest
_METHOD_DIGEST = next(
    row.method_digest
    for row in _COMPOSITION.foundation_binding.branch_methods
    if row.branch_id == _BRANCH
)
_FULL_METHOD_DIGEST = project_dell_research_method(
    _FOUNDATION, _BRANCHES
).method_sha256
_COMPILER_INVENTORY = _compiler_inventory_fixture.__wrapped__()
_COMPILER_BASELINE = _compiler_baseline_fixture.__wrapped__(_COMPILER_INVENTORY)
_SOURCE_FAMILY_COMPILER = SourceFamilyCompiler(
    inventory=_COMPILER_INVENTORY,
    baseline=_COMPILER_BASELINE,
)


def _binding():
    return _COMPOSITION.mcp_run_binding


def test_run_composition_projects_foundation_specialist_round_authority() -> None:
    ceiling = _COMPOSITION.foundation_binding.scope_ceiling

    assert ceiling.maximum_specialist_model_rounds == 2
    assert ceiling.maximum_specialist_model_rounds == (
        1 + ceiling.maximum_targeted_counter_reroutes
    )


def _task(
    lane: str,
    *,
    branch_id: str = _BRANCH,
    evidence_request: dict | None = None,
) -> dict:
    task = BoundBranchTask(
        task_id=f"task:{branch_id}:r0:adapter",
        case_id=_CASE,
        branch_id=branch_id,
        revision=0,
        priority="high",
        objective="Exercise the official MCP client tool lane.",
        evidence_requests=(
            evidence_request
            or {
                "query": "Dell AI server backlog definition",
                "purpose": "Locate reviewed issuer evidence for the bounded branch.",
                "source_route": "reviewed_first",
                "issuer_ids": ["DELL"],
                "fiscal_periods": ["FY2027_Q1"],
                "source_roles": ["issuer_management_disclosure"],
            },
        ),
        fact_requests=(
            {
                "ticker": "DELL",
                "metric_ids": ["revenue"],
                "granularity": "quarter_discrete",
                "period_end": "2026-05-01",
                "selection_mode": "exact_period_end",
            },
        ),
        research_as_of=_AS_OF,
        snapshot_id=_SNAPSHOT,
        foundation_digest=_FOUNDATION_DIGEST,
        method_digest=next(
            row.method_digest
            for row in _COMPOSITION.foundation_binding.branch_methods
            if row.branch_id == branch_id
        ) if branch_id in _BRANCHES else _METHOD_DIGEST,
        plan_digest=_PLAN_DIGEST,
    )
    return ToolLaneTask(lane=lane, task=task).model_dump(mode="json")


def _tool_names(result: dict) -> list[str]:
    names: list[str] = []
    for item in result["items"]:
        assert item["cell_binding_used"] is False
        for receipt in item["mcp_receipt_chain"]:
            names.append(receipt["tool_name"])
            assert len(receipt["tool_discovery_digest"]) == 64
            assert len(receipt["request_digest"]) == 64
    return names


def test_sync_facade_discovers_and_calls_non_cell_mcp_tools_with_bound_scope() -> None:
    with DellMCPToolLaneAdapter(
        _build_server(),
        run_binding=_binding(),
    ) as adapter:
        evidence = adapter.evidence_tool(_task("evidence"))
        finance = adapter.finance_tool(_task("finance"))

    assert evidence["status"] == "success"
    assert evidence["result_states"] == ["typed_gap"]
    assert evidence["items"][0]["public_information_gap_proved"] is False
    evidence_tools = _tool_names(evidence)
    assert evidence_tools == [
        GET_RESEARCH_METHOD_TOOL,
        SEARCH_REVIEWED_EVIDENCE_TOOL,
        SEARCH_LOCAL_KNOWLEDGE_TOOL,
    ]

    assert finance["status"] == "success"
    assert finance["result_states"] == ["typed_gap"]
    finance_tools = _tool_names(finance)
    assert finance_tools == [
        GET_RESEARCH_METHOD_TOOL,
        QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
    ]
    assert finance["items"][0]["metric_id"] == "revenue"

    for lane, output in (("evidence", evidence), ("finance", finance)):
        lane_task = ToolLaneTask.model_validate_json(json.dumps(_task(lane)))
        validated = ToolLaneResult.model_validate_json(json.dumps(output))
        _validate_tool_result(validated, lane_task=lane_task)


def test_finance_lane_requires_explicit_period_selection_mode() -> None:
    request = _task("finance")
    request["task"]["fact_requests"][0].pop("selection_mode")

    with DellMCPToolLaneAdapter(
        _build_server(),
        run_binding=_binding(),
    ) as adapter:
        result = adapter.finance_tool(request)

    assert result["status"] == "tool_failure"
    assert result["failure"]["owner_layer"] == "s2_tool"
    assert result["failure"]["code"] == "mcp_fact_selection_mode_required"


def test_finance_lane_rejects_response_query_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with DellMCPToolLaneAdapter(
        _build_server(),
        run_binding=_binding(),
    ) as adapter:
        original_call = adapter._call

        def substitute_query(name: str, arguments: dict) -> object:
            call = original_call(name, arguments)
            if name != QUERY_COMPANY_FINANCIAL_FACTS_TOOL or call.content is None:
                return call
            content = json.loads(json.dumps(call.content))
            content["query"]["period_end"] = "2026-04-30"
            content["query_digest"] = canonical_sha256(
                {
                    key: value
                    for key, value in content.items()
                    if key != "query_digest"
                }
            )
            return mcp_tools_module._Call(
                content=content,
                error=False,
                failure_kind=None,
                receipt={
                    **call.receipt,
                    "output_digest": canonical_sha256(content),
                },
            )

        monkeypatch.setattr(adapter, "_call", substitute_query)
        result = adapter.finance_tool(_task("finance"))

    assert result["status"] == "tool_failure"
    assert result["failure"]["owner_layer"] == "s2_tool"
    assert result["failure"]["code"] == (
        "mcp_financial_response_query_binding_mismatch"
    )


def test_finance_lane_rejects_resolved_fact_from_another_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with DellMCPToolLaneAdapter(
        _build_server(),
        run_binding=_binding(),
    ) as adapter:
        original_call = adapter._call

        def substitute_fact_period(name: str, arguments: dict) -> object:
            call = original_call(name, arguments)
            if name != QUERY_COMPANY_FINANCIAL_FACTS_TOOL or call.content is None:
                return call
            content = json.loads(json.dumps(call.content))
            row = content["results"][0]
            row.update(
                {
                    "status": "resolved",
                    "facts": [
                        {
                            "schema_version": "fin_ia_numeric_fact_v1_0",
                            "numeric_fact_id": "NUMFACT::SUBSTITUTED",
                            "fact_request_id": row["fact_request_id"],
                            "ticker": "DELL",
                            "metric_id": "revenue",
                            "value_decimal": "100",
                            "unit": "USD",
                            "unit_family": "currency",
                            "period_start": "2025-11-01",
                            "period_end": "2026-04-30",
                            "period_role": "quarter_discrete",
                            "fiscal_year": 2027,
                            "fiscal_period": "Q1",
                            "research_as_of": "2026-09-02",
                            "authority_mode": "company_reported_exact",
                            "accession_numbers": ["0001571996-26-000030"],
                            "accepted_at": "2026-06-09T20:11:41+00:00",
                            "source_observation_ids": ["OBS::SUBSTITUTED"],
                            "citation_urls": [
                                "https://www.sec.gov/Archives/example"
                            ],
                            "source_digests": ["a" * 64],
                            "formula_trace": None,
                            "numeric_fact_authority": True,
                        }
                    ],
                    "typed_gap": None,
                    "typed_conflict": None,
                }
            )
            content["resolved_metric_count"] = 1
            content["typed_gap_count"] = 0
            content["typed_conflict_count"] = 0
            content["query_digest"] = canonical_sha256(
                {
                    key: value
                    for key, value in content.items()
                    if key != "query_digest"
                }
            )
            return mcp_tools_module._Call(
                content=content,
                error=False,
                failure_kind=None,
                receipt={
                    **call.receipt,
                    "output_digest": canonical_sha256(content),
                },
            )

        monkeypatch.setattr(adapter, "_call", substitute_fact_period)
        result = adapter.finance_tool(_task("finance"))

    assert result["status"] == "tool_failure"
    assert result["failure"]["owner_layer"] == "s2_tool"
    assert result["failure"]["code"] == (
        "mcp_financial_fact_exact_period_binding_mismatch"
    )


def test_exact_local_route_never_suppresses_reviewed_first_search() -> None:
    request = _task(
        "evidence",
        evidence_request={
            "query": "Dell FY27 Q1 performance review pricing units",
            "purpose": "Require the exact official route without substitution.",
            "source_route": "reviewed_first",
            "issuer_ids": ["DELL"],
            "source_roles": ["issuer_management_disclosure"],
            "route_ids": ["dell_fy2027_q1_performance_review"],
            "limit": 3,
        },
    )
    with DellMCPToolLaneAdapter(_build_server(), run_binding=_binding()) as adapter:
        result = adapter.evidence_tool(request)

    assert result["status"] == "success"
    assert _tool_names(result) == [
        GET_RESEARCH_METHOD_TOOL,
        SEARCH_REVIEWED_EVIDENCE_TOOL,
        SEARCH_LOCAL_KNOWLEDGE_TOOL,
    ]
    gap = next(item for item in result["items"] if item.get("gap_code"))
    assert gap["gap_code"] == "exact_route_local_candidate_unavailable"
    assert gap["retrieval_scope"]["route_ids"] == [
        "dell_fy2027_q1_performance_review"
    ]


def test_unscoped_reviewed_hit_does_not_suppress_scoped_local_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with DellMCPToolLaneAdapter(_build_server(), run_binding=_binding()) as adapter:
        original_call = adapter._call

        def reviewed_hit(name: str, arguments: dict) -> object:
            call = original_call(name, arguments)
            if call.content is None:
                return call
            content = json.loads(json.dumps(call.content))
            if name == SEARCH_REVIEWED_EVIDENCE_TOOL:
                content["hits"] = [{"evidence_id": "EV::SCOPETEST"}]
            elif name == READ_REVIEWED_EVIDENCE_BY_ID_TOOL:
                content["evidence"] = [
                    {
                        "authority_state": "reviewed_evidence",
                        "writer_citable": True,
                        "evidence_id": "EV::SCOPETEST",
                    }
                ]
                content["missing_evidence_ids"] = []
            else:
                return call
            return mcp_tools_module._Call(
                content=content,
                error=False,
                failure_kind=None,
                receipt={
                    **call.receipt,
                    "output_digest": canonical_sha256(content),
                },
            )

        monkeypatch.setattr(adapter, "_call", reviewed_hit)
        result = adapter.evidence_tool(_task("evidence"))

    assert result["status"] == "success"
    assert result["result_states"] == ["reviewed_evidence", "typed_gap"]
    tool_names = _tool_names(result)
    assert SEARCH_REVIEWED_EVIDENCE_TOOL in tool_names
    assert READ_REVIEWED_EVIDENCE_BY_ID_TOOL in tool_names
    assert tool_names[-1] == SEARCH_LOCAL_KNOWLEDGE_TOOL


def test_local_response_scope_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with DellMCPToolLaneAdapter(_build_server(), run_binding=_binding()) as adapter:
        original_call = adapter._call

        def drift_scope(name: str, arguments: dict) -> object:
            call = original_call(name, arguments)
            if name != SEARCH_LOCAL_KNOWLEDGE_TOOL or call.content is None:
                return call
            content = dict(call.content)
            content["retrieval_scope"] = {
                **dict(content["retrieval_scope"]),
                "issuer_ids": ["NVIDIA"],
            }
            return mcp_tools_module._Call(
                content=content,
                error=False,
                failure_kind=None,
                receipt=call.receipt,
            )

        monkeypatch.setattr(adapter, "_call", drift_scope)
        result = adapter.evidence_tool(
            _task(
                "evidence",
                evidence_request={
                    "query": "Dell exact local result",
                    "purpose": "Reject a response outside the request scope.",
                    "source_route": "local_only",
                    "issuer_ids": ["DELL"],
                    "source_roles": ["issuer_management_disclosure"],
                    "limit": 2,
                },
            )
        )

    assert result["status"] == "tool_failure"
    assert result["failure"]["owner_layer"] == "s1_tool"
    assert result["failure"]["code"] == "mcp_local_scope_binding_failed"


def test_local_evidence_request_requires_bounded_issuer_and_source_role() -> None:
    with pytest.raises(ValueError, match="local_evidence_request_scope_underbounded"):
        EvidenceRequest(
            query="unbounded local query",
            purpose="This must not silently search the full corpus.",
            source_route="local_only",
        )

    normalized = EvidenceRequest(
        query="bounded local query",
        purpose="Canonicalize issuer identity before MCP dispatch.",
        source_route="local_only",
        issuer_ids=["dell"],
        source_roles=["issuer_management_disclosure"],
    )
    assert normalized.issuer_ids == ("DELL",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("issuer_ids", " "),
        ("issuer_ids", "DELL/../../"),
        ("source_roles", " "),
        ("source_roles", "issuer management disclosure"),
        ("fiscal_periods", " "),
        ("fiscal_periods", "FY2027/Q1"),
        ("route_ids", " "),
        ("route_ids", "https://example.com/source"),
    ],
)
def test_local_evidence_request_rejects_blank_or_invalid_scope_ids(
    field: str,
    value: str,
) -> None:
    payload = {
        "query": "bounded local query",
        "purpose": "Reject malformed answer-free metadata scope.",
        "source_route": "local_only",
        "issuer_ids": ["DELL"],
        "source_roles": ["issuer_management_disclosure"],
        field: [value],
    }

    with pytest.raises(
        ValueError,
        match="evidence_request_retrieval_scope_value_invalid",
    ):
        EvidenceRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("fact_overrides", "request_overrides", "expected_code"),
    [
        (
            {"fact_request_id": "MCPFACT::WRONG"},
            {},
            "mcp_financial_fact_identity_binding_mismatch",
        ),
        (
            {"period_role": "instant"},
            {},
            "mcp_financial_fact_granularity_binding_mismatch",
        ),
        (
            {"unit_family": "percentage"},
            {"unit_family": "currency"},
            "mcp_financial_fact_unit_family_binding_mismatch",
        ),
    ],
)
def test_finance_lane_rejects_cross_field_fact_substitution(
    monkeypatch: pytest.MonkeyPatch,
    fact_overrides: dict,
    request_overrides: dict,
    expected_code: str,
) -> None:
    request = _task("finance")
    request["task"]["fact_requests"][0].update(request_overrides)
    with DellMCPToolLaneAdapter(
        _build_server(), run_binding=_binding()
    ) as adapter:
        original_call = adapter._call

        def substitute_fact(name: str, arguments: dict) -> object:
            call = original_call(name, arguments)
            if name != QUERY_COMPANY_FINANCIAL_FACTS_TOOL or call.content is None:
                return call
            content = json.loads(json.dumps(call.content))
            row = content["results"][0]
            fact = {
                "schema_version": "fin_ia_numeric_fact_v1_0",
                "numeric_fact_id": "NUMFACT::SUBSTITUTED",
                "fact_request_id": row["fact_request_id"],
                "ticker": "DELL",
                "metric_id": "revenue",
                "value_decimal": "43842000000",
                "unit": "USD",
                "unit_family": "currency",
                "period_start": "2026-01-31",
                "period_end": "2026-05-01",
                "period_role": "quarter_discrete",
                "fiscal_year": 2027,
                "fiscal_period": "Q1",
                "research_as_of": "2026-09-02",
                "authority_mode": "source_bound_company_reported_numeric_fact",
                "accession_numbers": ["0001571996-26-000030"],
                "accepted_at": "2026-06-09T20:11:41+00:00",
                "source_observation_ids": ["OBS::SUBSTITUTED"],
                "citation_urls": ["https://www.sec.gov/Archives/example"],
                "source_digests": ["a" * 64],
                "formula_trace": None,
                "numeric_fact_authority": True,
            }
            fact.update(fact_overrides)
            row.update(
                {
                    "status": "resolved",
                    "facts": [fact],
                    "typed_gap": None,
                    "typed_conflict": None,
                }
            )
            content["resolved_metric_count"] = 1
            content["typed_gap_count"] = 0
            content["typed_conflict_count"] = 0
            content["query_digest"] = canonical_sha256(
                {
                    key: value
                    for key, value in content.items()
                    if key != "query_digest"
                }
            )
            return mcp_tools_module._Call(
                content=content,
                error=False,
                failure_kind=None,
                receipt={
                    **call.receipt,
                    "output_digest": canonical_sha256(content),
                },
            )

        monkeypatch.setattr(adapter, "_call", substitute_fact)
        result = adapter.finance_tool(request)

    assert result["status"] == "tool_failure"
    assert result["failure"]["owner_layer"] == "s2_tool"
    assert result["failure"]["code"] == expected_code


def test_graph_and_mcp_bindings_are_atomically_derived_from_one_foundation() -> None:
    branch = _COMPOSITION.foundation_binding.branch_methods[0]
    assert branch.branch_id == _BRANCH
    assert branch.method_digest == _COMPOSITION.mcp_run_binding.branch_method_digests[
        _BRANCH
    ]
    assert branch.method_context["selected_branch_ids"] == [_BRANCH]
    assert branch.method_digest != _FULL_METHOD_DIGEST
    request = {
        "case_id": _CASE,
        "research_as_of": _AS_OF,
        "snapshot_id": _SNAPSHOT,
        "foundation_digest": _FOUNDATION_DIGEST,
    }
    assert _COMPOSITION.foundation_binder(request)["branch_methods"][0][
        "method_digest"
    ] == _METHOD_DIGEST


def test_branch_outside_runtime_binding_is_a_typed_tool_failure() -> None:
    with DellMCPToolLaneAdapter(
        _build_server(),
        run_binding=_binding(),
    ) as adapter:
        result = adapter.evidence_tool(_task("evidence", branch_id="Q3_MODEL_CYCLE"))

    assert result["status"] == "tool_failure"
    assert result["result_states"] == ["tool_failure"]
    assert result["failure"]["owner_layer"] == "s1_tool"
    assert result["failure"]["code"] == "mcp_task_branch_outside_run_binding"


def test_semantic_external_failure_stays_owned_by_s1_with_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _task(
        "evidence",
        evidence_request={
            "query": "current Dell AI server demand",
            "purpose": "Exercise a typed external-provider failure.",
            "source_route": "external_required",
            "limit": 2,
            "capture_limit": 1,
        },
    )
    with DellMCPToolLaneAdapter(
        _build_server(),
        run_binding=_binding(),
    ) as adapter:
        original_call = adapter._call

        def semantic_failure(name: str, arguments: dict) -> object:
            call = original_call(name, arguments)
            if name != SEARCH_EXTERNAL_SOURCES_TOOL:
                return call
            diagnostic = {
                "status": "tool_failure",
                "attempted_providers": [
                    {
                        "provider": "fixture",
                        "failure_code": "provider_timeout",
                    }
                ],
                "public_information_gap_proved": False,
            }
            return mcp_tools_module._Call(
                content=diagnostic,
                error=True,
                failure_kind="semantic_tool_failure",
                receipt={
                    **call.receipt,
                    "output_digest": canonical_sha256(diagnostic),
                    "semantic_tool_failure": True,
                    "failure_kind": "semantic_tool_failure",
                },
            )

        monkeypatch.setattr(adapter, "_call", semantic_failure)
        result = adapter.evidence_tool(request)

    assert result["status"] == "tool_failure"
    assert result["failure"]["owner_layer"] == "s1_tool"
    discovery_failure = next(
        item
        for item in result["items"]
        if item.get("mcp_receipt", {}).get("tool_name")
        == SEARCH_EXTERNAL_SOURCES_TOOL
    )
    assert discovery_failure["mcp_receipt"]["semantic_tool_failure"] is True
    assert discovery_failure["structured_output_projection"][
        "attempted_providers"
    ][0]["failure_code"] == "provider_timeout"
    assert all(
        item.get("public_information_gap_proved") is not True
        for item in result["items"]
    )


def test_single_external_capture_failure_is_diagnostic_when_candidate_survives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _task(
        "evidence",
        evidence_request={
            "query": "current Dell AI server demand",
            "purpose": "Keep discovery usable when one page capture fails.",
            "source_route": "external_required",
            "limit": 2,
            "capture_limit": 1,
        },
    )
    with DellMCPToolLaneAdapter(
        _build_server(),
        run_binding=_binding(),
    ) as adapter:
        assert adapter._timeout == 60.0
        original_call = adapter._call

        def fail_capture(name: str, arguments: dict) -> object:
            call = original_call(name, arguments)
            if name != CAPTURE_EXTERNAL_SOURCE_TOOL:
                return call
            diagnostic = {
                "status": "tool_failure",
                "error_code": "capture_timeout",
                "retryable": True,
                "failure_is_not_public_information_gap": True,
            }
            return mcp_tools_module._Call(
                content=diagnostic,
                error=True,
                failure_kind="semantic_tool_failure",
                receipt={
                    **call.receipt,
                    "output_digest": canonical_sha256(diagnostic),
                    "semantic_tool_failure": True,
                    "failure_kind": "semantic_tool_failure",
                },
            )

        monkeypatch.setattr(adapter, "_call", fail_capture)
        result = adapter.evidence_tool(request)

    assert result["status"] == "success"
    assert result["failure"] is None
    assert result["result_states"] == ["retrieval_candidate", "tool_failure"]
    candidate = next(
        item for item in result["items"]
        if item.get("result_state") == "retrieval_candidate"
    )
    assert candidate["candidate_is_not_evidence"] is True
    diagnostic_item = next(
        item for item in result["items"]
        if item.get("failure_scope") == "external_capture"
    )
    assert diagnostic_item["tool_failure_is_not_information_gap"] is True
    assert diagnostic_item["partial_result_may_continue"] is True
    assert diagnostic_item["mcp_receipt_chain"][-1]["tool_name"] == (
        CAPTURE_EXTERNAL_SOURCE_TOOL
    )


def test_mid_lane_transport_failure_preserves_calls_and_partial_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _task(
        "evidence",
        evidence_request={
            "query": "first local query",
            "purpose": "Create one bounded partial result.",
            "source_route": "local_only",
            "issuer_ids": ["DELL"],
            "source_roles": ["issuer_management_disclosure"],
            "limit": 2,
        },
    )
    request["task"]["evidence_requests"].append(
        {
            "query": "second local query",
            "purpose": "Exercise transport failure after partial success.",
            "source_route": "local_only",
            "issuer_ids": ["DELL"],
            "source_roles": ["issuer_management_disclosure"],
            "limit": 2,
            "include_domains": [],
            "capture_limit": 1,
        }
    )
    with DellMCPToolLaneAdapter(
        _build_server(),
        run_binding=_binding(),
    ) as adapter:
        original_call = adapter._call
        local_calls = 0

        def fail_second_local(name: str, arguments: dict) -> object:
            nonlocal local_calls
            call = original_call(name, arguments)
            if name != SEARCH_LOCAL_KNOWLEDGE_TOOL:
                return call
            local_calls += 1
            if local_calls != 2:
                return call
            diagnostic = {
                "status": "tool_failure",
                "error_code": "mcp_transport_exception",
                "exception_type": "TimeoutError",
                "retryable": True,
            }
            return mcp_tools_module._Call(
                content=diagnostic,
                error=True,
                failure_kind="transport",
                receipt={
                    **call.receipt,
                    "output_digest": canonical_sha256(diagnostic),
                    "is_error": True,
                    "semantic_tool_failure": False,
                    "failure_kind": "transport",
                    "transport_exception": True,
                    "exception_type": "TimeoutError",
                },
            )

        monkeypatch.setattr(adapter, "_call", fail_second_local)
        result = adapter.evidence_tool(request)

    assert result["status"] == "tool_failure"
    assert result["failure"]["owner_layer"] == "tool_transport"
    call_items = [item for item in result["items"] if "mcp_receipt" in item]
    assert [item["mcp_receipt"]["tool_name"] for item in call_items] == [
        GET_RESEARCH_METHOD_TOOL,
        SEARCH_LOCAL_KNOWLEDGE_TOOL,
        SEARCH_LOCAL_KNOWLEDGE_TOOL,
    ]
    partial = next(
        item for item in result["items"] if "partial_success_item_count" in item
    )
    assert partial["partial_success_item_count"] >= 1
    assert partial["partial_success_not_promoted"] is True
    assert all(
        item.get("result_state") != "reviewed_evidence"
        for item in result["items"]
    )


def test_portal_transport_exception_still_produces_call_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingPortal:
        @staticmethod
        def call(*_args: object, **_kwargs: object) -> object:
            raise TimeoutError("fixture transport timeout")

    with DellMCPToolLaneAdapter(
        _build_server(),
        run_binding=_binding(),
    ) as adapter:
        monkeypatch.setattr(adapter, "_portal", FailingPortal())
        result = adapter.evidence_tool(_task("evidence"))

    assert result["status"] == "tool_failure"
    assert result["failure"]["owner_layer"] == "tool_transport"
    assert result["failure"]["retryable"] is True
    receipt = result["items"][0]["mcp_receipt"]
    assert receipt["tool_name"] == GET_RESEARCH_METHOD_TOOL
    assert receipt["failure_kind"] == "transport"
    assert receipt["transport_exception"] is True
    assert receipt["exception_type"] == "TimeoutError"
    assert len(receipt["request_digest"]) == 64
    assert result["items"][0]["structured_output_projection"][
        "error_code"
    ] == "mcp_transport_exception"


def test_runtime_composition_owns_portal_and_client_lifecycle() -> None:
    adapter = DellMCPToolLaneAdapter(_build_server(), run_binding=_binding())
    result = adapter.evidence_tool(_task("evidence"))
    assert result["status"] == "tool_failure"
    assert result["failure"]["code"] == "mcp_adapter_not_open"


def test_one_runtime_owned_client_supports_parallel_graph_lane_calls() -> None:
    with DellMCPToolLaneAdapter(_build_server(), run_binding=_binding()) as adapter:
        with ThreadPoolExecutor(max_workers=2) as pool:
            evidence_future = pool.submit(adapter.evidence_tool, _task("evidence"))
            finance_future = pool.submit(adapter.finance_tool, _task("finance"))
            evidence = evidence_future.result(timeout=5)
            finance = finance_future.result(timeout=5)

    assert evidence["status"] == "success"
    assert finance["status"] == "success"


def test_deepseek_semantic_intent_flows_through_compiler_to_local_mcp() -> None:
    planner_output = PlannerSemanticPayload.model_validate_json(
        json.dumps(
            {
                "tasks": [
                    {
                        "branch_id": "Q2_DEMAND_QUALITY",
                        "objective": "Check a bounded customer demand source family.",
                        "evidence_requests": [
                            {
                                "minimum_route_obligation_id": "route:Q2:F4:local",
                                "intent": {
                                    "intent_kind": "local_evidence",
                                    "query": "customer capital spending deployment",
                                    "purpose": "Locate bounded customer deployment context.",
                                    "entity_refs": [],
                                    "period_intents": [],
                                    "expected_information_gain": (
                                        "Determine whether a current customer source is reachable."
                                    ),
                                    "limit": 3,
                                    "semantic_source_family_refs": [
                                        "F4_CUSTOMER_CAPEX_DEPLOYMENT"
                                    ],
                                    "source_role_intents": [],
                                    "content_surface_intents": ["prose"],
                                },
                            }
                        ],
                        "fact_requests": [],
                    }
                ]
            }
        )
    )
    request = planner_output.tasks[0].evidence_requests[0].model_dump(mode="json")

    assert "issuer_ids" not in json.dumps(request)
    assert "route_ids" not in json.dumps(request)
    with DellMCPToolLaneAdapter(
        _build_server(),
        run_binding=_binding(),
        source_family_compiler=_SOURCE_FAMILY_COMPILER,
    ) as adapter:
        result = adapter.evidence_tool(
            _task(
                "evidence",
                branch_id="Q2_DEMAND_QUALITY",
                evidence_request=request,
            )
        )

    assert result["status"] == "success"
    assert set(result["result_states"]).issubset(
        {"retrieval_candidate", "typed_gap"}
    )
    assert any(
        receipt.get("contract_version") == "1.2"
        for row in result["items"]
        for receipt in row["mcp_receipt_chain"]
    )
    assert any(
        receipt.get("tool_name") == SEARCH_LOCAL_KNOWLEDGE_TOOL
        for row in result["items"]
        for receipt in row["mcp_receipt_chain"]
    )


def test_finance_adapter_preserves_typed_gap_and_typed_conflict() -> None:
    with DellMCPToolLaneAdapter(
        _build_server(financial_status="typed_gap"), run_binding=_binding()
    ) as adapter:
        gap = adapter.finance_tool(_task("finance"))
    with DellMCPToolLaneAdapter(
        _build_server(financial_status="typed_conflict"), run_binding=_binding()
    ) as adapter:
        conflict = adapter.finance_tool(_task("finance"))

    assert gap["status"] == "success"
    assert gap["result_states"] == ["typed_gap"]
    assert gap["items"][0]["result_state"] == "typed_gap"
    assert gap["items"][0]["typed_gap"]["gap_code"] == "fixture_gap"
    assert "typed_conflict" not in gap["items"][0]

    assert conflict["status"] == "success"
    assert conflict["result_states"] == ["typed_conflict"]
    assert conflict["items"][0]["result_state"] == "typed_conflict"
    assert conflict["items"][0]["typed_conflict"]["conflict_code"] == "fixture_conflict"
    assert "typed_gap" not in conflict["items"][0]
    ToolLaneResult.model_validate_json(json.dumps(conflict))


def test_canonical_evidence_request_enforces_per_request_capture_ceiling() -> None:
    with pytest.raises(ValueError, match="less than or equal to 3"):
        EvidenceRequest(
            query="official Dell evidence",
            purpose="Bound one request.",
            source_route="external_required",
            capture_limit=4,
        )
