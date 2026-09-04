from __future__ import annotations

from collections.abc import Callable, Mapping
import json
from typing import Any

import pytest

from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
    canonical_sha256,
)
from sec_agent.agent_runtime.dell_specialist_agentic_graph import (
    DellSpecialistAgenticDependencies,
    DellSpecialistAgenticGraphError,
    SpecialistAction,
    SpecialistHumanReviewHandoff,
    SpecialistNotebook,
    SpecialistToolObservation,
    SubmitWorkpaperAction,
    _submission_errors,
    build_dell_specialist_agentic_state_graph,
)


def _input() -> dict[str, Any]:
    return {
        "schema_version": "fin_ia_dell_specialist_agentic_graph_v1_0",
        "run_id": "dell-wave2-run-001",
        "run_invocation_id": "dell-wave2-invocation-001",
        "agent_id": "specialist:Q1_ISSUER_TRUTH",
        "task": {
            "task_id": "task:Q1_ISSUER_TRUTH:001",
            "case_id": "DELL_AI_INFRA_REFERENCE_VERTICAL",
            "branch_id": "Q1_ISSUER_TRUTH",
            "revision": 0,
            "priority": "high",
            "objective": "Establish the latest issuer-reported operating truth.",
            "evidence_requests": [
                {
                    "minimum_route_obligation_id": (
                        "route:Q1_ISSUER_TRUTH:required-reviewed"
                    ),
                    "answer_free_intent_kind": "reviewed_evidence",
                }
            ],
            "fact_requests": [],
            "research_as_of": "2026-09-02T00:00:00Z",
            "snapshot_id": "dell-owner-data-gate-test",
            "foundation_digest": "a" * 64,
            "method_digest": "b" * 64,
            "plan_digest": "c" * 64,
        },
        "required_route_obligation_ids": [
            "route:Q1_ISSUER_TRUTH:required-reviewed"
        ],
        "l0_context": {
            "owner_data_gate_decision_digest": "f" * 64,
            "source_route_catalog_digest": "d" * 64,
            "inventory_snapshot_digest": "e" * 64,
            "disclosure_runtime_state": (
                "current_state_authority_unavailable_fail_closed"
            ),
            "capability_summaries": [
                {
                    "capability_ref": "capability:dell:reviewed-evidence",
                    "purpose": "Read current reviewed issuer evidence.",
                }
            ],
            "skill_summaries": [
                {
                    "skill_ref": "skill:dell:issuer-truth",
                    "purpose": "Research-method guidance only.",
                }
            ],
        },
        "max_model_turns": 8,
        "max_tool_actions": 12,
    }


class _ScriptedModel:
    def __init__(
        self,
        actions: list[Callable[[Mapping[str, Any]], dict[str, Any]]],
    ) -> None:
        self._actions = list(actions)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, request: Mapping[str, Any]) -> dict[str, Any]:
        request_value = dict(request)
        self.requests.append(request_value)
        if not self._actions:
            raise AssertionError("scripted model exhausted")
        action = self._actions.pop(0)(request_value)
        action = {**action, "context_digest": request_value["context_digest"]}
        return action


def _action(kind: str, **fields: Any) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    def build(_request: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "action": kind,
            "reason_summary": f"Select {kind} for the current branch.",
            **fields,
        }

    return build


def _model_turn_receipt(
    request: Mapping[str, Any],
    action: Mapping[str, Any],
    **overrides: Any,
) -> dict[str, Any]:
    receipt = {
        "receipt_id": (
            "model:specialist:"
            f"{canonical_sha256(request)[:20]}:{canonical_sha256(action)[:20]}"
        ),
        "kind": "model",
        "actor": request["agent_id"],
        "status": "success",
        "request_digest": canonical_sha256(request),
        "output_digest": canonical_sha256(action),
        "elapsed_ms": 12.5,
        "input_tokens": 101,
        "output_tokens": 37,
        "total_tokens": 138,
        "usage_reported": True,
        "transport_attempts": 1,
    }
    receipt.update(overrides)
    return receipt


def _evidence_action(query: str = "Dell latest infrastructure demand") -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    return _action(
        "request_evidence",
        minimum_route_obligation_id="route:Q1_ISSUER_TRUTH:required-reviewed",
        intent={
            "intent_kind": "reviewed_evidence",
            "query": query,
            "purpose": "Establish current issuer-reported demand and performance.",
            "entity_refs": ["DELL"],
            "period_intents": ["FY2027Q2"],
            "expected_information_gain": "Resolve current operating direction.",
            "limit": 4,
            "topic_refs": ["operating_performance"],
            "evidence_role_refs": ["issuer_direct_source"],
            "minimum_authority_tier": "reviewed",
        },
    )


def _finance_action() -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    return _action(
        "request_finance",
        intent={
            "ticker": "DELL",
            "metric_ids": ["revenue"],
            "granularity": "quarter_discrete",
            "selection_mode": "latest_on_or_before",
            "period_start": None,
            "period_end": "2026-07-31",
            "fiscal_years": [2027],
            "requested_unit": "reported_source_unit",
            "unit_family": "monetary",
        },
    )


def _evidence_action_with_reason(
    *,
    query: str,
    reason: str,
) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    base = _evidence_action(query)

    def build(request: Mapping[str, Any]) -> dict[str, Any]:
        return {**base(request), "reason_summary": reason}

    return build


def _submission(
    *,
    evidence_id: str = "E:DELL:Q1",
    fact_id: str = "F:DELL:REVENUE:FY27Q2",
) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    return _action(
        "submit_workpaper",
        terminal_state="supported",
        thesis="Dell reported current infrastructure demand and revenue evidence.",
        mechanism="Issuer evidence and a period-bound S2 observation support the bounded conclusion.",
        narrative_markdown=(
            "Dell's current operating picture is supported by the cited issuer evidence "
            "and the period-bound financial fact. The causal interpretation remains bounded."
        ),
        claims=[
            {
                "claim_id": "claim:q1:reported",
                "kind": "reported_fact",
                "materiality": "high",
                "statement": "Dell reported current infrastructure demand information.",
                "evidence_ids": [evidence_id],
                "fact_ids": [],
                "numeric_authority": "not_applicable",
                "authority_note": None,
            },
            {
                "claim_id": "claim:q1:revenue",
                "kind": "numeric_fact",
                "materiality": "high",
                "statement": "The S2 mart contains a period-bound Dell revenue observation.",
                "evidence_ids": [],
                "fact_ids": [fact_id],
                "numeric_authority": "authoritative",
                "authority_note": None,
            },
        ],
        counterevidence=["Reported orders do not by themselves prove final revenue conversion."],
        what_would_change=["A later issuer filing reversing the demand signal."],
        open_gaps=["Customer-level mix remains undisclosed."],
    )


class _ToolPorts:
    def __init__(self, *, first_evidence_is_candidate: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self._first_evidence_is_candidate = first_evidence_is_candidate
        self._evidence_calls = 0

    @staticmethod
    def _receipt(
        request: Mapping[str, Any],
        *,
        kind: str,
        output_body: Mapping[str, Any] | None = None,
        success: bool = True,
    ) -> dict[str, Any]:
        return {
            "receipt_id": f"tool:{kind}:{request['request_digest'][:20]}",
            "kind": "tool",
            "actor": f"{kind}_tool",
            "status": "success" if success else "failure",
            "request_digest": request["request_digest"],
            "output_digest": (
                canonical_sha256(output_body)
                if success and output_body is not None
                else None
            ),
            "elapsed_ms": 1.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "usage_reported": None,
            "transport_attempts": 1,
        }

    def _observation(
        self,
        request: Mapping[str, Any],
        *,
        kind: str,
        references: list[dict[str, Any]],
        content: list[dict[str, Any]],
        route_completions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        source_receipt = self._receipt(request, kind=kind, output_body={})
        output_body = {
            "schema_version": "fin_ia_dell_specialist_tool_observation_v1_0",
            "action_attempt_id": request["action_attempt_id"],
            "kind": kind,
            "provenance_kind": "mcp_bridge",
            "status": "success",
            "request_digest": request["request_digest"],
            "references": references,
            "content": content,
            "route_completions": route_completions or [],
            "failure": None,
            "source_runtime_receipt": source_receipt,
        }
        host_receipt = {
            "receipt_id": f"host:{kind}:{request['request_digest'][:20]}",
            "kind": "host",
            "actor": "dell_specialist_agentic_mcp_bridge",
            "status": "success",
            "request_digest": request["request_digest"],
            "output_digest": canonical_sha256(output_body),
            "elapsed_ms": 1.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "usage_reported": None,
            "transport_attempts": 1,
        }
        body = {
            **output_body,
            "runtime_receipt": host_receipt,
        }
        return {**body, "observation_digest": canonical_sha256(body)}

    def disclosure(self, request: Mapping[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(request))
        return self._observation(
            request,
            kind="disclosure",
            references=[],
            content=[{"resource": "skill:dell:issuer-truth", "answer_free": True}],
        )

    def evidence(self, request: Mapping[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(request))
        self._evidence_calls += 1
        candidate = self._first_evidence_is_candidate and self._evidence_calls == 1
        ref_id = "C:DELL:Q1" if candidate else "E:DELL:Q1"
        authority = "retrieval_candidate" if candidate else "reviewed_evidence"
        completion_body = {
            "schema_version": "fin_ia_dell_specialist_route_completion_v1_0",
            "route_obligation_id": (
                "route:Q1_ISSUER_TRUTH:required-reviewed"
            ),
            "owner_data_gate_decision_digest": request[
                "owner_data_gate_decision_digest"
            ],
            "source_route_catalog_digest": request[
                "source_route_catalog_digest"
            ],
            "inventory_snapshot_digest": request["inventory_snapshot_digest"],
            "baseline_source_plan_digest": "8" * 64,
            "compilation_receipt_digest": "9" * 64,
            "reviewed_index_digests": ["7" * 64],
            "filter_receipt_digests": ["6" * 64],
            "expected_target_refs": ["compiled-target:F1", "compiled-target:F2"],
            "observed_target_refs": ["compiled-target:F1", "compiled-target:F2"],
            "source_family_refs": ["F1_SEC_ISSUER_FACTS", "F2_DELL_IR_EARNINGS"],
            "evidence_ids": [ref_id],
            "authority_status": "reviewed_evidence_complete",
        }
        return self._observation(
            request,
            kind="evidence",
            references=[
                {
                    "ref_id": ref_id,
                    "artifact_digest": ("c" if candidate else "e") * 64,
                    "authority_state": authority,
                    "writer_citable": not candidate,
                    "numeric_fact_authority": False,
                }
            ],
            content=[
                {
                    "ref_id": ref_id,
                    "bounded_excerpt": "Dell issuer evidence fixture.",
                    "candidate_only": candidate,
                }
            ],
            route_completions=(
                []
                if candidate
                else [
                    {
                        **completion_body,
                        "completion_digest": canonical_sha256(completion_body),
                    }
                ]
            ),
        )

    def finance(self, request: Mapping[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(request))
        return self._observation(
            request,
            kind="finance",
            references=[
                {
                    "ref_id": "F:DELL:REVENUE:FY27Q2",
                    "artifact_digest": "f" * 64,
                    "authority_state": "numeric_fact",
                    "writer_citable": False,
                    "numeric_fact_authority": True,
                }
            ],
            content=[
                {
                    "fact_id": "F:DELL:REVENUE:FY27Q2",
                    "metric_id": "revenue",
                    "period_end": "2026-07-31",
                    "value_decimal": "29800",
                    "unit": "USD million",
                }
            ],
        )


def _run(model: _ScriptedModel, tools: _ToolPorts) -> dict[str, Any]:
    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=model,
            evidence_tool=tools.evidence,
            finance_tool=tools.finance,
        )
    ).compile()
    return graph.invoke(_input(), {"recursion_limit": 50})


def test_specialist_runs_multi_turn_tools_then_accepts_source_bound_submission() -> None:
    model = _ScriptedModel(
        [
            _evidence_action(),
            _finance_action(),
            _submission(),
        ]
    )
    tools = _ToolPorts()

    result = _run(model, tools)

    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    assert result["phase"] == "specialist_submission_accepted"
    assert result["final_submission"]["terminal_state"] == "supported"
    assert notebook.status == "submitted"
    assert notebook.model_turn_count == 3
    assert tuple(record.turn_index for record in notebook.model_turn_records) == (
        1,
        2,
        3,
    )
    assert [record.action.action for record in notebook.model_turn_records] == [
        "request_evidence",
        "request_finance",
        "submit_workpaper",
    ]
    assert [record.context_digest for record in notebook.model_turn_records] == [
        request["context_digest"] for request in model.requests
    ]
    assert all(record.turn_source == "scripted_qualification" for record in notebook.model_turn_records)
    assert all(record.model_execution_evidence is False for record in notebook.model_turn_records)
    assert notebook.tool_action_count == 2
    assert notebook.required_route_obligation_ids == (
        "route:Q1_ISSUER_TRUTH:required-reviewed",
    )
    assert notebook.satisfied_route_obligation_ids == (
        "route:Q1_ISSUER_TRUTH:required-reviewed",
    )
    assert [row["action"]["action"] for row in tools.calls] == [
        "request_evidence",
        "request_finance",
    ]
    assert [row.kind for row in notebook.observations] == [
        "evidence",
        "finance",
    ]
    assert len({row["context_digest"] for row in model.requests}) == 3
    rendered = str(result).lower()
    assert "reasoning_content" not in rendered
    assert "chain_of_thought" not in rendered
    assert "api_key" not in rendered
    assert "method_context" not in model.requests[0]


def test_candidate_cannot_be_cited_as_evidence_and_typed_feedback_allows_repair() -> None:
    model = _ScriptedModel(
        [
            _evidence_action("Dell first candidate route"),
            _submission(evidence_id="C:DELL:Q1"),
            _evidence_action("Dell reviewed issuer route"),
            _finance_action(),
            _submission(),
        ]
    )
    tools = _ToolPorts(first_evidence_is_candidate=True)

    result = _run(model, tools)

    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    assert result["phase"] == "specialist_submission_accepted"
    assert any(
        row.code == "specialist_submission_reference_validation_failed"
        and "non_evidence_reference_cited:C:DELL:Q1" in row.message
        and row.public_information_gap_proved is False
        for row in notebook.feedback
    )
    assert notebook.model_turn_count == 5
    assert notebook.tool_action_count == 3


def test_identical_semantic_tool_request_is_blocked_before_second_dispatch() -> None:
    repeated = _evidence_action("Dell repeated reviewed route")
    model = _ScriptedModel(
        [
            repeated,
            repeated,
            _finance_action(),
            _submission(),
        ]
    )
    tools = _ToolPorts()

    result = _run(model, tools)

    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    evidence_calls = [
        row for row in tools.calls if row["action"]["action"] == "request_evidence"
    ]
    assert len(evidence_calls) == 1
    assert notebook.tool_action_count == 2
    assert any(
        row.code == "duplicate_tool_request_blocked_before_dispatch"
        for row in notebook.feedback
    )


def test_same_tool_intent_with_rewritten_rationale_is_still_blocked() -> None:
    model = _ScriptedModel(
        [
            _evidence_action_with_reason(
                query="Dell repeated reviewed route",
                reason="First wording for the same evidence request.",
            ),
            _evidence_action_with_reason(
                query="Dell repeated reviewed route",
                reason="Different prose must not create a new tool intent.",
            ),
            _finance_action(),
            _submission(),
        ]
    )
    tools = _ToolPorts()

    result = _run(model, tools)

    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    evidence_calls = [
        row for row in tools.calls if row["action"]["action"] == "request_evidence"
    ]
    assert len(evidence_calls) == 1
    assert any(
        row.code == "duplicate_tool_request_blocked_before_dispatch"
        for row in notebook.feedback
    )


def test_required_reviewed_route_must_succeed_before_submission() -> None:
    model = _ScriptedModel(
        [
            _submission(),
            _evidence_action(),
            _finance_action(),
            _submission(),
        ]
    )
    tools = _ToolPorts()

    result = _run(model, tools)

    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    assert result["phase"] == "specialist_submission_accepted"
    assert any(
        "required_route_unsatisfied:route:Q1_ISSUER_TRUTH:required-reviewed"
        in row.message
        for row in notebook.feedback
    )


def test_candidate_cannot_bypass_authority_gate_through_fact_ids() -> None:
    candidate_submission = _action(
        "submit_workpaper",
        terminal_state="supported",
        thesis="A candidate must not become a deliverable fact by changing fields.",
        mechanism="The attempted submission deliberately exercises the ref-type gate.",
        narrative_markdown="This draft is expected to be rejected by the runtime.",
        claims=[
            {
                "claim_id": "claim:q1:candidate-bypass",
                "kind": "inference",
                "materiality": "high",
                "statement": "The candidate supposedly supports a material inference.",
                "evidence_ids": [],
                "fact_ids": ["C:DELL:Q1"],
                "numeric_authority": "not_applicable",
                "authority_note": "A candidate is not accepted authority.",
            }
        ],
        counterevidence=["The source has not passed Evidence admission."],
        what_would_change=["Promotion to reviewed Evidence with a valid receipt."],
        open_gaps=["The candidate still requires review."],
    )
    model = _ScriptedModel(
        [
            _evidence_action("Dell candidate-only route"),
            candidate_submission,
            _evidence_action("Dell reviewed issuer route"),
            _finance_action(),
            _submission(),
        ]
    )
    tools = _ToolPorts(first_evidence_is_candidate=True)

    result = _run(model, tools)

    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    assert result["phase"] == "specialist_submission_accepted"
    assert any(
        "fact_reference_authority_invalid:inference:C:DELL:Q1" in row.message
        for row in notebook.feedback
    )


def test_bounded_gap_cannot_be_declared_without_canonical_gap_receipt() -> None:
    gap_submission = _action(
        "submit_workpaper",
        terminal_state="bounded_gap",
        thesis="The branch is claimed to be a public-information gap.",
        mechanism="No canonical route-exhaustion proof is attached.",
        narrative_markdown="The runtime must reject this attempted terminal gap.",
        claims=[],
        counterevidence=["A tool result alone does not prove source exhaustion."],
        what_would_change=["A canonical GapEligibilityReceipt."],
        open_gaps=["Route-exhaustion authority is absent."],
    )
    model = _ScriptedModel(
        [
            _evidence_action(),
            gap_submission,
            _finance_action(),
            _submission(),
        ]
    )
    tools = _ToolPorts()

    result = _run(model, tools)

    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    assert result["phase"] == "specialist_submission_accepted"
    assert any(
        "bounded_gap_requires_canonical_gap_eligibility_receipt" in row.message
        for row in notebook.feedback
    )


def test_calculation_cannot_ship_before_canonical_calculation_receipt_exists() -> None:
    calculation_submission = _action(
        "submit_workpaper",
        terminal_state="supported",
        thesis="A locally computed ratio is proposed for the workpaper.",
        mechanism="The calculation is labeled non-authoritative but lacks its receipt.",
        narrative_markdown="The runtime must reject the unreceipted calculation.",
        claims=[
            {
                "claim_id": "claim:q1:calculation",
                "kind": "calculation",
                "materiality": "high",
                "statement": "A derived ratio was calculated from research inputs.",
                "evidence_ids": ["E:DELL:Q1"],
                "fact_ids": [],
                "numeric_authority": "non_authoritative",
                "authority_note": "Derived research metric, not issuer-reported fact.",
            }
        ],
        counterevidence=["No CalculationReceipt is bound to the inputs and formula."],
        what_would_change=["A canonical receipt binding formula, inputs, and units."],
        open_gaps=["Calculation authority remains unavailable in Wave 2."],
    )
    model = _ScriptedModel(
        [
            _evidence_action(),
            calculation_submission,
            _finance_action(),
            _submission(),
        ]
    )
    tools = _ToolPorts()

    result = _run(model, tools)

    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    assert result["phase"] == "specialist_submission_accepted"
    assert any(
        "calculation_requires_canonical_receipt:claim:q1:calculation"
        in row.message
        for row in notebook.feedback
    )


def test_same_reference_id_with_different_artifact_digest_fails_closed() -> None:
    result = _run(
        _ScriptedModel([_evidence_action(), _finance_action(), _submission()]),
        _ToolPorts(),
    )
    notebook_body = {
        key: value
        for key, value in result["notebook"].items()
        if key != "notebook_digest"
    }
    conflicting = json.loads(json.dumps(notebook_body["observations"][0]))
    conflicting["references"][0]["artifact_digest"] = "0" * 64
    output_body = {
        key: value
        for key, value in conflicting.items()
        if key not in {"runtime_receipt", "observation_digest"}
    }
    conflicting["runtime_receipt"]["output_digest"] = canonical_sha256(
        output_body
    )
    conflicting_body = {
        key: value
        for key, value in conflicting.items()
        if key != "observation_digest"
    }
    conflicting["observation_digest"] = canonical_sha256(conflicting_body)
    SpecialistToolObservation.model_validate_json(json.dumps(conflicting))
    notebook_body["observations"].append(conflicting)
    notebook = SpecialistNotebook.model_validate_json(
        json.dumps(
            {
                **notebook_body,
                "notebook_digest": canonical_sha256(notebook_body),
            }
        )
    )
    submission = SubmitWorkpaperAction.model_validate_json(
        json.dumps(result["final_submission"])
    )

    assert (
        "reference_identity_conflict:E:DELL:Q1"
        in _submission_errors(submission, notebook)
    )


def test_tool_exception_becomes_typed_non_gap_feedback_before_model_replans() -> None:
    model = _ScriptedModel(
        [
            _evidence_action("Dell route whose adapter fails"),
            _action(
                "request_human_review",
                blocker_code="tool_owner_repair_required",
            ),
        ]
    )
    tools = _ToolPorts()

    def failing_evidence(_request: Mapping[str, Any]) -> dict[str, Any]:
        raise RuntimeError("private adapter detail must not enter graph state")

    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=model,
            evidence_tool=failing_evidence,
            finance_tool=tools.finance,
        )
    ).compile()
    result = graph.invoke(_input(), {"recursion_limit": 30})

    notebook = SpecialistNotebook.model_validate_json(
        json.dumps(result["notebook"])
    )
    handoff = SpecialistHumanReviewHandoff.model_validate_json(
        json.dumps(result["human_review_handoff"])
    )
    assert result["phase"] == "specialist_human_review_handoff_emitted"
    assert "__interrupt__" not in result
    assert handoff.trigger == "model_request"
    assert handoff.reason_code == "tool_owner_repair_required"
    assert handoff.notebook_digest == notebook.notebook_digest
    assert handoff.continuation_authorized is False
    assert handoff.required_resume_authority == (
        "canonical_intervention_authority_unavailable"
    )
    assert handoff.server_checkpoint_binding_state == (
        "qualification_terminal_not_server_bound"
    )
    assert notebook.tool_action_count == 1
    assert len(notebook.observations) == 1
    assert notebook.observations[0].status == "tool_failure"
    assert notebook.observations[0].failure is not None
    assert notebook.observations[0].failure.public_information_gap_proved is False
    assert any(
        row.code == "tool_port_exception"
        and row.owner_layer == "tool"
        and row.public_information_gap_proved is False
        for row in notebook.feedback
    )
    rendered = json.dumps(result, ensure_ascii=False)
    assert "private adapter detail" not in rendered


def test_unavailable_disclosure_is_not_advertised_or_dispatched() -> None:
    model = _ScriptedModel(
        [
            _action(
                "request_disclosure",
                selection={
                    "kind": "skill",
                    "ref": "skill:dell:issuer-truth",
                    "depth": "summary",
                    "reason": "Try an unavailable disclosure path.",
                    "expected_use": "Prove the host fails closed.",
                    "parent_receipt_digest": None,
                },
            ),
        ]
    )
    tools = _ToolPorts()
    graph_input = _input()
    graph_input["l0_context"]["disclosure_runtime_state"] = (
        "current_state_authority_unavailable_fail_closed"
    )
    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=model,
            evidence_tool=tools.evidence,
            finance_tool=tools.finance,
        )
    ).compile()

    with pytest.raises(
        DellSpecialistAgenticGraphError,
        match="specialist_model_action_invalid",
    ):
        graph.invoke(graph_input, {"recursion_limit": 20})

    assert "request_disclosure" not in model.requests[0]["allowed_actions"]
    assert tools.calls == []


def test_caller_cannot_declare_disclosure_authority_available() -> None:
    model = _ScriptedModel(
        [_action("request_human_review", blocker_code="should_not_execute")]
    )
    tools = _ToolPorts()
    graph_input = _input()
    graph_input["l0_context"]["disclosure_runtime_state"] = (
        "current_state_authority_available"
    )
    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=model,
            evidence_tool=tools.evidence,
            finance_tool=tools.finance,
        )
    ).compile()

    with pytest.raises(
        DellSpecialistAgenticGraphError,
        match="specialist_agentic_input_invalid",
    ):
        graph.invoke(graph_input, {"recursion_limit": 10})
    assert model.requests == []
    assert tools.calls == []


def test_unassigned_evidence_route_is_rejected_before_tool_dispatch() -> None:
    foreign = _evidence_action("Dell foreign route")

    def foreign_route(request: Mapping[str, Any]) -> dict[str, Any]:
        action = foreign(request)
        action["minimum_route_obligation_id"] = "route:Q2_DEMAND:foreign"
        return action

    model = _ScriptedModel(
        [
            foreign_route,
            _action(
                "request_human_review",
                blocker_code="route_not_assigned",
            ),
        ]
    )
    tools = _ToolPorts()

    result = _run(model, tools)
    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))

    assert tools.calls == []
    assert notebook.tool_action_count == 0
    assert any(
        row.code == "specialist_evidence_route_not_assigned"
        for row in notebook.feedback
    )
    assert result["phase"] == "specialist_human_review_handoff_emitted"


def test_tool_action_ceiling_emits_terminal_handoff_without_extra_dispatch() -> None:
    model = _ScriptedModel([_evidence_action(), _finance_action()])
    tools = _ToolPorts()
    graph_input = _input()
    graph_input["max_tool_actions"] = 1
    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=model,
            evidence_tool=tools.evidence,
            finance_tool=tools.finance,
        )
    ).compile()

    result = graph.invoke(graph_input, {"recursion_limit": 20})
    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    handoff = SpecialistHumanReviewHandoff.model_validate_json(
        json.dumps(result["human_review_handoff"])
    )

    assert [call["action"]["action"] for call in tools.calls] == [
        "request_evidence"
    ]
    assert notebook.tool_action_count == 1
    assert handoff.trigger == "tool_action_ceiling"
    assert handoff.reason_code == "tool_action_ceiling_reached_no_silent_completion"
    assert result["phase"] == "specialist_human_review_handoff_emitted"


def test_model_turn_ceiling_emits_terminal_handoff_without_silent_submission() -> None:
    model = _ScriptedModel([_evidence_action(), _finance_action()])
    tools = _ToolPorts()
    graph_input = _input()
    graph_input["max_model_turns"] = 2
    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=model,
            evidence_tool=tools.evidence,
            finance_tool=tools.finance,
        )
    ).compile()

    result = graph.invoke(graph_input, {"recursion_limit": 20})
    notebook = SpecialistNotebook.model_validate_json(json.dumps(result["notebook"]))
    handoff = SpecialistHumanReviewHandoff.model_validate_json(
        json.dumps(result["human_review_handoff"])
    )

    assert notebook.model_turn_count == 2
    assert notebook.status == "human_review_required"
    assert result["final_submission"] is None
    assert handoff.trigger == "model_turn_ceiling"
    assert handoff.reason_code == "model_turn_ceiling_reached_no_silent_completion"
    assert result["phase"] == "specialist_human_review_handoff_emitted"


def test_stale_context_bound_action_is_rejected_before_any_tool() -> None:
    def stale(_request: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "action": "request_evidence",
            "context_digest": "0" * 64,
            "reason_summary": "Use a stale request on purpose.",
            "minimum_route_obligation_id": "route:Q1_ISSUER_TRUTH:required-reviewed",
            "intent": {
                "intent_kind": "reviewed_evidence",
                "query": "Dell stale request",
                "purpose": "Prove stale context is rejected before tool dispatch.",
                "entity_refs": ["DELL"],
                "period_intents": [],
                "expected_information_gain": "Exercise the stale action guard.",
                "limit": 3,
                "topic_refs": ["operating_performance"],
                "evidence_role_refs": [],
                "minimum_authority_tier": "reviewed",
            },
        }

    class StaleModel:
        def __call__(self, request: Mapping[str, Any]) -> dict[str, Any]:
            return stale(request)

    tools = _ToolPorts()
    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=StaleModel(),
            evidence_tool=tools.evidence,
            finance_tool=tools.finance,
        )
    ).compile()

    with pytest.raises(
        DellSpecialistAgenticGraphError,
        match="specialist_model_turn_context_binding_invalid",
    ):
        graph.invoke(_input(), {"recursion_limit": 20})
    assert tools.calls == []


def test_model_transport_exception_is_redacted_at_graph_boundary() -> None:
    tools = _ToolPorts()

    def failing_model(_request: Mapping[str, Any]) -> dict[str, Any]:
        raise RuntimeError("private provider response and credential detail")

    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=failing_model,
            evidence_tool=tools.evidence,
            finance_tool=tools.finance,
        )
    ).compile()

    with pytest.raises(
        DellSpecialistAgenticGraphError,
        match="specialist_model_turn_failed",
    ) as raised:
        graph.invoke(_input(), {"recursion_limit": 10})

    assert str(raised.value) == "specialist_model_turn_failed"
    assert raised.value.__suppress_context__ is True
    assert "private provider response" not in str(raised.value)
    assert tools.calls == []


def test_model_port_cannot_self_issue_a_runtime_receipt() -> None:
    class SelfIssuingModel:
        def __call__(self, request: Mapping[str, Any]) -> dict[str, Any]:
            action = {
                **_evidence_action("Dell self-issued receipt")(request),
                "context_digest": request["context_digest"],
            }
            return {"action": action, "runtime_receipt": {"status": "success"}}

    tools = _ToolPorts()
    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=SelfIssuingModel(),
            evidence_tool=tools.evidence,
            finance_tool=tools.finance,
        )
    ).compile()

    with pytest.raises(
        DellSpecialistAgenticGraphError,
        match="specialist_model_action_invalid",
    ):
        graph.invoke(_input(), {"recursion_limit": 20})
    assert tools.calls == []


@pytest.mark.parametrize(
    ("turn_source", "model_execution_evidence"),
    [
        ("provider_model", True),
        ("saved_response_replay", False),
    ],
)
def test_receipted_turn_is_bound_to_composition_owned_source(
    turn_source: str,
    model_execution_evidence: bool,
) -> None:
    tools = _ToolPorts()
    requests: list[dict[str, Any]] = []

    def receipted_turn(request: Mapping[str, Any]) -> dict[str, Any]:
        request_value = dict(request)
        requests.append(request_value)
        action = {
            **_action(
                "request_human_review",
                blocker_code="explicit_owner_review",
            )(request),
            "context_digest": request["context_digest"],
        }
        receipt_overrides = (
            {}
            if turn_source == "provider_model"
            else {
                "receipt_id": "host:specialist-replay:fixture",
                "kind": "host",
                "actor": "dell_specialist_saved_response_replay",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "usage_reported": None,
            }
        )
        return {
            "action": action,
            "runtime_receipt": _model_turn_receipt(
                request,
                action,
                **receipt_overrides,
            ),
        }

    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=receipted_turn,
            evidence_tool=tools.evidence,
            finance_tool=tools.finance,
            turn_source=turn_source,
        )
    ).compile()

    result = graph.invoke(_input(), {"recursion_limit": 10})
    notebook = SpecialistNotebook.model_validate_json(
        json.dumps(result["notebook"])
    )
    record = notebook.model_turn_records[0]
    assert record.turn_source == turn_source
    assert record.model_execution_evidence is model_execution_evidence
    assert record.runtime_receipt is not None
    assert record.runtime_receipt.kind == (
        "model" if turn_source == "provider_model" else "host"
    )
    assert record.runtime_receipt.actor == (
        _input()["agent_id"]
        if turn_source == "provider_model"
        else "dell_specialist_saved_response_replay"
    )
    assert record.runtime_receipt.request_digest == canonical_sha256(requests[0])
    assert record.runtime_receipt.output_digest == record.action_digest
    assert record.runtime_receipt.total_tokens == (
        138 if turn_source == "provider_model" else 0
    )
    assert result["phase"] == "specialist_human_review_handoff_emitted"
    assert tools.calls == []


@pytest.mark.parametrize(
    "receipt_override",
    [
        {"kind": "host", "usage_reported": None},
        {"actor": "attacker-model"},
        {"request_digest": "0" * 64},
        {"output_digest": "0" * 64},
        {"transport_attempts": 2},
    ],
)
def test_receipted_turn_rejects_unbound_receipt_before_dispatch(
    receipt_override: dict[str, Any],
) -> None:
    tools = _ToolPorts()

    def tampered_turn(request: Mapping[str, Any]) -> dict[str, Any]:
        action = {
            **_evidence_action("Dell receipt binding")(request),
            "context_digest": request["context_digest"],
        }
        return {
            "action": action,
            "runtime_receipt": _model_turn_receipt(
                request,
                action,
                **receipt_override,
            ),
        }

    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=tampered_turn,
            evidence_tool=tools.evidence,
            finance_tool=tools.finance,
            turn_source="provider_model",
        )
    ).compile()

    with pytest.raises(
        DellSpecialistAgenticGraphError,
        match="specialist_model_turn_receipt_binding_invalid",
    ):
        graph.invoke(_input(), {"recursion_limit": 10})
    assert tools.calls == []


def test_structured_failure_receipt_is_bound_to_exact_failure_payload() -> None:
    failure = {
        "code": "failure-A",
        "owning_plane": "tool_adapter",
        "retryability": "owner_repair_required",
        "public_information_gap_proved": False,
    }
    output_body = {
        "schema_version": "fin_ia_dell_specialist_tool_observation_v1_0",
        "action_attempt_id": "action-attempt:failure-binding",
        "kind": "evidence",
        "provenance_kind": "runtime_failure",
        "status": "tool_failure",
        "request_digest": "7" * 64,
        "references": [],
        "content": [],
        "route_completions": [],
        "failure": failure,
        "source_runtime_receipt": None,
    }
    body = {
        **output_body,
        "runtime_receipt": {
            "receipt_id": "host:failure-binding",
            "kind": "host",
            "actor": "dell_specialist_agentic_runtime",
            "status": "failure",
            "request_digest": "7" * 64,
            "output_digest": canonical_sha256(output_body),
            "elapsed_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "usage_reported": None,
            "transport_attempts": 1,
        },
    }
    valid = {**body, "observation_digest": canonical_sha256(body)}
    SpecialistToolObservation.model_validate_json(json.dumps(valid))

    mutated = json.loads(json.dumps(valid))
    mutated["failure"]["code"] = "failure-B"
    mutated["observation_digest"] = canonical_sha256(
        {key: value for key, value in mutated.items() if key != "observation_digest"}
    )

    with pytest.raises(ValueError, match="specialist_observation_output_receipt_mismatch"):
        SpecialistToolObservation.model_validate_json(json.dumps(mutated))


def test_mcp_bridge_observation_rejects_wrong_host_actor_even_if_rehashed() -> None:
    tools = _ToolPorts()
    valid = tools._observation(
        {
            "action_attempt_id": "action-attempt:actor-binding",
            "request_digest": "8" * 64,
        },
        kind="evidence",
        references=[],
        content=[],
    )
    mutated = json.loads(json.dumps(valid))
    mutated["runtime_receipt"]["actor"] = "attacker-tool"
    mutated["observation_digest"] = canonical_sha256(
        {key: value for key, value in mutated.items() if key != "observation_digest"}
    )

    with pytest.raises(ValueError, match="specialist_observation_mcp_identity_invalid"):
        SpecialistToolObservation.model_validate_json(json.dumps(mutated))


def test_direct_tool_completion_cannot_satisfy_a_required_route() -> None:
    tools = _ToolPorts()
    request = {
        "action_attempt_id": "action-attempt:direct-completion",
        "request_digest": "5" * 64,
        "owner_data_gate_decision_digest": "f" * 64,
        "source_route_catalog_digest": "d" * 64,
        "inventory_snapshot_digest": "e" * 64,
    }
    valid_mcp = tools.evidence(request)
    output_body = {
        key: value
        for key, value in valid_mcp.items()
        if key not in {"runtime_receipt", "observation_digest"}
    }
    output_body["provenance_kind"] = "direct_tool"
    output_body["source_runtime_receipt"] = None
    direct_receipt = tools._receipt(
        request,
        kind="evidence",
        output_body=output_body,
    )
    direct_body = {**output_body, "runtime_receipt": direct_receipt}

    with pytest.raises(
        ValueError,
        match="specialist_observation_route_completion_invalid",
    ):
        SpecialistToolObservation.model_validate_json(
            json.dumps(
                {
                    **direct_body,
                    "observation_digest": canonical_sha256(direct_body),
                }
            )
        )


def test_provider_action_schema_exposes_no_physical_or_authority_write_fields() -> None:
    schema_text = str(__import__("pydantic").TypeAdapter(SpecialistAction).json_schema())

    assert "request_disclosure" not in schema_text
    for forbidden in (
        "route_ids",
        "retrieval_lanes",
        "source_roles",
        "issuer_ids",
        "action_attempt_id",
        "runtime_scope",
        "evidence_admission",
        "public_information_gap_authority",
    ):
        assert forbidden not in schema_text


def test_graph_topology_is_a_real_cycle_not_a_single_step_wrapper() -> None:
    tools = _ToolPorts()
    graph = build_dell_specialist_agentic_state_graph(
        dependencies=DellSpecialistAgenticDependencies(
            model_turn=lambda _request: {},
            evidence_tool=tools.evidence,
            finance_tool=tools.finance,
        )
    ).compile()
    drawable = graph.get_graph()
    edges = {(edge.source, edge.target) for edge in drawable.edges}

    assert {
        "initialize",
        "model_decide",
        "execute_evidence",
        "execute_finance",
        "validate_submission",
        "human_review",
    }.issubset(drawable.nodes)
    assert ("execute_evidence", "model_decide") in edges
    assert ("execute_finance", "model_decide") in edges
    assert ("validate_submission", "model_decide") in edges
