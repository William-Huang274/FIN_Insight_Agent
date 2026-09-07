from __future__ import annotations

import json
from collections.abc import Mapping
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest
pytest.importorskip("mcp", reason="agent-runtime optional dependency")

from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
    BoundBranchTask,
    RuntimeReceipt,
    ToolLaneResult,
    canonical_sha256,
)
from sec_agent.agent_runtime.dell_specialist_agentic_composition import (
    DellSpecialistAgenticCompositionError,
    _bound_task_for_action,
    _mcp_port,
    _observation_from_result,
    open_dell_specialist_receipted_composition,
    open_dell_specialist_scripted_qualification_composition,
)
from sec_agent.agent_runtime.deepseek_structured_agents import (
    DeepSeekStructuredAgentAdapter,
    load_deepseek_structured_agent_config,
)
from sec_agent.agent_runtime.dell_specialist_agentic_graph import (
    RequestEvidenceAction,
    SpecialistNotebook,
    SpecialistToolRequest,
)


ROOT = Path(__file__).resolve().parents[1]
DEEPSEEK_CONFIG_PATH = (
    ROOT
    / "configs"
    / "research"
    / "fin_ia_0_1_3_dell_reference_vertical_deepseek_structured_agents_v1_0.json"
)
RUNTIME_ENVIRONMENT = {
    "FIN_REPO_ROOT": str(ROOT),
    "FINSIGHT_DELL_S1_NODES_PATH": str(
        Path(
            "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
            "rag_mature_stack/retrieval_qualification/"
            "dell_rag_full_stack_preview_attempt_20260902_03/"
            "retrieval_nodes.jsonl"
        )
    ),
    "FINSIGHT_DELL_REVIEWED_BASE_PACK_PATH": str(
        ROOT
        / "data/workbench_private/fin_0_1_3_s1_dell_direct_source_evidence/"
        "r4/successor/pack.json"
    ),
    "FINSIGHT_DELL_REVIEWED_OVERLAY_PATH": str(
        Path(
            "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
            "evidence_overlay/attempts/"
            "20260902T051005+0800-dell-fy27q2-sec-ex99-review-a01/"
            "reviewed-evidence-case-projection.json"
        )
    ),
    "FINSIGHT_DELL_S2_RESULT_PATH": str(
        Path(
            "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/s2/"
            "s2_exact_period_contract_successor_20260902_r1/"
            "company_financial_fact_mart_result.json"
        )
    ),
    "FINSIGHT_COMPANY_FINANCIAL_FACT_MART_PATH": str(
        Path(
            "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/s2/"
            "s2_exact_period_contract_successor_20260902_r1/"
            "company_financial_facts.sqlite"
        )
    ),
    "FINSIGHT_DELL_EXTERNAL_MANIFEST_PATH": str(
        Path(
            "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
            "external_exact_url_qualification/"
            "dell_external_exact_url_zero_model_20260902_r12/manifest.json"
        )
    ),
}

pytestmark = pytest.mark.local_data_integration


def _assert_assets() -> None:
    missing = [path for path in RUNTIME_ENVIRONMENT.values() if not Path(path).exists()]
    assert not missing, f"Dell approved data assets missing: {missing}"


def test_existing_derived_finance_metrics_are_disclosed_and_real_mcp_returns_formula_trace():
    _assert_assets()
    requests = []

    def model(request):
        requests.append(request)
        if len(requests) == 1:
            return {"action": "request_finance", "context_digest": request["context_digest"],
                "reason_summary": "Offline qualification of existing S2 derived metrics, not model research.",
                "intent": {"ticker": "DELL", "metric_ids": ["free_cash_flow", "gross_margin", "operating_margin"],
                    "granularity": "quarter_discrete", "selection_mode": "latest_on_or_before"}}
        return {"action": "request_human_review", "context_digest": request["context_digest"],
                "reason_summary": "Offline fixture complete.", "blocker_code": "offline_complete"}

    with open_dell_specialist_scripted_qualification_composition(
        run_id="test:existing-derived-finance", run_invocation_id="test:existing-derived-finance:1",
        branch_id="Q1_ISSUER_TRUTH", environment=RUNTIME_ENVIRONMENT, scripted_model_turn=model,
        source_read_enabled=True) as composition:
        result = composition.graph.invoke(composition.graph_input.model_dump(mode="json"), config={"recursion_limit": 20})
    finance = next(row for row in requests[0]["l0_context"]["capability_summaries"]
                   if row.get("capability_ref") == "capability:dell:financial-fact-query")
    derived = {row["metric_id"]: row for row in finance["metrics"] if row["availability"] == "derived_at_query_time"}
    assert set(derived) == {"free_cash_flow", "gross_margin", "operating_margin"}
    assert all(row["formula"] and not row["observed_period_roles"] for row in derived.values())
    assert "typed_gap" in finance["derived_metric_rule"] and "does not make" in finance["calculation_submission_rule"]
    items = result["notebook"]["observations"][0]["content"]
    facts = [row for row in items if row.get("result_state") == "numeric_fact"]
    assert {row["metric_id"] for row in facts} == set(derived)
    fcf = next(row for row in facts if row["metric_id"] == "free_cash_flow" and row["period_end"] == "2026-05-01")
    assert fcf["value_decimal"] == "3118000000" and fcf["unit"] == "USD"
    assert fcf["authority_mode"] == "deterministically_derived_numeric_fact"
    assert fcf["formula_trace"]["input_metrics"] == ["operating_cash_flow", "capital_expenditures"]
    assert len(fcf["formula_trace"]["input_numeric_fact_ids"]) == 2
    assert len(fcf["source_observation_ids"]) == 2
    assert result["notebook"]["tool_action_count"] == 1 and result["final_submission"] is None


class _RealMCPFakeModel:
    def __init__(self, *, force_residual_first: bool = False) -> None:
        self.turns = 0
        self.force_residual_first = force_residual_first
        self.requests: list[dict[str, Any]] = []
        self.actions: list[dict[str, Any]] = []

    @staticmethod
    def _evidence_action(
        *,
        context_digest: str,
        complete_route: bool,
    ) -> dict[str, Any]:
        return {
            "action": "request_evidence",
            "context_digest": context_digest,
            "reason_summary": (
                "Repair the residual and close every compiled reviewed target."
                if complete_route
                else "Probe only the operating-performance part of the route."
            ),
            "minimum_route_obligation_id": (
                "route:Q1_ISSUER_TRUTH:required-reviewed"
            ),
            "intent": {
                "intent_kind": "reviewed_evidence",
                "query": (
                    "Dell operating performance infrastructure demand cash flow "
                    "cash and cash equivalents balance sheet"
                    if complete_route
                    else "Dell operating performance and infrastructure demand"
                ),
                "purpose": (
                    "Establish current issuer-reported performance and filing truth."
                    if complete_route
                    else "Probe current issuer-reported operating performance."
                ),
                "entity_refs": ["DELL"],
                "period_intents": [],
                "expected_information_gain": (
                    "Close every required source-family target."
                    if complete_route
                    else "Expose any residual source-family requirement."
                ),
                "limit": 12 if complete_route else 3,
                "topic_refs": (
                    [
                        "cash_conversion_balance_sheet",
                        "operating_performance",
                    ]
                    if complete_route
                    else ["operating_performance"]
                ),
                "evidence_role_refs": [],
                "minimum_authority_tier": "reviewed",
            },
        }

    def __call__(self, request: Mapping[str, Any]) -> dict[str, Any]:
        self.turns += 1
        self.requests.append(dict(request))
        context_digest = request["context_digest"]
        notebook = SpecialistNotebook.model_validate_json(
            json.dumps(request["notebook"])
        )
        route_complete = any(
            observation.route_completions
            for observation in notebook.observations
            if observation.kind == "evidence"
        )
        evidence_observed = any(
            observation.kind == "evidence"
            for observation in notebook.observations
        )
        numeric_fact_observed = any(
            reference.numeric_fact_authority
            for observation in notebook.observations
            for reference in observation.references
        )
        if not evidence_observed:
            action = self._evidence_action(
                context_digest=context_digest,
                complete_route=not self.force_residual_first,
            )
        elif not route_complete:
            assert any(
                item.get("gap_code") == "source_family_compilation_residual"
                for observation in notebook.observations
                for item in observation.content
            )
            action = self._evidence_action(
                context_digest=context_digest,
                complete_route=True,
            )
        elif not numeric_fact_observed:
            action = {
                "action": "request_finance",
                "context_digest": context_digest,
                "reason_summary": "Read a period-bound Dell revenue fact.",
                "intent": {
                    "ticker": "DELL",
                    "metric_ids": ["revenue"],
                    "granularity": "quarter_discrete",
                    "selection_mode": "latest_on_or_before",
                    "period_start": None,
                    "period_end": None,
                    "fiscal_years": [],
                    "requested_unit": "reported_source_unit",
                    "unit_family": None,
                },
            }
        else:
            evidence_id = next(
                ref.ref_id
                for observation in notebook.observations
                for ref in observation.references
                if ref.writer_citable
            )
            fact_id = next(
                ref.ref_id
                for observation in notebook.observations
                for ref in observation.references
                if ref.numeric_fact_authority
            )
            action = {
                "action": "submit_workpaper",
                "context_digest": context_digest,
                "reason_summary": "Submit only the claims supported by current refs.",
                "terminal_state": "supported",
                "thesis": "Dell has current issuer evidence and a period-bound revenue fact.",
                "mechanism": (
                    "The reviewed issuer item supplies textual authority while S2 supplies "
                    "the exact numeric observation; no causal claim is inferred from either."
                ),
                "narrative_markdown": (
                    "The current Q1 workpaper is grounded in one reviewed issuer item and "
                    "one period-bound S2 revenue observation. It intentionally does not "
                    "promote local or captured candidates to Evidence."
                ),
                "claims": [
                    {
                        "claim_id": "claim:q1:issuer",
                        "kind": "reported_fact",
                        "materiality": "high",
                        "statement": "Dell has a current reviewed issuer disclosure.",
                        "evidence_ids": [evidence_id],
                        "fact_ids": [],
                        "numeric_authority": "not_applicable",
                        "authority_note": None,
                    },
                    {
                        "claim_id": "claim:q1:revenue",
                        "kind": "numeric_fact",
                        "materiality": "high",
                        "statement": "S2 contains the latest eligible Dell revenue fact.",
                        "evidence_ids": [],
                        "fact_ids": [fact_id],
                        "numeric_authority": "authoritative",
                        "authority_note": None,
                    },
                ],
                "counterevidence": [
                    "A reported demand signal does not by itself prove future conversion."
                ],
                "what_would_change": [
                    "A later issuer disclosure reversing the demand or revenue trend."
                ],
                "open_gaps": ["Customer-level mix remains outside this Q1 proof."],
            }
        self.actions.append(dict(action))
        for claim in action.get("claims", ()):
            claim.setdefault("reasoning_summary", None)
            claim.setdefault("citation_quotes", {})
        return action


def test_locked_mcp_runtime_preflight() -> None:
    assert version("mcp") == "2.1.1"
    from mcp import Client
    from mcp.server import MCPServer

    assert Client is not None
    assert MCPServer is not None


def test_single_specialist_loop_uses_existing_real_mcp_without_model_or_network() -> None:
    _assert_assets()
    fake_model = _RealMCPFakeModel()

    with open_dell_specialist_scripted_qualification_composition(
        run_id="test:dell-wave2-real-mcp",
        run_invocation_id="test:dell-wave2-real-mcp:invocation:1",
        branch_id="Q1_ISSUER_TRUTH",
        environment=RUNTIME_ENVIRONMENT,
        scripted_model_turn=fake_model,
    ) as composition:
        assert composition.model_execution_state == (
            "scripted_qualification_not_model_execution"
        )
        assert composition.model_execution_receipts_authorized is False
        assert composition.provider_model_calls_authorized is False
        assert composition.model_execution_receipts_authorized is False
        assert composition.network_calls_authorized is False
        assert composition.paid_calls_authorized is False
        assert composition.live_external_calls_authorized is False
        assert not hasattr(composition, "dependencies")
        capability_summaries = (
            composition.graph_input.l0_context.capability_summaries
        )
        reviewed_capability = next(
            row
            for row in capability_summaries
            if row.get("capability_ref")
            == "capability:dell:reviewed-evidence-query"
        )
        assert "operating_performance" in reviewed_capability[
            "allowed_topic_refs"
        ]
        finance_capability = next(
            row
            for row in capability_summaries
            if row.get("capability_ref")
            == "capability:dell:financial-fact-query"
        )
        assert "revenue" in {
            row["metric_id"] for row in finance_capability["metrics"]
        }
        assert composition.graph_input.l0_context.skill_summaries[0].get(
            "method_context"
        )
        result = composition.graph.invoke(
            composition.graph_input.model_dump(mode="json"),
            {"recursion_limit": 40},
        )

    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    assert fake_model.turns == 3
    assert notebook.model_turn_count == 3
    assert notebook.tool_action_count == 2
    assert notebook.satisfied_route_obligation_ids == (
        "route:Q1_ISSUER_TRUTH:required-reviewed",
    )
    assert len(notebook.observations[0].route_completions) == 1
    route_completion = notebook.observations[0].route_completions[0]
    assert route_completion.owner_data_gate_decision_digest == (
        composition.owner_data_gate_decision_digest
    )
    assert route_completion.inventory_snapshot_digest == (
        composition.inventory_snapshot_digest
    )
    assert route_completion.source_route_catalog_digest == (
        composition.source_route_catalog_digest
    )
    assert route_completion.reviewed_index_digests
    assert route_completion.filter_receipt_digests
    assert route_completion.source_family_refs == (
        "F1_SEC_ISSUER_FACTS",
        "F2_DELL_IR_EARNINGS",
    )
    assert route_completion.expected_target_refs == (
        route_completion.observed_target_refs
    )
    reviewed_items = [
        item
        for item in notebook.observations[0].content
        if item.get("result_state") == "reviewed_evidence"
    ]
    assert {
        item["source_family_ref"] for item in reviewed_items
    } == {"F1_SEC_ISSUER_FACTS", "F2_DELL_IR_EARNINGS"}
    assert all(
        any(
            receipt.get("strict_route_satisfied") is True
            and item["evidence_id"] in receipt["accepted_evidence_ids"]
            for receipt in item["mcp_receipt_chain"]
            if receipt.get("filter_receipt_id")
        )
        for item in reviewed_items
    )
    assert result["phase"] == "specialist_submission_accepted"
    assert result["final_submission"]["terminal_state"] == "supported"
    states = {
        ref.authority_state
        for observation in notebook.observations
        for ref in observation.references
    }
    assert "reviewed_evidence" in states
    assert "numeric_fact" in states
    assert "retrieval_candidate" not in {
        ref.authority_state
        for claim in result["final_submission"]["claims"]
        for observation in notebook.observations
        for ref in observation.references
        if ref.ref_id in claim["evidence_ids"]
    }
    serialized = json.dumps(result, ensure_ascii=False)
    assert "Z:/" not in serialized
    assert "D:/" not in serialized
    assert "DEEPSEEK_API_KEY" not in serialized


def test_receipted_synthetic_replay_runs_full_real_mcp_loop_without_transport() -> None:
    _assert_assets()

    class NoTransportModel:
        def with_structured_output(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("saved replay must not construct model transport")

    no_transport_model = NoTransportModel()
    events: list[dict[str, Any]] = []
    adapter = DeepSeekStructuredAgentAdapter(
        config=load_deepseek_structured_agent_config(DEEPSEEK_CONFIG_PATH),
        chat_models={
            "planner": no_transport_model,
            "specialist": no_transport_model,
            "counter": no_transport_model,
            "lead": no_transport_model,
        },
        audit_sink=lambda event: events.append(dict(event)),
    )
    action_source = _RealMCPFakeModel()

    def replay_turn(request: Mapping[str, Any]) -> dict[str, Any]:
        action = action_source(request)
        replay_body = {
            "schema_version": (
                "fin_ia_dell_specialist_action_replay_record_v1_0"
            ),
            "replay_source": "synthetic_qualification",
            "request_digest": canonical_sha256(request),
            "parsed_action": action,
        }
        return adapter.replay_specialist_model_turn(
            request,
            replay_record={
                **replay_body,
                "replay_record_digest": canonical_sha256(replay_body),
            },
        )

    with open_dell_specialist_receipted_composition(
        run_id="test:dell-wave2-receipted-replay",
        run_invocation_id="test:dell-wave2-receipted-replay:invocation:1",
        branch_id="Q1_ISSUER_TRUTH",
        turn_source="saved_response_replay",
        model_turn=replay_turn,
        environment=RUNTIME_ENVIRONMENT,
    ) as composition:
        assert composition.provider_model_calls_authorized is False
        assert composition.network_calls_authorized is False
        assert composition.paid_calls_authorized is False
        result = composition.graph.invoke(
            composition.graph_input.model_dump(mode="json"),
            {"recursion_limit": 40},
        )

    notebook = SpecialistNotebook.model_validate_json(
        json.dumps(result["notebook"])
    )
    assert result["phase"] == "specialist_submission_accepted"
    assert notebook.model_turn_count == 3
    assert all(
        record.turn_source == "saved_response_replay"
        and record.model_execution_evidence is False
        and record.runtime_receipt is not None
        for record in notebook.model_turn_records
    )
    assert len(events) == 6
    assert all(event["provider_call_attempted"] is False for event in events)
    assert all("raw_response" not in event for event in events)


def test_specialist_observes_compilation_residual_and_repairs_route() -> None:
    _assert_assets()
    fake_model = _RealMCPFakeModel(force_residual_first=True)

    with open_dell_specialist_scripted_qualification_composition(
        run_id="test:dell-wave2-residual-repair",
        run_invocation_id="test:dell-wave2-residual-repair:invocation:1",
        branch_id="Q1_ISSUER_TRUTH",
        environment=RUNTIME_ENVIRONMENT,
        scripted_model_turn=fake_model,
    ) as composition:
        result = composition.graph.invoke(
            composition.graph_input.model_dump(mode="json"),
            {"recursion_limit": 50},
        )

    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    assert fake_model.turns == 4
    assert notebook.model_turn_count == 4
    assert notebook.tool_action_count == 3
    assert notebook.observations[0].route_completions == ()
    assert any(
        item.get("gap_code") == "source_family_compilation_residual"
        and item.get("compilation_disposition")
        == "accepted_with_residual_feedback"
        for item in notebook.observations[0].content
    )
    assert notebook.observations[1].route_completions
    assert notebook.satisfied_route_obligation_ids == (
        "route:Q1_ISSUER_TRUTH:required-reviewed",
    )
    assert result["phase"] == "specialist_submission_accepted"


def test_source_mcp_receipt_rejects_host_kind_even_with_valid_digests() -> None:
    task = BoundBranchTask(
        task_id="task:source-receipt-kind",
        case_id="DELL_AI_INFRA_REFERENCE_VERTICAL",
        branch_id="Q1_ISSUER_TRUTH",
        revision=0,
        priority="high",
        objective="Test exact source MCP receipt kind binding.",
        evidence_requests=(
            {
                "minimum_route_obligation_id": (
                    "route:Q1_ISSUER_TRUTH:required-reviewed"
                ),
                "answer_free_intent_kind": "reviewed_evidence",
            },
        ),
        fact_requests=(),
        research_as_of="2026-09-02T00:00:00Z",
        snapshot_id="snapshot:source-receipt-kind",
        foundation_digest="a" * 64,
        method_digest="b" * 64,
        plan_digest="c" * 64,
    )
    action = RequestEvidenceAction(
        action="request_evidence",
        context_digest="d" * 64,
        reason_summary="Exercise the source receipt kind guard.",
        minimum_route_obligation_id=(
            "route:Q1_ISSUER_TRUTH:required-reviewed"
        ),
        intent={
            "intent_kind": "reviewed_evidence",
            "query": "Dell source receipt kind",
            "purpose": "Test the MCP source receipt boundary.",
            "entity_refs": ("DELL",),
            "period_intents": (),
            "expected_information_gain": "Reject a host receipt posing as a tool.",
            "limit": 2,
            "topic_refs": ("operating_performance",),
            "evidence_role_refs": (),
            "minimum_authority_tier": "reviewed",
        },
    )
    request_body = {
        "schema_version": "fin_ia_dell_specialist_tool_request_v1_0",
        "action_attempt_id": "action-attempt:source-receipt-kind",
        "run_id": "run:source-receipt-kind",
        "run_invocation_id": "invocation:source-receipt-kind",
        "agent_id": "specialist:Q1_ISSUER_TRUTH",
        "task": task.model_dump(mode="json"),
        "owner_data_gate_decision_digest": "d" * 64,
        "source_route_catalog_digest": "e" * 64,
        "inventory_snapshot_digest": "f" * 64,
        "disclosure_runtime_state": (
            "current_state_authority_unavailable_fail_closed"
        ),
        "action": action.model_dump(mode="json"),
    }
    request = SpecialistToolRequest.model_validate_json(
        json.dumps(
            {
                **request_body,
                "request_digest": canonical_sha256(request_body),
            }
        )
    )
    lane_task = _bound_task_for_action(request, lane="evidence")
    result_body = {
        "status": "not_applicable",
        "result_states": ["not_applicable"],
        "items": [],
        "failure": None,
    }
    source_receipt = RuntimeReceipt(
        receipt_id="host-posing-as-source-tool",
        kind="host",
        actor="evidence_tool",
        status="success",
        request_digest=canonical_sha256(lane_task),
        output_digest=canonical_sha256(result_body),
        elapsed_ms=0.0,
    )
    result = ToolLaneResult(
        lane="evidence",
        task_id=lane_task.task.task_id,
        case_id=lane_task.task.case_id,
        branch_id=lane_task.task.branch_id,
        revision=lane_task.task.revision,
        research_as_of=lane_task.task.research_as_of,
        snapshot_id=lane_task.task.snapshot_id,
        foundation_digest=lane_task.task.foundation_digest,
        method_digest=lane_task.task.method_digest,
        plan_digest=lane_task.task.plan_digest,
        status="not_applicable",
        result_states=("not_applicable",),
        items=(),
        failure=None,
        runtime_receipt=source_receipt,
    )

    with pytest.raises(
        DellSpecialistAgenticCompositionError,
        match="specialist_mcp_source_receipt_binding_invalid",
    ):
        _observation_from_result(
            request=request,
            result=result,
            kind="evidence",
            baseline_source_plan=None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "owner_data_gate_decision_digest",
        "inventory_snapshot_digest",
        "source_route_catalog_digest",
    ),
)
def test_mcp_port_rejects_stale_current_authority_before_dispatch(
    field_name: str,
) -> None:
    task = BoundBranchTask(
        task_id="task:authority-binding",
        case_id="DELL_AI_INFRA_REFERENCE_VERTICAL",
        branch_id="Q1_ISSUER_TRUTH",
        revision=0,
        priority="high",
        objective="Prove exact current authority binding before tool dispatch.",
        evidence_requests=(
            {
                "minimum_route_obligation_id": (
                    "route:Q1_ISSUER_TRUTH:required-reviewed"
                ),
                "answer_free_intent_kind": "reviewed_evidence",
            },
        ),
        fact_requests=(),
        research_as_of="2026-09-02T00:00:00Z",
        snapshot_id="snapshot:authority-binding",
        foundation_digest="a" * 64,
        method_digest="b" * 64,
        plan_digest="c" * 64,
    )
    action = _RealMCPFakeModel._evidence_action(
        context_digest="4" * 64,
        complete_route=True,
    )
    current = {
        "owner_data_gate_decision_digest": "d" * 64,
        "inventory_snapshot_digest": "e" * 64,
        "source_route_catalog_digest": "f" * 64,
    }
    request_body = {
        "schema_version": "fin_ia_dell_specialist_tool_request_v1_0",
        "action_attempt_id": "action-attempt:authority-binding",
        "run_id": "run:authority-binding",
        "run_invocation_id": "invocation:authority-binding",
        "agent_id": "specialist:Q1_ISSUER_TRUTH",
        "task": task.model_dump(mode="json"),
        **current,
        "disclosure_runtime_state": (
            "current_state_authority_unavailable_fail_closed"
        ),
        "action": action,
    }
    request_body[field_name] = "0" * 64
    request = {**request_body, "request_digest": canonical_sha256(request_body)}
    calls: list[Mapping[str, Any]] = []

    def tool(value: Mapping[str, Any]) -> Mapping[str, Any]:
        calls.append(value)
        return {}

    port = _mcp_port(
        expected_task=task,
        baseline_source_plan=None,  # type: ignore[arg-type]
        owner_data_gate_decision_digest=current[
            "owner_data_gate_decision_digest"
        ],
        inventory_snapshot_digest=current["inventory_snapshot_digest"],
        source_route_catalog_digest=current["source_route_catalog_digest"],
        lane="evidence",
        tool=tool,
    )

    with pytest.raises(
        DellSpecialistAgenticCompositionError,
        match="specialist_tool_current_authority_binding_mismatch",
    ):
        port(request)
    assert calls == []
