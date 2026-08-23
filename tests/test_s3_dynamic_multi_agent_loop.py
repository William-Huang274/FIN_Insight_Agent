from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from retrieval.contracts import load_financial_research_kernel
from retrieval.route_compiler import load_query_object_fact_route_policy
from sec_agent.research.dynamic_multi_agent_loop import (
    DynamicMultiAgentLoopError,
    compile_dynamic_multi_agent_role_programs,
    compile_role_material_requirement_blueprints,
    compile_role_stop_decision,
    load_dynamic_multi_agent_loop_policy,
    normalize_bound_specialist_workpaper,
)
from sec_agent.research.multi_agent_preview import (
    SPECIALIST_WORKPAPER_SCHEMA_VERSION,
    compile_planner_payload_from_role_opinions,
    load_multi_agent_role_topology,
    validate_lead_plan_checkpoint,
    validate_specialist_plan_checkpoint,
    validate_specialist_workpaper,
)
from sec_agent.research.multi_agent_preview_runtime import (
    load_preview_planning_policy,
)
from sec_agent.runtime_resource_registry import read_registered_runtime_json
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from scripts.research.run_s3_current_dynamic_multi_agent import (
    LIVE_AUTHORITY_SCHEMA,
    LIVE_AUTHORITY_STATUS,
    SPECIALIST_WORKPAPER_SUBMISSION_TOOL_NAME,
    _bind_predecessor_session_event,
    _call_live_tool,
    _call_live_tool_draft,
    _provider_attempt_count,
    _tool_draft,
    _tool_arguments,
    expected_live_execution_budget,
    expected_submission_repair_resume_budget,
    expected_submission_resume_budget,
    expected_submission_successor_budget,
    validate_live_authority,
)
from sec_agent.providers.chat_completions import (
    ChatCompletionToolStepResult,
    ModelGatewayError,
)


ROOT = Path(__file__).resolve().parents[1]


def test_submission_successor_workpaper_tool_name_is_bound_at_module_import() -> None:
    assert (
        SPECIALIST_WORKPAPER_SUBMISSION_TOOL_NAME
        == "submit_specialist_workpaper_judgment"
    )


def _load(ref: str) -> dict:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _inputs() -> tuple:
    topology = load_multi_agent_role_topology(
        _load("configs/research/fin_ia_0_1_3_multi_agent_role_topology_v1_0.json")
    )
    checkpoint = validate_specialist_plan_checkpoint(
        _load(
            "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_R3_specialist_plan_checkpoint_v1_0.json"
        ),
        topology=topology,
    )
    opinions = checkpoint["specialist_plans"]
    lead = validate_lead_plan_checkpoint(
        _load(
            "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_R6_lead_plan_checkpoint_v1_0.json"
        ),
        opinions=opinions,
        topology=topology,
    )["lead_plan"]
    kernel = load_financial_research_kernel(
        read_registered_runtime_json(
            ROOT, "application.config.current_financial_research_kernel"
        )
    )
    route = load_query_object_fact_route_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        kernel,
    )
    planning = load_preview_planning_policy(ROOT, route_policy=route)
    compiled = compile_planner_payload_from_role_opinions(
        objective_id="OBJECTIVE::TEST",
        opinions=opinions,
        lead_plan=lead,
        topology=topology,
    )
    return topology, kernel, route, planning, compiled


def test_role_partition_recovers_all_thirteen_facets_before_execution() -> None:
    topology, kernel, route, planning, compiled = _inputs()
    result = compile_dynamic_multi_agent_role_programs(
        policy=_load(
            "configs/research/fin_ia_0_1_3_s3_current_dynamic_multi_agent_loop_policy_v1_0.json"
        ),
        topology=topology,
        objective_payload=_load(
            "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_objective_v1_0.json"
        ),
        planner_compilation=compiled,
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
    )

    assert result["summary"] == {
        "specialist_role_count": 6,
        "assigned_facet_count": 13,
        "compiled_request_count": 13,
        "deferred_facet_count": 0,
        "independent_session_required_count": 6,
        "model_calls": 0,
        "network_calls": 0,
    }
    supply = next(
        row
        for row in result["role_programs"]
        if row["agent_id"] == "AGENT::SUPPLY_RELATIONSHIP"
    )
    assert supply["facet_ids"] == [
        "upstream_capacity_context",
        "counterparty_direct_mention",
        "subject_relationship_disclosure",
    ]
    assert len(supply["requests"]) == 3
    assert supply["loop_policy"]["coverage_groups"][
        "counterparty_direct_mention"
    ]
    blueprints = compile_role_material_requirement_blueprints(supply)
    assert set(blueprints) == {
        row["request_id"] for row in supply["requests"]
    }
    direct_mention = next(
        row
        for row in supply["requests"]
        if row["requested_facet_ids"] == ["counterparty_direct_mention"]
    )
    assert {
        row["role"]
        for row in blueprints[direct_mention["request_id"]][
            "material_requirements"
        ]
    } == {"direct", "context"}


def test_role_partition_fails_closed_when_one_facet_is_missing() -> None:
    topology, kernel, route, planning, compiled = _inputs()
    mutated = deepcopy(compiled)
    mutated["planner_payload"]["atoms"] = [
        row
        for row in mutated["planner_payload"]["atoms"]
        if row["facet_id"] != "counterparty_direct_mention"
    ]
    with pytest.raises(
        DynamicMultiAgentLoopError,
        match="dynamic_multi_agent_atom_partition_invalid",
    ):
        compile_dynamic_multi_agent_role_programs(
            policy=_load(
                "configs/research/fin_ia_0_1_3_s3_current_dynamic_multi_agent_loop_policy_v1_0.json"
            ),
            topology=topology,
            objective_payload=_load(
                "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_objective_v1_0.json"
            ),
            planner_compilation=mutated,
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
        )


def test_role_policy_rejects_overlapping_facet_ownership() -> None:
    topology, *_ = _inputs()
    policy = _load(
        "configs/research/fin_ia_0_1_3_s3_current_dynamic_multi_agent_loop_policy_v1_0.json"
    )
    policy["specialist_roles"][1]["facet_ids"][0] = "orders_and_backlog"
    with pytest.raises(
        DynamicMultiAgentLoopError,
        match="dynamic_multi_agent_policy_role_invalid",
    ):
        load_dynamic_multi_agent_loop_policy(policy, topology=topology)


def test_role_stop_distinguishes_catalog_exhaustion_from_sufficiency() -> None:
    assert compile_role_stop_decision(
        next_request_ids=["REQ::NEXT"], open_gap_refs=[], feedback_refs=[]
    ) == "continue"
    assert compile_role_stop_decision(
        next_request_ids=[], open_gap_refs=["GAP::OPEN"], feedback_refs=[]
    ) == "stop_no_progress"
    assert compile_role_stop_decision(
        next_request_ids=[], open_gap_refs=[], feedback_refs=["FEEDBACK::OPEN"]
    ) == "stop_no_progress"
    assert compile_role_stop_decision(
        next_request_ids=[], open_gap_refs=[], feedback_refs=[]
    ) == "stop_sufficient"


def _minimal_workpaper_context(agent_id: str) -> dict:
    return {
        "context_digest": "CONTEXT::BOUND",
        "agent": {"agent_id": agent_id},
        "cell_analysis_view": {
            "cell": {
                "cell_evidence_views": [{"evidence_ref": "EV::ONE"}],
                "allowed_numeric_refs": ["NUM::ONE"],
                "allowed_numeric_relation_refs": ["REL::ONE"],
                "residual_gap_cards": [{"gap_ref": "GAP::ONE"}],
            }
        },
    }


def _bound_workpaper(agent_id: str) -> tuple[dict, dict]:
    context = _minimal_workpaper_context(agent_id)
    payload = {
        "schema_version": SPECIALIST_WORKPAPER_SCHEMA_VERSION,
        "agent_id": agent_id,
        "thesis": "现有证据支持有限的公司层判断，但不支持把全部利润变化归因于单一产品。",
        "confidence": "medium",
        "sourced_claims": [
            {
                "claim": "公司披露直接支持当前经营结果，但产品到利润的桥接仍不完整。",
                "authority": "sourced_fact",
                "evidence_refs": ["EV::ONE"],
                "numeric_refs": ["NUM::ONE"],
                "numeric_relation_refs": ["REL::ONE"],
            }
        ],
        "mechanism": "规模、组合、成本和费用杠杆可能共同影响利润，当前资料不能只分配给单一产品。",
        "alternative_explanations": ["其他业务组合也可能解释公司层利润变化。"],
        "strongest_counterarguments": ["产品到公司利润的直接桥接仍然缺失。"],
        "remaining_gap_refs": ["GAP::ONE"],
        "what_would_change": ["获得同期间产品收入和利润桥后重新裁决。"],
        "cross_role_challenges": [],
        "stop_reason": "当前证据只支持有限结论，剩余问题保留为可追溯缺口。",
    }
    return (
        validate_specialist_workpaper(
            payload,
            context=context,
            expected_agent_id=agent_id,
        ),
        context,
    )


def test_workpaper_digest_normalization_accepts_only_reproducible_legacy_bug() -> None:
    agent_id = "AGENT::VALUE_CAPTURE"
    bound, context = _bound_workpaper(agent_id)
    canonical, canonical_receipt = normalize_bound_specialist_workpaper(
        bound,
        context=context,
        expected_agent_id=agent_id,
    )
    assert canonical == bound
    assert canonical_receipt["status"] == "canonical"

    legacy = deepcopy(bound)
    legacy["workpaper_digest"] = canonical_digest(bound)
    normalized, receipt = normalize_bound_specialist_workpaper(
        legacy,
        context=context,
        expected_agent_id=agent_id,
        allow_legacy_double_hash=True,
    )
    assert normalized == bound
    assert receipt["status"] == "legacy_double_hash_normalized"
    assert receipt["input_workpaper_digest"] == legacy["workpaper_digest"]
    assert receipt["canonical_workpaper_digest"] == bound["workpaper_digest"]
    assert receipt["content_changed"] is False
    assert receipt["authority_refs_changed"] is False

    with pytest.raises(
        DynamicMultiAgentLoopError,
        match="dynamic_multi_agent_bound_workpaper_digest_invalid",
    ):
        normalize_bound_specialist_workpaper(
            legacy,
            context=context,
            expected_agent_id=agent_id,
        )

    tampered = deepcopy(legacy)
    tampered["thesis"] += " 未经摘要绑定的改写。"
    with pytest.raises(
        DynamicMultiAgentLoopError,
        match="dynamic_multi_agent_bound_workpaper_digest_invalid",
    ):
        normalize_bound_specialist_workpaper(
            tampered,
            context=context,
            expected_agent_id=agent_id,
            allow_legacy_double_hash=True,
        )


def _provider_step(*, name: str, arguments: dict) -> ChatCompletionToolStepResult:
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="fixture",
        model="fixture-model",
        content="",
        reasoning_content="private reasoning must not be persisted",
        tool_calls=(
            {
                "id": "call-fixture",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            },
        ),
        finish_reason="tool_calls",
        usage={"prompt_tokens": 20, "completion_tokens": 10},
        request_capture_ref=str(ROOT / "data/captures/request.json"),
        response_capture_ref=str(ROOT / "data/captures/response.json"),
        request_digest="a" * 64,
        response_digest="b" * 64,
        private_reasoning_fields_redacted=1,
    )


def test_live_budget_is_derived_from_six_bounded_role_loops() -> None:
    assert expected_live_execution_budget() == {
        "maximum_model_calls": 29,
        "maximum_transport_attempts": 29,
        "maximum_specialist_sessions": 6,
        "maximum_retrieval_rounds": 12,
        "maximum_s1_s2_requests": 13,
        "maximum_lead_coordination_rounds": 2,
        "maximum_role_repairs": 3,
        "maximum_external_source_network_calls": 0,
        "retries_per_model_node": 0,
        "fallbacks": 0,
        "candidate_promotions": 0,
        "current_product_pointer_mutations": 0,
    }


def test_submission_successor_budget_is_derived_from_capture_bound_topology() -> None:
    budget = expected_submission_successor_budget()
    assert budget["maximum_new_model_calls"] == 25
    assert sum(
        budget[key]
        for key in (
            "reflection_submissions_from_R1_captures",
            "supply_followup_reflection_drafts",
            "supply_followup_reflection_submissions",
            "new_specialist_workpaper_drafts",
            "specialist_workpaper_submissions",
            "lead_coordination_drafts",
            "lead_coordination_submissions",
            "role_repair_drafts",
            "role_repair_submissions",
        )
    ) == budget["maximum_new_model_calls"]
    assert budget["maximum_new_s1_s2_requests"] == 1
    assert budget["maximum_external_source_network_calls"] == 0


def test_submission_resume_budget_counts_only_unfinished_R3_frontier() -> None:
    budget = expected_submission_resume_budget()
    assert budget["maximum_new_model_calls"] == 17
    assert sum(
        budget[key]
        for key in (
            "reflection_submissions_from_R1_captures",
            "supply_followup_reflection_drafts",
            "supply_followup_reflection_submissions",
            "new_specialist_workpaper_drafts",
            "specialist_workpaper_submissions",
            "lead_coordination_drafts",
            "lead_coordination_submissions",
            "role_repair_drafts",
            "role_repair_submissions",
        )
    ) == budget["maximum_new_model_calls"]
    assert budget["new_specialist_workpaper_drafts"] == 2
    assert budget["specialist_workpaper_submissions"] == 2
    assert budget["maximum_new_s1_s2_requests"] == 1
    assert budget["retries"] == 0


def test_submission_repair_resume_budget_counts_only_repairs_and_lead_R2() -> None:
    budget = expected_submission_repair_resume_budget()
    assert budget["maximum_new_model_calls"] == 8
    assert sum(
        budget[key]
        for key in (
            "reflection_submissions_from_R1_captures",
            "supply_followup_reflection_drafts",
            "supply_followup_reflection_submissions",
            "new_specialist_workpaper_drafts",
            "specialist_workpaper_submissions",
            "lead_coordination_drafts",
            "lead_coordination_submissions",
            "role_repair_drafts",
            "role_repair_submissions",
        )
    ) == budget["maximum_new_model_calls"]
    assert budget["role_repair_drafts"] == 3
    assert budget["role_repair_submissions"] == 3
    assert budget["lead_coordination_drafts"] == 1
    assert budget["lead_coordination_submissions"] == 1
    assert budget["maximum_new_s1_s2_requests"] == 1
    assert budget["maximum_new_retrieval_rounds"] == 1
    assert budget["retries"] == 0


def test_live_authority_rejects_budget_drift_before_execution(tmp_path: Path) -> None:
    authority = {
        "schema_version": LIVE_AUTHORITY_SCHEMA,
        "status": LIVE_AUTHORITY_STATUS,
        "signed_at": "2026-08-23T00:00:00Z",
        "implementation_commit": "0" * 40,
        "case_key": "DELL",
        "execution_budget": {"maximum_model_calls": 30},
        "bound_inputs": {},
        "output_contract": {},
        "known_boundary": "x" * 160,
    }
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    with pytest.raises(
        DynamicMultiAgentLoopError,
        match="dynamic_multi_agent_live_authority_identity_or_budget_invalid",
    ):
        validate_live_authority(authority, authority_path=path.resolve())


def test_live_provider_seam_records_exact_once_attempt_and_parses_tool(
    tmp_path: Path,
) -> None:
    calls: list[dict] = []

    def executor(**kwargs: object) -> ChatCompletionToolStepResult:
        calls.append(dict(kwargs))
        return _provider_step(name="submit_fixture", arguments={"ok": True})

    from sec_agent.canonical_runtime.session import create_agent_session

    session = create_agent_session(
        session_id="SESSION::MULTI-LIVE-SEAM",
        run_id="RUN::MULTI-LIVE-SEAM",
        case_id="case_dell_current",
        case_version="FIN_0_1_3",
        as_of_date="2026-08-06",
        objective_ref="objective://test",
        active_plan_ref="PLAN::TEST",
        created_at="2026-08-23T00:00:00Z",
    )
    events: list[dict] = []
    step, payload, call_id = _call_live_tool(
        events=events,
        session_id=session["session_id"],
        actor_id="AGENT::TEST",
        profile=SimpleNamespace(provider_id="fixture"),
        messages=({"role": "user", "content": "test"},),
        tool={
            "type": "function",
            "function": {
                "name": "submit_fixture",
                "parameters": {"type": "object"},
            },
        },
        expected_name="submit_fixture",
        capture_root=tmp_path,
        run_id=session["run_id"],
        attempt_id="ATTEMPT::MULTI-LIVE-SEAM",
        occurred_at="2026-08-23T00:00:01Z",
        executor=executor,
    )
    assert payload == {"ok": True}
    assert call_id == "call-fixture"
    assert step.model == "fixture-model"
    assert len(calls) == 1 and calls[0]["tool_choice"] is None
    assert [row["event_type"] for row in events] == [
        "provider_attempt_requested",
        "provider_attempt_completed",
    ]
    parsed, _ = _tool_arguments(step, expected_name="submit_fixture")
    assert parsed == {"ok": True}
    assert _provider_attempt_count(events) == 1


def test_submission_successor_predecessor_binding_uses_registered_runtime_event() -> None:
    from sec_agent.canonical_runtime.session import create_agent_session

    session = create_agent_session(
        session_id="SESSION::SUBMISSION-SUCCESSOR-SEAM",
        run_id="RUN::SUBMISSION-SUCCESSOR-SEAM",
        case_id="case_dell_current",
        case_version="FIN_0_1_3",
        as_of_date="2026-08-06",
        objective_ref="objective://test",
        active_plan_ref="PLAN::SUCCESSOR",
        created_at="2026-08-23T00:00:00Z",
    )
    events: list[dict] = []
    from scripts.research.run_s3_current_dynamic_multi_agent import _event

    _event(
        events,
        session_id=session["session_id"],
        event_type="session_created",
        actor_id="S0.CanonicalRuntime",
        occurred_at="2026-08-23T00:00:00Z",
        output_refs=(session["session_id"],),
    )
    _bind_predecessor_session_event(
        events,
        session_id=session["session_id"],
        predecessor_session_id="SESSION::R1-PREDECESSOR",
        role_program_digest="a" * 64,
        round_response_digests=("b" * 64,),
        active_plan_ref=session["active_plan_ref"],
        recorded_at="2026-08-23T00:00:01Z",
    )
    assert [row["event_type"] for row in events] == [
        "session_created",
        "plan_bound",
    ]
    assert events[-1]["input_refs"] == [
        "SESSION::R1-PREDECESSOR",
        "a" * 64,
        "b" * 64,
    ]


def test_live_draft_seam_preserves_invalid_json_for_separate_submission(
    tmp_path: Path,
) -> None:
    def executor(**_: object) -> ChatCompletionToolStepResult:
        step = _provider_step(name="submit_fixture", arguments={"ok": True})
        broken = dict(step.tool_calls[0])
        broken["function"] = {
            "name": "submit_fixture",
            "arguments": '{"useful_judgment":"preserved","broken":"quote " here"}',
        }
        return ChatCompletionToolStepResult(
            status=step.status,
            provider_id=step.provider_id,
            model=step.model,
            content=step.content,
            reasoning_content="private reasoning must not be persisted",
            tool_calls=(broken,),
            finish_reason=step.finish_reason,
            usage=step.usage,
            request_capture_ref=step.request_capture_ref,
            response_capture_ref=step.response_capture_ref,
            request_digest=step.request_digest,
            response_digest=step.response_digest,
            private_reasoning_fields_redacted=(
                step.private_reasoning_fields_redacted
            ),
        )

    events: list[dict] = []
    step, draft, call_id = _call_live_tool_draft(
        events=events,
        session_id="SESSION::MULTI-LIVE-DRAFT-SEAM",
        actor_id="AGENT::TEST",
        profile=SimpleNamespace(provider_id="fixture"),
        messages=({"role": "user", "content": "test"},),
        tool={
            "type": "function",
            "function": {
                "name": "submit_fixture",
                "parameters": {"type": "object"},
            },
        },
        expected_name="submit_fixture",
        capture_root=tmp_path,
        run_id="RUN::MULTI-LIVE-DRAFT-SEAM",
        attempt_id="ATTEMPT::MULTI-LIVE-DRAFT-SEAM",
        occurred_at="2026-08-23T00:00:01Z",
        executor=executor,
    )
    assert "useful_judgment" in draft
    assert call_id == "call-fixture"
    with pytest.raises(json.JSONDecodeError):
        json.loads(draft)
    assert _tool_draft(step, expected_name="submit_fixture")[0] == draft
    assert [row["event_type"] for row in events] == [
        "provider_attempt_requested",
        "provider_attempt_completed",
    ]


def test_live_provider_seam_counts_failed_attempt_from_requested_event(
    tmp_path: Path,
) -> None:
    def executor(**_: object) -> ChatCompletionToolStepResult:
        raise ModelGatewayError(
            "fixture_transport_failed",
            capture_ref=str(tmp_path / "failed-response.json"),
        )

    events: list[dict] = []
    with pytest.raises(ModelGatewayError, match="fixture_transport_failed"):
        _call_live_tool(
            events=events,
            session_id="SESSION::MULTI-LIVE-FAILURE-SEAM",
            actor_id="AGENT::TEST",
            profile=SimpleNamespace(provider_id="fixture"),
            messages=({"role": "user", "content": "test"},),
            tool={
                "type": "function",
                "function": {
                    "name": "submit_fixture",
                    "parameters": {"type": "object"},
                },
            },
            expected_name="submit_fixture",
            capture_root=tmp_path,
            run_id="RUN::MULTI-LIVE-FAILURE-SEAM",
            attempt_id="ATTEMPT::MULTI-LIVE-FAILURE-SEAM",
            occurred_at="2026-08-23T00:00:02Z",
            executor=executor,
        )
    assert [row["event_type"] for row in events] == [
        "provider_attempt_requested",
        "provider_attempt_failed",
    ]
    assert _provider_attempt_count(events) == 1
