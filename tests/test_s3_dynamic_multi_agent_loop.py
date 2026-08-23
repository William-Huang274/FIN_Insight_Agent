from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.research.run_s3_current_dynamic_multi_agent as multi_agent_runner

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
from sec_agent.research.multi_agent_content_repair import (
    MultiAgentContentRepairError,
    compile_independent_content_challenges,
    rebind_workpaper_context_semantic_rules,
    semantic_relation_rules,
)
from sec_agent.runtime_resource_registry import read_registered_runtime_json
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from scripts.research.run_s3_current_dynamic_multi_agent import (
    CONTENT_REPAIR_AUTHORITY_SCHEMA,
    CONTENT_REPAIR_AUTHORITY_STATUS,
    CONTENT_REPAIR_SUBMISSION_RESUME_AUTHORITY_SCHEMA,
    CONTENT_REPAIR_SUBMISSION_RESUME_AUTHORITY_STATUS,
    LIVE_AUTHORITY_SCHEMA,
    LIVE_AUTHORITY_STATUS,
    SPECIALIST_WORKPAPER_SUBMISSION_TOOL_NAME,
    _bind_predecessor_session_event,
    _call_live_tool,
    _call_live_tool_draft,
    _provider_attempt_count,
    _provider_attempt_count_for_prefix,
    _resume_capture_for_attempt,
    _tool_draft,
    _tool_arguments,
    expected_content_repair_budget,
    expected_content_repair_submission_resume_budget,
    expected_live_execution_budget,
    expected_submission_repair_resume_budget,
    expected_submission_resume_budget,
    expected_submission_successor_budget,
    validate_content_repair_authority,
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


def test_role_programs_include_provider_neutral_semantic_relation_rules() -> None:
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
    by_agent = {row["agent_id"]: row for row in result["role_programs"]}
    for agent_id, program in by_agent.items():
        assert set(semantic_relation_rules(agent_id)).issubset(
            set(program["loop_policy"]["role_contract"]["workpaper_rules"])
        )


def test_independent_assessment_compiles_seven_findings_into_five_role_challenges() -> None:
    assessment = _load(
        "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R5_content_assessment_v1_0.json"
    )
    source = _load(
        "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_live_result_v1_4.json"
    )
    workpapers = [row["workpaper"] for row in source["role_summaries"]]
    challenges = compile_independent_content_challenges(
        assessment=assessment,
        workpapers=workpapers,
    )
    assert len(challenges) == 7
    assert len({row["challenge_id"] for row in challenges}) == 7
    assert {row["target_agent_id"] for row in challenges} == {
        "AGENT::DEMAND_QUALITY",
        "AGENT::OPERATING_PERFORMANCE",
        "AGENT::VALUE_CAPTURE",
        "AGENT::CASH_CONVERSION",
        "AGENT::COUNTEREVIDENCE",
    }
    assert all(
        row["source_agent_id"] == "S3.INDEPENDENT_CONTENT_VERIFIER"
        for row in challenges
    )


def test_independent_assessment_rejects_unknown_target() -> None:
    assessment = _load(
        "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_R5_content_assessment_v1_0.json"
    )
    source = _load(
        "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_live_result_v1_4.json"
    )
    mutated = deepcopy(assessment)
    mutated["material_findings"][0]["target_agent_id"] = "AGENT::UNKNOWN"
    with pytest.raises(
        MultiAgentContentRepairError,
        match="multi_agent_content_repair_target_invalid",
    ):
        compile_independent_content_challenges(
            assessment=mutated,
            workpapers=[row["workpaper"] for row in source["role_summaries"]],
        )


def test_semantic_rule_rebind_changes_only_rules_and_digest() -> None:
    body = {
        "schema_version": "fin_ia_dynamic_single_unit_workpaper_context_v1_0",
        "agent": {"agent_id": "AGENT::CASH_CONVERSION"},
        "rules": ["preserve company scope"],
        "cell_analysis_view": {"cell": {"cell_id": "CELL::cash_conversion"}},
        "case_identity": {"case_key": "DELL"},
        "graph_context_packs": [],
        "reflection_history": [],
        "task_scenarios": [],
    }
    context = {**body, "context_digest": canonical_digest(body)}
    rebound, receipt = rebind_workpaper_context_semantic_rules(
        context,
        expected_agent_id="AGENT::CASH_CONVERSION",
    )
    assert rebound["context_digest"] != context["context_digest"]
    assert receipt[
        "evidence_numeric_relation_gap_graph_and_case_authority_changed"
    ] is False
    assert any("资产负债表营运资金代理" in row for row in rebound["rules"])
    for field in (
        "cell_analysis_view",
        "case_identity",
        "graph_context_packs",
        "reflection_history",
        "task_scenarios",
    ):
        assert rebound[field] == context[field]


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


def test_content_repair_budget_counts_exactly_five_repairs_and_one_lead() -> None:
    budget = expected_content_repair_budget()
    assert budget["maximum_new_model_calls"] == 12
    assert sum(
        budget[key]
        for key in (
            "role_repair_drafts",
            "role_repair_submissions",
            "lead_coordination_drafts",
            "lead_coordination_submissions",
        )
    ) == budget["maximum_new_model_calls"]
    assert budget["maximum_role_repairs"] == 5
    assert budget["maximum_lead_rounds"] == 1
    assert budget["maximum_new_s1_s2_requests"] == 0
    assert budget["maximum_external_source_network_calls"] == 0
    assert budget["retries"] == 0


def test_content_repair_submission_resume_budget_counts_only_unfinished_nodes() -> None:
    budget = expected_content_repair_submission_resume_budget()
    assert budget["maximum_new_model_calls"] == 7
    assert sum(
        budget[key]
        for key in (
            "demand_repair_submissions",
            "remaining_role_repair_drafts",
            "remaining_role_repair_submissions",
            "lead_coordination_drafts",
            "lead_coordination_submissions",
        )
    ) == budget["maximum_new_model_calls"]
    assert budget["maximum_new_role_repairs"] == 3
    assert budget["maximum_new_s1_s2_requests"] == 0
    assert budget["maximum_external_source_network_calls"] == 0
    assert budget["retries"] == 0


def test_optional_resume_manifest_allows_fresh_provider_frontier() -> None:
    assert (
        _resume_capture_for_attempt(
            (), attempt_fragment="demand-quality-repair-r1-draft"
        )
        is None
    )


def test_content_repair_submission_resume_fake_runs_all_seven_fresh_nodes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the exact R8 resume topology without network or model calls."""

    scope_ref = (
        "configs/research/evals/"
        "fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_"
        "content_repair_submission_resume_scope_decision_v1_0.json"
    )
    scope = _load(scope_ref)
    authority_path = tmp_path / "authority.json"
    capture_root = tmp_path / "captures"
    private_root = tmp_path / "private"
    public_path = tmp_path / "public.json"
    attempt_prefix = "ATTEMPT::R8-FAKE"
    authority = {
        "schema_version": CONTENT_REPAIR_SUBMISSION_RESUME_AUTHORITY_SCHEMA,
        "status": CONTENT_REPAIR_SUBMISSION_RESUME_AUTHORITY_STATUS,
        "signed_at": "2026-08-24T00:00:00Z",
        "implementation_commit": "0" * 40,
        "case_key": "DELL",
        "execution_budget": expected_content_repair_submission_resume_budget(),
        "token_budget_basis": {},
        "bound_inputs": {
            "predecessor_public_ref": scope["predecessor_public_result_ref"],
            "predecessor_private_ref": scope["predecessor_private_result_ref"],
            "assessment_ref": scope["assessment_ref"],
            "failed_authority_ref": scope["failed_R7_authority_ref"],
            "failed_public_ref": scope["failed_R7_public_ref"],
            "failed_private_ref": scope["failed_R7_private_ref"],
        },
        "output_contract": {
            "capture_root_ref": "__pytest_r8__/captures",
            "private_output_root_ref": "__pytest_r8__/private",
            "public_result_ref": "__pytest_r8__/public.json",
            "run_id": "RUN::R8-FAKE",
            "attempt_prefix": attempt_prefix,
            "product_publication": "forbidden",
        },
        "known_boundary": (
            "This fixture exercises only the exact seven-node local execution seam. "
            "It performs no network, Provider, retrieval, publication or product "
            "acceptance action and does not assess financial content quality."
        ),
    }
    authority_path.write_text(
        json.dumps(authority, ensure_ascii=False), encoding="utf-8"
    )
    paths = {
        "predecessor_public_ref": ROOT / scope["predecessor_public_result_ref"],
        "predecessor_private_ref": ROOT / scope["predecessor_private_result_ref"],
        "assessment_ref": ROOT / scope["assessment_ref"],
        "failed_private_ref": ROOT / scope["failed_R7_private_ref"],
        "provider_profile_ref": ROOT / scope["provider_profile_ref"],
        "submission_profile_ref": ROOT / scope["submission_profile_ref"],
    }
    monkeypatch.setattr(
        multi_agent_runner,
        "validate_content_repair_authority",
        lambda *_args, **_kwargs: paths,
    )
    original_resolve = multi_agent_runner._resolve_repo_ref
    test_output_refs = {
        "__pytest_r8__/captures": capture_root,
        "__pytest_r8__/private": private_root,
        "__pytest_r8__/public.json": public_path,
    }

    def resolve_test_ref(ref: str | Path) -> Path:
        raw = str(ref)
        if raw in test_output_refs:
            return test_output_refs[raw]
        return original_resolve(ref)

    monkeypatch.setattr(multi_agent_runner, "_resolve_repo_ref", resolve_test_ref)
    monkeypatch.setattr(
        multi_agent_runner,
        "_relative",
        lambda path: Path(path).resolve().as_posix(),
    )

    attempts: list[str] = []
    demand_feedback_seen = False

    def research_executor(**kwargs: object) -> ChatCompletionToolStepResult:
        attempt_id = str(kwargs["attempt_id"])
        attempts.append(attempt_id)
        tool = dict(list(kwargs["tools"])[0])
        name = str(dict(tool["function"])["name"])
        return _provider_step(
            name=name,
            arguments={"fixture_draft": f"local draft for {attempt_id}"},
        )

    def submission_executor(**kwargs: object) -> ChatCompletionToolStepResult:
        nonlocal demand_feedback_seen
        attempt_id = str(kwargs["attempt_id"])
        attempts.append(attempt_id)
        tool = dict(list(kwargs["tools"])[0])
        function = dict(tool["function"])
        name = str(function["name"])
        messages = list(kwargs["messages"])
        visible = json.loads(str(dict(messages[-1])["content"]))
        if name == SPECIALIST_WORKPAPER_SUBMISSION_TOOL_NAME:
            if attempt_id.endswith("demand-quality-repair-r3-submit"):
                feedback = visible.get("prior_submission_feedback") or []
                demand_feedback_seen = (
                    len(feedback) == 1
                    and feedback[0]["error_code"]
                    == "multi_agent_workpaper_claim_unbound"
                    and feedback[0]["authority_expansion_allowed"] is False
                )
            prior = deepcopy(
                visible["validated_context"]["repair_state"]["prior_workpaper"]
            )
            for field in (
                "schema_version",
                "agent_id",
                "context_digest",
                "workpaper_digest",
            ):
                prior.pop(field, None)
            prior["confidence"] = (
                "low" if prior["confidence"] != "low" else "medium"
            )
            payload = prior
        else:
            assert name == "submit_lead_coordination_judgment"
            properties = dict(function["parameters"])["properties"]
            deferred_schema = dict(properties["deferred_challenge_ids"])
            selectable = list(dict(deferred_schema["items"]).get("enum") or ())
            payload = {
                "accepted_challenge_ids": [],
                "deferred_challenge_ids": [
                    value
                    for value in selectable
                    if str(value).startswith("CHALLENGE::")
                ],
                "coordination_rationale": (
                    "The fixture defers the catalog to independent reassessment "
                    "without adding facts or changing research authority."
                ),
                "next_state": "proceed_to_evaluation",
            }
        return _provider_step(name=name, arguments=payload)

    result = multi_agent_runner.run_content_repair_live(
        authority_path=authority_path,
        research_executor=research_executor,
        submission_executor=submission_executor,
    )

    assert attempts == [
        f"{attempt_prefix}-demand-quality-repair-r3-submit",
        f"{attempt_prefix}-operating-performance-repair-r4-draft",
        f"{attempt_prefix}-operating-performance-repair-r4-submit",
        f"{attempt_prefix}-value-capture-repair-r5-draft",
        f"{attempt_prefix}-value-capture-repair-r5-submit",
        f"{attempt_prefix}-lead-r1-draft",
        f"{attempt_prefix}-lead-r1-submit",
    ]
    assert demand_feedback_seen is True
    assert result["status"] == "completed_contract_valid_reassessment_pending"
    assert result["execution"]["new_provider_calls_attempted"] == 7
    assert result["execution"]["role_repairs_executed"] == 3
    assert result["execution"]["role_repairs_reused"] == 2
    assert public_path.is_file()
    assert (private_root / "full_result.json").is_file()


def test_content_repair_authority_rejects_budget_drift_before_execution(
    tmp_path: Path,
) -> None:
    authority = {
        "schema_version": CONTENT_REPAIR_AUTHORITY_SCHEMA,
        "status": CONTENT_REPAIR_AUTHORITY_STATUS,
        "signed_at": "2026-08-23T00:00:00Z",
        "implementation_commit": "0" * 40,
        "case_key": "DELL",
        "execution_budget": {"maximum_new_model_calls": 13},
        "token_budget_basis": {},
        "bound_inputs": {},
        "output_contract": {},
        "known_boundary": "x" * 160,
    }
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    with pytest.raises(
        DynamicMultiAgentLoopError,
        match="dynamic_multi_agent_content_repair_authority_invalid",
    ):
        validate_content_repair_authority(authority, authority_path=path.resolve())


def test_content_repair_submission_resume_authority_rejects_old_budget(
    tmp_path: Path,
) -> None:
    authority = {
        "schema_version": CONTENT_REPAIR_SUBMISSION_RESUME_AUTHORITY_SCHEMA,
        "status": CONTENT_REPAIR_SUBMISSION_RESUME_AUTHORITY_STATUS,
        "signed_at": "2026-08-24T00:00:00Z",
        "implementation_commit": "0" * 40,
        "case_key": "DELL",
        "execution_budget": expected_content_repair_budget(),
        "token_budget_basis": {},
        "bound_inputs": {},
        "output_contract": {},
        "known_boundary": "x" * 160,
    }
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    with pytest.raises(
        DynamicMultiAgentLoopError,
        match="dynamic_multi_agent_content_repair_authority_invalid",
    ):
        validate_content_repair_authority(authority, authority_path=path.resolve())


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


def test_provider_attempt_count_for_prefix_excludes_predecessor_events() -> None:
    events = [
        {
            "event_type": "provider_attempt_requested",
            "attempt_id": "R5-demand-workpaper",
        },
        {
            "event_type": "provider_attempt_requested",
            "attempt_id": "R7-demand-repair-draft",
        },
        {
            "event_type": "provider_attempt_failed",
            "attempt_id": "R7-demand-repair-draft",
        },
    ]

    assert _provider_attempt_count_for_prefix(events, attempt_prefix="R7-") == 1
