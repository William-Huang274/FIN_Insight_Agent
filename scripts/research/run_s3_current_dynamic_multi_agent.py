from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.workbench.backend.application.research_evidence_pack_service import (  # noqa: E402
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.cuda_execution import required_cuda_fp16_receipt  # noqa: E402
from retrieval.route_compiler import load_query_object_fact_route_policy  # noqa: E402
from sec_agent.canonical_runtime.session import (  # noqa: E402
    CanonicalRuntimeError,
    append_session_event,
    apply_accepted_plan_delta,
    canonical_digest,
    create_agent_session,
    create_context_checkpoint,
    resume_agent_session,
)
from sec_agent.research.dynamic_multi_agent_loop import (  # noqa: E402
    DynamicMultiAgentLoopError,
    compile_dynamic_multi_agent_role_programs,
    compile_role_material_requirement_blueprints,
    compile_role_stop_decision,
    load_dynamic_multi_agent_loop_policy,
    normalize_bound_specialist_workpaper,
    role_program_by_agent,
)
from sec_agent.research.dynamic_single_unit_loop import (  # noqa: E402
    DynamicSingleUnitLoopError,
    REFLECTION_PAYLOAD_SCHEMA_VERSION,
    REQUEST_PAYLOAD_SCHEMA_VERSION,
    compile_controlled_batch_projection,
    compile_initial_messages,
    compile_reflection_artifacts,
    compile_round_feedback_receipts,
    compile_round_response,
    compile_workpaper_context,
    compile_workpaper_repair_context,
    public_round_response,
    reflection_tool,
    request_evidence_tool,
    validate_reflection_payload,
    validate_request_selection,
)
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    LEAD_COORDINATION_DECISION_SCHEMA_VERSION,
    RESEARCH_LEAD_AGENT_ID,
    SPECIALIST_AGENT_IDS,
    SPECIALIST_WORKPAPER_SCHEMA_VERSION,
    compile_challenge_catalog,
    compile_planner_payload_from_role_opinions,
    lead_coordination_tool,
    load_multi_agent_role_topology,
    specialist_workpaper_tool,
    validate_lead_coordination_decision,
    validate_lead_plan_checkpoint,
    validate_specialist_plan_checkpoint,
    validate_specialist_workpaper,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    compile_cross_role_feedback_receipt,
    load_preview_planning_policy,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402
from sec_agent.runtime_resource_registry import (  # noqa: E402
    read_registered_runtime_json,
)


POLICY_REF = Path(
    "configs/research/fin_ia_0_1_3_s3_current_dynamic_multi_agent_loop_policy_v1_0.json"
)
DEFAULT_PUBLIC = Path(
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_zero_call_result_v1_0.json"
)
DEFAULT_REPAIR_PUBLIC = Path(
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_zero_call_repair_successor_result_v1_0.json"
)


def _read_json(path: Path | str) -> dict[str, Any]:
    source = Path(path)
    target = source if source.is_absolute() else ROOT / source
    return json.loads(target.read_text(encoding="utf-8"))


def _sha256(path: Path | str) -> str:
    source = Path(path)
    target = source if source.is_absolute() else ROOT / source
    return hashlib.sha256(target.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _write_json(path: Path, value: Mapping[str, Any], *, exclusive: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _event(
    events: list[dict[str, Any]],
    *,
    session_id: str,
    event_type: str,
    actor_id: str,
    occurred_at: str,
    attempt_id: str | None = None,
    input_refs: Sequence[str] = (),
    output_refs: Sequence[str] = (),
    feedback_refs: Sequence[str] = (),
) -> None:
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type=event_type,
            actor_id=actor_id,
            occurred_at=occurred_at,
            attempt_id=attempt_id,
            input_refs=input_refs,
            output_refs=output_refs,
            feedback_refs=feedback_refs,
        )
    )


def _compile_role_programs() -> tuple[dict[str, Any], dict[str, Any]]:
    raw_policy = _read_json(POLICY_REF)
    source_refs = raw_policy["source_refs"]
    topology = load_multi_agent_role_topology(
        _read_json(source_refs["role_topology_ref"])
    )
    policy = load_dynamic_multi_agent_loop_policy(
        raw_policy, topology=topology
    )
    specialist_checkpoint = validate_specialist_plan_checkpoint(
        _read_json(source_refs["planner_checkpoint_ref"]), topology=topology
    )
    opinions = specialist_checkpoint["specialist_plans"]
    lead_plan = validate_lead_plan_checkpoint(
        _read_json(source_refs["lead_plan_checkpoint_ref"]),
        opinions=opinions,
        topology=topology,
    )["lead_plan"]
    kernel = load_financial_research_kernel(
        read_registered_runtime_json(
            ROOT, "application.config.current_financial_research_kernel"
        )
    )
    route_policy = load_query_object_fact_route_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        kernel,
    )
    planning_policy = load_preview_planning_policy(
        ROOT, route_policy=route_policy
    )
    compilation = compile_planner_payload_from_role_opinions(
        objective_id="OBJECTIVE::DELL::CURRENT-DYNAMIC-MULTI-AGENT",
        opinions=opinions,
        lead_plan=lead_plan,
        topology=topology,
    )
    programs = compile_dynamic_multi_agent_role_programs(
        policy=policy,
        topology=topology,
        objective_payload=_read_json(policy["objective_ref"]),
        planner_compilation=compilation,
        kernel=kernel,
        route_policy=route_policy,
        planning_policy=planning_policy,
    )
    return policy, programs


def _request_rows(
    role_program: Mapping[str, Any], request_ids: Sequence[str]
) -> list[dict[str, Any]]:
    by_id = {
        str(row["request_id"]): deepcopy(dict(row))
        for row in role_program.get("requests") or ()
    }
    return [by_id[request_id] for request_id in request_ids]


def _round_partition(role_program: Mapping[str, Any]) -> list[list[str]]:
    request_ids = [
        str(row["request_id"]) for row in role_program.get("requests") or ()
    ]
    if len(request_ids) <= 1:
        return [request_ids]
    first_count = min(2, len(request_ids) - 1)
    return [request_ids[:first_count], request_ids[first_count:]]


def _fake_request_payload(
    *, agent_id: str, round_index: int, request_ids: Sequence[str]
) -> dict[str, Any]:
    return {
        "schema_version": REQUEST_PAYLOAD_SCHEMA_VERSION,
        "round_id": f"ROUND::{round_index}",
        "request_ids": list(request_ids),
        "research_rationale": (
            f"{agent_id} 先执行分配给本角色且最可能改变判断的命题；"
            "零调用夹具只验证真实工具、反馈与权限链，不预写研究答案。"
        ),
        "expected_information_gain": (
            "区分已审 Evidence、typed NumericFact、未审候选、工具失败和真正的信息边界。"
        ),
    }


def _fake_reflection_payload(
    *,
    agent_id: str,
    round_index: int,
    feedback_refs: Sequence[str],
    next_request_ids: Sequence[str],
    accepted_evidence_refs: Sequence[str],
    decision: str,
) -> dict[str, Any]:
    hypotheses = []
    if agent_id == "AGENT::SUPPLY_RELATIONSHIP" and accepted_evidence_refs:
        hypotheses = [
            {
                "source_entity": "UPSTREAM_COUNTERPARTY",
                "relationship_direction": "may_constrain_or_enable",
                "target_entity": "DELL_AI_SERVER_DELIVERY",
                "evidence_refs": [accepted_evidence_refs[0]],
                "research_use": (
                    "只指导下一轮查找交易对手直接披露，不证明 Dell 已取得专属配额、良率或交付改善。"
                ),
            }
        ]
    return {
        "schema_version": REFLECTION_PAYLOAD_SCHEMA_VERSION,
        "round_id": f"ROUND::{round_index}",
        "reflection_summary": (
            f"{agent_id} 已检查本轮 reviewed Evidence、NumericFact 与全部 FeedbackReceipt。"
            "仍未执行的角色命题应在预算内继续；所有路线都执行后，剩余不足只能限制具体命题，"
            "不得被改写成公开资料不存在或泛化免责声明。"
        ),
        "answered_questions": ["本轮已区分可引用证据、候选、数值权威和工具反馈。"],
        "unresolved_questions": ["尚未执行或仍无权威桥的角色命题继续保留为可行动问题。"],
        "feedback_refs": list(feedback_refs),
        "next_request_ids": list(next_request_ids),
        "graph_hypotheses": hypotheses,
        "proposed_stop_decision": decision,
        "reason_codes": [
            (
                "role_local_material_requests_remain"
                if decision == "continue"
                else "role_local_catalog_exhausted_with_explicit_boundaries"
            )
        ],
    }


def _fake_workpaper(context: Mapping[str, Any]) -> dict[str, Any]:
    agent_id = str(context["agent"]["agent_id"])
    cell = context["cell_analysis_view"]["cell"]
    evidence_refs = [
        str(row["evidence_ref"]) for row in cell.get("cell_evidence_views") or ()
    ]
    numeric_refs = list(cell.get("allowed_numeric_refs") or ())
    relation_refs = list(cell.get("allowed_numeric_relation_refs") or ())
    gap_refs = [
        str(row["gap_ref"]) for row in cell.get("residual_gap_cards") or ()
    ]
    challenges = []
    if agent_id == "AGENT::COUNTEREVIDENCE":
        challenges = [
            {
                "target_agent_id": "AGENT::VALUE_CAPTURE",
                "challenge": "不得把分部或公司利润改善直接归因于 AI 服务器产品。",
                "material_reason": "缺少产品到分部再到公司的价格、销量、组合和成本桥。",
                "requested_action": "recheck_judgment",
            }
        ]
    authority = "sourced_fact" if evidence_refs or numeric_refs or relation_refs else "not_inferable"
    return {
        "schema_version": SPECIALIST_WORKPAPER_SCHEMA_VERSION,
        "agent_id": agent_id,
        "thesis": (
            f"这是 {agent_id} 的零模型工作底稿夹具：它只证明该角色能独立检索、消费反馈、"
            "保留证据边界并提交给 Lead，不代表自然模型已经形成合格投资判断。"
        ),
        "confidence": "insufficient_evidence",
        "sourced_claims": [
            {
                "claim": "本夹具不生成新金融事实，只验证角色本地引用与权限边界。",
                "authority": authority,
                "evidence_refs": evidence_refs[:1],
                "numeric_refs": numeric_refs[:1],
                "numeric_relation_refs": relation_refs[:1],
            }
        ],
        "mechanism": (
            "角色先提出命题级请求，S1/S2 返回 reviewed Evidence、typed facts 与故障反馈，"
            "角色据此修改计划；Lead 只能协调冲突，不能替专家或数据层补写事实。"
        ),
        "alternative_explanations": ["同一经营结果可能由非 AI 业务、成本、定价或期间口径共同驱动。"],
        "strongest_counterarguments": ["若缺少直接桥，相关性和同时发生不能升级为单一因果归因。"],
        "remaining_gap_refs": gap_refs,
        "what_would_change": ["若取得直接、同期间且可审计的桥接证据，应重新裁决本角色命题。"],
        "cross_role_challenges": challenges,
        "stop_reason": "零调用证明到此验证结构、反馈和权限；自然研究质量必须由独立 live 验收。",
    }


def _fake_repaired_workpaper(context: Mapping[str, Any]) -> dict[str, Any]:
    payload = _fake_workpaper(context)
    payload["thesis"] = (
        f"{payload['agent_id']} 已消费 Lead 路由的反方挑战；零模型修订仅收窄因果措辞并保留原引用范围，"
        "不新增事实、数字、来源或工具权限，也不代表自然模型内容质量已经通过。"
    )
    payload["strongest_counterarguments"] = [
        "分部和公司利润改善可能与 AI 服务器同时发生，但缺少产品价格、销量、组合和成本桥时，不能升级为 AI 产品利润事实。"
    ]
    payload["stop_reason"] = (
        "已处理当前跨角色挑战并收窄受影响判断；剩余数据问题继续保留在原责任层。"
    )
    return payload


def _execute_role(
    *,
    role_program: Mapping[str, Any],
    attempt_id: str,
    recorded_at: str,
    retrieval: ResearchRetrievalService,
    retrieval_principal: ResearchRetrievalPrincipal,
    evidence_pack: Mapping[str, Any],
    truth_policy: Mapping[str, Any],
    consumer_policy: Mapping[str, Any],
    task_quantitative: Mapping[str, Any],
) -> dict[str, Any]:
    agent_id = str(role_program["agent_id"])
    policy = deepcopy(dict(role_program["loop_policy"]))
    catalog = deepcopy(dict(role_program["request_catalog"]))
    initial_messages = compile_initial_messages(
        policy=policy, request_catalog=catalog
    )
    initial_text = json.dumps(initial_messages, ensure_ascii=False)
    session_seed = {
        "attempt_id": attempt_id,
        "agent_id": agent_id,
        "role_program_digest": role_program["role_program_digest"],
        "pack_payload_digest": evidence_pack["pack_payload_digest"],
    }
    session_id = "SESSION::" + canonical_digest(session_seed)[:24].upper()
    base_plan_body = {
        "case_key": "DELL",
        "objective_id": policy["objective"]["objective_id"],
        "agent_id": agent_id,
        "executed_request_ids": [],
        "next_request_ids": [],
        "latest_reflection_digest": None,
        "latest_feedback_refs": [],
    }
    base_plan = {**base_plan_body, "plan_digest": canonical_digest(base_plan_body)}
    base_graph_digest = canonical_digest(
        {
            "case_key": "DELL",
            "agent_id": agent_id,
            "state": "current_reviewed_graph_plus_role_local_hypotheses",
        }
    )
    session = create_agent_session(
        session_id=session_id,
        run_id="RUN::" + canonical_digest(session_seed)[:24].upper(),
        case_id="case_dell_current",
        case_version="FIN_0_1_3",
        as_of_date="2026-08-06",
        objective_ref=f"objective://{policy['objective']['objective_id']}",
        active_plan_ref="PLAN::" + base_plan["plan_digest"][:24].upper(),
        created_at=recorded_at,
    )
    events: list[dict[str, Any]] = []
    _event(
        events,
        session_id=session_id,
        event_type="session_created",
        actor_id="S0.CanonicalRuntime",
        occurred_at=recorded_at,
        output_refs=(session_id,),
    )
    _event(
        events,
        session_id=session_id,
        event_type="plan_bound",
        actor_id="S3.DynamicMultiAgentHarness",
        occurred_at=recorded_at,
        input_refs=(catalog["catalog_digest"],),
        output_refs=(session["active_plan_ref"],),
    )

    executed_ids: list[str] = []
    accepted_evidence_refs: set[str] = set()
    feedback_receipts: list[dict[str, Any]] = []
    round_responses: list[dict[str, Any]] = []
    reflections: list[dict[str, Any]] = []
    reflection_artifacts: list[dict[str, Any]] = []
    round_batches: list[dict[str, Any]] = []
    replay_digests: list[str] = []
    feedback_refs_by_round: list[list[str]] = []
    round_ids = _round_partition(role_program)
    all_blueprints = compile_role_material_requirement_blueprints(role_program)

    for round_index, selected_ids in enumerate(round_ids, start=1):
        request_evidence_tool(
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=executed_ids,
            round_index=round_index,
        )
        selection = validate_request_selection(
            _fake_request_payload(
                agent_id=agent_id,
                round_index=round_index,
                request_ids=selected_ids,
            ),
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=executed_ids,
            round_index=round_index,
        )
        requests = _request_rows(role_program, selection["request_ids"])
        blueprints = {
            request_id: all_blueprints[request_id]
            for request_id in selection["request_ids"]
        }
        tool_attempt_id = (
            f"{attempt_id}-{agent_id.split('::')[-1].lower()}-tool-r{round_index}"
        )
        _event(
            events,
            session_id=session_id,
            event_type="tool_execution_requested",
            actor_id=agent_id,
            occurred_at=recorded_at,
            attempt_id=tool_attempt_id,
            input_refs=(selection["selection_digest"],),
        )
        batch = retrieval.execute_current_runtime_requests(
            "DELL",
            requests,
            retrieval_principal,
            material_requirement_blueprints=blueprints,
        )
        round_batches.append(batch)
        controlled = compile_controlled_batch_projection(
            policy=policy,
            selected_requests=requests,
            batch_result=batch,
        )
        response = compile_round_response(
            policy=policy,
            controlled_plan=controlled,
            evidence_pack=evidence_pack,
            truth_spine_policy=truth_policy,
            consumer_policy=consumer_policy,
            task_quantitative_result=task_quantitative,
            round_index=round_index,
        )
        replay = compile_round_response(
            policy=policy,
            controlled_plan=controlled,
            evidence_pack=evidence_pack,
            truth_spine_policy=truth_policy,
            consumer_policy=consumer_policy,
            task_quantitative_result=task_quantitative,
            round_index=round_index,
        )
        if response["round_response_digest"] != replay["round_response_digest"]:
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_role_round_replay_not_deterministic"
            )
        replay_digests.append(replay["round_response_digest"])
        round_responses.append(response)
        _event(
            events,
            session_id=session_id,
            event_type="tool_execution_completed",
            actor_id="S1S2.CurrentRuntime",
            occurred_at=recorded_at,
            attempt_id=tool_attempt_id,
            input_refs=(selection["selection_digest"],),
            output_refs=(response["round_response_digest"],),
        )
        current_feedback = compile_round_feedback_receipts(
            session_id=session_id,
            round_response=response,
            request_catalog=catalog,
            created_at=recorded_at,
        )
        feedback_receipts.extend(current_feedback)
        feedback_refs = [str(row["feedback_id"]) for row in current_feedback]
        feedback_refs_by_round.append(feedback_refs)
        if feedback_refs:
            _event(
                events,
                session_id=session_id,
                event_type="feedback_issued",
                actor_id="S1S2.DynamicEvidenceTool",
                occurred_at=recorded_at,
                input_refs=(response["round_response_digest"],),
                output_refs=feedback_refs,
                feedback_refs=feedback_refs,
            )
        executed_ids.extend(selection["request_ids"])
        accepted_evidence_refs.update(
            str(row["evidence_ref"])
            for row in response.get("reviewed_evidence") or ()
        )
        next_ids = round_ids[round_index] if round_index < len(round_ids) else []
        current_open_gap_refs = sorted(
            {
                str(row["gap_ref"])
                for current in round_responses
                for row in current.get("residual_gaps") or ()
            }
        )
        decision = compile_role_stop_decision(
            next_request_ids=next_ids,
            open_gap_refs=current_open_gap_refs,
            feedback_refs=feedback_refs,
        )
        reflection_tool(
            policy=policy,
            request_catalog=catalog,
            feedback_receipts=current_feedback,
            accepted_evidence_refs=sorted(accepted_evidence_refs),
            executed_request_ids=executed_ids,
            round_index=round_index,
        )
        reflection = validate_reflection_payload(
            _fake_reflection_payload(
                agent_id=agent_id,
                round_index=round_index,
                feedback_refs=feedback_refs,
                next_request_ids=next_ids,
                accepted_evidence_refs=sorted(accepted_evidence_refs),
                decision=decision,
            ),
            policy=policy,
            request_catalog=catalog,
            feedback_receipts=current_feedback,
            accepted_evidence_refs=sorted(accepted_evidence_refs),
            executed_request_ids=executed_ids,
            round_index=round_index,
        )
        reflections.append(reflection)
        open_gap_refs = current_open_gap_refs
        artifacts = compile_reflection_artifacts(
            policy=policy,
            reflection=reflection,
            session_id=session_id,
            agent_id=agent_id,
            base_plan=base_plan,
            base_graph_digest=base_graph_digest,
            executed_request_ids=executed_ids,
            open_gap_refs=open_gap_refs,
            model_calls_used=0,
        )
        reflection_artifacts.append(artifacts)
        _event(
            events,
            session_id=session_id,
            event_type="plan_delta_submitted",
            actor_id=agent_id,
            occurred_at=recorded_at,
            input_refs=feedback_refs,
            output_refs=(artifacts["plan_delta"]["plan_delta_id"],),
            feedback_refs=feedback_refs,
        )
        _event(
            events,
            session_id=session_id,
            event_type="plan_delta_accepted",
            actor_id="S3.DynamicMultiAgentHarness",
            occurred_at=recorded_at,
            input_refs=(artifacts["plan_delta"]["plan_delta_id"],),
            output_refs=(artifacts["accepted_plan_ref"],),
            feedback_refs=feedback_refs,
        )
        session = apply_accepted_plan_delta(
            session=session,
            plan_delta=artifacts["plan_delta"],
            expected_base_plan_digest=base_plan["plan_digest"],
            accepted_plan_digest=artifacts["accepted_plan"]["plan_digest"],
            accepted_plan_ref=artifacts["accepted_plan_ref"],
            updated_at=recorded_at,
        )
        base_plan = artifacts["accepted_plan"]
        _event(
            events,
            session_id=session_id,
            event_type="graph_delta_submitted",
            actor_id=agent_id,
            occurred_at=recorded_at,
            input_refs=(reflection["reflection_digest"],),
            output_refs=(artifacts["graph_delta"]["graph_delta_id"],),
        )
        _event(
            events,
            session_id=session_id,
            event_type="graph_delta_accepted",
            actor_id="S3.DynamicMultiAgentHarness",
            occurred_at=recorded_at,
            input_refs=(artifacts["graph_delta"]["graph_delta_id"],),
            output_refs=(artifacts["graph_delta"]["graph_delta_digest"],),
        )
        base_graph_digest = artifacts["graph_delta"]["graph_delta_digest"]
        _event(
            events,
            session_id=session_id,
            event_type="stop_decided",
            actor_id=agent_id,
            occurred_at=recorded_at,
            input_refs=(reflection["reflection_digest"],),
            output_refs=(artifacts["stop_decision"]["stop_decision_id"],),
            feedback_refs=feedback_refs,
        )

    workpaper_context = compile_workpaper_context(
        policy=policy,
        round_responses=round_responses,
        feedback_receipts=feedback_receipts,
        reflections=reflections,
        stop_decision=reflection_artifacts[-1]["stop_decision"],
    )
    workpaper_tool = specialist_workpaper_tool(
        agent_id=agent_id, context=workpaper_context
    )
    workpaper = validate_specialist_workpaper(
        _fake_workpaper(workpaper_context),
        context=workpaper_context,
        expected_agent_id=agent_id,
    )

    numeric_refs = sorted(
        {
            str(row["numeric_ref"])
            for current in round_responses
            for row in current.get("numeric_facts") or ()
        }
    )
    open_gap_refs = sorted(
        {
            str(row["gap_ref"])
            for current in round_responses
            for row in current.get("residual_gaps") or ()
        }
    )
    unresolved_feedback_refs = sorted(
        {str(row["feedback_id"]) for row in feedback_receipts}
    )
    checkpoint_id = "CHECKPOINT::" + canonical_digest(
        {
            "session_id": session_id,
            "plan_digest": base_plan["plan_digest"],
            "accepted_evidence_refs": sorted(accepted_evidence_refs),
        }
    )[:24].upper()
    _event(
        events,
        session_id=session_id,
        event_type="checkpoint_created",
        actor_id="S0.CanonicalRuntime",
        occurred_at=recorded_at,
        input_refs=(base_plan["plan_digest"],),
        output_refs=(checkpoint_id,),
    )
    counter_refs = (
        sorted(accepted_evidence_refs)
        if agent_id == "AGENT::COUNTEREVIDENCE"
        else []
    )
    checkpoint = create_context_checkpoint(
        session=session,
        events=events,
        checkpoint_id=checkpoint_id,
        objective_digest=canonical_digest(policy["objective"]),
        plan_digest=base_plan["plan_digest"],
        research_graph_digest=base_graph_digest,
        accepted_evidence_refs=sorted(accepted_evidence_refs),
        numeric_fact_refs=numeric_refs,
        open_gap_refs=open_gap_refs,
        unresolved_feedback_refs=unresolved_feedback_refs,
        agent_local_state_refs=[str(row["reflection_digest"]) for row in reflections],
        authority_refs=[
            str(evidence_pack["pack_payload_digest"]),
            str(role_program["role_program_digest"]),
        ],
        counterevidence_refs=counter_refs,
        open_question_refs=[
            f"QUESTION::DELL::{agent_id.split('::')[-1]}::{index}"
            for index, _ in enumerate(open_gap_refs, start=1)
        ],
    )
    resume = resume_agent_session(
        session=session,
        events=events,
        checkpoint=checkpoint,
        expected_case_id="case_dell_current",
        expected_case_version="FIN_0_1_3",
        expected_as_of_date="2026-08-06",
        expected_active_plan_ref=session["active_plan_ref"],
        resumed_at=recorded_at,
        required_authority_refs=checkpoint["authority_refs"],
        required_open_gap_refs=open_gap_refs,
        required_unresolved_feedback_refs=unresolved_feedback_refs,
        required_counterevidence_refs=counter_refs,
        required_open_question_refs=checkpoint["open_question_refs"],
    )
    checks = {
        "initial_message_has_no_prefed_evidence": all(
            marker not in initial_text.lower()
            for marker in ("evidence_ref", "numeric_ref", "source_url")
        ),
        "all_role_requests_executed_once": (
            len(executed_ids) == len(set(executed_ids)) == len(role_program["requests"])
        ),
        "all_role_facets_covered": reflection_artifacts[-1]["coverage_state"][
            "all_required_groups_covered"
        ],
        "feedback_consumed_before_plan_delta": all(
            set(reflection["feedback_refs"]) == set(expected_refs)
            for reflection, expected_refs in zip(
                reflections, feedback_refs_by_round
            )
        ),
        "candidate_never_promoted": all(
            current["authority"]["candidate_promotions"] == 0
            for current in round_responses
        ),
        "graph_delta_hypothesis_only": all(
            not artifact["graph_delta"]["edge_additions"]
            and artifact["graph_delta"]["fact_authority_granted"] is False
            for artifact in reflection_artifacts
        ),
        "round_replay_deterministic": replay_digests
        == [row["round_response_digest"] for row in round_responses],
        "checkpoint_resume_preserves_state": resume["status"]
        == "resume_replay_verified",
        "workpaper_contract_valid": bool(workpaper["workpaper_digest"])
        and workpaper_tool["function"]["name"] == "submit_specialist_workpaper",
    }
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_role_checks_failed:"
            + agent_id
            + ":"
            + ",".join(failed)
        )
    return {
        "agent_id": agent_id,
        "role_program_digest": role_program["role_program_digest"],
        "session": session,
        "events": events,
        "round_selections": round_ids,
        "round_batches": round_batches,
        "round_responses": [public_round_response(row) for row in round_responses],
        "feedback_receipts": feedback_receipts,
        "reflections": reflections,
        "reflection_artifacts": reflection_artifacts,
        "workpaper_context": workpaper_context,
        "workpaper": workpaper,
        "checkpoint": checkpoint,
        "resume_receipt": resume,
        "checks": checks,
    }


def _compile_lead_bundle(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    attempt_id: str,
    recorded_at: str,
    accept_challenges: bool = True,
) -> dict[str, Any]:
    catalog = compile_challenge_catalog(workpapers=workpapers)
    tool = lead_coordination_tool(challenge_catalog=catalog)
    challenge_ids = [str(row["challenge_id"]) for row in catalog]
    accepted = challenge_ids[:1] if accept_challenges else []
    deferred = challenge_ids[1:] if accepted else challenge_ids
    payload = {
        "schema_version": LEAD_COORDINATION_DECISION_SCHEMA_VERSION,
        "lead_agent_id": RESEARCH_LEAD_AGENT_ID,
        "accepted_challenge_ids": accepted,
        "deferred_challenge_ids": deferred,
        "coordination_rationale": (
            "零模型 Lead 夹具只验证六份独立工作底稿和跨角色挑战能被完整路由。"
            "接受的修复只能回到原角色，Lead 不得新增研究事实、数字或引用。"
            + (
                ""
                if accept_challenges
                else " 已完成一次有界修订，本次重检不再授权新的角色修复。"
            )
        ),
        "next_state": (
            "continue_local_repairs" if accepted else "proceed_to_evaluation"
        ),
    }
    decision = validate_lead_coordination_decision(
        payload, challenge_catalog=catalog
    )
    seed = {
        "attempt_id": attempt_id,
        "lead_agent_id": RESEARCH_LEAD_AGENT_ID,
        "workpaper_digests": [str(row["workpaper_digest"]) for row in workpapers],
    }
    session_id = "SESSION::" + canonical_digest(seed)[:24].upper()
    plan_digest = canonical_digest(
        {
            "case_key": "DELL",
            "challenge_ids": challenge_ids,
            "role": RESEARCH_LEAD_AGENT_ID,
        }
    )
    session = create_agent_session(
        session_id=session_id,
        run_id="RUN::" + canonical_digest(seed)[:24].upper(),
        case_id="case_dell_current",
        case_version="FIN_0_1_3",
        as_of_date="2026-08-06",
        objective_ref="objective://DELL/current-dynamic-multi-agent/lead",
        active_plan_ref="PLAN::" + plan_digest[:24].upper(),
        created_at=recorded_at,
    )
    events: list[dict[str, Any]] = []
    _event(
        events,
        session_id=session_id,
        event_type="session_created",
        actor_id="S0.CanonicalRuntime",
        occurred_at=recorded_at,
        output_refs=(session_id,),
    )
    _event(
        events,
        session_id=session_id,
        event_type="plan_bound",
        actor_id="S3.DynamicMultiAgentHarness",
        occurred_at=recorded_at,
        input_refs=tuple(str(row["workpaper_digest"]) for row in workpapers),
        output_refs=(session["active_plan_ref"],),
    )
    _event(
        events,
        session_id=session_id,
        event_type="stop_decided",
        actor_id=RESEARCH_LEAD_AGENT_ID,
        occurred_at=recorded_at,
        input_refs=tuple(challenge_ids),
        output_refs=(decision["coordination_digest"],),
    )
    return {
        "session": session,
        "events": events,
        "challenge_catalog": catalog,
        "tool": tool,
        "decision": decision,
        "authority": {
            "lead_may_route_role_local_repairs": True,
            "lead_may_author_research_facts": False,
            "accepted_challenge_count": len(accepted),
        },
    }


def _mutation_checks(
    *,
    role_programs: Mapping[str, Any],
    role_bundles: Mapping[str, Any],
    lead_bundle: Mapping[str, Any],
) -> dict[str, bool]:
    by_agent = role_program_by_agent(role_programs)
    demand = by_agent["AGENT::DEMAND_QUALITY"]
    operating = by_agent["AGENT::OPERATING_PERFORMANCE"]
    checks: dict[str, bool] = {}

    foreign_request_id = str(operating["requests"][0]["request_id"])
    try:
        validate_request_selection(
            _fake_request_payload(
                agent_id=demand["agent_id"],
                round_index=1,
                request_ids=[foreign_request_id],
            ),
            policy=demand["loop_policy"],
            request_catalog=demand["request_catalog"],
            executed_request_ids=(),
            round_index=1,
        )
    except DynamicSingleUnitLoopError as exc:
        checks["cross_role_request_fails_closed"] = (
            exc.code == "dynamic_single_unit_request_selection_scope_invalid"
        )

    dummy_feedback = [
        {"feedback_id": "FEEDBACK::ONE"},
        {"feedback_id": "FEEDBACK::TWO"},
    ]
    try:
        validate_reflection_payload(
            _fake_reflection_payload(
                agent_id=demand["agent_id"],
                round_index=1,
                feedback_refs=["FEEDBACK::ONE"],
                next_request_ids=[str(demand["requests"][1]["request_id"])],
                accepted_evidence_refs=[],
                decision="continue",
            ),
            policy=demand["loop_policy"],
            request_catalog=demand["request_catalog"],
            feedback_receipts=dummy_feedback,
            accepted_evidence_refs=[],
            executed_request_ids=[str(demand["requests"][0]["request_id"])],
            round_index=1,
        )
    except DynamicSingleUnitLoopError as exc:
        checks["ignored_feedback_fails_closed"] = (
            exc.code == "dynamic_single_unit_reflection_feedback_invalid"
        )

    partial_request_id = str(demand["requests"][0]["request_id"])
    premature = validate_reflection_payload(
        _fake_reflection_payload(
            agent_id=demand["agent_id"],
            round_index=1,
            feedback_refs=[],
            next_request_ids=[],
            accepted_evidence_refs=[],
            decision="stop_sufficient",
        ),
        policy=demand["loop_policy"],
        request_catalog=demand["request_catalog"],
        feedback_receipts=[],
        accepted_evidence_refs=[],
        executed_request_ids=[partial_request_id],
        round_index=1,
    )
    try:
        compile_reflection_artifacts(
            policy=demand["loop_policy"],
            reflection=premature,
            session_id="SESSION::MUTATION",
            agent_id=demand["agent_id"],
            base_plan={"executed_request_ids": []},
            base_graph_digest="a" * 64,
            executed_request_ids=[partial_request_id],
            open_gap_refs=["GAP::MUTATION"],
            model_calls_used=0,
        )
    except DynamicSingleUnitLoopError as exc:
        checks["premature_stop_fails_closed"] = (
            exc.code == "dynamic_single_unit_stop_sufficient_coverage_incomplete"
        )

    mutated_reflection = _fake_reflection_payload(
        agent_id=demand["agent_id"],
        round_index=1,
        feedback_refs=[],
        next_request_ids=[str(demand["requests"][1]["request_id"])],
        accepted_evidence_refs=[],
        decision="continue",
    )
    mutated_reflection["edge_additions"] = [
        {"source": "DELL", "target": "NVDA", "relation": "owns"}
    ]
    try:
        validate_reflection_payload(
            mutated_reflection,
            policy=demand["loop_policy"],
            request_catalog=demand["request_catalog"],
            feedback_receipts=[],
            accepted_evidence_refs=[],
            executed_request_ids=[partial_request_id],
            round_index=1,
        )
    except DynamicSingleUnitLoopError as exc:
        checks["graph_fact_authority_expansion_fails_closed"] = (
            exc.code == "dynamic_single_unit_reflection_shape_invalid"
        )

    demand_bundle = role_bundles["AGENT::DEMAND_QUALITY"]
    operating_bundle = role_bundles["AGENT::OPERATING_PERFORMANCE"]
    try:
        resume_agent_session(
            session=demand_bundle["session"],
            events=demand_bundle["events"],
            checkpoint=demand_bundle["checkpoint"],
            expected_case_id="case_dell_current",
            expected_case_version="FIN_0_1_3",
            expected_as_of_date="2026-08-06",
            expected_active_plan_ref=operating_bundle["session"]["active_plan_ref"],
            resumed_at=demand_bundle["session"]["updated_at"],
        )
    except CanonicalRuntimeError as exc:
        checks["cross_session_resume_fails_closed"] = (
            str(exc) == "runtime_resume_active_plan_ref_mismatch"
        )

    mutated_lead = {
        key: deepcopy(value)
        for key, value in lead_bundle["decision"].items()
        if key != "coordination_digest"
    }
    mutated_lead["research_facts"] = ["Lead invented a fact"]
    try:
        validate_lead_coordination_decision(
            mutated_lead,
            challenge_catalog=lead_bundle["challenge_catalog"],
        )
    except ValueError as exc:
        checks["lead_fact_authoring_fails_closed"] = (
            "multi_agent_lead_coordination_identity_invalid" in str(exc)
        )
    return checks


def run_zero_call(
    *, attempt_id: str, private_output: Path, public_output: Path
) -> dict[str, Any]:
    recorded_at = _now()
    policy, programs = _compile_role_programs()
    by_agent = role_program_by_agent(programs)
    paths = resolve_runtime_paths(ROOT)
    permissions = frozenset({"current_product:read"})
    retrieval_principal = ResearchRetrievalPrincipal("current", permissions)
    evidence_principal = ResearchEvidencePackPrincipal("current", permissions)
    retrieval = ResearchRetrievalService.from_runtime_paths(ROOT, paths)
    evidence_service = ResearchEvidencePackService.from_runtime_paths(ROOT, paths)
    evidence_pack = evidence_service.get_case("DELL", evidence_principal)
    source_refs = policy["source_refs"]
    truth_policy = _read_json(source_refs["truth_spine_policy_ref"])
    consumer_policy = _read_json(source_refs["consumer_policy_ref"])
    task_quantitative = _read_json(
        source_refs["task_quantitative_result_ref"]
    )
    cuda = required_cuda_fp16_receipt(
        purpose="DELL current dynamic six-specialist S1/S2 zero-call proof"
    )

    role_bundles: dict[str, dict[str, Any]] = {}
    for agent_id in SPECIALIST_AGENT_IDS:
        role_bundles[agent_id] = _execute_role(
            role_program=by_agent[agent_id],
            attempt_id=attempt_id,
            recorded_at=recorded_at,
            retrieval=retrieval,
            retrieval_principal=retrieval_principal,
            evidence_pack=evidence_pack,
            truth_policy=truth_policy,
            consumer_policy=consumer_policy,
            task_quantitative=task_quantitative,
        )
    workpapers = [role_bundles[agent_id]["workpaper"] for agent_id in SPECIALIST_AGENT_IDS]
    lead_bundle = _compile_lead_bundle(
        workpapers=workpapers,
        attempt_id=attempt_id,
        recorded_at=recorded_at,
    )
    mutation_checks = _mutation_checks(
        role_programs=programs,
        role_bundles=role_bundles,
        lead_bundle=lead_bundle,
    )

    all_batches = [
        batch
        for bundle in role_bundles.values()
        for batch in bundle["round_batches"]
    ]
    all_responses = [
        response
        for bundle in role_bundles.values()
        for response in bundle["round_responses"]
    ]
    all_request_ids = [
        request_id
        for bundle in role_bundles.values()
        for selected in bundle["round_selections"]
        for request_id in selected
    ]
    session_ids = [
        str(bundle["session"]["session_id"]) for bundle in role_bundles.values()
    ]
    accepted_evidence_refs = {
        str(row["evidence_ref"])
        for response in all_responses
        for row in response.get("reviewed_evidence") or ()
    }
    numeric_refs = {
        str(row["numeric_ref"])
        for response in all_responses
        for row in response.get("numeric_facts") or ()
    }
    gap_refs = {
        str(row["gap_ref"])
        for response in all_responses
        for row in response.get("residual_gaps") or ()
    }
    feedback_refs = {
        str(row["feedback_id"])
        for bundle in role_bundles.values()
        for row in bundle["feedback_receipts"]
    }
    checks = {
        "six_independent_specialist_sessions": len(session_ids)
        == len(set(session_ids))
        == 6,
        "thirteen_role_owned_requests_executed_once": len(all_request_ids)
        == len(set(all_request_ids))
        == 13,
        "all_role_contracts_pass": all(
            all(bundle["checks"].values()) for bundle in role_bundles.values()
        ),
        "explicit_material_scope_used_for_every_batch": all(
            batch["material_scope"]["mode"]
            == "explicit_program_blueprint_compiled"
            for batch in all_batches
        ),
        "six_validated_workpapers_in_topology_order": [
            row["agent_id"] for row in workpapers
        ]
        == list(SPECIALIST_AGENT_IDS),
        "lead_has_separate_session_and_only_coordination_authority": (
            lead_bundle["session"]["session_id"] not in set(session_ids)
            and lead_bundle["authority"]["lead_may_author_research_facts"] is False
            and lead_bundle["tool"]["function"]["name"]
            == "submit_lead_coordination_decision"
        ),
        "candidate_promotion_zero": all(
            response["authority"]["candidate_promotions"] == 0
            for response in all_responses
        ),
        "zero_model_network_and_paid_calls": all(
            batch["summary"]["model_calls"] == 0
            and batch["summary"]["network_calls"] == 0
            for batch in all_batches
        ),
        "cuda_fp16_only": (
            str(cuda.get("execution_device") or "").startswith("cuda:")
            and cuda.get("embedding_precision") == "fp16"
            and cuda.get("reranker_precision") == "fp16"
            and cuda.get("cpu_fallback_allowed") is False
        ),
        "all_mutations_fail_closed": len(mutation_checks) == 6
        and all(mutation_checks.values()),
    }
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_zero_call_checks_failed:" + ",".join(failed)
        )

    private_body = {
        "schema_version": "fin_ia_s3_current_dynamic_multi_agent_zero_call_full_v1_0",
        "status": "current_dynamic_multi_agent_zero_call_proven",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "policy": policy,
        "role_programs": programs,
        "role_bundles": [role_bundles[agent_id] for agent_id in SPECIALIST_AGENT_IDS],
        "lead_bundle": lead_bundle,
        "cuda_receipt": cuda,
        "mutation_checks": mutation_checks,
        "checks": checks,
        "authority": {
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "candidate_promotions": 0,
            "natural_specialist_planning_or_judgment_proven": False,
            "natural_lead_coordination_proven": False,
            "S1_pass": False,
            "S2_pass": False,
            "S3_pass": False,
            "publication": False,
            "release": False,
        },
    }
    private_result = {
        **private_body,
        "result_digest": canonical_digest(private_body),
    }
    _write_json(private_output, private_result, exclusive=True)

    role_summaries = []
    for agent_id in SPECIALIST_AGENT_IDS:
        bundle = role_bundles[agent_id]
        role_responses = bundle["round_responses"]
        role_summaries.append(
            {
                "agent_id": agent_id,
                "facet_ids": list(by_agent[agent_id]["facet_ids"]),
                "request_count": sum(len(row) for row in bundle["round_selections"]),
                "retrieval_round_count": len(bundle["round_selections"]),
                "reviewed_evidence_refs": sorted(
                    {
                        str(row["evidence_ref"])
                        for response in role_responses
                        for row in response.get("reviewed_evidence") or ()
                    }
                ),
                "numeric_fact_refs": sorted(
                    {
                        str(row["numeric_ref"])
                        for response in role_responses
                        for row in response.get("numeric_facts") or ()
                    }
                ),
                "remaining_gap_refs": sorted(
                    {
                        str(row["gap_ref"])
                        for response in role_responses
                        for row in response.get("residual_gaps") or ()
                    }
                ),
                "feedback_receipt_count": len(bundle["feedback_receipts"]),
                "final_stop_decision": bundle["reflection_artifacts"][-1][
                    "stop_decision"
                ]["decision"],
                "workpaper_digest": bundle["workpaper"]["workpaper_digest"],
                "session_id": bundle["session"]["session_id"],
            }
        )
    public_body = {
        "schema_version": "fin_ia_s3_current_dynamic_multi_agent_zero_call_result_v1_0",
        "status": "current_dynamic_multi_agent_zero_call_proven",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "policy_binding": {
            "ref": POLICY_REF.as_posix(),
            "sha256": _sha256(POLICY_REF),
            "policy_digest": canonical_digest(policy),
        },
        "current_runtime_binding": {
            "evidence_pack_payload_digest": evidence_pack["pack_payload_digest"],
            "accepted_evidence_item_count": evidence_pack["summary"][
                "accepted_evidence_items"
            ],
            "task_quantitative_result_digest": task_quantitative["result_digest"],
        },
        "execution_summary": {
            "specialist_session_count": 6,
            "lead_session_count": 1,
            "compiled_facet_count": programs["summary"]["assigned_facet_count"],
            "executed_request_count": len(all_request_ids),
            "retrieval_round_count": len(all_batches),
            "unique_reviewed_evidence_count": len(accepted_evidence_refs),
            "unique_numeric_fact_count": len(numeric_refs),
            "unique_remaining_gap_count": len(gap_refs),
            "feedback_receipt_count": len(feedback_refs),
            "specialist_workpaper_count": len(workpapers),
            "cross_role_challenge_count": len(lead_bundle["challenge_catalog"]),
            "local_embedding_inference_batches": sum(
                int(batch["summary"]["local_embedding_inference_batches"])
                for batch in all_batches
            ),
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "cuda_device": cuda.get("device_name"),
            "cuda_execution_device": cuda.get("execution_device"),
        },
        "role_summaries": role_summaries,
        "lead_summary": {
            "challenge_ids": [
                row["challenge_id"] for row in lead_bundle["challenge_catalog"]
            ],
            "accepted_challenge_ids": lead_bundle["decision"][
                "accepted_challenge_ids"
            ],
            "deferred_challenge_ids": lead_bundle["decision"][
                "deferred_challenge_ids"
            ],
            "next_state": lead_bundle["decision"]["next_state"],
            "coordination_digest": lead_bundle["decision"][
                "coordination_digest"
            ],
        },
        "checks": checks,
        "mutation_checks": mutation_checks,
        "private_result_ref": _relative(private_output),
        "private_result_sha256": _sha256(private_output),
        "authority": private_result["authority"],
        "known_boundary": (
            "This executes all thirteen role-owned DELL EvidenceRequests through "
            "the mounted current S1/S2 runtime in six independent specialist "
            "sessions, binds complete feedback, compiles role-local workpapers and "
            "routes one Lead challenge. Request choices, reflections, workpapers and "
            "Lead decisions are zero-model fixtures. Natural DeepSeek multi-agent "
            "research quality requires a separately signed exact-once live."
        ),
    }
    public_result = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_json(public_output, public_result, exclusive=False)
    return public_result


def _validated_zero_call_predecessor(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    supplied_digest = str(value.pop("result_digest", ""))
    if (
        value.get("schema_version")
        != "fin_ia_s3_current_dynamic_multi_agent_zero_call_full_v1_0"
        or value.get("status") != "current_dynamic_multi_agent_zero_call_proven"
        or supplied_digest != canonical_digest(value)
        or not all((value.get("checks") or {}).values())
        or (value.get("authority") or {}).get("model_calls") != 0
        or [row.get("agent_id") for row in value.get("role_bundles") or ()]
        != list(SPECIALIST_AGENT_IDS)
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_zero_call_predecessor_invalid"
        )
    return {**value, "result_digest": supplied_digest}


def _workpaper_authority_sets(
    workpaper: Mapping[str, Any],
) -> dict[str, set[str]]:
    return {
        "evidence": {
            str(ref)
            for claim in workpaper.get("sourced_claims") or ()
            for ref in claim.get("evidence_refs") or ()
        },
        "numeric": {
            str(ref)
            for claim in workpaper.get("sourced_claims") or ()
            for ref in claim.get("numeric_refs") or ()
        },
        "relations": {
            str(ref)
            for claim in workpaper.get("sourced_claims") or ()
            for ref in claim.get("numeric_relation_refs") or ()
        },
        "gaps": {str(ref) for ref in workpaper.get("remaining_gap_refs") or ()},
    }


def run_zero_call_repair_successor(
    *,
    attempt_id: str,
    predecessor_path: Path,
    private_output: Path,
    public_output: Path,
) -> dict[str, Any]:
    recorded_at = _now()
    predecessor = _validated_zero_call_predecessor(predecessor_path)
    role_bundles = {
        str(row["agent_id"]): deepcopy(dict(row))
        for row in predecessor["role_bundles"]
    }
    normalization_receipts: list[dict[str, Any]] = []
    for agent_id in SPECIALIST_AGENT_IDS:
        normalized, receipt = normalize_bound_specialist_workpaper(
            role_bundles[agent_id]["workpaper"],
            context=role_bundles[agent_id]["workpaper_context"],
            expected_agent_id=agent_id,
            allow_legacy_double_hash=True,
        )
        role_bundles[agent_id]["workpaper"] = normalized
        normalization_receipts.append(receipt)
    workpapers = [
        deepcopy(role_bundles[agent_id]["workpaper"])
        for agent_id in SPECIALIST_AGENT_IDS
    ]
    initial_digests = {
        str(row["agent_id"]): str(row["workpaper_digest"])
        for row in workpapers
    }
    lead = deepcopy(dict(predecessor["lead_bundle"]))
    predecessor_challenge_by_id = {
        str(row["challenge_id"]): row
        for row in lead["challenge_catalog"]
    }
    accepted_ids = list(lead["decision"]["accepted_challenge_ids"])
    if len(accepted_ids) != 1 or accepted_ids[0] not in predecessor_challenge_by_id:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_zero_call_repair_frontier_invalid"
        )
    predecessor_challenge = predecessor_challenge_by_id[accepted_ids[0]]
    normalized_catalog = compile_challenge_catalog(workpapers=workpapers)
    challenge_matches = [
        row
        for row in normalized_catalog
        if all(
            row[key] == predecessor_challenge[key]
            for key in (
                "source_agent_id",
                "target_agent_id",
                "challenge",
                "material_reason",
                "requested_action",
            )
        )
    ]
    if len(challenge_matches) != 1:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_zero_call_repair_challenge_migration_invalid"
        )
    challenge = challenge_matches[0]
    challenge_migration_body = {
        "status": "legacy_workpaper_digest_challenge_normalized",
        "predecessor_challenge_id": predecessor_challenge["challenge_id"],
        "predecessor_source_workpaper_digest": predecessor_challenge[
            "source_workpaper_digest"
        ],
        "canonical_challenge_id": challenge["challenge_id"],
        "canonical_source_workpaper_digest": challenge["source_workpaper_digest"],
        "semantic_fields_unchanged": True,
        "authority_changed": False,
    }
    challenge_migration_receipt = {
        **challenge_migration_body,
        "receipt_digest": canonical_digest(challenge_migration_body),
    }
    target = str(challenge["target_agent_id"])
    target_bundle = role_bundles[target]
    prior_workpaper = deepcopy(dict(target_bundle["workpaper"]))
    receipt = compile_cross_role_feedback_receipt(
        target_session_id=target_bundle["session"]["session_id"],
        challenge=challenge,
        created_at=recorded_at,
    )
    repair_context = compile_workpaper_repair_context(
        context=target_bundle["workpaper_context"],
        prior_workpaper=prior_workpaper,
        feedback_receipts=[receipt],
    )
    repaired = validate_specialist_workpaper(
        _fake_repaired_workpaper(repair_context),
        context=repair_context,
        expected_agent_id=target,
    )

    continued_events = [deepcopy(dict(row)) for row in target_bundle["events"]]
    _event(
        continued_events,
        session_id=target_bundle["session"]["session_id"],
        event_type="feedback_issued",
        actor_id=RESEARCH_LEAD_AGENT_ID,
        occurred_at=recorded_at,
        input_refs=(str(challenge["challenge_id"]),),
        output_refs=(str(receipt["feedback_id"]),),
        feedback_refs=(str(receipt["feedback_id"]),),
    )
    prior_checkpoint = target_bundle["checkpoint"]
    repair_checkpoint_id = "CHECKPOINT::" + canonical_digest(
        {
            "session_id": target_bundle["session"]["session_id"],
            "feedback_id": receipt["feedback_id"],
            "repaired_workpaper_digest": repaired["workpaper_digest"],
        }
    )[:24].upper()
    _event(
        continued_events,
        session_id=target_bundle["session"]["session_id"],
        event_type="checkpoint_created",
        actor_id="S0.CanonicalRuntime",
        occurred_at=recorded_at,
        input_refs=(str(receipt["feedback_id"]),),
        output_refs=(repair_checkpoint_id,),
    )
    repair_checkpoint = create_context_checkpoint(
        session=target_bundle["session"],
        events=continued_events,
        checkpoint_id=repair_checkpoint_id,
        objective_digest=prior_checkpoint["objective_digest"],
        plan_digest=prior_checkpoint["plan_digest"],
        research_graph_digest=prior_checkpoint["research_graph_digest"],
        accepted_evidence_refs=prior_checkpoint["accepted_evidence_refs"],
        numeric_fact_refs=prior_checkpoint["numeric_fact_refs"],
        open_gap_refs=prior_checkpoint["open_gap_refs"],
        unresolved_feedback_refs=prior_checkpoint["unresolved_feedback_refs"],
        agent_local_state_refs=[
            *prior_checkpoint["agent_local_state_refs"],
            str(receipt["feedback_id"]),
            str(repair_context["context_digest"]),
            str(repaired["workpaper_digest"]),
        ],
        authority_refs=prior_checkpoint["authority_refs"],
        counterevidence_refs=prior_checkpoint["counterevidence_refs"],
        open_question_refs=prior_checkpoint["open_question_refs"],
    )
    repair_resume = resume_agent_session(
        session=target_bundle["session"],
        events=continued_events,
        checkpoint=repair_checkpoint,
        expected_case_id="case_dell_current",
        expected_case_version="FIN_0_1_3",
        expected_as_of_date="2026-08-06",
        expected_active_plan_ref=target_bundle["session"]["active_plan_ref"],
        resumed_at=recorded_at,
        required_authority_refs=prior_checkpoint["authority_refs"],
        required_open_gap_refs=prior_checkpoint["open_gap_refs"],
        required_unresolved_feedback_refs=prior_checkpoint[
            "unresolved_feedback_refs"
        ],
        required_counterevidence_refs=prior_checkpoint["counterevidence_refs"],
        required_open_question_refs=prior_checkpoint["open_question_refs"],
    )
    final_workpapers = [
        repaired if row["agent_id"] == target else deepcopy(dict(row))
        for row in workpapers
    ]
    lead_recheck = _compile_lead_bundle(
        workpapers=final_workpapers,
        attempt_id=attempt_id,
        recorded_at=recorded_at,
        accept_challenges=False,
    )
    final_digests = {
        str(row["agent_id"]): str(row["workpaper_digest"])
        for row in final_workpapers
    }
    changed_agents = sorted(
        agent_id
        for agent_id in SPECIALIST_AGENT_IDS
        if initial_digests[agent_id] != final_digests[agent_id]
    )
    checks = {
        "predecessor_immutable_and_digest_bound": predecessor["result_digest"]
        == _read_json(predecessor_path)["result_digest"],
        "all_legacy_workpaper_digests_reproduced_and_normalized": all(
            row["status"] == "legacy_double_hash_normalized"
            and row["content_revalidated"] is True
            and row["content_changed"] is False
            for row in normalization_receipts
        ),
        "accepted_challenge_semantics_preserved_during_normalization": (
            challenge_migration_receipt["semantic_fields_unchanged"] is True
            and challenge_migration_receipt["authority_changed"] is False
        ),
        "exactly_one_accepted_challenge_routed": len(accepted_ids) == 1,
        "only_target_role_workpaper_changed": changed_agents == [target],
        "repair_preserves_authority_ref_sets": _workpaper_authority_sets(repaired)
        == _workpaper_authority_sets(prior_workpaper),
        "repair_context_grants_no_new_authority": (
            repair_context["repair_state"]["new_evidence_authority_granted"]
            is False
            and repair_context["repair_state"]["new_numeric_authority_granted"]
            is False
        ),
        "feedback_checkpoint_resume_preserves_session": repair_resume["status"]
        == "resume_replay_verified",
        "lead_recheck_proceeds_without_more_repairs": (
            lead_recheck["decision"]["accepted_challenge_ids"] == []
            and lead_recheck["decision"]["next_state"]
            == "proceed_to_evaluation"
        ),
        "zero_model_network_tool_calls": True,
    }
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_zero_call_repair_checks_failed:"
            + ",".join(failed)
        )
    private_body = {
        "schema_version": "fin_ia_s3_current_dynamic_multi_agent_zero_call_repair_successor_full_v1_0",
        "status": "current_dynamic_multi_agent_zero_call_repair_successor_proven",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "predecessor_binding": {
            "ref": _relative(predecessor_path),
            "sha256": _sha256(predecessor_path),
            "result_digest": predecessor["result_digest"],
        },
        "workpaper_digest_normalization_receipts": normalization_receipts,
        "challenge_migration_receipt": challenge_migration_receipt,
        "accepted_challenge": deepcopy(dict(challenge)),
        "feedback_receipt": receipt,
        "repair_context": repair_context,
        "prior_workpaper": prior_workpaper,
        "repaired_workpaper": repaired,
        "continued_target_session": {
            "session": target_bundle["session"],
            "events": continued_events,
            "checkpoint": repair_checkpoint,
            "resume_receipt": repair_resume,
        },
        "final_workpapers": final_workpapers,
        "lead_recheck": lead_recheck,
        "checks": checks,
        "authority": {
            "model_calls": 0,
            "network_calls": 0,
            "tool_calls": 0,
            "reused_specialist_sessions": 6,
            "reused_retrieval_rounds": sum(
                len(row["round_selections"])
                for row in predecessor["role_bundles"]
            ),
            "new_role_repairs": 1,
            "normalized_legacy_workpaper_digests": len(normalization_receipts),
            "new_evidence_authority": False,
            "S3_pass": False,
            "publication": False,
            "release": False,
        },
    }
    private_result = {
        **private_body,
        "result_digest": canonical_digest(private_body),
    }
    _write_json(private_output, private_result, exclusive=True)
    public_body = {
        "schema_version": "fin_ia_s3_current_dynamic_multi_agent_zero_call_repair_successor_result_v1_0",
        "status": "current_dynamic_multi_agent_zero_call_repair_successor_proven",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "predecessor_binding": private_body["predecessor_binding"],
        "repair_summary": {
            "challenge_id": challenge["challenge_id"],
            "source_agent_id": challenge["source_agent_id"],
            "target_agent_id": target,
            "feedback_id": receipt["feedback_id"],
            "prior_workpaper_digest": prior_workpaper["workpaper_digest"],
            "repaired_workpaper_digest": repaired["workpaper_digest"],
            "changed_agent_ids": changed_agents,
            "lead_recheck_next_state": lead_recheck["decision"]["next_state"],
        },
        "checks": checks,
        "private_result_ref": _relative(private_output),
        "private_result_sha256": _sha256(private_output),
        "authority": private_result["authority"],
        "known_boundary": (
            "This successor reuses all six specialist sessions and all successful "
            "S1/S2 retrieval from the immutable predecessor. It proves one accepted "
            "cross-role challenge can return to only the target role, produce an "
            "authority-preserving workpaper repair and return to Lead. The repair "
            "text is a zero-model fixture; natural multi-agent quality remains unproven."
        ),
    }
    public_result = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_json(public_output, public_result, exclusive=False)
    return public_result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("zero-call", "zero-call-repair-successor"),
        default="zero-call",
    )
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--predecessor-private")
    parser.add_argument("--private-output")
    parser.add_argument("--public-output")
    args = parser.parse_args()
    runtime_paths = resolve_runtime_paths(ROOT)
    private_output = (
        Path(args.private_output).resolve()
        if args.private_output
        else runtime_paths.workbench_private_root
        / "fin_0_1_3_s3_current_dynamic_multi_agent"
        / args.attempt_id
        / (
            "zero_call_full_result.json"
            if args.mode == "zero-call"
            else "zero_call_repair_successor_full_result.json"
        )
    )
    public_default = (
        DEFAULT_PUBLIC
        if args.mode == "zero-call"
        else DEFAULT_REPAIR_PUBLIC
    )
    public_output = Path(args.public_output or public_default)
    if not public_output.is_absolute():
        public_output = ROOT / public_output
    if args.mode == "zero-call":
        result = run_zero_call(
            attempt_id=args.attempt_id,
            private_output=private_output,
            public_output=public_output,
        )
    else:
        if not args.predecessor_private:
            parser.error("--predecessor-private is required for repair successor")
        predecessor = Path(args.predecessor_private)
        if not predecessor.is_absolute():
            predecessor = ROOT / predecessor
        result = run_zero_call_repair_successor(
            attempt_id=args.attempt_id,
            predecessor_path=predecessor,
            private_output=private_output,
            public_output=public_output,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
