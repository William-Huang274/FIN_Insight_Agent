from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.workbench.backend.application.research_evidence_pack_service import (  # noqa: E402
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
    ResearchEvidencePackServiceError,
)
from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
    ResearchRetrievalServiceError,
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
from sec_agent.providers import (  # noqa: E402
    AgentToolStepResult,
    ModelGatewayError,
    execute_agent_tool_step_exact_once,
    execute_chat_completion_tool_step_exact_once,
    load_agent_transport_profile,
    load_chat_completion_profile,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    validate_deepseek_ga_node_profile,
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
    REFLECTION_SUBMISSION_TOOL_NAME,
    REFLECTION_TOOL_NAME,
    REQUEST_PAYLOAD_SCHEMA_VERSION,
    REQUEST_TOOL_NAME,
    compile_controlled_batch_projection,
    compile_initial_messages,
    compile_reflection_artifacts,
    compile_reflection_submission_messages,
    compile_round_feedback_receipts,
    compile_round_response,
    compile_workpaper_context,
    compile_workpaper_repair_context,
    compile_workpaper_submission_view,
    public_round_response,
    coverage_state,
    reflection_submission_tool,
    reflection_tool,
    request_evidence_tool,
    validate_reflection_payload,
    validate_reflection_submission,
    validate_request_selection,
)
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    LEAD_COORDINATION_SUBMISSION_TOOL_NAME,
    LEAD_COORDINATION_DECISION_SCHEMA_VERSION,
    RESEARCH_LEAD_AGENT_ID,
    SPECIALIST_AGENT_IDS,
    SPECIALIST_WORKPAPER_SUBMISSION_TOOL_NAME,
    SPECIALIST_WORKPAPER_SCHEMA_VERSION,
    compile_challenge_catalog,
    compile_lead_coordination_messages,
    compile_lead_coordination_submission_messages,
    compile_specialist_workpaper_messages,
    compile_specialist_workpaper_submission_messages,
    compile_planner_payload_from_role_opinions,
    lead_coordination_submission_tool,
    lead_coordination_tool,
    load_multi_agent_role_topology,
    specialist_workpaper_submission_tool,
    specialist_workpaper_tool,
    validate_lead_coordination_decision,
    validate_lead_coordination_submission,
    validate_lead_plan_checkpoint,
    validate_specialist_plan_checkpoint,
    validate_specialist_workpaper,
    validate_specialist_workpaper_submission,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    compile_cross_role_feedback_receipt,
    load_preview_planning_policy,
)
from sec_agent.research.multi_agent_content_repair import (  # noqa: E402
    compile_independent_content_challenges,
    expected_content_repair_budget,
    rebind_workpaper_context_semantic_rules,
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
LIVE_AUTHORITY_SCHEMA = "fin_ia_s3_current_dynamic_multi_agent_live_authority_v1_0"
LIVE_AUTHORITY_STATUS = "signed_exact_once_DELL_current_dynamic_multi_agent_live"
LIVE_RESULT_SCHEMA = "fin_ia_s3_current_dynamic_multi_agent_live_result_v1_0"
LIVE_FULL_RESULT_SCHEMA = "fin_ia_s3_current_dynamic_multi_agent_live_full_v1_0"
DEFAULT_LIVE_PUBLIC = Path(
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_live_result_v1_0.json"
)
SUBMISSION_SUCCESSOR_ZERO_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_submission_successor_zero_call_v1_0"
)
SUBMISSION_SUCCESSOR_LIVE_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_submission_successor_live_v1_0"
)
SUBMISSION_SUCCESSOR_FULL_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_submission_successor_full_v1_0"
)
SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_submission_successor_authority_v1_0"
)
SUBMISSION_RESUME_AUTHORITY_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_submission_successor_authority_v1_1"
)
SUBMISSION_REPAIR_RESUME_AUTHORITY_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_submission_successor_authority_v1_2"
)
DEFAULT_SUBMISSION_SUCCESSOR_ZERO_PUBLIC = Path(
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_zero_call_result_v1_0.json"
)
DEFAULT_SUBMISSION_SUCCESSOR_LIVE_PUBLIC = Path(
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_live_result_v1_0.json"
)
CONTENT_REPAIR_ZERO_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_content_repair_zero_call_v1_0"
)
CONTENT_REPAIR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_content_repair_authority_v1_0"
)
CONTENT_REPAIR_AUTHORITY_STATUS = (
    "signed_exact_once_DELL_current_dynamic_multi_agent_content_repair"
)
CONTENT_REPAIR_LIVE_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_content_repair_live_v1_0"
)
CONTENT_REPAIR_FULL_SCHEMA = (
    "fin_ia_s3_current_dynamic_multi_agent_content_repair_full_v1_0"
)
DEFAULT_CONTENT_REPAIR_ZERO_PUBLIC = Path(
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_zero_call_result_v1_0.json"
)
DEFAULT_CONTENT_REPAIR_LIVE_PUBLIC = Path(
    "configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_live_result_v1_0.json"
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
        "all_workpaper_digests_canonical_or_reproducibly_normalized": all(
            row["status"] in {"canonical", "legacy_double_hash_normalized"}
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
            "normalized_legacy_workpaper_digests": sum(
                row["status"] == "legacy_double_hash_normalized"
                for row in normalization_receipts
            ),
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


def _resolve_repo_ref(ref: str | Path) -> Path:
    raw = str(ref)
    value = PurePosixPath(raw)
    if value.is_absolute() or "\\" in raw or ".." in value.parts:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_path_invalid"
        )
    path = (ROOT / Path(*value.parts)).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_path_outside_repository"
        ) from exc
    return path


def _git_blob_sha256(*, commit: str, ref: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", str(commit or "").lower()):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_implementation_commit_invalid"
        )
    completed = subprocess.run(
        ["git", "show", f"{commit}:{ref}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise DynamicMultiAgentLoopError(
            f"dynamic_multi_agent_live_bound_git_blob_missing:{ref}"
        )
    return hashlib.sha256(completed.stdout).hexdigest()


def _tool_arguments(
    step: AgentToolStepResult, *, expected_name: str
) -> tuple[dict[str, Any], str]:
    if str(getattr(step, "finish_reason", "") or "") == "length":
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_tool_arguments_truncated"
        )
    if len(step.tool_calls) != 1:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_exactly_one_tool_call_required"
        )
    call = dict(step.tool_calls[0])
    function = call.get("function")
    if not (
        isinstance(function, Mapping)
        and str(function.get("name") or "") == expected_name
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_unexpected_tool_call"
        )
    try:
        payload = json.loads(str(function.get("arguments") or ""))
    except json.JSONDecodeError as exc:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_tool_arguments_json_invalid"
        ) from exc
    if not isinstance(payload, dict):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_tool_arguments_object_required"
        )
    return payload, str(call.get("id") or "")


def _tool_draft(
    step: AgentToolStepResult, *, expected_name: str
) -> tuple[str, str]:
    """Return the model-visible tool draft without treating it as valid JSON.

    Research and writing nodes may produce useful judgment in a syntactically
    imperfect tool argument string.  The string is preserved as immutable draft
    input for a separate strict submission node; it is never promoted as a
    contract-valid artifact by this helper.
    """

    if str(getattr(step, "finish_reason", "") or "") == "length":
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_tool_draft_truncated"
        )
    if len(step.tool_calls) != 1:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_exactly_one_tool_draft_required"
        )
    call = dict(step.tool_calls[0])
    function = call.get("function")
    if not (
        isinstance(function, Mapping)
        and str(function.get("name") or "") == expected_name
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_unexpected_tool_draft"
        )
    draft = str(function.get("arguments") or "")
    if not draft.strip():
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_tool_draft_missing"
        )
    return draft, str(call.get("id") or "")


def _capture_tool_draft(
    capture_path: Path, *, expected_name: str
) -> tuple[str, str, dict[str, Any]]:
    """Read one complete capture as an audit-only draft, never as Evidence."""

    capture = _read_json(capture_path)
    body = capture.get("response_body")
    choices = body.get("choices") if isinstance(body, Mapping) else None
    if not (
        str(capture.get("capture_type") or "").startswith(
            "provider_response"
        )
        and capture.get("status_code") == 200
        and capture.get("response_body_complete") is True
        and capture.get("credential_or_authorization_captured") is False
        and isinstance(choices, list)
        and len(choices) == 1
        and str(choices[0].get("finish_reason") or "") != "length"
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_successor_capture_not_reusable"
        )
    message = choices[0].get("message")
    calls = message.get("tool_calls") if isinstance(message, Mapping) else None
    if not isinstance(calls, list) or len(calls) != 1:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_successor_capture_tool_call_invalid"
        )
    call = calls[0]
    function = call.get("function") if isinstance(call, Mapping) else None
    if not (
        isinstance(function, Mapping)
        and str(function.get("name") or "") == expected_name
        and str(function.get("arguments") or "").strip()
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_successor_capture_tool_name_invalid"
        )
    receipt = {
        "capture_ref": _relative(capture_path),
        "capture_sha256": _sha256(capture_path),
        "response_digest": str(capture.get("response_digest") or ""),
        "attempt_id": str(capture.get("attempt_id") or ""),
        "response_body_complete": True,
        "eligible_for_contract_parse": bool(
            capture.get("eligible_for_contract_parse")
        ),
        "eligible_for_business_promotion": False,
        "reasoning_content_persisted": False,
    }
    return (
        str(function["arguments"]),
        str(call.get("id") or ""),
        receipt,
    )


_RESUME_CAPTURE_FIELDS = {
    "attempt_id",
    "request_ref",
    "request_sha256",
    "request_digest",
    "response_ref",
    "response_sha256",
    "response_digest",
    "status_code",
    "finish_reason",
    "tool_name",
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "reusable",
}


def _validate_resume_capture_manifest(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Validate an immutable partial-live capture manifest without promotion."""

    if not rows or len(rows) > 64:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_manifest_size_invalid"
        )
    validated: list[dict[str, Any]] = []
    attempt_ids: set[str] = set()
    for raw in rows:
        row = deepcopy(dict(raw))
        attempt_id = str(row.get("attempt_id") or "")
        if set(row) != _RESUME_CAPTURE_FIELDS or not attempt_id:
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_manifest_invalid"
            )
        if attempt_id in attempt_ids:
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_attempt_duplicate"
            )
        attempt_ids.add(attempt_id)
        request_path = _resolve_repo_ref(str(row["request_ref"]))
        response_path = _resolve_repo_ref(str(row["response_ref"]))
        if not (
            request_path.is_file()
            and response_path.is_file()
            and _sha256(request_path) == str(row["request_sha256"])
            and _sha256(response_path) == str(row["response_sha256"])
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_capture_drift"
            )
        request_capture = _read_json(request_path)
        response_capture = _read_json(response_path)
        body = response_capture.get("response_body")
        choices = body.get("choices") if isinstance(body, Mapping) else None
        if not (
            request_capture.get("request_digest") == row["request_digest"]
            and response_capture.get("response_digest")
            == row["response_digest"]
            and response_capture.get("status_code") == row["status_code"] == 200
            and isinstance(choices, list)
            and len(choices) == 1
            and choices[0].get("finish_reason") == row["finish_reason"]
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_capture_invalid"
            )
        message = choices[0].get("message")
        calls = message.get("tool_calls") if isinstance(message, Mapping) else None
        actual_tool = ""
        if isinstance(calls, list) and len(calls) == 1:
            function = calls[0].get("function")
            if isinstance(function, Mapping):
                actual_tool = str(function.get("name") or "")
        reusable = bool(row["reusable"])
        if not (
            actual_tool == str(row["tool_name"])
            and reusable
            == (str(row["finish_reason"]) != "length" and bool(actual_tool))
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_reuse_state_invalid"
            )
        validated.append(row)
    return validated


def _resume_capture_for_attempt(
    rows: Sequence[Mapping[str, Any]], *, attempt_fragment: str
) -> Path | None:
    validated = _validate_resume_capture_manifest(rows)
    matches = [
        row
        for row in validated
        if attempt_fragment in str(row["attempt_id"])
        and bool(row["reusable"])
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_capture_ambiguous"
        )
    return _resolve_repo_ref(str(matches[0]["response_ref"])).resolve()


def _resume_capture_draft(
    rows: Sequence[Mapping[str, Any]],
    *,
    attempt_fragment: str,
    expected_name: str,
) -> tuple[str, str, dict[str, Any]] | None:
    path = _resume_capture_for_attempt(
        rows, attempt_fragment=attempt_fragment
    )
    if path is None:
        return None
    draft, call_id, receipt = _capture_tool_draft(
        path, expected_name=expected_name
    )
    return (
        draft,
        call_id,
        {
            **receipt,
            "capture_origin": "partial_submission_successor",
        },
    )


def _resume_replay_recorded_at(
    rows: Sequence[Mapping[str, Any]],
) -> str:
    """Recover the timestamp that binds R4 deterministic feedback identities."""

    validated = _validate_resume_capture_manifest(rows)
    match = next(
        (
            row
            for row in validated
            if str(row["attempt_id"]).endswith(
                "supply-relationship-reflection-r2-draft"
            )
        ),
        None,
    )
    if match is None:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_recorded_at_missing"
        )
    request = _read_json(_resolve_repo_ref(str(match["request_ref"])))
    body = request.get("request_body")
    messages = body.get("messages") if isinstance(body, Mapping) else None
    if not isinstance(messages, list):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_recorded_at_invalid"
        )
    user_content = next(
        (
            str(row.get("content") or "")
            for row in reversed(messages)
            if isinstance(row, Mapping) and row.get("role") == "user"
        ),
        "",
    )
    try:
        visible = json.loads(user_content)
    except json.JSONDecodeError as exc:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_recorded_at_invalid"
        ) from exc
    feedback = visible.get("feedback_receipts") if isinstance(visible, Mapping) else None
    value = (
        str(feedback[0].get("created_at") or "")
        if isinstance(feedback, list)
        and feedback
        and isinstance(feedback[0], Mapping)
        else ""
    )
    if not value:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_recorded_at_invalid"
        )
    return value


def _resume_lead_input_workpapers(
    rows: Sequence[Mapping[str, Any]],
    *,
    round_index: int,
) -> list[dict[str, Any]]:
    """Recover the exact locally validated workpapers visible to a Lead round."""

    validated = _validate_resume_capture_manifest(rows)
    match = next(
        (
            row
            for row in validated
            if str(row["attempt_id"]).endswith(
                f"lead-r{round_index}-draft"
            )
        ),
        None,
    )
    if match is None:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_lead_input_missing"
        )
    request = _read_json(_resolve_repo_ref(str(match["request_ref"])))
    body = request.get("request_body")
    messages = body.get("messages") if isinstance(body, Mapping) else None
    user_content = next(
        (
            str(row.get("content") or "")
            for row in reversed(messages or [])
            if isinstance(row, Mapping) and row.get("role") == "user"
        ),
        "",
    )
    try:
        visible = json.loads(user_content)
    except json.JSONDecodeError as exc:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_lead_input_invalid"
        ) from exc
    workpapers = (
        visible.get("validated_workpapers")
        if isinstance(visible, Mapping)
        else None
    )
    if not (
        isinstance(workpapers, list)
        and len(workpapers) == len(SPECIALIST_AGENT_IDS)
        and {
            str(row.get("agent_id") or "")
            for row in workpapers
            if isinstance(row, Mapping)
        }
        == set(SPECIALIST_AGENT_IDS)
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_lead_input_invalid"
        )
    return [deepcopy(dict(row)) for row in workpapers]


def _validate_resume_workpaper_authority(
    payload: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    expected_agent_id: str,
) -> dict[str, Any]:
    """Recheck captured content/refs while retaining its original Lead identity."""

    captured = deepcopy(dict(payload))
    raw = deepcopy(captured)
    if not (
        str(raw.pop("workpaper_digest", ""))
        and str(raw.pop("context_digest", ""))
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_workpaper_identity_missing"
        )
    rebound = validate_specialist_workpaper(
        raw,
        context=context,
        expected_agent_id=expected_agent_id,
    )
    if _workpaper_authority_sets(captured) != _workpaper_authority_sets(rebound):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_workpaper_authority_drift"
        )
    return captured


def _capture_manifest_from_root(capture_root: Path) -> list[dict[str, Any]]:
    """Index every complete request/response pair in one immutable attempt root."""

    rows: list[dict[str, Any]] = []
    if not capture_root.is_dir():
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_capture_root_missing"
        )
    for request_path in sorted(capture_root.rglob("model_visible_request.json")):
        response_path = request_path.with_name("provider_response.json")
        if not response_path.is_file():
            continue
        request = _read_json(request_path)
        response = _read_json(response_path)
        body = response.get("response_body")
        choices = body.get("choices") if isinstance(body, Mapping) else None
        if not (
            response.get("status_code") == 200
            and isinstance(choices, list)
            and len(choices) == 1
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_capture_response_invalid"
            )
        choice = choices[0]
        message = choice.get("message")
        calls = message.get("tool_calls") if isinstance(message, Mapping) else None
        tool_name = ""
        if isinstance(calls, list) and len(calls) == 1:
            function = calls[0].get("function")
            if isinstance(function, Mapping):
                tool_name = str(function.get("name") or "")
        usage = body.get("usage") if isinstance(body, Mapping) else {}
        usage = usage if isinstance(usage, Mapping) else {}
        details = usage.get("completion_tokens_details")
        details = details if isinstance(details, Mapping) else {}
        finish_reason = str(choice.get("finish_reason") or "")
        row = {
            "attempt_id": str(request.get("attempt_id") or request_path.parent.name),
            "request_ref": _relative(request_path),
            "request_sha256": _sha256(request_path),
            "request_digest": str(request.get("request_digest") or ""),
            "response_ref": _relative(response_path),
            "response_sha256": _sha256(response_path),
            "response_digest": str(response.get("response_digest") or ""),
            "status_code": int(response["status_code"]),
            "finish_reason": finish_reason,
            "tool_name": tool_name,
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "reasoning_tokens": int(details.get("reasoning_tokens") or 0),
            "reusable": bool(finish_reason != "length" and tool_name),
        }
        rows.append(row)
    return _validate_resume_capture_manifest(rows)


def materialize_submission_successor_local_failure(
    *,
    authority_path: Path,
    phase: str,
    code: str,
) -> dict[str, Any]:
    """Persist a post-Provider local failure before any successor is authorized."""

    authority_path = authority_path.resolve()
    authority = _read_json(authority_path)
    try:
        paths = validate_submission_successor_authority(
            authority, authority_path=authority_path
        )
    except DynamicMultiAgentLoopError as exc:
        # A root-cause patch may already have changed the working-tree copy of
        # the runner/runtime.  The failed attempt remains bound to the signed
        # commit, so verify implementation refs against that commit while all
        # data/config/result refs must still match on disk.
        if not str(exc).startswith(
            "dynamic_multi_agent_submission_successor_input_drift:"
        ):
            raise
        if not (
            authority.get("status")
            == "signed_exact_once_submission_successor_live"
            and authority.get("schema_version")
            in {
                SUBMISSION_RESUME_AUTHORITY_SCHEMA,
                SUBMISSION_REPAIR_RESUME_AUTHORITY_SCHEMA,
            }
            and authority.get("case_key") == "DELL"
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_failure_authority_invalid"
            ) from exc
        bound = authority.get("bound_inputs")
        if not isinstance(bound, Mapping):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_failure_inputs_invalid"
            ) from exc
        commit = str(authority.get("implementation_commit") or "").lower()
        ref_names = (
            "runtime_registry",
            "loop_policy",
            "provider_profile",
            "submission_profile",
            "runner",
            "loop_runtime",
            "multi_agent_runtime",
            "zero_call_result",
            "predecessor_public",
            "predecessor_private",
            "resume_public",
            "resume_private",
        )
        implementation_names = {
            "loop_policy",
            "runner",
            "loop_runtime",
            "multi_agent_runtime",
        }
        paths = {}
        for name in ref_names:
            ref = str(bound.get(f"{name}_ref") or "")
            path = _resolve_repo_ref(ref)
            expected_sha = str(bound.get(f"{name}_sha256") or "")
            valid = (
                _git_blob_sha256(commit=commit, ref=ref) == expected_sha
                if name in implementation_names
                else path.is_file() and _sha256(path) == expected_sha
            )
            if not valid:
                raise DynamicMultiAgentLoopError(
                    "dynamic_multi_agent_submission_failure_input_drift:"
                    + name
                ) from exc
            paths[f"{name}_ref"] = path
    output = dict(authority["output_contract"])
    capture_root = _resolve_repo_ref(str(output["capture_root_ref"]))
    private_root = _resolve_repo_ref(str(output["private_output_root_ref"]))
    public_path = _resolve_repo_ref(str(output["public_result_ref"]))
    new_manifest = _capture_manifest_from_root(capture_root)
    inherited_manifest: list[dict[str, Any]] = []
    if authority.get("schema_version") in {
        SUBMISSION_RESUME_AUTHORITY_SCHEMA,
        SUBMISSION_REPAIR_RESUME_AUTHORITY_SCHEMA,
    }:
        inherited = _read_json(paths["resume_private_ref"])
        inherited_manifest = [
            deepcopy(dict(row))
            for row in inherited.get("capture_manifest") or ()
            if bool(row.get("reusable"))
        ]
    combined_manifest = _validate_resume_capture_manifest(
        [*inherited_manifest, *new_manifest]
    )
    if not (
        phase.strip()
        and code.strip()
        and new_manifest
        and all(row["reusable"] for row in new_manifest)
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_local_failure_materialization_invalid"
        )
    last_capture = next(
        (
            row
            for row in new_manifest
            if str(row["attempt_id"]).endswith("lead-r1-submit")
        ),
        new_manifest[-1],
    )
    recorded_at = _now()
    full_body = {
        "schema_version": SUBMISSION_SUCCESSOR_FULL_SCHEMA,
        "status": "terminal_partial_local_contract_failure_preserved",
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha256(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "run_id": str(output["run_id"]),
        "attempt_prefix": str(output["attempt_prefix"]),
        "predecessor_public_ref": authority["bound_inputs"][
            "predecessor_public_ref"
        ],
        "predecessor_private_ref": authority["bound_inputs"][
            "predecessor_private_ref"
        ],
        "resume_public_ref": authority["bound_inputs"].get(
            "resume_public_ref", ""
        ),
        "resume_private_ref": authority["bound_inputs"].get(
            "resume_private_ref", ""
        ),
        "capture_root_ref": _relative(capture_root),
        "capture_manifest": combined_manifest,
        "new_capture_manifest": new_manifest,
        "failure": {
            "phase": phase,
            "code": code,
            "capture_ref": last_capture["response_ref"],
            "provider_failure": False,
            "failure_occurred_before_next_provider_attempt": True,
        },
        "execution": {
            "new_provider_calls_attempted": len(new_manifest),
            "new_provider_http_200": len(new_manifest),
            "reusable_completed_captures": len(combined_manifest),
            "inherited_reusable_captures": len(inherited_manifest),
            "specialist_sessions_reconstructable": 6,
            "lead_rounds_reconstructable": 1,
            "role_repairs_executed": 0,
            "external_source_network_calls": 0,
            "candidate_promotions": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "claims": {
            "prior_attempts_preserved_immutable": True,
            "six_specialist_workpapers_reconstructable": True,
            "lead_R1_decision_reconstructable": True,
            "failed_role_repair_provider_call_attempted": False,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "known_boundary": (
            "The six specialist workpapers and the first Lead decision are "
            "reconstructable from immutable captures. The attempt stopped in "
            "the local repair-context projection before any repair Provider "
            "call. A later successor must first prove exact zero-call replay, "
            "reuse every completed capture, preserve authority sets, and begin "
            "only at the first accepted role-repair draft."
        ),
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    _write_json(private_root / "full_result.json", full, exclusive=True)
    public_body = {
        "schema_version": SUBMISSION_SUCCESSOR_LIVE_SCHEMA,
        "status": full["status"],
        "recorded_at": recorded_at,
        "authority_ref": full["authority_ref"],
        "implementation_commit": full["implementation_commit"],
        "case_key": "DELL",
        "model": "deepseek-v4-pro",
        "frontier": "first_accepted_role_repair_draft",
        "failure": deepcopy(full["failure"]),
        "execution": deepcopy(full["execution"]),
        "claims": deepcopy(full["claims"]),
        "acceptance": {
            "dynamic_multi_agent_contract_pass": False,
            "L1_assessment_pending": False,
            "eight_dimension_content_assessment_pending": False,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "private_full_result_ref": _relative(private_root / "full_result.json"),
        "private_full_result_sha256": _sha256(private_root / "full_result.json"),
        "known_boundary": full["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_json(public_path, public, exclusive=True)
    return public


def _public_provider_step(step: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "finish_reason": str(step.get("finish_reason") or ""),
        "usage": deepcopy(dict(step.get("usage") or {})),
        "request_digest": str(step.get("request_digest") or ""),
        "response_digest": str(step.get("response_digest") or ""),
        "request_capture_ref": _relative(Path(str(step["request_capture_ref"]))),
        "response_capture_ref": _relative(Path(str(step["response_capture_ref"]))),
        "private_reasoning_fields_redacted": int(
            step.get("private_reasoning_fields_redacted") or 0
        ),
        "reasoning_content_persisted": False,
    }


def expected_live_execution_budget() -> dict[str, int]:
    """Derive the exact ceiling from the six-role bounded loop topology."""

    return {
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


def expected_submission_successor_budget() -> dict[str, int]:
    """Ceiling derived from the capture-bound continuation topology."""

    return {
        "maximum_new_model_calls": 25,
        "maximum_new_transport_attempts": 25,
        "reflection_submissions_from_R1_captures": 4,
        "supply_followup_reflection_drafts": 1,
        "supply_followup_reflection_submissions": 1,
        "new_specialist_workpaper_drafts": 4,
        "specialist_workpaper_submissions": 5,
        "lead_coordination_drafts": 2,
        "lead_coordination_submissions": 2,
        "role_repair_drafts": 3,
        "role_repair_submissions": 3,
        "maximum_new_s1_s2_requests": 1,
        "maximum_new_retrieval_rounds": 1,
        "maximum_lead_rounds": 2,
        "maximum_role_repairs": 3,
        "maximum_external_source_network_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "candidate_promotions": 0,
        "current_product_pointer_mutations": 0,
    }


def expected_submission_resume_budget() -> dict[str, int]:
    """Ceiling after reusing the eight valid R3 Provider captures."""

    return {
        "maximum_new_model_calls": 17,
        "maximum_new_transport_attempts": 17,
        "reflection_submissions_from_R1_captures": 1,
        "supply_followup_reflection_drafts": 1,
        "supply_followup_reflection_submissions": 1,
        "new_specialist_workpaper_drafts": 2,
        "specialist_workpaper_submissions": 2,
        "lead_coordination_drafts": 2,
        "lead_coordination_submissions": 2,
        "role_repair_drafts": 3,
        "role_repair_submissions": 3,
        "maximum_new_s1_s2_requests": 1,
        "maximum_new_retrieval_rounds": 1,
        "maximum_lead_rounds": 2,
        "maximum_role_repairs": 3,
        "maximum_external_source_network_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "candidate_promotions": 0,
        "current_product_pointer_mutations": 0,
    }


def expected_submission_repair_resume_budget() -> dict[str, int]:
    """Ceiling after reusing the complete six-role and Lead-R1 frontier."""

    return {
        "maximum_new_model_calls": 8,
        "maximum_new_transport_attempts": 8,
        "reflection_submissions_from_R1_captures": 0,
        "supply_followup_reflection_drafts": 0,
        "supply_followup_reflection_submissions": 0,
        "new_specialist_workpaper_drafts": 0,
        "specialist_workpaper_submissions": 0,
        "lead_coordination_drafts": 1,
        "lead_coordination_submissions": 1,
        "role_repair_drafts": 3,
        "role_repair_submissions": 3,
        "maximum_new_s1_s2_requests": 1,
        "maximum_new_retrieval_rounds": 1,
        "maximum_lead_rounds": 2,
        "maximum_role_repairs": 3,
        "maximum_external_source_network_calls": 0,
        "retries": 0,
        "fallbacks": 0,
        "candidate_promotions": 0,
        "current_product_pointer_mutations": 0,
    }


def _validate_token_budget_basis(value: Any) -> None:
    required = {
        "node_purpose",
        "input_scale",
        "required_outputs",
        "schema_burden",
        "materiality_quality_risk",
        "comparable_run_evidence",
        "reasoning_profile",
        "stop_and_truncation_behavior",
        "maximum_calls",
    }
    if not isinstance(value, Mapping) or not value:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_successor_token_budget_basis_missing"
        )
    for node_class, row in value.items():
        if not (
            str(node_class).strip()
            and isinstance(row, Mapping)
            and set(row) == required
            and isinstance(row.get("maximum_calls"), int)
            and int(row["maximum_calls"]) > 0
            and all(
                len(str(row[field]).strip()) >= 12
                for field in required - {"maximum_calls"}
            )
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_successor_token_budget_basis_invalid"
            )


def validate_submission_successor_authority(
    authority: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    expected = {
        "schema_version",
        "status",
        "signed_at",
        "implementation_commit",
        "case_key",
        "execution_budget",
        "token_budget_basis",
        "bound_inputs",
        "output_contract",
        "known_boundary",
    }
    schema_version = str(authority.get("schema_version") or "")
    resume_enabled = schema_version in {
        SUBMISSION_RESUME_AUTHORITY_SCHEMA,
        SUBMISSION_REPAIR_RESUME_AUTHORITY_SCHEMA,
    }
    repair_resume_enabled = (
        schema_version == SUBMISSION_REPAIR_RESUME_AUTHORITY_SCHEMA
    )
    expected_budget = (
        expected_submission_repair_resume_budget()
        if repair_resume_enabled
        else (
            expected_submission_resume_budget()
            if resume_enabled
            else expected_submission_successor_budget()
        )
    )
    if not (
        set(authority) == expected
        and schema_version
        in {
            SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA,
            SUBMISSION_RESUME_AUTHORITY_SCHEMA,
            SUBMISSION_REPAIR_RESUME_AUTHORITY_SCHEMA,
        }
        and authority.get("status")
        == "signed_exact_once_submission_successor_live"
        and authority.get("case_key") == "DELL"
        and dict(authority.get("execution_budget") or {})
        == expected_budget
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_authority_invalid"
        )
    _validate_token_budget_basis(authority.get("token_budget_basis"))
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_inputs_invalid"
        )
    ref_names = (
        "runtime_registry",
        "loop_policy",
        "provider_profile",
        "submission_profile",
        "runner",
        "loop_runtime",
        "multi_agent_runtime",
        "zero_call_result",
        "predecessor_public",
        "predecessor_private",
    )
    if resume_enabled:
        ref_names += ("resume_public", "resume_private")
    paths: dict[str, Path] = {}
    for name in ref_names:
        ref = str(bound.get(f"{name}_ref") or "")
        path = _resolve_repo_ref(ref)
        if not path.is_file() or _sha256(path) != str(
            bound.get(f"{name}_sha256") or ""
        ):
            raise DynamicMultiAgentLoopError(
                f"dynamic_multi_agent_submission_successor_input_drift:{name}"
            )
        paths[f"{name}_ref"] = path
    commit = str(authority.get("implementation_commit") or "").lower()
    for name in ("loop_policy", "runner", "loop_runtime", "multi_agent_runtime"):
        ref = str(bound[f"{name}_ref"])
        if _git_blob_sha256(commit=commit, ref=ref) != str(
            bound[f"{name}_sha256"]
        ):
            raise DynamicMultiAgentLoopError(
                f"dynamic_multi_agent_submission_successor_git_binding_invalid:{name}"
            )
    zero = _read_json(paths["zero_call_result_ref"])
    predecessor_public = _read_json(paths["predecessor_public_ref"])
    predecessor_private = _read_json(paths["predecessor_private_ref"])
    expected_zero_status = (
        "submission_successor_repair_resume_zero_call_proven"
        if repair_resume_enabled
        else (
            "submission_successor_resume_zero_call_proven"
            if resume_enabled
            else "submission_successor_zero_call_proven"
        )
    )
    if not (
        zero.get("status") == expected_zero_status
        and zero.get("result_digest") == bound.get("zero_call_result_digest")
        and all((zero.get("checks") or {}).values())
        and predecessor_public.get("result_digest")
        == bound.get("predecessor_public_result_digest")
        and predecessor_private.get("full_result_digest")
        == bound.get("predecessor_private_result_digest")
        and predecessor_public.get("private_full_result_sha256")
        == _sha256(paths["predecessor_private_ref"])
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_chain_invalid"
        )
    if resume_enabled:
        resume_public = _read_json(paths["resume_public_ref"])
        resume_private = _read_json(paths["resume_private_ref"])
        expected_resume_status = (
            "terminal_partial_local_contract_failure_preserved"
            if repair_resume_enabled
            else "terminal_partial_provider_reasoning_budget_exhausted_preserved"
        )
        if not (
            resume_public.get("status")
            == expected_resume_status
            and resume_private.get("status")
            == expected_resume_status
            and resume_public.get("result_digest")
            == bound.get("resume_public_result_digest")
            and resume_private.get("full_result_digest")
            == bound.get("resume_private_full_result_digest")
            and resume_public.get("private_full_result_sha256")
            == _sha256(paths["resume_private_ref"])
            and zero.get("resume_public_result_digest")
            == resume_public.get("result_digest")
            and zero.get("resume_private_full_result_digest")
            == resume_private.get("full_result_digest")
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_chain_invalid"
            )
    output = authority.get("output_contract")
    if not (
        isinstance(output, Mapping)
        and set(output)
        == {
            "capture_root_ref",
            "private_output_root_ref",
            "public_result_ref",
            "run_id",
            "attempt_prefix",
            "product_publication",
        }
        and output.get("product_publication") == "forbidden"
        and str(output.get("run_id") or "").strip()
        and str(output.get("attempt_prefix") or "").strip()
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_output_invalid"
        )
    for key in ("private_output_root_ref", "public_result_ref"):
        if _resolve_repo_ref(str(output[key])).exists():
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_successor_output_consumed"
            )
    if not (
        authority_path.is_file()
        and str(authority.get("signed_at") or "").strip()
        and len(str(authority.get("known_boundary") or "").strip()) >= 120
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_metadata_invalid"
        )
    return paths


def validate_content_repair_authority(
    authority: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    expected = {
        "schema_version",
        "status",
        "signed_at",
        "implementation_commit",
        "case_key",
        "execution_budget",
        "token_budget_basis",
        "bound_inputs",
        "output_contract",
        "known_boundary",
    }
    if not (
        set(authority) == expected
        and authority.get("schema_version") == CONTENT_REPAIR_AUTHORITY_SCHEMA
        and authority.get("status") == CONTENT_REPAIR_AUTHORITY_STATUS
        and authority.get("case_key") == "DELL"
        and dict(authority.get("execution_budget") or {})
        == expected_content_repair_budget()
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_content_repair_authority_invalid"
        )
    _validate_token_budget_basis(authority.get("token_budget_basis"))
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_content_repair_inputs_invalid"
        )
    ref_names = (
        "provider_profile",
        "submission_profile",
        "runner",
        "loop_runtime",
        "multi_agent_runtime",
        "content_repair_runtime",
        "scope_decision",
        "zero_call_result",
        "predecessor_public",
        "predecessor_private",
        "assessment",
    )
    paths: dict[str, Path] = {}
    for name in ref_names:
        ref = str(bound.get(f"{name}_ref") or "")
        path = _resolve_repo_ref(ref)
        if not path.is_file() or _sha256(path) != str(
            bound.get(f"{name}_sha256") or ""
        ):
            raise DynamicMultiAgentLoopError(
                f"dynamic_multi_agent_content_repair_input_drift:{name}"
            )
        paths[f"{name}_ref"] = path
    commit = str(authority.get("implementation_commit") or "").lower()
    for name in (
        "runner",
        "loop_runtime",
        "multi_agent_runtime",
        "content_repair_runtime",
    ):
        if _git_blob_sha256(commit=commit, ref=str(bound[f"{name}_ref"])) != str(
            bound[f"{name}_sha256"]
        ):
            raise DynamicMultiAgentLoopError(
                f"dynamic_multi_agent_content_repair_git_binding_invalid:{name}"
            )
    zero = _read_json(paths["zero_call_result_ref"])
    scope_decision = _read_json(paths["scope_decision_ref"])
    predecessor_public = _read_json(paths["predecessor_public_ref"])
    predecessor_private = _read_json(paths["predecessor_private_ref"])
    assessment = _read_json(paths["assessment_ref"])
    if not (
        scope_decision.get("schema_version")
        == "fin_ia_s3_current_dynamic_multi_agent_content_repair_scope_decision_v1_0"
        and scope_decision.get("status")
        == "R5_independent_L1_L2_failure_preserved_one_five_role_repair_authorized"
        and scope_decision.get("next_authorized_scope")
        == "one_clean_authorized_five_role_content_repair_and_Lead_recheck"
        and dict(scope_decision.get("execution_budget") or {})
        == expected_content_repair_budget()
        and scope_decision.get("content_repair_live_authorized") is True
        and scope_decision.get("new_S1_S2_authorized") is False
        and scope_decision.get("writer_authorized") is False
        and zero.get("status") == "content_repair_zero_call_proven"
        and zero.get("result_digest") == bound.get("zero_call_result_digest")
        and all((zero.get("checks") or {}).values())
        and predecessor_public.get("status")
        == "completed_contract_valid_assessment_pending"
        and predecessor_public.get("result_digest")
        == bound.get("predecessor_public_result_digest")
        and predecessor_private.get("status")
        == "completed_contract_valid_assessment_pending"
        and predecessor_private.get("full_result_digest")
        == bound.get("predecessor_private_full_result_digest")
        and predecessor_public.get("private_full_result_sha256")
        == _sha256(paths["predecessor_private_ref"])
        and assessment.get("status")
        == "dynamic_multi_agent_contract_pass_financial_truth_and_evidence_authority_fail_writer_not_eligible"
        and assessment.get("source_result_digest")
        == predecessor_public.get("result_digest")
        and assessment.get("private_full_result_digest")
        == predecessor_private.get("full_result_digest")
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_content_repair_chain_invalid"
        )
    output = authority.get("output_contract")
    if not (
        isinstance(output, Mapping)
        and set(output)
        == {
            "capture_root_ref",
            "private_output_root_ref",
            "public_result_ref",
            "run_id",
            "attempt_prefix",
            "product_publication",
        }
        and output.get("product_publication") == "forbidden"
        and str(output.get("run_id") or "").strip()
        and str(output.get("attempt_prefix") or "").strip()
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_content_repair_output_invalid"
        )
    for key in ("private_output_root_ref", "public_result_ref"):
        if _resolve_repo_ref(str(output[key])).exists():
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_content_repair_output_consumed"
            )
    if not (
        authority_path.is_file()
        and str(authority.get("signed_at") or "").strip()
        and len(str(authority.get("known_boundary") or "").strip()) >= 120
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_content_repair_metadata_invalid"
        )
    return paths


def validate_live_authority(
    authority: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    expected = {
        "schema_version",
        "status",
        "signed_at",
        "implementation_commit",
        "case_key",
        "execution_budget",
        "bound_inputs",
        "output_contract",
        "known_boundary",
    }
    if not (
        set(authority) == expected
        and authority.get("schema_version") == LIVE_AUTHORITY_SCHEMA
        and authority.get("status") == LIVE_AUTHORITY_STATUS
        and authority.get("case_key") == "DELL"
        and dict(authority.get("execution_budget") or {})
        == expected_live_execution_budget()
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_authority_identity_or_budget_invalid"
        )
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_bound_inputs_invalid"
        )
    ref_names = (
        "runtime_registry",
        "loop_policy",
        "zero_call_result",
        "repair_successor_result",
        "provider_profile",
        "submission_profile",
        "runner",
        "loop_runtime",
        "provider_transport",
        "scope_decision",
    )
    paths: dict[str, Path] = {}
    for name in ref_names:
        ref = str(bound.get(f"{name}_ref") or "")
        path = _resolve_repo_ref(ref)
        if not path.is_file() or _sha256(path) != str(
            bound.get(f"{name}_sha256") or ""
        ):
            raise DynamicMultiAgentLoopError(
                f"dynamic_multi_agent_live_bound_input_drift:{name}"
            )
        paths[f"{name}_ref"] = path
    commit = str(authority.get("implementation_commit") or "").lower()
    for name in (
        "loop_policy",
        "runner",
        "loop_runtime",
        "provider_transport",
    ):
        ref = str(bound[f"{name}_ref"])
        if _git_blob_sha256(commit=commit, ref=ref) != str(
            bound[f"{name}_sha256"]
        ):
            raise DynamicMultiAgentLoopError(
                f"dynamic_multi_agent_live_implementation_binding_invalid:{name}"
            )
    zero = _read_json(paths["zero_call_result_ref"])
    repair = _read_json(paths["repair_successor_result_ref"])
    decision = _read_json(paths["scope_decision_ref"])
    if not (
        zero.get("status") == "current_dynamic_multi_agent_zero_call_proven"
        and zero.get("result_digest") == bound.get("zero_call_result_digest")
        and all((zero.get("checks") or {}).values())
        and repair.get("status")
        == "current_dynamic_multi_agent_zero_call_repair_successor_proven"
        and repair.get("result_digest")
        == bound.get("repair_successor_result_digest")
        and all((repair.get("checks") or {}).values())
        and decision.get("schema_version")
        == "fin_ia_s3_current_dynamic_multi_agent_live_scope_decision_v1_0"
        and decision.get("status")
        == "current_dynamic_multi_agent_zero_call_pass_one_natural_live_authorized"
        and decision.get("multi_agent_authorized") is True
        and decision.get("product_publication_authorized") is False
        and decision.get("S3_acceptance_authorized") is False
        and dict(decision.get("execution_budget") or {})
        == expected_live_execution_budget()
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_predecessor_or_decision_invalid"
        )
    output = authority.get("output_contract")
    if not (
        isinstance(output, Mapping)
        and set(output)
        == {
            "capture_root_ref",
            "private_output_root_ref",
            "public_result_ref",
            "run_id",
            "attempt_prefix",
            "product_publication",
        }
        and output.get("product_publication") == "forbidden"
        and str(output.get("run_id") or "").strip()
        and str(output.get("attempt_prefix") or "").strip()
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_output_contract_invalid"
        )
    for key in ("private_output_root_ref", "public_result_ref"):
        if _resolve_repo_ref(str(output[key])).exists():
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_live_output_identity_consumed"
            )
    if not (
        authority_path.resolve() == authority_path
        and authority_path.is_file()
        and str(authority.get("signed_at") or "").strip()
        and len(str(authority.get("known_boundary") or "").strip()) >= 120
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_authority_metadata_invalid"
        )
    return paths


def _call_live_tool(
    *,
    events: list[dict[str, Any]],
    session_id: str,
    actor_id: str,
    profile: Any,
    messages: Sequence[Mapping[str, Any]],
    tool: Mapping[str, Any],
    expected_name: str,
    capture_root: Path,
    run_id: str,
    attempt_id: str,
    occurred_at: str,
    executor: Callable[..., AgentToolStepResult],
) -> tuple[AgentToolStepResult, dict[str, Any], str]:
    _event(
        events,
        session_id=session_id,
        event_type="provider_attempt_requested",
        actor_id=actor_id,
        occurred_at=occurred_at,
        attempt_id=attempt_id,
        input_refs=(
            f"messages://{canonical_digest(list(messages))}",
            f"tool://{canonical_digest(tool)}",
        ),
    )
    try:
        step = executor(
            profile=profile,
            messages=messages,
            tools=[tool],
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=attempt_id,
            tool_choice=None,
        )
    except ModelGatewayError as exc:
        _event(
            events,
            session_id=session_id,
            event_type="provider_attempt_failed",
            actor_id="PROVIDER::" + str(profile.provider_id).upper(),
            occurred_at=occurred_at,
            attempt_id=attempt_id,
            output_refs=((str(exc.capture_ref),) if exc.capture_ref else ()),
        )
        raise
    _event(
        events,
        session_id=session_id,
        event_type="provider_attempt_completed",
        actor_id="PROVIDER::" + str(profile.provider_id).upper(),
        occurred_at=occurred_at,
        attempt_id=attempt_id,
        output_refs=tuple(
            str(value)
            for value in (step.request_capture_ref, step.response_capture_ref)
            if str(value or "")
        ),
    )
    payload, call_id = _tool_arguments(step, expected_name=expected_name)
    return step, payload, call_id


def _call_live_tool_draft(
    *,
    events: list[dict[str, Any]],
    session_id: str,
    actor_id: str,
    profile: Any,
    messages: Sequence[Mapping[str, Any]],
    tool: Mapping[str, Any],
    expected_name: str,
    capture_root: Path,
    run_id: str,
    attempt_id: str,
    occurred_at: str,
    executor: Callable[..., AgentToolStepResult],
) -> tuple[AgentToolStepResult, str, str]:
    """Execute a natural analysis/writing node and preserve its tool draft."""

    _event(
        events,
        session_id=session_id,
        event_type="provider_attempt_requested",
        actor_id=actor_id,
        occurred_at=occurred_at,
        attempt_id=attempt_id,
        input_refs=(
            f"messages://{canonical_digest(list(messages))}",
            f"tool://{canonical_digest(tool)}",
        ),
    )
    try:
        step = executor(
            profile=profile,
            messages=messages,
            tools=[tool],
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=attempt_id,
            tool_choice=None,
        )
    except ModelGatewayError as exc:
        _event(
            events,
            session_id=session_id,
            event_type="provider_attempt_failed",
            actor_id="PROVIDER::" + str(profile.provider_id).upper(),
            occurred_at=occurred_at,
            attempt_id=attempt_id,
            output_refs=((str(exc.capture_ref),) if exc.capture_ref else ()),
        )
        raise
    _event(
        events,
        session_id=session_id,
        event_type="provider_attempt_completed",
        actor_id="PROVIDER::" + str(profile.provider_id).upper(),
        occurred_at=occurred_at,
        attempt_id=attempt_id,
        output_refs=tuple(
            str(value)
            for value in (step.request_capture_ref, step.response_capture_ref)
            if str(value or "")
        ),
    )
    draft, call_id = _tool_draft(step, expected_name=expected_name)
    return step, draft, call_id


def _provider_attempt_count(events: Sequence[Mapping[str, Any]]) -> int:
    return sum(
        1
        for event in events
        if str(event.get("event_type") or "") == "provider_attempt_requested"
    )


def _execute_live_round(
    *,
    role_program: Mapping[str, Any],
    request_ids: Sequence[str],
    round_index: int,
    retrieval: ResearchRetrievalService,
    retrieval_principal: ResearchRetrievalPrincipal,
    evidence_pack: Mapping[str, Any],
    truth_policy: Mapping[str, Any],
    consumer_policy: Mapping[str, Any],
    task_quantitative: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    requests = _request_rows(role_program, request_ids)
    all_blueprints = compile_role_material_requirement_blueprints(role_program)
    batch = retrieval.execute_current_runtime_requests(
        "DELL",
        requests,
        retrieval_principal,
        material_requirement_blueprints={
            request_id: all_blueprints[request_id] for request_id in request_ids
        },
    )
    controlled = compile_controlled_batch_projection(
        policy=role_program["loop_policy"],
        selected_requests=requests,
        batch_result=batch,
    )
    response = compile_round_response(
        policy=role_program["loop_policy"],
        controlled_plan=controlled,
        evidence_pack=evidence_pack,
        truth_spine_policy=truth_policy,
        consumer_policy=consumer_policy,
        task_quantitative_result=task_quantitative,
        round_index=round_index,
    )
    return batch, response


def _rebuild_predecessor_rounds(
    *,
    role_program: Mapping[str, Any],
    predecessor_bundle: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    truth_policy: Mapping[str, Any],
    consumer_policy: Mapping[str, Any],
    task_quantitative: Mapping[str, Any],
    recorded_at: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rehydrate hidden current-runtime inputs from immutable S1/S2 batches."""

    selections = list(predecessor_bundle.get("selections") or ())
    batches = [deepcopy(dict(row)) for row in predecessor_bundle.get("round_batches") or ()]
    public_responses = list(predecessor_bundle.get("round_responses") or ())
    if not (len(selections) == len(batches) == len(public_responses) and batches):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_successor_predecessor_round_shape_invalid"
        )
    rebuilt: list[dict[str, Any]] = []
    feedback: list[dict[str, Any]] = []
    for index, (selection, batch, persisted) in enumerate(
        zip(selections, batches, public_responses), start=1
    ):
        request_ids = [str(value) for value in selection.get("request_ids") or ()]
        requests = _request_rows(role_program, request_ids)
        controlled = compile_controlled_batch_projection(
            policy=role_program["loop_policy"],
            selected_requests=requests,
            batch_result=batch,
        )
        response = compile_round_response(
            policy=role_program["loop_policy"],
            controlled_plan=controlled,
            evidence_pack=evidence_pack,
            truth_spine_policy=truth_policy,
            consumer_policy=consumer_policy,
            task_quantitative_result=task_quantitative,
            round_index=index,
        )
        if (
            response.get("round_response_digest")
            != persisted.get("round_response_digest")
            or public_round_response(response) != persisted
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_successor_round_replay_drift"
            )
        rebuilt.append(response)
        feedback.extend(
            compile_round_feedback_receipts(
                session_id=str(predecessor_bundle["session"]["session_id"]),
                round_response=response,
                request_catalog=role_program["request_catalog"],
                created_at=recorded_at,
            )
        )
    persisted_feedback = list(predecessor_bundle.get("feedback_receipts") or ())
    if [row.get("feedback_id") for row in feedback] != [
        row.get("feedback_id") for row in persisted_feedback
    ]:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_successor_feedback_replay_drift"
        )
    return rebuilt, feedback


def _completed_capture_for_attempt(
    bundle: Mapping[str, Any], *, attempt_fragment: str
) -> Path:
    matches: list[Path] = []
    for event in bundle.get("events") or ():
        if not (
            event.get("event_type") == "provider_attempt_completed"
            and attempt_fragment in str(event.get("attempt_id") or "")
        ):
            continue
        for ref in event.get("output_refs") or ():
            if str(ref).endswith("provider_response.json"):
                matches.append(Path(str(ref)))
    if len(matches) != 1 or not matches[0].is_file():
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_successor_capture_binding_invalid"
        )
    return matches[0].resolve()


def _role_base_state(
    *, role_program: Mapping[str, Any]
) -> tuple[dict[str, Any], str]:
    policy = role_program["loop_policy"]
    agent_id = str(role_program["agent_id"])
    body = {
        "case_key": "DELL",
        "objective_id": policy["objective"]["objective_id"],
        "agent_id": agent_id,
        "executed_request_ids": [],
        "next_request_ids": [],
        "latest_reflection_digest": None,
        "latest_feedback_refs": [],
    }
    plan = {**body, "plan_digest": canonical_digest(body)}
    graph_digest = canonical_digest(
        {
            "case_key": "DELL",
            "agent_id": agent_id,
            "state": "current_reviewed_graph_plus_role_local_hypotheses",
        }
    )
    return plan, graph_digest


def _bind_predecessor_session_event(
    events: list[dict[str, Any]],
    *,
    session_id: str,
    predecessor_session_id: str,
    role_program_digest: str,
    round_response_digests: Sequence[str],
    active_plan_ref: str,
    recorded_at: str,
) -> None:
    """Bind a successor predecessor using the canonical ``plan_bound`` event."""

    _event(
        events,
        session_id=session_id,
        event_type="plan_bound",
        actor_id="S3.DynamicMultiAgentHarness",
        occurred_at=recorded_at,
        input_refs=(
            predecessor_session_id,
            role_program_digest,
            *[str(value) for value in round_response_digests],
        ),
        output_refs=(active_plan_ref,),
    )


def _open_gap_refs(
    round_responses: Sequence[Mapping[str, Any]],
) -> list[str]:
    return sorted(
        {
            str(row["gap_ref"])
            for response in round_responses
            for row in response.get("residual_gaps") or ()
        }
    )


def _accepted_evidence_refs(
    round_responses: Sequence[Mapping[str, Any]],
) -> list[str]:
    return sorted(
        {
            str(row["evidence_ref"])
            for response in round_responses
            for row in response.get("reviewed_evidence") or ()
        }
    )


def _execute_live_role(
    *,
    role_program: Mapping[str, Any],
    run_id: str,
    attempt_prefix: str,
    recorded_at: str,
    capture_root: Path,
    research_profile: Any,
    submission_profile: Any,
    retrieval: ResearchRetrievalService,
    retrieval_principal: ResearchRetrievalPrincipal,
    evidence_pack: Mapping[str, Any],
    truth_policy: Mapping[str, Any],
    consumer_policy: Mapping[str, Any],
    task_quantitative: Mapping[str, Any],
    research_executor: Callable[..., AgentToolStepResult],
    submission_executor: Callable[..., AgentToolStepResult],
) -> dict[str, Any]:
    agent_id = str(role_program["agent_id"])
    slug = agent_id.split("::")[-1].lower().replace("_", "-")
    policy = deepcopy(dict(role_program["loop_policy"]))
    catalog = deepcopy(dict(role_program["request_catalog"]))
    messages: list[dict[str, Any]] = list(
        compile_initial_messages(policy=policy, request_catalog=catalog)
    )
    initial_messages_digest = canonical_digest(messages)
    seed = {
        "run_id": run_id,
        "agent_id": agent_id,
        "role_program_digest": role_program["role_program_digest"],
        "pack_payload_digest": evidence_pack["pack_payload_digest"],
    }
    session_id = "SESSION::" + canonical_digest(seed)[:24].upper()
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
        run_id=run_id,
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
    provider_steps: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []
    round_responses: list[dict[str, Any]] = []
    feedback_receipts: list[dict[str, Any]] = []
    reflections: list[dict[str, Any]] = []
    reflection_artifacts: list[dict[str, Any]] = []
    executed_ids: list[str] = []
    accepted_evidence_refs: set[str] = set()
    workpaper_context: dict[str, Any] = {}
    submission_view: dict[str, Any] = {}
    workpaper: dict[str, Any] = {}
    failure = {"phase": "", "code": "", "capture_ref": ""}
    checkpoint: dict[str, Any] = {}
    resume: dict[str, Any] = {}
    provider_calls = 0
    current_attempt_id = ""
    pending_plan_delta: dict[str, Any] | None = None
    try:
        request_tool = request_evidence_tool(
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=executed_ids,
            round_index=1,
        )
        current_attempt_id = f"{attempt_prefix}-{slug}-request-r1"
        request_step, request_payload, request_call_id = _call_live_tool(
            events=events,
            session_id=session_id,
            actor_id=agent_id,
            profile=research_profile,
            messages=messages,
            tool=request_tool,
            expected_name=REQUEST_TOOL_NAME,
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=current_attempt_id,
            occurred_at=recorded_at,
            executor=research_executor,
        )
        provider_calls += 1
        provider_steps.append(request_step.as_dict())
        selection = validate_request_selection(
            request_payload,
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=executed_ids,
            round_index=1,
        )
        selections.append(selection)

        maximum_rounds = int(policy["loop_limits"]["maximum_retrieval_rounds"])
        round_index = 1
        while True:
            tool_attempt_id = f"{attempt_prefix}-{slug}-s1s2-r{round_index}"
            _event(
                events,
                session_id=session_id,
                event_type="tool_execution_requested",
                actor_id=agent_id,
                occurred_at=recorded_at,
                attempt_id=tool_attempt_id,
                input_refs=(selection["selection_digest"],),
            )
            batch, response = _execute_live_round(
                role_program=role_program,
                request_ids=selection["request_ids"],
                round_index=round_index,
                retrieval=retrieval,
                retrieval_principal=retrieval_principal,
                evidence_pack=evidence_pack,
                truth_policy=truth_policy,
                consumer_policy=consumer_policy,
                task_quantitative=task_quantitative,
            )
            batches.append(batch)
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
            executed_ids.extend(selection["request_ids"])
            accepted_evidence_refs.update(
                str(row["evidence_ref"])
                for row in response.get("reviewed_evidence") or ()
            )
            feedback = compile_round_feedback_receipts(
                session_id=session_id,
                round_response=response,
                request_catalog=catalog,
                created_at=recorded_at,
            )
            feedback_receipts.extend(feedback)
            feedback_refs = [str(row["feedback_id"]) for row in feedback]
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
            tool_result_payload: dict[str, Any] = {
                "round_response": public_round_response(response),
                "feedback_receipts": feedback,
            }
            if pending_plan_delta is not None:
                tool_result_payload["accepted_plan_delta"] = pending_plan_delta
            messages.extend(
                [
                    request_step.continuation_assistant_message(),
                    {
                        "role": "tool",
                        "tool_call_id": request_call_id,
                        "content": json.dumps(
                            tool_result_payload,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    },
                ]
            )
            reflect_tool = reflection_tool(
                policy=policy,
                request_catalog=catalog,
                feedback_receipts=feedback,
                accepted_evidence_refs=sorted(accepted_evidence_refs),
                executed_request_ids=executed_ids,
                round_index=round_index,
            )
            current_attempt_id = f"{attempt_prefix}-{slug}-reflection-r{round_index}"
            reflection_step, reflection_payload, reflection_call_id = (
                _call_live_tool(
                    events=events,
                    session_id=session_id,
                    actor_id=agent_id,
                    profile=research_profile,
                    messages=messages,
                    tool=reflect_tool,
                    expected_name=REFLECTION_TOOL_NAME,
                    capture_root=capture_root,
                    run_id=run_id,
                    attempt_id=current_attempt_id,
                    occurred_at=recorded_at,
                    executor=research_executor,
                )
            )
            provider_calls += 1
            provider_steps.append(reflection_step.as_dict())
            reflection = validate_reflection_payload(
                reflection_payload,
                policy=policy,
                request_catalog=catalog,
                feedback_receipts=feedback,
                accepted_evidence_refs=sorted(accepted_evidence_refs),
                executed_request_ids=executed_ids,
                round_index=round_index,
            )
            reflections.append(reflection)
            open_gap_refs = sorted(
                {
                    str(row["gap_ref"])
                    for current in round_responses
                    for row in current.get("residual_gaps") or ()
                }
            )
            artifacts = compile_reflection_artifacts(
                policy=policy,
                reflection=reflection,
                session_id=session_id,
                agent_id=agent_id,
                base_plan=base_plan,
                base_graph_digest=base_graph_digest,
                executed_request_ids=executed_ids,
                open_gap_refs=open_gap_refs,
                model_calls_used=provider_calls,
            )
            reflection_artifacts.append(artifacts)
            session = apply_accepted_plan_delta(
                session=session,
                plan_delta=artifacts["plan_delta"],
                expected_base_plan_digest=base_plan["plan_digest"],
                accepted_plan_digest=artifacts["accepted_plan"]["plan_digest"],
                accepted_plan_ref=artifacts["accepted_plan_ref"],
                updated_at=recorded_at,
            )
            base_plan = artifacts["accepted_plan"]
            base_graph_digest = artifacts["graph_delta"]["graph_delta_digest"]
            _event(
                events,
                session_id=session_id,
                event_type="plan_delta_accepted",
                actor_id="S3.DynamicMultiAgentHarness",
                occurred_at=recorded_at,
                attempt_id=current_attempt_id,
                output_refs=(artifacts["accepted_plan_ref"],),
                feedback_refs=reflection["feedback_refs"],
            )
            decision = str(reflection["proposed_stop_decision"])
            if decision != "continue":
                break
            if round_index >= maximum_rounds:
                raise DynamicMultiAgentLoopError(
                    "dynamic_multi_agent_live_round_budget_exhausted_without_stop"
                )
            next_ids = list(reflection["next_request_ids"])
            round_index += 1
            selection = validate_request_selection(
                {
                    "schema_version": REQUEST_PAYLOAD_SCHEMA_VERSION,
                    "round_id": f"ROUND::{round_index}",
                    "request_ids": next_ids,
                    "research_rationale": reflection["reflection_summary"],
                    "expected_information_gain": (
                        "执行模型在上一轮 FeedbackReceipt 后选择的下一组命题。"
                    ),
                },
                policy=policy,
                request_catalog=catalog,
                executed_request_ids=executed_ids,
                round_index=round_index,
            )
            selections.append(selection)
            request_step = reflection_step
            request_call_id = reflection_call_id
            pending_plan_delta = deepcopy(dict(artifacts["plan_delta"]))

        if not (
            reflection_artifacts
            and reflection_artifacts[-1]["stop_decision"]["decision"]
            in {"stop_sufficient", "stop_no_progress"}
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_live_terminal_stop_missing"
            )
        workpaper_context = compile_workpaper_context(
            policy=policy,
            round_responses=round_responses,
            feedback_receipts=feedback_receipts,
            reflections=reflections,
            stop_decision=reflection_artifacts[-1]["stop_decision"],
        )
        submission_view = compile_workpaper_submission_view(workpaper_context)
        workpaper_tool = specialist_workpaper_tool(
            agent_id=agent_id, context=workpaper_context
        )
        current_attempt_id = f"{attempt_prefix}-{slug}-workpaper"
        workpaper_step, workpaper_payload, _ = _call_live_tool(
            events=events,
            session_id=session_id,
            actor_id=agent_id,
            profile=submission_profile,
            messages=compile_specialist_workpaper_messages(
                context=submission_view
            ),
            tool=workpaper_tool,
            expected_name="submit_specialist_workpaper",
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=current_attempt_id,
            occurred_at=recorded_at,
            executor=submission_executor,
        )
        provider_calls += 1
        provider_steps.append(workpaper_step.as_dict())
        workpaper = validate_specialist_workpaper(
            workpaper_payload,
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
        gap_refs = sorted(
            {
                str(row["gap_ref"])
                for current in round_responses
                for row in current.get("residual_gaps") or ()
            }
        )
        checkpoint_id = "CHECKPOINT::" + canonical_digest(
            {
                "session_id": session_id,
                "plan_digest": base_plan["plan_digest"],
                "workpaper_digest": workpaper["workpaper_digest"],
            }
        )[:24].upper()
        checkpoint = create_context_checkpoint(
            session=session,
            events=events,
            checkpoint_id=checkpoint_id,
            objective_digest=canonical_digest(policy["objective"]),
            plan_digest=base_plan["plan_digest"],
            research_graph_digest=base_graph_digest,
            accepted_evidence_refs=sorted(accepted_evidence_refs),
            numeric_fact_refs=numeric_refs,
            open_gap_refs=gap_refs,
            unresolved_feedback_refs=sorted(
                str(row["feedback_id"]) for row in feedback_receipts
            ),
            agent_local_state_refs=[
                str(row["reflection_digest"]) for row in reflections
            ],
            authority_refs=[
                str(evidence_pack["pack_payload_digest"]),
                str(role_program["role_program_digest"]),
                str(workpaper["workpaper_digest"]),
            ],
            counterevidence_refs=(
                sorted(accepted_evidence_refs)
                if agent_id == "AGENT::COUNTEREVIDENCE"
                else []
            ),
            open_question_refs=[
                f"QUESTION::DELL::{slug.upper()}::{index}"
                for index, _ in enumerate(gap_refs, start=1)
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
            required_open_gap_refs=gap_refs,
            required_unresolved_feedback_refs=checkpoint[
                "unresolved_feedback_refs"
            ],
            required_counterevidence_refs=checkpoint[
                "counterevidence_refs"
            ],
            required_open_question_refs=checkpoint["open_question_refs"],
        )
    except ModelGatewayError as exc:
        failure = {
            "phase": "provider_transport_or_response",
            "code": exc.code,
            "capture_ref": (
                _relative(Path(exc.capture_ref)) if exc.capture_ref else ""
            ),
        }
    except ResearchRetrievalServiceError as exc:
        failure = {
            "phase": "current_S1_S2_retrieval",
            "code": exc.error_code,
            "capture_ref": "",
        }
    except ResearchEvidencePackServiceError as exc:
        failure = {
            "phase": "current_reviewed_evidence_pack",
            "code": exc.error_code,
            "capture_ref": "",
        }
    except DynamicSingleUnitLoopError as exc:
        failure = {
            "phase": "dynamic_research_loop_contract",
            "code": exc.code,
            "capture_ref": "",
        }
    except DynamicMultiAgentLoopError as exc:
        failure = {
            "phase": "dynamic_multi_agent_orchestration",
            "code": exc.code,
            "capture_ref": "",
        }
    except ValueError as exc:
        failure = {
            "phase": "specialist_workpaper_or_runtime_contract",
            "code": str(exc),
            "capture_ref": "",
        }
    return {
        "agent_id": agent_id,
        "status": (
            "completed_contract_valid" if workpaper else "terminal_failed_no_retry"
        ),
        "role_program_digest": role_program["role_program_digest"],
        "session": session,
        "events": events,
        "initial_messages_digest": initial_messages_digest,
        "provider_steps": [_public_provider_step(row) for row in provider_steps],
        "selections": selections,
        "round_batches": batches,
        "round_responses": [public_round_response(row) for row in round_responses],
        "feedback_receipts": feedback_receipts,
        "reflections": reflections,
        "reflection_artifacts": reflection_artifacts,
        "workpaper_context": workpaper_context,
        "submission_view": submission_view,
        "workpaper": workpaper,
        "checkpoint": checkpoint,
        "resume_receipt": resume,
        "execution": {
            "provider_calls_attempted": _provider_attempt_count(events),
            "maximum_provider_calls": int(
                role_program["loop_policy"]["loop_limits"][
                    "maximum_provider_steps"
                ]
            ),
            "retrieval_rounds_executed": len(round_responses),
            "request_ids_executed": executed_ids,
            "unique_request_ids_executed": len(set(executed_ids)),
            "candidate_promotions": 0,
            "external_source_network_calls": 0,
            "retries": 0,
        },
        "failure": failure,
    }


def _compile_successor_reflection_draft_messages(
    *,
    role_program: Mapping[str, Any],
    round_responses: Sequence[Mapping[str, Any]],
    feedback_receipts: Sequence[Mapping[str, Any]],
    prior_reflections: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, str], ...]:
    visible = {
        "agent_id": role_program["agent_id"],
        "objective": deepcopy(role_program["loop_policy"]["objective"]),
        "role_contract": deepcopy(
            role_program["loop_policy"].get("role_contract") or {}
        ),
        "current_round_responses": [
            public_round_response(row) for row in round_responses
        ],
        "feedback_receipts": [deepcopy(dict(row)) for row in feedback_receipts],
        "prior_reflections": [deepcopy(dict(row)) for row in prior_reflections],
        "remaining_request_catalog": deepcopy(role_program["request_catalog"]),
        "rules": [
            "Reflect on the newly executed request; do not repeat the prior draft.",
            "Use only reviewed Evidence, NumericFact, typed relations and visible gaps.",
            "Candidate text and graph hypotheses are not business truth.",
            "State what is now supported, what remains unresolved and why further search can or cannot add information.",
            "Submit one reflection tool draft; a separate node will map it to the strict contract.",
        ],
    }
    return (
        {
            "role": "system",
            "content": (
                "You are the named independent financial research specialist. "
                "Continue the same session after a real S1/S2 tool result and "
                "produce a substantive reflection and next-step judgment."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def _execute_submission_successor_role(
    *,
    role_program: Mapping[str, Any],
    predecessor_bundle: Mapping[str, Any],
    predecessor_recorded_at: str,
    run_id: str,
    attempt_prefix: str,
    recorded_at: str,
    capture_root: Path,
    research_profile: Any,
    submission_profile: Any,
    retrieval: ResearchRetrievalService,
    retrieval_principal: ResearchRetrievalPrincipal,
    evidence_pack: Mapping[str, Any],
    truth_policy: Mapping[str, Any],
    consumer_policy: Mapping[str, Any],
    task_quantitative: Mapping[str, Any],
    research_executor: Callable[..., AgentToolStepResult],
    submission_executor: Callable[..., AgentToolStepResult],
    resume_capture_manifest: Sequence[Mapping[str, Any]] = (),
    session_seed_run_id: str | None = None,
) -> dict[str, Any]:
    """Resume one R1 specialist from immutable captures and exact S1/S2 state."""

    agent_id = str(role_program["agent_id"])
    slug = agent_id.split("::")[-1].lower().replace("_", "-")
    policy = role_program["loop_policy"]
    catalog = role_program["request_catalog"]
    round_responses, feedback_receipts = _rebuild_predecessor_rounds(
        role_program=role_program,
        predecessor_bundle=predecessor_bundle,
        evidence_pack=evidence_pack,
        truth_policy=truth_policy,
        consumer_policy=consumer_policy,
        task_quantitative=task_quantitative,
        recorded_at=predecessor_recorded_at,
    )
    batches = [
        deepcopy(dict(row)) for row in predecessor_bundle["round_batches"]
    ]
    selections = [
        deepcopy(dict(row)) for row in predecessor_bundle["selections"]
    ]
    executed_ids = [
        str(value)
        for value in predecessor_bundle["execution"]["request_ids_executed"]
    ]
    accepted_refs = _accepted_evidence_refs(round_responses)
    gaps = _open_gap_refs(round_responses)
    base_plan, base_graph = _role_base_state(role_program=role_program)
    effective_session_run_id = session_seed_run_id or run_id
    session_seed = {
        "run_id": effective_session_run_id,
        "agent_id": agent_id,
        "predecessor_session_id": predecessor_bundle["session"]["session_id"],
        "role_program_digest": role_program["role_program_digest"],
    }
    session_id = "SESSION::" + canonical_digest(session_seed)[:24].upper()
    session = create_agent_session(
        session_id=session_id,
        run_id=effective_session_run_id,
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
    _bind_predecessor_session_event(
        events,
        session_id=session_id,
        predecessor_session_id=str(
            predecessor_bundle["session"]["session_id"]
        ),
        role_program_digest=str(predecessor_bundle["role_program_digest"]),
        round_response_digests=[
            str(row["round_response_digest"]) for row in round_responses
        ],
        active_plan_ref=str(session["active_plan_ref"]),
        recorded_at=recorded_at,
    )
    provider_steps: list[dict[str, Any]] = []
    source_capture_receipts: list[dict[str, Any]] = []
    submission_receipts: list[dict[str, Any]] = []
    reflections: list[dict[str, Any]] = []
    reflection_artifacts: list[dict[str, Any]] = []

    reflection_capture = _completed_capture_for_attempt(
        predecessor_bundle, attempt_fragment=f"{slug}-reflection-r1"
    )
    reflection_draft, _, capture_receipt = _capture_tool_draft(
        reflection_capture, expected_name=REFLECTION_TOOL_NAME
    )
    source_capture_receipts.append(capture_receipt)
    parsed: dict[str, Any] | None = None
    try:
        raw = json.loads(reflection_draft)
        if isinstance(raw, dict):
            parsed = validate_reflection_payload(
                raw,
                policy=policy,
                request_catalog=catalog,
                feedback_receipts=feedback_receipts,
                accepted_evidence_refs=accepted_refs,
                executed_request_ids=executed_ids,
                round_index=1,
            )
    except (json.JSONDecodeError, DynamicSingleUnitLoopError):
        parsed = None
    if parsed is None:
        submission_tool = reflection_submission_tool(
            policy=policy,
            request_catalog=catalog,
            feedback_receipts=feedback_receipts,
            accepted_evidence_refs=accepted_refs,
            executed_request_ids=executed_ids,
            open_gap_refs=gaps,
            round_index=1,
        )
        resumed = _resume_capture_draft(
            resume_capture_manifest,
            attempt_fragment=f"{slug}-reflection-r1-submit",
            expected_name=REFLECTION_SUBMISSION_TOOL_NAME,
        )
        if resumed is not None:
            resumed_payload, _, resumed_receipt = resumed
            payload = json.loads(resumed_payload)
            if not isinstance(payload, dict):
                raise DynamicMultiAgentLoopError(
                    "dynamic_multi_agent_submission_resume_reflection_invalid"
                )
            source_capture_receipts.append(resumed_receipt)
        else:
            step, payload, _ = _call_live_tool(
                events=events,
                session_id=session_id,
                actor_id="HARNESS::STRICT-SUBMISSION-MAPPER",
                profile=submission_profile,
                messages=compile_reflection_submission_messages(
                    source_draft=reflection_draft,
                    source_capture_digest=capture_receipt["response_digest"],
                    tool=submission_tool,
                ),
                tool=submission_tool,
                expected_name=REFLECTION_SUBMISSION_TOOL_NAME,
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=f"{attempt_prefix}-{slug}-reflection-r1-submit",
                occurred_at=recorded_at,
                executor=submission_executor,
            )
            provider_steps.append(_public_provider_step(step.as_dict()))
        parsed, receipt = validate_reflection_submission(
            payload,
            policy=policy,
            request_catalog=catalog,
            feedback_receipts=feedback_receipts,
            accepted_evidence_refs=accepted_refs,
            executed_request_ids=executed_ids,
            open_gap_refs=gaps,
            round_index=1,
        )
        submission_receipts.append(receipt)
    else:
        receipt_body = {
            "schema_version": "fin_ia_reflection_capture_migration_receipt_v1_0",
            "agent_id": agent_id,
            "source_capture_digest": capture_receipt["response_digest"],
            "local_control_recompilation_only": True,
            "model_research_judgment_changed": False,
        }
        submission_receipts.append(
            {**receipt_body, "receipt_digest": canonical_digest(receipt_body)}
        )
    reflections.append(parsed)
    artifacts = compile_reflection_artifacts(
        policy=policy,
        reflection=parsed,
        session_id=session_id,
        agent_id=agent_id,
        base_plan=base_plan,
        base_graph_digest=base_graph,
        executed_request_ids=executed_ids,
        open_gap_refs=gaps,
        model_calls_used=_provider_attempt_count(events),
    )
    reflection_artifacts.append(artifacts)
    session = apply_accepted_plan_delta(
        session=session,
        plan_delta=artifacts["plan_delta"],
        expected_base_plan_digest=base_plan["plan_digest"],
        accepted_plan_digest=artifacts["accepted_plan"]["plan_digest"],
        accepted_plan_ref=artifacts["accepted_plan_ref"],
        updated_at=recorded_at,
    )
    base_plan = artifacts["accepted_plan"]
    base_graph = artifacts["graph_delta"]["graph_delta_digest"]
    _event(
        events,
        session_id=session_id,
        event_type="plan_delta_accepted",
        actor_id="S3.DynamicMultiAgentHarness",
        occurred_at=recorded_at,
        output_refs=(artifacts["accepted_plan_ref"],),
        feedback_refs=parsed["feedback_refs"],
    )

    if artifacts["stop_decision"]["decision"] == "continue":
        next_ids = [str(value) for value in parsed["next_request_ids"]]
        if agent_id != "AGENT::SUPPLY_RELATIONSHIP" or len(next_ids) != 1:
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_successor_scope_expansion"
            )
        selection = validate_request_selection(
            {
                "schema_version": REQUEST_PAYLOAD_SCHEMA_VERSION,
                "round_id": "ROUND::2",
                "request_ids": next_ids,
                "research_rationale": parsed["reflection_summary"],
                "expected_information_gain": (
                    "补齐未覆盖的 Dell 主体供应关系披露后再作停止判断。"
                ),
            },
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=executed_ids,
            round_index=2,
        )
        selections.append(selection)
        tool_attempt_id = f"{attempt_prefix}-{slug}-s1s2-r2"
        _event(
            events,
            session_id=session_id,
            event_type="tool_execution_requested",
            actor_id=agent_id,
            occurred_at=recorded_at,
            attempt_id=tool_attempt_id,
            input_refs=(selection["selection_digest"],),
        )
        batch, response = _execute_live_round(
            role_program=role_program,
            request_ids=next_ids,
            round_index=2,
            retrieval=retrieval,
            retrieval_principal=retrieval_principal,
            evidence_pack=evidence_pack,
            truth_policy=truth_policy,
            consumer_policy=consumer_policy,
            task_quantitative=task_quantitative,
        )
        batches.append(batch)
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
        executed_ids.extend(next_ids)
        new_feedback = compile_round_feedback_receipts(
            session_id=session_id,
            round_response=response,
            request_catalog=catalog,
            created_at=recorded_at,
        )
        feedback_receipts.extend(new_feedback)
        if new_feedback:
            _event(
                events,
                session_id=session_id,
                event_type="feedback_issued",
                actor_id="S1S2.DynamicEvidenceTool",
                occurred_at=recorded_at,
                input_refs=(response["round_response_digest"],),
                output_refs=tuple(
                    str(row["feedback_id"]) for row in new_feedback
                ),
                feedback_refs=tuple(
                    str(row["feedback_id"]) for row in new_feedback
                ),
            )
        accepted_refs = _accepted_evidence_refs(round_responses)
        gaps = _open_gap_refs(round_responses)
        draft_tool = reflection_tool(
            policy=policy,
            request_catalog=catalog,
            feedback_receipts=new_feedback,
            accepted_evidence_refs=accepted_refs,
            executed_request_ids=executed_ids,
            round_index=2,
        )
        resumed_draft = _resume_capture_draft(
            resume_capture_manifest,
            attempt_fragment=f"{slug}-reflection-r2-draft",
            expected_name=REFLECTION_TOOL_NAME,
        )
        if resumed_draft is not None:
            followup_draft, _, draft_receipt = resumed_draft
            source_capture_receipts.append(draft_receipt)
            draft_response_digest = str(draft_receipt["response_digest"])
        else:
            draft_step, followup_draft, _ = _call_live_tool_draft(
                events=events,
                session_id=session_id,
                actor_id=agent_id,
                profile=research_profile,
                messages=_compile_successor_reflection_draft_messages(
                    role_program=role_program,
                    round_responses=[response],
                    feedback_receipts=new_feedback,
                    prior_reflections=reflections,
                ),
                tool=draft_tool,
                expected_name=REFLECTION_TOOL_NAME,
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=f"{attempt_prefix}-{slug}-reflection-r2-draft",
                occurred_at=recorded_at,
                executor=research_executor,
            )
            provider_steps.append(_public_provider_step(draft_step.as_dict()))
            draft_response_digest = str(draft_step.response_digest)
        submission_tool = reflection_submission_tool(
            policy=policy,
            request_catalog=catalog,
            feedback_receipts=new_feedback,
            accepted_evidence_refs=accepted_refs,
            executed_request_ids=executed_ids,
            open_gap_refs=gaps,
            round_index=2,
        )
        resumed_submission = _resume_capture_draft(
            resume_capture_manifest,
            attempt_fragment=f"{slug}-reflection-r2-submit",
            expected_name=REFLECTION_SUBMISSION_TOOL_NAME,
        )
        if resumed_submission is not None:
            resumed_payload, _, submit_receipt = resumed_submission
            payload = json.loads(resumed_payload)
            if not isinstance(payload, dict):
                raise DynamicMultiAgentLoopError(
                    "dynamic_multi_agent_submission_resume_reflection_invalid"
                )
            source_capture_receipts.append(submit_receipt)
        else:
            step, payload, _ = _call_live_tool(
                events=events,
                session_id=session_id,
                actor_id="HARNESS::STRICT-SUBMISSION-MAPPER",
                profile=submission_profile,
                messages=compile_reflection_submission_messages(
                    source_draft=followup_draft,
                    source_capture_digest=draft_response_digest,
                    tool=submission_tool,
                ),
                tool=submission_tool,
                expected_name=REFLECTION_SUBMISSION_TOOL_NAME,
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=f"{attempt_prefix}-{slug}-reflection-r2-submit",
                occurred_at=recorded_at,
                executor=submission_executor,
            )
            provider_steps.append(_public_provider_step(step.as_dict()))
        followup, receipt = validate_reflection_submission(
            payload,
            policy=policy,
            request_catalog=catalog,
            feedback_receipts=new_feedback,
            accepted_evidence_refs=accepted_refs,
            executed_request_ids=executed_ids,
            open_gap_refs=gaps,
            round_index=2,
        )
        submission_receipts.append(receipt)
        reflections.append(followup)
        artifacts = compile_reflection_artifacts(
            policy=policy,
            reflection=followup,
            session_id=session_id,
            agent_id=agent_id,
            base_plan=base_plan,
            base_graph_digest=base_graph,
            executed_request_ids=executed_ids,
            open_gap_refs=gaps,
            model_calls_used=_provider_attempt_count(events),
        )
        reflection_artifacts.append(artifacts)
        session = apply_accepted_plan_delta(
            session=session,
            plan_delta=artifacts["plan_delta"],
            expected_base_plan_digest=base_plan["plan_digest"],
            accepted_plan_digest=artifacts["accepted_plan"]["plan_digest"],
            accepted_plan_ref=artifacts["accepted_plan_ref"],
            updated_at=recorded_at,
        )
        base_plan = artifacts["accepted_plan"]
        base_graph = artifacts["graph_delta"]["graph_delta_digest"]
        _event(
            events,
            session_id=session_id,
            event_type="plan_delta_accepted",
            actor_id="S3.DynamicMultiAgentHarness",
            occurred_at=recorded_at,
            output_refs=(artifacts["accepted_plan_ref"],),
            feedback_refs=followup["feedback_refs"],
        )

    if artifacts["stop_decision"]["decision"] not in {
        "stop_sufficient",
        "stop_no_progress",
    }:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_terminal_stop_missing"
        )
    workpaper_context = compile_workpaper_context(
        policy=policy,
        round_responses=round_responses,
        feedback_receipts=feedback_receipts,
        reflections=reflections,
        stop_decision=artifacts["stop_decision"],
    )
    submission_view = compile_workpaper_submission_view(workpaper_context)
    workpaper_source = "new_natural_draft"
    if agent_id in {"AGENT::DEMAND_QUALITY", "AGENT::COUNTEREVIDENCE"}:
        workpaper_capture = _completed_capture_for_attempt(
            predecessor_bundle, attempt_fragment=f"{slug}-workpaper"
        )
        workpaper_draft, _, workpaper_capture_receipt = _capture_tool_draft(
            workpaper_capture, expected_name="submit_specialist_workpaper"
        )
        source_capture_receipts.append(workpaper_capture_receipt)
        workpaper_draft_digest = workpaper_capture_receipt["response_digest"]
        workpaper_source = "R1_capture_draft"
    else:
        resumed = _resume_capture_draft(
            resume_capture_manifest,
            attempt_fragment=f"{slug}-workpaper-draft",
            expected_name="submit_specialist_workpaper",
        )
        if resumed is not None:
            workpaper_draft, _, workpaper_capture_receipt = resumed
            source_capture_receipts.append(workpaper_capture_receipt)
            workpaper_draft_digest = str(
                workpaper_capture_receipt["response_digest"]
            )
            workpaper_source = "resume_capture_draft"
        else:
            draft_step, workpaper_draft, _ = _call_live_tool_draft(
                events=events,
                session_id=session_id,
                actor_id=agent_id,
                profile=research_profile,
                messages=compile_specialist_workpaper_messages(
                    context=submission_view
                ),
                tool=specialist_workpaper_tool(
                    agent_id=agent_id, context=workpaper_context
                ),
                expected_name="submit_specialist_workpaper",
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=f"{attempt_prefix}-{slug}-workpaper-draft",
                occurred_at=recorded_at,
                executor=research_executor,
            )
            provider_steps.append(_public_provider_step(draft_step.as_dict()))
            workpaper_draft_digest = str(draft_step.response_digest)

    workpaper: dict[str, Any]
    if agent_id == "AGENT::COUNTEREVIDENCE":
        model_payload = json.loads(workpaper_draft)
        if not isinstance(model_payload, dict):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_counter_workpaper_capture_invalid"
            )
        model_payload.pop("schema_version", None)
        model_payload.pop("agent_id", None)
        workpaper, receipt = validate_specialist_workpaper_submission(
            model_payload,
            context=workpaper_context,
            expected_agent_id=agent_id,
        )
        submission_receipts.append(receipt)
    else:
        workpaper_submit_tool = specialist_workpaper_submission_tool(
            agent_id=agent_id, context=workpaper_context
        )
        resumed = _resume_capture_draft(
            resume_capture_manifest,
            attempt_fragment=f"{slug}-workpaper-submit",
            expected_name=SPECIALIST_WORKPAPER_SUBMISSION_TOOL_NAME,
        )
        if resumed is not None:
            resumed_payload, _, resumed_receipt = resumed
            payload = json.loads(resumed_payload)
            if not isinstance(payload, dict):
                raise DynamicMultiAgentLoopError(
                    "dynamic_multi_agent_submission_resume_workpaper_invalid"
                )
            source_capture_receipts.append(resumed_receipt)
        else:
            step, payload, _ = _call_live_tool(
                events=events,
                session_id=session_id,
                actor_id="HARNESS::STRICT-SUBMISSION-MAPPER",
                profile=submission_profile,
                messages=compile_specialist_workpaper_submission_messages(
                    context=submission_view,
                    source_draft=workpaper_draft,
                    source_capture_digest=workpaper_draft_digest,
                    tool=workpaper_submit_tool,
                ),
                tool=workpaper_submit_tool,
                expected_name=SPECIALIST_WORKPAPER_SUBMISSION_TOOL_NAME,
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=f"{attempt_prefix}-{slug}-workpaper-submit",
                occurred_at=recorded_at,
                executor=submission_executor,
            )
            provider_steps.append(_public_provider_step(step.as_dict()))
        workpaper, receipt = validate_specialist_workpaper_submission(
            payload,
            context=workpaper_context,
            expected_agent_id=agent_id,
        )
        submission_receipts.append(receipt)

    numeric_refs = sorted(
        {
            str(row["numeric_ref"])
            for response in round_responses
            for row in response.get("numeric_facts") or ()
        }
    )
    checkpoint_id = "CHECKPOINT::" + canonical_digest(
        {
            "session_id": session_id,
            "plan_digest": base_plan["plan_digest"],
            "workpaper_digest": workpaper["workpaper_digest"],
        }
    )[:24].upper()
    checkpoint = create_context_checkpoint(
        session=session,
        events=events,
        checkpoint_id=checkpoint_id,
        objective_digest=canonical_digest(policy["objective"]),
        plan_digest=base_plan["plan_digest"],
        research_graph_digest=base_graph,
        accepted_evidence_refs=accepted_refs,
        numeric_fact_refs=numeric_refs,
        open_gap_refs=gaps,
        unresolved_feedback_refs=sorted(
            str(row["feedback_id"]) for row in feedback_receipts
        ),
        agent_local_state_refs=[
            str(row["reflection_digest"]) for row in reflections
        ],
        authority_refs=[
            str(evidence_pack["pack_payload_digest"]),
            str(role_program["role_program_digest"]),
            str(workpaper["workpaper_digest"]),
        ],
        counterevidence_refs=(
            accepted_refs if agent_id == "AGENT::COUNTEREVIDENCE" else []
        ),
        open_question_refs=[
            f"QUESTION::DELL::{slug.upper()}::{index}"
            for index, _ in enumerate(gaps, start=1)
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
        required_open_gap_refs=gaps,
        required_unresolved_feedback_refs=checkpoint[
            "unresolved_feedback_refs"
        ],
        required_counterevidence_refs=checkpoint["counterevidence_refs"],
        required_open_question_refs=checkpoint["open_question_refs"],
    )
    return {
        "agent_id": agent_id,
        "status": "completed_contract_valid",
        "role_program_digest": role_program["role_program_digest"],
        "predecessor_session_id": predecessor_bundle["session"]["session_id"],
        "session": session,
        "events": events,
        "provider_steps": provider_steps,
        "source_capture_receipts": source_capture_receipts,
        "submission_receipts": submission_receipts,
        "selections": selections,
        "round_batches": batches,
        "round_responses": [public_round_response(row) for row in round_responses],
        "feedback_receipts": feedback_receipts,
        "reflections": reflections,
        "reflection_artifacts": reflection_artifacts,
        "workpaper_context": workpaper_context,
        "submission_view": submission_view,
        "workpaper_source": workpaper_source,
        "workpaper": workpaper,
        "checkpoint": checkpoint,
        "resume_receipt": resume,
        "execution": {
            "provider_calls_attempted": _provider_attempt_count(events),
            "predecessor_provider_calls_reused": int(
                predecessor_bundle["execution"]["provider_calls_attempted"]
            ),
            "resume_provider_captures_reused": sum(
                1
                for row in source_capture_receipts
                if row.get("capture_origin")
                == "partial_submission_successor"
            ),
            "retrieval_rounds_reused": len(
                predecessor_bundle["round_responses"]
            ),
            "new_retrieval_rounds": (
                len(round_responses)
                - len(predecessor_bundle["round_responses"])
            ),
            "request_ids_executed": executed_ids,
            "external_source_network_calls": 0,
            "candidate_promotions": 0,
            "retries": 0,
        },
        "failure": {"phase": "", "code": "", "capture_ref": ""},
    }


def _create_lead_session(
    *, run_id: str, workpapers: Sequence[Mapping[str, Any]], recorded_at: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    seed = {
        "run_id": run_id,
        "lead_agent_id": RESEARCH_LEAD_AGENT_ID,
        "workpaper_digests": [str(row["workpaper_digest"]) for row in workpapers],
    }
    session_id = "SESSION::" + canonical_digest(seed)[:24].upper()
    plan_digest = canonical_digest(
        {
            "case_key": "DELL",
            "role": RESEARCH_LEAD_AGENT_ID,
            "workpaper_digests": seed["workpaper_digests"],
        }
    )
    session = create_agent_session(
        session_id=session_id,
        run_id=run_id,
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
        input_refs=tuple(seed["workpaper_digests"]),
        output_refs=(session["active_plan_ref"],),
    )
    return session, events


def _execute_live_lead_round(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    local_failure_receipts: Sequence[Mapping[str, Any]],
    session: Mapping[str, Any],
    events: list[dict[str, Any]],
    profile: Any,
    capture_root: Path,
    run_id: str,
    attempt_id: str,
    recorded_at: str,
    executor: Callable[..., AgentToolStepResult],
) -> dict[str, Any]:
    catalog = compile_challenge_catalog(workpapers=workpapers)
    tool = lead_coordination_tool(challenge_catalog=catalog)
    step, payload, _ = _call_live_tool(
        events=events,
        session_id=str(session["session_id"]),
        actor_id=RESEARCH_LEAD_AGENT_ID,
        profile=profile,
        messages=compile_lead_coordination_messages(
            workpapers=workpapers,
            challenge_catalog=catalog,
            local_failure_receipts=local_failure_receipts,
        ),
        tool=tool,
        expected_name="submit_lead_coordination_decision",
        capture_root=capture_root,
        run_id=run_id,
        attempt_id=attempt_id,
        occurred_at=recorded_at,
        executor=executor,
    )
    decision = validate_lead_coordination_decision(
        payload, challenge_catalog=catalog
    )
    _event(
        events,
        session_id=str(session["session_id"]),
        event_type="stop_decided",
        actor_id=RESEARCH_LEAD_AGENT_ID,
        occurred_at=recorded_at,
        input_refs=tuple(str(row["challenge_id"]) for row in catalog),
        output_refs=(decision["coordination_digest"],),
    )
    return {
        "challenge_catalog": catalog,
        "decision": decision,
        "provider_step": _public_provider_step(step.as_dict()),
    }


def _execute_live_role_repair(
    *,
    role_bundle: Mapping[str, Any],
    challenges: Sequence[Mapping[str, Any]],
    profile: Any,
    capture_root: Path,
    run_id: str,
    attempt_id: str,
    recorded_at: str,
    executor: Callable[..., AgentToolStepResult],
) -> dict[str, Any]:
    agent_id = str(role_bundle["agent_id"])
    receipts = [
        compile_cross_role_feedback_receipt(
            target_session_id=str(role_bundle["session"]["session_id"]),
            challenge=challenge,
            created_at=recorded_at,
        )
        for challenge in challenges
    ]
    repair_context = compile_workpaper_repair_context(
        context=role_bundle["workpaper_context"],
        prior_workpaper=role_bundle["workpaper"],
        feedback_receipts=receipts,
    )
    submission_view = compile_workpaper_submission_view(repair_context)
    # Append to the live role event stream itself so a failed repair attempt is
    # still materialized and counted. The full prior role result is only an
    # in-memory predecessor here; persisted predecessor attempts remain immutable.
    continued_events = role_bundle["events"]
    step, payload, _ = _call_live_tool(
        events=continued_events,
        session_id=str(role_bundle["session"]["session_id"]),
        actor_id=agent_id,
        profile=profile,
        messages=compile_specialist_workpaper_messages(context=submission_view),
        tool=specialist_workpaper_tool(
            agent_id=agent_id, context=repair_context
        ),
        expected_name="submit_specialist_workpaper",
        capture_root=capture_root,
        run_id=run_id,
        attempt_id=attempt_id,
        occurred_at=recorded_at,
        executor=executor,
    )
    repaired = validate_specialist_workpaper(
        payload,
        context=repair_context,
        expected_agent_id=agent_id,
    )
    before = _workpaper_authority_sets(role_bundle["workpaper"])
    after = _workpaper_authority_sets(repaired)
    if before != after:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_role_repair_authority_changed"
        )
    return {
        "agent_id": agent_id,
        "challenge_ids": [str(row["challenge_id"]) for row in challenges],
        "feedback_receipts": receipts,
        "repair_context": repair_context,
        "prior_workpaper_digest": role_bundle["workpaper"]["workpaper_digest"],
        "repaired_workpaper": repaired,
        "continued_events": continued_events,
        "provider_step": _public_provider_step(step.as_dict()),
        "authority_refs_unchanged": True,
    }


def _execute_submission_successor_lead_round(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    local_failure_receipts: Sequence[Mapping[str, Any]],
    session: Mapping[str, Any],
    events: list[dict[str, Any]],
    research_profile: Any,
    submission_profile: Any,
    capture_root: Path,
    run_id: str,
    attempt_prefix: str,
    round_index: int,
    recorded_at: str,
    research_executor: Callable[..., AgentToolStepResult],
    submission_executor: Callable[..., AgentToolStepResult],
    resume_capture_manifest: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    catalog = compile_challenge_catalog(workpapers=workpapers)
    draft_tool = lead_coordination_tool(challenge_catalog=catalog)
    source_capture_receipts: list[dict[str, Any]] = []
    provider_steps: list[dict[str, Any]] = []
    resumed_draft = _resume_capture_draft(
        resume_capture_manifest,
        attempt_fragment=f"lead-r{round_index}-draft",
        expected_name="submit_lead_coordination_decision",
    )
    if resumed_draft is not None:
        source_draft, _, draft_receipt = resumed_draft
        source_capture_receipts.append(draft_receipt)
        draft_response_digest = str(draft_receipt["response_digest"])
    else:
        draft_step, source_draft, _ = _call_live_tool_draft(
            events=events,
            session_id=str(session["session_id"]),
            actor_id=RESEARCH_LEAD_AGENT_ID,
            profile=research_profile,
            messages=compile_lead_coordination_messages(
                workpapers=workpapers,
                challenge_catalog=catalog,
                local_failure_receipts=local_failure_receipts,
            ),
            tool=draft_tool,
            expected_name="submit_lead_coordination_decision",
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=f"{attempt_prefix}-lead-r{round_index}-draft",
            occurred_at=recorded_at,
            executor=research_executor,
        )
        provider_steps.append(_public_provider_step(draft_step.as_dict()))
        draft_response_digest = str(draft_step.response_digest)
    submission_tool = lead_coordination_submission_tool(
        challenge_catalog=catalog
    )
    resumed_submission = _resume_capture_draft(
        resume_capture_manifest,
        attempt_fragment=f"lead-r{round_index}-submit",
        expected_name=LEAD_COORDINATION_SUBMISSION_TOOL_NAME,
    )
    if resumed_submission is not None:
        resumed_payload, _, submit_receipt = resumed_submission
        payload = json.loads(resumed_payload)
        if not isinstance(payload, dict):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_lead_invalid"
            )
        source_capture_receipts.append(submit_receipt)
    else:
        submission_step, payload, _ = _call_live_tool(
            events=events,
            session_id=str(session["session_id"]),
            actor_id="HARNESS::STRICT-SUBMISSION-MAPPER",
            profile=submission_profile,
            messages=compile_lead_coordination_submission_messages(
                source_draft=source_draft,
                source_capture_digest=draft_response_digest,
                tool=submission_tool,
            ),
            tool=submission_tool,
            expected_name=LEAD_COORDINATION_SUBMISSION_TOOL_NAME,
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=f"{attempt_prefix}-lead-r{round_index}-submit",
            occurred_at=recorded_at,
            executor=submission_executor,
        )
        provider_steps.append(_public_provider_step(submission_step.as_dict()))
    decision, receipt = validate_lead_coordination_submission(
        payload, challenge_catalog=catalog
    )
    _event(
        events,
        session_id=str(session["session_id"]),
        event_type="stop_decided",
        actor_id=RESEARCH_LEAD_AGENT_ID,
        occurred_at=recorded_at,
        input_refs=tuple(str(row["challenge_id"]) for row in catalog),
        output_refs=(decision["coordination_digest"],),
    )
    return {
        "challenge_catalog": catalog,
        "decision": decision,
        "submission_receipt": receipt,
        "provider_steps": provider_steps,
        "source_capture_receipts": source_capture_receipts,
    }


def _execute_submission_successor_role_repair(
    *,
    role_bundle: Mapping[str, Any],
    challenges: Sequence[Mapping[str, Any]],
    research_profile: Any,
    submission_profile: Any,
    capture_root: Path,
    run_id: str,
    attempt_prefix: str,
    repair_index: int,
    recorded_at: str,
    research_executor: Callable[..., AgentToolStepResult],
    submission_executor: Callable[..., AgentToolStepResult],
    resume_capture_manifest: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    agent_id = str(role_bundle["agent_id"])
    slug = agent_id.split("::")[-1].lower().replace("_", "-")
    receipts = [
        compile_cross_role_feedback_receipt(
            target_session_id=str(role_bundle["session"]["session_id"]),
            challenge=challenge,
            created_at=recorded_at,
        )
        for challenge in challenges
    ]
    repair_context = compile_workpaper_repair_context(
        context=role_bundle["workpaper_context"],
        prior_workpaper=role_bundle["workpaper"],
        feedback_receipts=receipts,
    )
    submission_view = compile_workpaper_submission_view(repair_context)
    events = role_bundle["events"]
    provider_steps: list[dict[str, Any]] = []
    source_capture_receipts: list[dict[str, Any]] = []
    repair_fragment = f"{slug}-repair-r{repair_index}"
    resumed_draft = _resume_capture_draft(
        resume_capture_manifest,
        attempt_fragment=f"{repair_fragment}-draft",
        expected_name="submit_specialist_workpaper",
    )
    if resumed_draft is not None:
        source_draft, _, draft_receipt = resumed_draft
        source_capture_receipts.append(draft_receipt)
        draft_response_digest = str(draft_receipt["response_digest"])
    else:
        draft_step, source_draft, _ = _call_live_tool_draft(
            events=events,
            session_id=str(role_bundle["session"]["session_id"]),
            actor_id=agent_id,
            profile=research_profile,
            messages=compile_specialist_workpaper_messages(context=submission_view),
            tool=specialist_workpaper_tool(
                agent_id=agent_id, context=repair_context
            ),
            expected_name="submit_specialist_workpaper",
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=(
                f"{attempt_prefix}-{repair_fragment}-draft"
            ),
            occurred_at=recorded_at,
            executor=research_executor,
        )
        provider_steps.append(_public_provider_step(draft_step.as_dict()))
        draft_response_digest = str(draft_step.response_digest)
    submission_tool = specialist_workpaper_submission_tool(
        agent_id=agent_id, context=repair_context
    )
    resumed_submission = _resume_capture_draft(
        resume_capture_manifest,
        attempt_fragment=f"{repair_fragment}-submit",
        expected_name=SPECIALIST_WORKPAPER_SUBMISSION_TOOL_NAME,
    )
    if resumed_submission is not None:
        resumed_payload, _, submit_receipt = resumed_submission
        payload = json.loads(resumed_payload)
        if not isinstance(payload, dict):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_repair_invalid"
            )
        source_capture_receipts.append(submit_receipt)
    else:
        submission_step, payload, _ = _call_live_tool(
            events=events,
            session_id=str(role_bundle["session"]["session_id"]),
            actor_id="HARNESS::STRICT-SUBMISSION-MAPPER",
            profile=submission_profile,
            messages=compile_specialist_workpaper_submission_messages(
                context=submission_view,
                source_draft=source_draft,
                source_capture_digest=draft_response_digest,
                tool=submission_tool,
            ),
            tool=submission_tool,
            expected_name=SPECIALIST_WORKPAPER_SUBMISSION_TOOL_NAME,
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=(
                f"{attempt_prefix}-{repair_fragment}-submit"
            ),
            occurred_at=recorded_at,
            executor=submission_executor,
        )
        provider_steps.append(_public_provider_step(submission_step.as_dict()))
    repaired, receipt = validate_specialist_workpaper_submission(
        payload,
        context=repair_context,
        expected_agent_id=agent_id,
    )
    before = _workpaper_authority_sets(role_bundle["workpaper"])
    after = _workpaper_authority_sets(repaired)
    if before != after:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_repair_authority_changed"
        )
    return {
        "agent_id": agent_id,
        "challenge_ids": [str(row["challenge_id"]) for row in challenges],
        "feedback_receipts": receipts,
        "repair_context": repair_context,
        "prior_workpaper_digest": role_bundle["workpaper"]["workpaper_digest"],
        "repaired_workpaper": repaired,
        "continued_events": events,
        "submission_receipt": receipt,
        "provider_steps": provider_steps,
        "source_capture_receipts": source_capture_receipts,
        "authority_refs_unchanged": True,
    }


def run_live(
    *,
    authority_path: Path,
    research_executor: Callable[..., AgentToolStepResult] = (
        execute_agent_tool_step_exact_once
    ),
    submission_executor: Callable[..., AgentToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority_path = authority_path.resolve()
    authority = _read_json(authority_path)
    paths = validate_live_authority(authority, authority_path=authority_path)
    output = dict(authority["output_contract"])
    run_id = str(output["run_id"])
    attempt_prefix = str(output["attempt_prefix"])
    capture_root = _resolve_repo_ref(str(output["capture_root_ref"]))
    private_root = _resolve_repo_ref(str(output["private_output_root_ref"]))
    public_path = _resolve_repo_ref(str(output["public_result_ref"]))
    recorded_at = _now()

    policy, programs = _compile_role_programs()
    by_agent = role_program_by_agent(programs)
    source_refs = policy["source_refs"]
    research_profile = load_agent_transport_profile(
        _read_json(paths["provider_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _read_json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_node_profile(
        submission_profile, node_class="workpaper_submission_non_thinking"
    )
    runtime_paths = resolve_runtime_paths(ROOT)
    permissions = frozenset({"current_product:read"})
    retrieval_principal = ResearchRetrievalPrincipal("current", permissions)
    evidence_principal = ResearchEvidencePackPrincipal("current", permissions)
    retrieval = ResearchRetrievalService.from_runtime_paths(ROOT, runtime_paths)
    evidence_service = ResearchEvidencePackService.from_runtime_paths(
        ROOT, runtime_paths
    )
    evidence_pack = evidence_service.get_case("DELL", evidence_principal)
    if evidence_pack.get("pack_payload_digest") != authority["bound_inputs"].get(
        "current_evidence_pack_payload_digest"
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_evidence_pack_drift"
        )
    truth_policy = _read_json(source_refs["truth_spine_policy_ref"])
    consumer_policy = _read_json(source_refs["consumer_policy_ref"])
    task_quantitative = _read_json(
        source_refs["task_quantitative_result_ref"]
    )
    if task_quantitative.get("result_digest") != authority["bound_inputs"].get(
        "task_quantitative_result_digest"
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_quantitative_input_drift"
        )
    cuda = required_cuda_fp16_receipt(
        purpose="DELL current dynamic natural six-specialist multi-agent live"
    )

    role_bundles: dict[str, dict[str, Any]] = {}
    for agent_id in SPECIALIST_AGENT_IDS:
        role_bundles[agent_id] = _execute_live_role(
            role_program=by_agent[agent_id],
            run_id=run_id,
            attempt_prefix=attempt_prefix,
            recorded_at=recorded_at,
            capture_root=capture_root,
            research_profile=research_profile,
            submission_profile=submission_profile,
            retrieval=retrieval,
            retrieval_principal=retrieval_principal,
            evidence_pack=evidence_pack,
            truth_policy=truth_policy,
            consumer_policy=consumer_policy,
            task_quantitative=task_quantitative,
            research_executor=research_executor,
            submission_executor=submission_executor,
        )

    successful_agents = [
        agent_id
        for agent_id in SPECIALIST_AGENT_IDS
        if role_bundles[agent_id]["status"] == "completed_contract_valid"
    ]
    failed_agents = [
        agent_id for agent_id in SPECIALIST_AGENT_IDS if agent_id not in successful_agents
    ]
    lead_bundle: dict[str, Any] = {}
    repairs: list[dict[str, Any]] = []
    final_workpapers = [
        deepcopy(role_bundles[agent_id]["workpaper"])
        for agent_id in successful_agents
    ]
    frontier = "specialist_failures_preserved"
    if len(successful_agents) == len(SPECIALIST_AGENT_IDS):
        lead_session, lead_events = _create_lead_session(
            run_id=run_id,
            workpapers=final_workpapers,
            recorded_at=recorded_at,
        )
        try:
            first = _execute_live_lead_round(
                workpapers=final_workpapers,
                local_failure_receipts=(),
                session=lead_session,
                events=lead_events,
                profile=research_profile,
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=f"{attempt_prefix}-lead-r1",
                recorded_at=recorded_at,
                executor=research_executor,
            )
            lead_bundle = {
                "session": lead_session,
                "events": lead_events,
                "rounds": [first],
                "failure": {"phase": "", "code": "", "capture_ref": ""},
            }
            accepted = set(first["decision"]["accepted_challenge_ids"])
            challenge_by_id = {
                str(row["challenge_id"]): row
                for row in first["challenge_catalog"]
            }
            accepted_rows = [challenge_by_id[value] for value in sorted(accepted)]
            by_target: dict[str, list[dict[str, Any]]] = {}
            for challenge in accepted_rows:
                by_target.setdefault(
                    str(challenge["target_agent_id"]), []
                ).append(challenge)
            if len(by_target) > int(
                policy["loop_limits"]["maximum_role_repairs_per_lead_round"]
            ):
                raise DynamicMultiAgentLoopError(
                    "dynamic_multi_agent_live_role_repair_budget_exceeded"
                )
            for target, challenges in by_target.items():
                repair = _execute_live_role_repair(
                    role_bundle=role_bundles[target],
                    challenges=challenges,
                    profile=submission_profile,
                    capture_root=capture_root,
                    run_id=run_id,
                    attempt_id=(
                        f"{attempt_prefix}-{target.split('::')[-1].lower()}-repair-r1"
                    ),
                    recorded_at=recorded_at,
                    executor=submission_executor,
                )
                repairs.append(repair)
                role_bundles[target]["workpaper"] = repair[
                    "repaired_workpaper"
                ]
                role_bundles[target]["events"] = repair["continued_events"]
            final_workpapers = [
                deepcopy(role_bundles[agent_id]["workpaper"])
                for agent_id in SPECIALIST_AGENT_IDS
            ]
            if repairs:
                second = _execute_live_lead_round(
                    workpapers=final_workpapers,
                    local_failure_receipts=(),
                    session=lead_session,
                    events=lead_events,
                    profile=research_profile,
                    capture_root=capture_root,
                    run_id=run_id,
                    attempt_id=f"{attempt_prefix}-lead-r2",
                    recorded_at=recorded_at,
                    executor=research_executor,
                )
                lead_bundle["rounds"].append(second)
                frontier = (
                    "proceed_to_independent_evaluation"
                    if not second["decision"]["accepted_challenge_ids"]
                    and second["decision"]["next_state"]
                    == "proceed_to_evaluation"
                    else "bounded_lead_frontier_requires_successor_or_data"
                )
            else:
                frontier = (
                    "proceed_to_independent_evaluation"
                    if first["decision"]["next_state"]
                    == "proceed_to_evaluation"
                    else "lead_paused_for_data_or_tool"
                )
        except ModelGatewayError as exc:
            lead_bundle = {
                "session": lead_session,
                "events": lead_events,
                "rounds": lead_bundle.get("rounds", []),
                "failure": {
                    "phase": "provider_transport_or_response",
                    "code": exc.code,
                    "capture_ref": (
                        _relative(Path(exc.capture_ref))
                        if exc.capture_ref
                        else ""
                    ),
                },
            }
            frontier = "lead_terminal_failure_preserved"
        except (DynamicMultiAgentLoopError, ValueError) as exc:
            lead_bundle = {
                "session": lead_session,
                "events": lead_events,
                "rounds": lead_bundle.get("rounds", []),
                "failure": {
                    "phase": "lead_or_repair_contract",
                    "code": (
                        exc.code
                        if isinstance(exc, DynamicMultiAgentLoopError)
                        else str(exc)
                    ),
                    "capture_ref": "",
                },
            }
            frontier = "lead_or_repair_terminal_failure_preserved"

    provider_calls = sum(
        _provider_attempt_count(bundle["events"])
        for bundle in role_bundles.values()
    ) + _provider_attempt_count(lead_bundle.get("events") or ())
    all_requests = [
        request_id
        for bundle in role_bundles.values()
        for request_id in bundle["execution"]["request_ids_executed"]
    ]
    all_rounds = sum(
        int(bundle["execution"]["retrieval_rounds_executed"])
        for bundle in role_bundles.values()
    )
    if not (
        provider_calls <= expected_live_execution_budget()["maximum_model_calls"]
        and len(set(all_requests)) == len(all_requests)
        and len(all_requests)
        <= expected_live_execution_budget()["maximum_s1_s2_requests"]
        and all_rounds
        <= expected_live_execution_budget()["maximum_retrieval_rounds"]
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_live_aggregate_budget_invalid"
        )
    succeeded = frontier == "proceed_to_independent_evaluation"
    status = (
        "completed_contract_valid_assessment_pending"
        if succeeded
        else "terminal_frontier_preserved_no_automatic_rerun"
    )
    full_body = {
        "schema_version": LIVE_FULL_RESULT_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha256(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "policy": policy,
        "role_programs_digest": programs["role_programs_digest"],
        "role_bundles": [role_bundles[agent_id] for agent_id in SPECIALIST_AGENT_IDS],
        "lead_bundle": lead_bundle,
        "repairs": repairs,
        "final_workpapers": final_workpapers,
        "frontier": frontier,
        "cuda_receipt": cuda,
        "execution": {
            "provider_calls_attempted": provider_calls,
            "maximum_provider_calls": expected_live_execution_budget()[
                "maximum_model_calls"
            ],
            "specialist_sessions_started": 6,
            "specialist_sessions_completed": len(successful_agents),
            "specialist_sessions_failed": len(failed_agents),
            "retrieval_rounds_executed": all_rounds,
            "request_ids_executed": all_requests,
            "unique_request_ids_executed": len(set(all_requests)),
            "lead_rounds_executed": len(lead_bundle.get("rounds") or ()),
            "role_repairs_executed": len(repairs),
            "external_source_network_calls": 0,
            "candidate_promotions": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "claims": {
            "natural_dynamic_multi_agent_executed": True,
            "six_independent_specialists_completed": len(successful_agents) == 6,
            "natural_lead_coordination_completed": bool(
                lead_bundle.get("rounds")
            ),
            "role_local_feedback_repairs_completed": len(repairs),
            "current_S1_S2_executed": all_rounds > 0,
            "initial_evidence_prefeed": False,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    _write_json(private_root / "full_result.json", full, exclusive=True)

    role_summaries = []
    for agent_id in SPECIALIST_AGENT_IDS:
        bundle = role_bundles[agent_id]
        role_summaries.append(
            {
                "agent_id": agent_id,
                "status": bundle["status"],
                "provider_calls_attempted": bundle["execution"][
                    "provider_calls_attempted"
                ],
                "retrieval_rounds_executed": bundle["execution"][
                    "retrieval_rounds_executed"
                ],
                "request_ids_executed": bundle["execution"][
                    "request_ids_executed"
                ],
                "reviewed_evidence_count": len(
                    {
                        str(row["evidence_ref"])
                        for response in bundle["round_responses"]
                        for row in response.get("reviewed_evidence") or ()
                    }
                ),
                "numeric_fact_count": len(
                    {
                        str(row["numeric_ref"])
                        for response in bundle["round_responses"]
                        for row in response.get("numeric_facts") or ()
                    }
                ),
                "remaining_gap_count": len(
                    {
                        str(row["gap_ref"])
                        for response in bundle["round_responses"]
                        for row in response.get("residual_gaps") or ()
                    }
                ),
                "workpaper": deepcopy(bundle["workpaper"]),
                "failure": deepcopy(bundle["failure"]),
            }
        )
    public_body = {
        "schema_version": LIVE_RESULT_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "model": research_profile.model,
        "frontier": frontier,
        "execution": full["execution"],
        "role_summaries": role_summaries,
        "lead_summary": {
            "round_count": len(lead_bundle.get("rounds") or ()),
            "decisions": [
                deepcopy(row["decision"])
                for row in lead_bundle.get("rounds") or ()
            ],
            "failure": deepcopy(lead_bundle.get("failure") or {}),
        },
        "repair_summaries": [
            {
                "agent_id": row["agent_id"],
                "challenge_ids": row["challenge_ids"],
                "prior_workpaper_digest": row["prior_workpaper_digest"],
                "repaired_workpaper_digest": row["repaired_workpaper"][
                    "workpaper_digest"
                ],
                "authority_refs_unchanged": row[
                    "authority_refs_unchanged"
                ],
            }
            for row in repairs
        ],
        "claims": full["claims"],
        "acceptance": {
            "dynamic_multi_agent_contract_pass": succeeded,
            "L1_assessment_pending": succeeded,
            "eight_dimension_content_assessment_pending": succeeded,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "private_full_result_ref": _relative(private_root / "full_result.json"),
        "private_full_result_sha256": _sha256(private_root / "full_result.json"),
        "known_boundary": authority["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_json(public_path, public, exclusive=True)
    return public


def run_zero_call_submission_successor(
    *,
    attempt_id: str,
    predecessor_public_path: Path,
    predecessor_private_path: Path,
    private_output: Path,
    public_output: Path,
    resume_public_path: Path | None = None,
    resume_private_path: Path | None = None,
) -> dict[str, Any]:
    """Prove a capture-bound continuation without model or network calls."""

    predecessor_public = _read_json(predecessor_public_path)
    predecessor = _read_json(predecessor_private_path)
    if not (
        predecessor_public.get("result_digest")
        == canonical_digest(
            {
                key: deepcopy(value)
                for key, value in predecessor_public.items()
                if key != "result_digest"
            }
        )
        and predecessor.get("full_result_digest")
        == canonical_digest(
            {
                key: deepcopy(value)
                for key, value in predecessor.items()
                if key != "full_result_digest"
            }
        )
        and predecessor_public.get("private_full_result_sha256")
        == _sha256(predecessor_private_path)
        and predecessor_public.get("status")
        == "terminal_frontier_preserved_no_automatic_rerun"
        and predecessor.get("frontier") == "specialist_failures_preserved"
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_predecessor_invalid"
        )

    if (resume_public_path is None) != (resume_private_path is None):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_resume_pair_required"
        )
    resume_enabled = resume_public_path is not None
    resume_public: dict[str, Any] = {}
    resume_private: dict[str, Any] = {}
    resume_manifest: list[dict[str, Any]] = []
    resume_authority: dict[str, Any] = {}
    if resume_enabled:
        assert resume_public_path is not None
        assert resume_private_path is not None
        resume_public = _read_json(resume_public_path)
        resume_private = _read_json(resume_private_path)
        resume_authority_path = _resolve_repo_ref(
            str(resume_public.get("authority_ref") or "")
        )
        resume_authority = _read_json(resume_authority_path)
        if not (
            resume_public.get("result_digest")
            == canonical_digest(
                {
                    key: deepcopy(value)
                    for key, value in resume_public.items()
                    if key != "result_digest"
                }
            )
            and resume_private.get("full_result_digest")
            == canonical_digest(
                {
                    key: deepcopy(value)
                    for key, value in resume_private.items()
                    if key != "full_result_digest"
                }
            )
            and resume_public.get("private_full_result_sha256")
            == _sha256(resume_private_path)
            and resume_public.get("status")
            == "terminal_partial_provider_reasoning_budget_exhausted_preserved"
            and resume_private.get("status")
            == "terminal_partial_provider_reasoning_budget_exhausted_preserved"
            and resume_private.get("authority_ref")
            == resume_public.get("authority_ref")
            and resume_private.get("authority_sha256")
            == _sha256(resume_authority_path)
            and resume_private.get("failure", {}).get("phase")
            == "cash_conversion_workpaper_analysis"
            and resume_private.get("failure", {}).get("code")
            == "model_gateway_reasoning_budget_exhausted"
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_predecessor_invalid"
            )
        resume_manifest = _validate_resume_capture_manifest(
            resume_private.get("capture_manifest") or ()
        )

    policy, programs = _compile_role_programs()
    by_agent = role_program_by_agent(programs)
    source_refs = policy["source_refs"]
    runtime_paths = resolve_runtime_paths(ROOT)
    permissions = frozenset({"current_product:read"})
    evidence_pack = ResearchEvidencePackService.from_runtime_paths(
        ROOT, runtime_paths
    ).get_case(
        "DELL", ResearchEvidencePackPrincipal("current", permissions)
    )
    truth_policy = _read_json(source_refs["truth_spine_policy_ref"])
    consumer_policy = _read_json(source_refs["consumer_policy_ref"])
    task_quantitative = _read_json(source_refs["task_quantitative_result_ref"])
    retrieval_principal = ResearchRetrievalPrincipal("current", permissions)
    retrieval = ResearchRetrievalService.from_runtime_paths(ROOT, runtime_paths)

    role_proofs: list[dict[str, Any]] = []
    capture_receipts: list[dict[str, Any]] = []
    counter_workpaper_digest = ""
    mapping_required_agents: list[str] = []
    locally_migrated_agents: list[str] = []
    supply_required_request_ids: list[str] = []
    predecessor_by_agent = {
        str(row["agent_id"]): row for row in predecessor["role_bundles"]
    }
    for agent_id in SPECIALIST_AGENT_IDS:
        role_program = by_agent[agent_id]
        bundle = predecessor_by_agent[agent_id]
        round_responses, feedback = _rebuild_predecessor_rounds(
            role_program=role_program,
            predecessor_bundle=bundle,
            evidence_pack=evidence_pack,
            truth_policy=truth_policy,
            consumer_policy=consumer_policy,
            task_quantitative=task_quantitative,
            recorded_at=str(predecessor["recorded_at"]),
        )
        executed_ids = [
            str(value)
            for value in bundle["execution"]["request_ids_executed"]
        ]
        accepted_refs = _accepted_evidence_refs(round_responses)
        gaps = _open_gap_refs(round_responses)
        slug = agent_id.split("::")[-1].lower().replace("_", "-")
        reflection_capture = _completed_capture_for_attempt(
            bundle, attempt_fragment=f"{slug}-reflection-r1"
        )
        reflection_draft, _, reflection_receipt = _capture_tool_draft(
            reflection_capture, expected_name=REFLECTION_TOOL_NAME
        )
        capture_receipts.append(reflection_receipt)
        parsed_reflection: dict[str, Any] | None = None
        try:
            candidate = json.loads(reflection_draft)
            if isinstance(candidate, dict):
                parsed_reflection = validate_reflection_payload(
                    candidate,
                    policy=role_program["loop_policy"],
                    request_catalog=role_program["request_catalog"],
                    feedback_receipts=feedback,
                    accepted_evidence_refs=accepted_refs,
                    executed_request_ids=executed_ids,
                    round_index=1,
                )
        except (json.JSONDecodeError, DynamicSingleUnitLoopError):
            parsed_reflection = None

        state = coverage_state(
            policy=role_program["loop_policy"],
            executed_request_ids=executed_ids,
        )
        submission_tool = reflection_submission_tool(
            policy=role_program["loop_policy"],
            request_catalog=role_program["request_catalog"],
            feedback_receipts=feedback,
            accepted_evidence_refs=accepted_refs,
            executed_request_ids=executed_ids,
            open_gap_refs=gaps,
            round_index=1,
        )
        parameters = submission_tool["function"]["parameters"]
        if {"schema_version", "round_id"}.intersection(
            parameters["properties"]
        ) or not (
            parameters["properties"]["graph_hypotheses"]["items"][
                "properties"
            ]["relationship_direction"]["maxLength"]
            == 80
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_contract_surface_invalid"
            )

        effective_stop = "pending_strict_mapping"
        if parsed_reflection is not None:
            base_plan, base_graph = _role_base_state(
                role_program=role_program
            )
            artifacts = compile_reflection_artifacts(
                policy=role_program["loop_policy"],
                reflection=parsed_reflection,
                session_id=str(bundle["session"]["session_id"]),
                agent_id=agent_id,
                base_plan=base_plan,
                base_graph_digest=base_graph,
                executed_request_ids=executed_ids,
                open_gap_refs=gaps,
                model_calls_used=int(bundle["execution"]["provider_calls_attempted"]),
            )
            effective_stop = str(artifacts["stop_decision"]["decision"])
            locally_migrated_agents.append(agent_id)
            workpaper_context = compile_workpaper_context(
                policy=role_program["loop_policy"],
                round_responses=round_responses,
                feedback_receipts=feedback,
                reflections=[parsed_reflection],
                stop_decision=artifacts["stop_decision"],
            )
            if agent_id == "AGENT::COUNTEREVIDENCE":
                workpaper_capture = _completed_capture_for_attempt(
                    bundle, attempt_fragment=f"{slug}-workpaper"
                )
                workpaper_draft, _, workpaper_receipt = _capture_tool_draft(
                    workpaper_capture,
                    expected_name="submit_specialist_workpaper",
                )
                capture_receipts.append(workpaper_receipt)
                model_payload = json.loads(workpaper_draft)
                if not isinstance(model_payload, dict):
                    raise DynamicMultiAgentLoopError(
                        "dynamic_multi_agent_counter_workpaper_draft_invalid"
                    )
                model_payload.pop("schema_version", None)
                model_payload.pop("agent_id", None)
                counter_workpaper, _ = validate_specialist_workpaper_submission(
                    model_payload,
                    context=workpaper_context,
                    expected_agent_id=agent_id,
                )
                counter_workpaper_digest = str(
                    counter_workpaper["workpaper_digest"]
                )
            elif agent_id == "AGENT::DEMAND_QUALITY":
                workpaper_capture = _completed_capture_for_attempt(
                    bundle, attempt_fragment=f"{slug}-workpaper"
                )
                _, _, workpaper_receipt = _capture_tool_draft(
                    workpaper_capture,
                    expected_name="submit_specialist_workpaper",
                )
                capture_receipts.append(workpaper_receipt)
        else:
            mapping_required_agents.append(agent_id)

        if not state["all_required_groups_covered"]:
            available = {
                str(row["request_id"])
                for row in role_program["request_catalog"]["requests"]
            } - set(executed_ids)
            allowed = parameters["properties"]["proposed_stop_decision"]["enum"]
            if allowed != ["continue"] or not available:
                raise DynamicMultiAgentLoopError(
                    "dynamic_multi_agent_supply_coverage_control_invalid"
                )
            supply_required_request_ids = sorted(available)

        workpaper_submission = specialist_workpaper_submission_tool(
            agent_id=agent_id,
            context=(
                workpaper_context
                if parsed_reflection is not None
                else deepcopy(bundle.get("workpaper_context") or {})
            ),
        ) if parsed_reflection is not None else None
        if workpaper_submission is not None and {
            "schema_version",
            "agent_id",
        }.intersection(workpaper_submission["function"]["parameters"]["properties"]):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_workpaper_submission_surface_invalid"
            )
        role_proofs.append(
            {
                "agent_id": agent_id,
                "round_response_digests": [
                    str(row["round_response_digest"])
                    for row in round_responses
                ],
                "feedback_refs": [str(row["feedback_id"]) for row in feedback],
                "reflection_capture_ref": reflection_receipt["capture_ref"],
                "reflection_capture_reusable_as_draft": True,
                "reflection_requires_strict_mapping": parsed_reflection is None,
                "current_coverage_complete": state["all_required_groups_covered"],
                "effective_stop_after_local_compilation": effective_stop,
            }
        )

    resume_role_proofs: list[dict[str, Any]] = []
    resume_frontier: dict[str, Any] = {}
    if resume_enabled:
        expected_reusable_suffixes = {
            "demand-quality-workpaper-submit",
            "operating-performance-reflection-r1-submit",
            "operating-performance-workpaper-draft",
            "operating-performance-workpaper-submit",
            "value-capture-reflection-r1-submit",
            "value-capture-workpaper-draft",
            "value-capture-workpaper-submit",
            "cash-conversion-reflection-r1-submit",
        }
        actual_reusable_suffixes = {
            next(
                (
                    suffix
                    for suffix in expected_reusable_suffixes
                    if str(row["attempt_id"]).endswith(suffix)
                ),
                "",
            )
            for row in resume_manifest
            if bool(row["reusable"])
        }
        failed_rows = [row for row in resume_manifest if not row["reusable"]]
        if not (
            actual_reusable_suffixes == expected_reusable_suffixes
            and len(failed_rows) == 1
            and str(failed_rows[0]["attempt_id"]).endswith(
                "cash-conversion-workpaper-draft"
            )
            and failed_rows[0]["finish_reason"] == "length"
            and int(failed_rows[0]["completion_tokens"]) == 16000
            and int(failed_rows[0]["reasoning_tokens"]) == 16000
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_frontier_invalid"
            )

        resume_authority_bound = resume_authority["bound_inputs"]
        research_profile = load_agent_transport_profile(
            _read_json(resume_authority_bound["provider_profile_ref"])
        )
        submission_profile = load_chat_completion_profile(
            _read_json(resume_authority_bound["submission_profile_ref"])
        )

        def _forbid_provider(**kwargs: Any) -> AgentToolStepResult:
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_unexpected_provider_call:"
                + str(kwargs.get("attempt_id") or "")
            )

        replay_recorded_at = str(resume_private["recorded_at"])
        for agent_id in (
            "AGENT::DEMAND_QUALITY",
            "AGENT::OPERATING_PERFORMANCE",
            "AGENT::VALUE_CAPTURE",
        ):
            replay = _execute_submission_successor_role(
                role_program=by_agent[agent_id],
                predecessor_bundle=predecessor_by_agent[agent_id],
                predecessor_recorded_at=str(predecessor["recorded_at"]),
                run_id=f"{attempt_id}-REQUAL",
                attempt_prefix=f"{attempt_id}-REQUAL",
                recorded_at=replay_recorded_at,
                capture_root=private_output.parent / "forbidden-captures",
                research_profile=research_profile,
                submission_profile=submission_profile,
                retrieval=retrieval,
                retrieval_principal=retrieval_principal,
                evidence_pack=evidence_pack,
                truth_policy=truth_policy,
                consumer_policy=consumer_policy,
                task_quantitative=task_quantitative,
                research_executor=_forbid_provider,
                submission_executor=_forbid_provider,
                resume_capture_manifest=resume_manifest,
            )
            resume_role_proofs.append(
                {
                    "agent_id": agent_id,
                    "status": replay["status"],
                    "workpaper_digest": replay["workpaper"][
                        "workpaper_digest"
                    ],
                    "provider_calls": replay["execution"][
                        "provider_calls_attempted"
                    ],
                    "resume_provider_captures_reused": replay["execution"][
                        "resume_provider_captures_reused"
                    ],
                }
            )

        class _ResumeFrontierReached(RuntimeError):
            pass

        frontier_attempts: list[str] = []

        def _cash_frontier(**kwargs: Any) -> AgentToolStepResult:
            frontier_attempts.append(str(kwargs.get("attempt_id") or ""))
            raise _ResumeFrontierReached(frontier_attempts[-1])

        try:
            _execute_submission_successor_role(
                role_program=by_agent["AGENT::CASH_CONVERSION"],
                predecessor_bundle=predecessor_by_agent[
                    "AGENT::CASH_CONVERSION"
                ],
                predecessor_recorded_at=str(predecessor["recorded_at"]),
                run_id=f"{attempt_id}-FRONTIER",
                attempt_prefix=f"{attempt_id}-FRONTIER",
                recorded_at=replay_recorded_at,
                capture_root=private_output.parent / "forbidden-captures",
                research_profile=research_profile,
                submission_profile=submission_profile,
                retrieval=retrieval,
                retrieval_principal=retrieval_principal,
                evidence_pack=evidence_pack,
                truth_policy=truth_policy,
                consumer_policy=consumer_policy,
                task_quantitative=task_quantitative,
                research_executor=_cash_frontier,
                submission_executor=_forbid_provider,
                resume_capture_manifest=resume_manifest,
            )
        except _ResumeFrontierReached:
            pass
        if not (
            len(frontier_attempts) == 1
            and frontier_attempts[0].endswith(
                "cash-conversion-workpaper-draft"
            )
        ):
            raise DynamicMultiAgentLoopError(
                "dynamic_multi_agent_submission_resume_frontier_not_exact"
            )
        resume_frontier = {
            "agent_id": "AGENT::CASH_CONVERSION",
            "next_attempt_suffix": "cash-conversion-workpaper-draft",
            "prior_reflection_capture_reused": True,
            "failed_R3_draft_reused": False,
        }

    lead_tool = lead_coordination_submission_tool(challenge_catalog=[])
    if {"schema_version", "lead_agent_id"}.intersection(
        lead_tool["function"]["parameters"]["properties"]
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_lead_submission_surface_invalid"
        )
    checks = {
        "predecessor_public_and_private_digest_bound": True,
        "six_role_S1_S2_rounds_replayed_exactly": len(role_proofs) == 6,
        "eight_relevant_capture_drafts_complete": len(capture_receipts) == 8,
        "valid_reflections_migrated_without_model_research_change": sorted(
            locally_migrated_agents
        )
        == sorted(["AGENT::COUNTEREVIDENCE", "AGENT::DEMAND_QUALITY"]),
        "four_failed_reflections_require_strict_mapping": sorted(
            mapping_required_agents
        )
        == sorted(
            [
                "AGENT::OPERATING_PERFORMANCE",
                "AGENT::VALUE_CAPTURE",
                "AGENT::CASH_CONVERSION",
                "AGENT::SUPPLY_RELATIONSHIP",
            ]
        ),
        "counterevidence_workpaper_requalified_locally": bool(
            counter_workpaper_digest
        ),
        "supply_missing_coverage_forces_exact_continuation": len(
            supply_required_request_ids
        )
        == 1,
        "runtime_owned_identity_removed_from_model_submission": True,
        "graph_predicate_compacted_separately_from_research_narrative": True,
        "lead_submission_contract_provider_neutral": True,
        "zero_model_network_paid_calls": True,
    }
    if resume_enabled:
        checks.update(
            {
                "R3_public_private_and_authority_digest_bound": True,
                "R3_nine_capture_manifest_verified": len(resume_manifest) == 9,
                "R3_eight_completed_captures_reusable": sum(
                    1 for row in resume_manifest if row["reusable"]
                )
                == 8,
                "three_completed_workpapers_requalified_without_provider": (
                    len(resume_role_proofs) == 3
                    and all(
                        row["status"] == "completed_contract_valid"
                        and row["provider_calls"] == 0
                        for row in resume_role_proofs
                    )
                ),
                "cash_resume_frontier_is_exact": bool(resume_frontier),
                "failed_cash_draft_not_promoted": True,
                "resume_budget_compiles_to_seventeen_calls": (
                    expected_submission_resume_budget()[
                        "maximum_new_model_calls"
                    ]
                    == 17
                ),
            }
        )
    if not all(checks.values()):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_zero_call_not_proven"
        )
    private_body = {
        "schema_version": SUBMISSION_SUCCESSOR_ZERO_SCHEMA,
        "status": (
            "submission_successor_resume_zero_call_proven"
            if resume_enabled
            else "submission_successor_zero_call_proven"
        ),
        "recorded_at": _now(),
        "attempt_id": attempt_id,
        "predecessor_public_ref": _relative(predecessor_public_path),
        "predecessor_public_sha256": _sha256(predecessor_public_path),
        "predecessor_private_ref": _relative(predecessor_private_path),
        "predecessor_private_sha256": _sha256(predecessor_private_path),
        "role_proofs": role_proofs,
        "capture_receipts": capture_receipts,
        "counterevidence_workpaper_digest": counter_workpaper_digest,
        "supply_required_request_ids": supply_required_request_ids,
        "resume_role_proofs": resume_role_proofs,
        "resume_frontier": resume_frontier,
        "checks": checks,
        "execution": {
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "retrieval_calls": 0,
            "predecessor_rounds_replayed": 6,
            "resume_provider_captures_reused": (
                sum(
                    int(row["resume_provider_captures_reused"])
                    for row in resume_role_proofs
                )
                if resume_enabled
                else 0
            ),
        },
        "claims": {
            "R1_relabelled_as_success": False,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
    }
    private_result = {
        **private_body,
        "full_result_digest": canonical_digest(private_body),
    }
    if resume_enabled:
        assert resume_public_path is not None
        assert resume_private_path is not None
        private_result.update(
            {
                "resume_public_ref": _relative(resume_public_path),
                "resume_public_sha256": _sha256(resume_public_path),
                "resume_public_result_digest": resume_public[
                    "result_digest"
                ],
                "resume_private_ref": _relative(resume_private_path),
                "resume_private_sha256": _sha256(resume_private_path),
                "resume_private_full_result_digest": resume_private[
                    "full_result_digest"
                ],
            }
        )
        private_result["full_result_digest"] = canonical_digest(
            {
                key: deepcopy(value)
                for key, value in private_result.items()
                if key != "full_result_digest"
            }
        )
    _write_json(private_output, private_result, exclusive=True)
    public_body = {
        "schema_version": SUBMISSION_SUCCESSOR_ZERO_SCHEMA,
        "status": private_result["status"],
        "recorded_at": private_result["recorded_at"],
        "attempt_id": attempt_id,
        "predecessor_public_ref": private_result["predecessor_public_ref"],
        "predecessor_public_sha256": private_result["predecessor_public_sha256"],
        "predecessor_private_ref": private_result["predecessor_private_ref"],
        "predecessor_private_sha256": private_result["predecessor_private_sha256"],
        "role_proofs": role_proofs,
        "counterevidence_workpaper_digest": counter_workpaper_digest,
        "supply_required_request_ids": supply_required_request_ids,
        "resume_role_proofs": resume_role_proofs,
        "resume_frontier": resume_frontier,
        "checks": checks,
        "execution": private_result["execution"],
        "claims": private_result["claims"],
        "private_result_ref": _relative(private_output),
        "private_result_sha256": _sha256(private_output),
    }
    if resume_enabled:
        public_body.update(
            {
                "resume_public_ref": private_result["resume_public_ref"],
                "resume_public_sha256": private_result[
                    "resume_public_sha256"
                ],
                "resume_public_result_digest": private_result[
                    "resume_public_result_digest"
                ],
                "resume_private_ref": private_result["resume_private_ref"],
                "resume_private_sha256": private_result[
                    "resume_private_sha256"
                ],
                "resume_private_full_result_digest": private_result[
                    "resume_private_full_result_digest"
                ],
            }
        )
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_json(public_output, public, exclusive=True)
    return public


def run_zero_call_submission_repair_resume(
    *,
    attempt_id: str,
    predecessor_public_path: Path,
    predecessor_private_path: Path,
    resume_public_path: Path,
    resume_private_path: Path,
    private_output: Path,
    public_output: Path,
) -> dict[str, Any]:
    """Prove the exact first repair frontier after the R4 local failure."""

    predecessor_public = _read_json(predecessor_public_path)
    predecessor = _read_json(predecessor_private_path)
    resume_public = _read_json(resume_public_path)
    resume_private = _read_json(resume_private_path)
    resume_authority_path = _resolve_repo_ref(
        str(resume_public.get("authority_ref") or "")
    )
    resume_authority = _read_json(resume_authority_path)
    if not (
        predecessor_public.get("result_digest")
        == canonical_digest(
            {
                key: deepcopy(value)
                for key, value in predecessor_public.items()
                if key != "result_digest"
            }
        )
        and predecessor.get("full_result_digest")
        == canonical_digest(
            {
                key: deepcopy(value)
                for key, value in predecessor.items()
                if key != "full_result_digest"
            }
        )
        and predecessor_public.get("private_full_result_sha256")
        == _sha256(predecessor_private_path)
        and resume_public.get("result_digest")
        == canonical_digest(
            {
                key: deepcopy(value)
                for key, value in resume_public.items()
                if key != "result_digest"
            }
        )
        and resume_private.get("full_result_digest")
        == canonical_digest(
            {
                key: deepcopy(value)
                for key, value in resume_private.items()
                if key != "full_result_digest"
            }
        )
        and resume_public.get("private_full_result_sha256")
        == _sha256(resume_private_path)
        and resume_public.get("status")
        == "terminal_partial_local_contract_failure_preserved"
        and resume_private.get("status")
        == "terminal_partial_local_contract_failure_preserved"
        and resume_private.get("authority_sha256")
        == _sha256(resume_authority_path)
        and resume_private.get("failure", {}).get("code")
        == "dynamic_single_unit_workpaper_submission_context_invalid"
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_repair_resume_predecessor_invalid"
        )
    manifest = _validate_resume_capture_manifest(
        resume_private.get("capture_manifest") or ()
    )
    if not (
        len(manifest) == 17
        and all(row["reusable"] for row in manifest)
        and len({str(row["attempt_id"]) for row in manifest}) == 17
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_repair_resume_manifest_invalid"
        )

    policy, programs = _compile_role_programs()
    by_agent = role_program_by_agent(programs)
    source_refs = policy["source_refs"]
    runtime_paths = resolve_runtime_paths(ROOT)
    permissions = frozenset({"current_product:read"})
    retrieval_principal = ResearchRetrievalPrincipal("current", permissions)
    retrieval = ResearchRetrievalService.from_runtime_paths(ROOT, runtime_paths)
    evidence_pack = ResearchEvidencePackService.from_runtime_paths(
        ROOT, runtime_paths
    ).get_case(
        "DELL", ResearchEvidencePackPrincipal("current", permissions)
    )
    truth_policy = _read_json(source_refs["truth_spine_policy_ref"])
    consumer_policy = _read_json(source_refs["consumer_policy_ref"])
    task_quantitative = _read_json(source_refs["task_quantitative_result_ref"])
    authority_bound = resume_authority["bound_inputs"]
    research_profile = load_agent_transport_profile(
        _read_json(authority_bound["provider_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _read_json(authority_bound["submission_profile_ref"])
    )
    predecessor_by_agent = {
        str(row["agent_id"]): row for row in predecessor["role_bundles"]
    }

    def _forbid_provider(**kwargs: Any) -> AgentToolStepResult:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_repair_resume_unexpected_provider:"
            + str(kwargs.get("attempt_id") or "")
        )

    replay_recorded_at = _resume_replay_recorded_at(manifest)
    role_bundles: dict[str, dict[str, Any]] = {}
    for agent_id in SPECIALIST_AGENT_IDS:
        role_bundles[agent_id] = _execute_submission_successor_role(
            role_program=by_agent[agent_id],
            predecessor_bundle=predecessor_by_agent[agent_id],
            predecessor_recorded_at=str(predecessor["recorded_at"]),
            run_id=f"{attempt_id}-REQUAL",
            attempt_prefix=f"{attempt_id}-REQUAL",
            recorded_at=replay_recorded_at,
            capture_root=private_output.parent / "forbidden-captures",
            research_profile=research_profile,
            submission_profile=submission_profile,
            retrieval=retrieval,
            retrieval_principal=retrieval_principal,
            evidence_pack=evidence_pack,
            truth_policy=truth_policy,
            consumer_policy=consumer_policy,
            task_quantitative=task_quantitative,
            research_executor=_forbid_provider,
            submission_executor=_forbid_provider,
            resume_capture_manifest=manifest,
            session_seed_run_id=str(resume_private["run_id"]),
        )
    captured_workpapers = {
        str(row["agent_id"]): row
        for row in _resume_lead_input_workpapers(manifest, round_index=1)
    }
    for agent_id in SPECIALIST_AGENT_IDS:
        exact_workpaper = _validate_resume_workpaper_authority(
            captured_workpapers[agent_id],
            context=role_bundles[agent_id]["workpaper_context"],
            expected_agent_id=agent_id,
        )
        role_bundles[agent_id]["workpaper"] = exact_workpaper
    final_workpapers = [
        deepcopy(role_bundles[agent_id]["workpaper"])
        for agent_id in SPECIALIST_AGENT_IDS
    ]
    lead_session, lead_events = _create_lead_session(
        run_id=str(resume_private["run_id"]),
        workpapers=final_workpapers,
        recorded_at=replay_recorded_at,
    )
    first = _execute_submission_successor_lead_round(
        workpapers=final_workpapers,
        local_failure_receipts=(),
        session=lead_session,
        events=lead_events,
        research_profile=research_profile,
        submission_profile=submission_profile,
        capture_root=private_output.parent / "forbidden-captures",
        run_id=f"{attempt_id}-REQUAL",
        attempt_prefix=f"{attempt_id}-REQUAL",
        round_index=1,
        recorded_at=replay_recorded_at,
        research_executor=_forbid_provider,
        submission_executor=_forbid_provider,
        resume_capture_manifest=manifest,
    )
    accepted = set(first["decision"]["accepted_challenge_ids"])
    challenge_by_id = {
        str(row["challenge_id"]): row for row in first["challenge_catalog"]
    }
    by_target: dict[str, list[dict[str, Any]]] = {}
    for challenge_id in sorted(accepted):
        challenge = challenge_by_id[challenge_id]
        by_target.setdefault(str(challenge["target_agent_id"]), []).append(
            challenge
        )
    ordered_targets = sorted(by_target)
    if len(ordered_targets) != 3:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_repair_resume_targets_invalid"
        )
    first_target = ordered_targets[0]
    receipts = [
        compile_cross_role_feedback_receipt(
            target_session_id=str(
                role_bundles[first_target]["session"]["session_id"]
            ),
            challenge=challenge,
            created_at=replay_recorded_at,
        )
        for challenge in by_target[first_target]
    ]
    repair_context = compile_workpaper_repair_context(
        context=role_bundles[first_target]["workpaper_context"],
        prior_workpaper=role_bundles[first_target]["workpaper"],
        feedback_receipts=receipts,
    )
    repair_view = compile_workpaper_submission_view(repair_context)

    class _RepairFrontierReached(RuntimeError):
        pass

    frontier_attempts: list[str] = []

    def _repair_frontier(**kwargs: Any) -> AgentToolStepResult:
        frontier_attempts.append(str(kwargs.get("attempt_id") or ""))
        raise _RepairFrontierReached(frontier_attempts[-1])

    try:
        _execute_submission_successor_role_repair(
            role_bundle=role_bundles[first_target],
            challenges=by_target[first_target],
            research_profile=research_profile,
            submission_profile=submission_profile,
            capture_root=private_output.parent / "forbidden-captures",
            run_id=f"{attempt_id}-FRONTIER",
            attempt_prefix=f"{attempt_id}-FRONTIER",
            repair_index=1,
            recorded_at=replay_recorded_at,
            research_executor=_repair_frontier,
            submission_executor=_forbid_provider,
            resume_capture_manifest=manifest,
        )
    except _RepairFrontierReached:
        pass
    expected_suffix = (
        first_target.split("::")[-1].lower().replace("_", "-")
        + "-repair-r1-draft"
    )
    checks = {
        "R1_and_R4_public_private_digests_bound": True,
        "seventeen_completed_captures_reusable": len(manifest) == 17,
        "six_specialist_workpapers_reconstructed_without_provider": (
            len(role_bundles) == 6
            and all(
                bundle["status"] == "completed_contract_valid"
                and bundle["execution"]["provider_calls_attempted"] == 0
                for bundle in role_bundles.values()
            )
        ),
        "lead_R1_decision_reconstructed_without_provider": (
            _provider_attempt_count(lead_events) == 0
            and len(first["decision"]["accepted_challenge_ids"]) == 3
        ),
        "three_material_role_repairs_selected": len(ordered_targets) == 3,
        "repair_context_carries_prior_workpaper_and_feedback": (
            repair_view.get("repair_state", {}).get("prior_workpaper", {}).get(
                "workpaper_digest"
            )
            == role_bundles[first_target]["workpaper"]["workpaper_digest"]
            and repair_view.get("repair_state", {}).get(
                "accepted_feedback_refs"
            )
            == [str(row["feedback_id"]) for row in receipts]
        ),
        "first_new_provider_frontier_is_exact": (
            len(frontier_attempts) == 1
            and frontier_attempts[0].endswith(expected_suffix)
        ),
        "repair_resume_budget_compiles_to_eight_calls": (
            expected_submission_repair_resume_budget()[
                "maximum_new_model_calls"
            ]
            == 8
        ),
        "zero_model_network_paid_calls": True,
    }
    if not all(checks.values()):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_repair_resume_zero_call_not_proven"
        )
    private_body = {
        "schema_version": SUBMISSION_SUCCESSOR_ZERO_SCHEMA,
        "status": "submission_successor_repair_resume_zero_call_proven",
        "recorded_at": _now(),
        "attempt_id": attempt_id,
        "predecessor_public_ref": _relative(predecessor_public_path),
        "predecessor_public_sha256": _sha256(predecessor_public_path),
        "predecessor_private_ref": _relative(predecessor_private_path),
        "predecessor_private_sha256": _sha256(predecessor_private_path),
        "resume_public_ref": _relative(resume_public_path),
        "resume_public_sha256": _sha256(resume_public_path),
        "resume_public_result_digest": resume_public["result_digest"],
        "resume_private_ref": _relative(resume_private_path),
        "resume_private_sha256": _sha256(resume_private_path),
        "resume_private_full_result_digest": resume_private[
            "full_result_digest"
        ],
        "role_proofs": [
            {
                "agent_id": agent_id,
                "workpaper_digest": role_bundles[agent_id]["workpaper"][
                    "workpaper_digest"
                ],
                "provider_calls": role_bundles[agent_id]["execution"][
                    "provider_calls_attempted"
                ],
                "resume_provider_captures_reused": role_bundles[agent_id][
                    "execution"
                ]["resume_provider_captures_reused"],
            }
            for agent_id in SPECIALIST_AGENT_IDS
        ],
        "lead_R1_decision": deepcopy(first["decision"]),
        "repair_targets": ordered_targets,
        "first_repair_target": first_target,
        "first_repair_submission_view_digest": repair_view[
            "submission_view_digest"
        ],
        "frontier": {
            "next_attempt_suffix": expected_suffix,
            "completed_capture_reuse_count": 17,
            "prior_provider_call_repeat_count": 0,
        },
        "checks": checks,
        "execution": {
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "retrieval_calls": 0,
            "deterministic_S1_S2_replays": 1,
        },
        "claims": {
            "R1_or_R4_relabelled_as_success": False,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
    }
    private_result = {
        **private_body,
        "full_result_digest": canonical_digest(private_body),
    }
    _write_json(private_output, private_result, exclusive=True)
    public_body = {
        **{
            key: deepcopy(value)
            for key, value in private_result.items()
            if key != "full_result_digest"
        },
        "private_result_ref": _relative(private_output),
        "private_result_sha256": _sha256(private_output),
    }
    public_body.pop("role_proofs", None)
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_json(public_output, public, exclusive=True)
    return public


def run_submission_successor_live(
    *,
    authority_path: Path,
    research_executor: Callable[..., AgentToolStepResult] = (
        execute_agent_tool_step_exact_once
    ),
    submission_executor: Callable[..., AgentToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority_path = authority_path.resolve()
    authority = _read_json(authority_path)
    paths = validate_submission_successor_authority(
        authority, authority_path=authority_path
    )
    output = dict(authority["output_contract"])
    run_id = str(output["run_id"])
    attempt_prefix = str(output["attempt_prefix"])
    capture_root = _resolve_repo_ref(str(output["capture_root_ref"]))
    private_root = _resolve_repo_ref(str(output["private_output_root_ref"]))
    public_path = _resolve_repo_ref(str(output["public_result_ref"]))
    recorded_at = _now()
    predecessor = _read_json(paths["predecessor_private_ref"])
    resume_enabled = (
        authority.get("schema_version")
        in {
            SUBMISSION_RESUME_AUTHORITY_SCHEMA,
            SUBMISSION_REPAIR_RESUME_AUTHORITY_SCHEMA,
        }
    )
    resume_capture_manifest: list[dict[str, Any]] = []
    resume_private: dict[str, Any] = {}
    if resume_enabled:
        resume_private = _read_json(paths["resume_private_ref"])
        resume_capture_manifest = _validate_resume_capture_manifest(
            resume_private.get("capture_manifest") or ()
        )
    role_replay_recorded_at = (
        _resume_replay_recorded_at(resume_capture_manifest)
        if authority.get("schema_version")
        == SUBMISSION_REPAIR_RESUME_AUTHORITY_SCHEMA
        else recorded_at
    )
    role_session_seed_run_id = (
        str(resume_private["run_id"])
        if authority.get("schema_version")
        == SUBMISSION_REPAIR_RESUME_AUTHORITY_SCHEMA
        else run_id
    )

    policy, programs = _compile_role_programs()
    by_agent = role_program_by_agent(programs)
    source_refs = policy["source_refs"]
    research_profile = load_agent_transport_profile(
        _read_json(paths["provider_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _read_json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_node_profile(
        submission_profile, node_class="workpaper_submission_non_thinking"
    )
    runtime_paths = resolve_runtime_paths(ROOT)
    permissions = frozenset({"current_product:read"})
    retrieval_principal = ResearchRetrievalPrincipal("current", permissions)
    evidence_principal = ResearchEvidencePackPrincipal("current", permissions)
    retrieval = ResearchRetrievalService.from_runtime_paths(ROOT, runtime_paths)
    evidence_pack = ResearchEvidencePackService.from_runtime_paths(
        ROOT, runtime_paths
    ).get_case("DELL", evidence_principal)
    if evidence_pack.get("pack_payload_digest") != authority["bound_inputs"].get(
        "current_evidence_pack_payload_digest"
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_evidence_pack_drift"
        )
    truth_policy = _read_json(source_refs["truth_spine_policy_ref"])
    consumer_policy = _read_json(source_refs["consumer_policy_ref"])
    task_quantitative = _read_json(source_refs["task_quantitative_result_ref"])
    if task_quantitative.get("result_digest") != authority["bound_inputs"].get(
        "task_quantitative_result_digest"
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_quantitative_drift"
        )
    cuda = required_cuda_fp16_receipt(
        purpose=(
            "DELL current dynamic multi-agent capture-bound submission successor"
        )
    )
    predecessor_by_agent = {
        str(row["agent_id"]): row for row in predecessor["role_bundles"]
    }
    role_bundles: dict[str, dict[str, Any]] = {}
    for agent_id in SPECIALIST_AGENT_IDS:
        role_bundles[agent_id] = _execute_submission_successor_role(
            role_program=by_agent[agent_id],
            predecessor_bundle=predecessor_by_agent[agent_id],
            predecessor_recorded_at=str(predecessor["recorded_at"]),
            run_id=run_id,
            attempt_prefix=attempt_prefix,
            recorded_at=role_replay_recorded_at,
            capture_root=capture_root,
            research_profile=research_profile,
            submission_profile=submission_profile,
            retrieval=retrieval,
            retrieval_principal=retrieval_principal,
            evidence_pack=evidence_pack,
            truth_policy=truth_policy,
            consumer_policy=consumer_policy,
            task_quantitative=task_quantitative,
            research_executor=research_executor,
            submission_executor=submission_executor,
            resume_capture_manifest=resume_capture_manifest,
            session_seed_run_id=role_session_seed_run_id,
        )
    if repair_resume_enabled := (
        authority.get("schema_version")
        == SUBMISSION_REPAIR_RESUME_AUTHORITY_SCHEMA
    ):
        captured_workpapers = {
            str(row["agent_id"]): row
            for row in _resume_lead_input_workpapers(
                resume_capture_manifest, round_index=1
            )
        }
        for agent_id in SPECIALIST_AGENT_IDS:
            exact_workpaper = _validate_resume_workpaper_authority(
                captured_workpapers[agent_id],
                context=role_bundles[agent_id]["workpaper_context"],
                expected_agent_id=agent_id,
            )
            role_bundles[agent_id]["workpaper"] = exact_workpaper

    final_workpapers = [
        deepcopy(role_bundles[agent_id]["workpaper"])
        for agent_id in SPECIALIST_AGENT_IDS
    ]
    lead_session, lead_events = _create_lead_session(
        run_id=role_session_seed_run_id,
        workpapers=final_workpapers,
        recorded_at=role_replay_recorded_at,
    )
    repairs: list[dict[str, Any]] = []
    first = _execute_submission_successor_lead_round(
        workpapers=final_workpapers,
        local_failure_receipts=(),
        session=lead_session,
        events=lead_events,
        research_profile=research_profile,
        submission_profile=submission_profile,
        capture_root=capture_root,
        run_id=run_id,
        attempt_prefix=attempt_prefix,
        round_index=1,
        recorded_at=role_replay_recorded_at,
        research_executor=research_executor,
        submission_executor=submission_executor,
        resume_capture_manifest=resume_capture_manifest,
    )
    lead_rounds = [first]
    accepted = set(first["decision"]["accepted_challenge_ids"])
    challenge_by_id = {
        str(row["challenge_id"]): row for row in first["challenge_catalog"]
    }
    accepted_rows = [challenge_by_id[value] for value in sorted(accepted)]
    by_target: dict[str, list[dict[str, Any]]] = {}
    for challenge in accepted_rows:
        by_target.setdefault(str(challenge["target_agent_id"]), []).append(
            challenge
        )
    budget = (
        expected_submission_repair_resume_budget()
        if repair_resume_enabled
        else (
            expected_submission_resume_budget()
            if resume_enabled
            else expected_submission_successor_budget()
        )
    )
    if len(by_target) > budget["maximum_role_repairs"]:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_repair_budget_exceeded"
        )
    for repair_index, (target, challenges) in enumerate(
        sorted(by_target.items()), start=1
    ):
        repair = _execute_submission_successor_role_repair(
            role_bundle=role_bundles[target],
            challenges=challenges,
            research_profile=research_profile,
            submission_profile=submission_profile,
            capture_root=capture_root,
            run_id=run_id,
            attempt_prefix=attempt_prefix,
            repair_index=repair_index,
            recorded_at=recorded_at,
            research_executor=research_executor,
            submission_executor=submission_executor,
            resume_capture_manifest=resume_capture_manifest,
        )
        repairs.append(repair)
        role_bundles[target]["workpaper"] = repair["repaired_workpaper"]
        role_bundles[target]["events"] = repair["continued_events"]
    final_workpapers = [
        deepcopy(role_bundles[agent_id]["workpaper"])
        for agent_id in SPECIALIST_AGENT_IDS
    ]
    if repairs:
        lead_rounds.append(
            _execute_submission_successor_lead_round(
                workpapers=final_workpapers,
                local_failure_receipts=(),
                session=lead_session,
                events=lead_events,
                research_profile=research_profile,
                submission_profile=submission_profile,
                capture_root=capture_root,
                run_id=run_id,
                attempt_prefix=attempt_prefix,
                round_index=2,
                recorded_at=recorded_at,
                research_executor=research_executor,
                submission_executor=submission_executor,
                resume_capture_manifest=resume_capture_manifest,
            )
        )
    last_decision = lead_rounds[-1]["decision"]
    frontier = (
        "proceed_to_independent_evaluation"
        if (
            not last_decision["accepted_challenge_ids"]
            and last_decision["next_state"] == "proceed_to_evaluation"
        )
        else (
            "lead_paused_for_data_or_tool"
            if last_decision["next_state"] == "pause_for_data_or_tool"
            else "bounded_lead_frontier_requires_successor_or_data"
        )
    )
    lead_bundle = {
        "session": lead_session,
        "events": lead_events,
        "rounds": lead_rounds,
        "failure": {"phase": "", "code": "", "capture_ref": ""},
    }
    provider_calls = sum(
        _provider_attempt_count(bundle["events"])
        for bundle in role_bundles.values()
    ) + _provider_attempt_count(lead_events)
    new_rounds = sum(
        int(bundle["execution"]["new_retrieval_rounds"])
        for bundle in role_bundles.values()
    )
    predecessor_request_ids = {
        str(value)
        for row in predecessor["role_bundles"]
        for value in row["execution"]["request_ids_executed"]
    }
    successor_request_ids = {
        str(value)
        for bundle in role_bundles.values()
        for value in bundle["execution"]["request_ids_executed"]
    }
    new_request_ids = sorted(successor_request_ids - predecessor_request_ids)
    if not (
        provider_calls <= budget["maximum_new_model_calls"]
        and new_rounds <= budget["maximum_new_retrieval_rounds"]
        and len(new_request_ids) <= budget["maximum_new_s1_s2_requests"]
        and len(lead_rounds) <= budget["maximum_lead_rounds"]
        and len(repairs) <= budget["maximum_role_repairs"]
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_submission_successor_budget_invalid"
        )
    succeeded = frontier == "proceed_to_independent_evaluation"
    status = (
        "completed_contract_valid_assessment_pending"
        if succeeded
        else "completed_bounded_frontier_preserved"
    )
    full_body = {
        "schema_version": SUBMISSION_SUCCESSOR_FULL_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha256(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "predecessor_public_ref": authority["bound_inputs"][
            "predecessor_public_ref"
        ],
        "predecessor_private_ref": authority["bound_inputs"][
            "predecessor_private_ref"
        ],
        "resume_public_ref": (
            authority["bound_inputs"]["resume_public_ref"]
            if resume_enabled
            else ""
        ),
        "resume_private_ref": (
            authority["bound_inputs"]["resume_private_ref"]
            if resume_enabled
            else ""
        ),
        "role_bundles": [
            role_bundles[agent_id] for agent_id in SPECIALIST_AGENT_IDS
        ],
        "lead_bundle": lead_bundle,
        "repairs": repairs,
        "final_workpapers": final_workpapers,
        "frontier": frontier,
        "cuda_receipt": cuda,
        "execution": {
            "new_provider_calls_attempted": provider_calls,
            "maximum_new_provider_calls": budget["maximum_new_model_calls"],
            "predecessor_provider_calls_reused": sum(
                int(
                    predecessor_by_agent[agent_id]["execution"][
                        "provider_calls_attempted"
                    ]
                )
                for agent_id in SPECIALIST_AGENT_IDS
            ),
            "resume_provider_captures_reused": sum(
                int(
                    role_bundles[agent_id]["execution"].get(
                        "resume_provider_captures_reused", 0
                    )
                )
                for agent_id in SPECIALIST_AGENT_IDS
            )
            + sum(
                len(row.get("source_capture_receipts") or ())
                for row in lead_rounds
            )
            + sum(
                len(row.get("source_capture_receipts") or ())
                for row in repairs
            ),
            "specialist_sessions_completed": 6,
            "new_retrieval_rounds": new_rounds,
            "new_request_ids": new_request_ids,
            "lead_rounds_executed": len(lead_rounds),
            "role_repairs_executed": len(repairs),
            "external_source_network_calls": 0,
            "candidate_promotions": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "claims": {
            "R1_preserved_immutable": True,
            "six_independent_specialists_completed": True,
            "natural_lead_coordination_completed": True,
            "capture_bound_continuation_used": True,
            "partial_submission_successor_captures_reused": resume_enabled,
            "model_research_judgment_and_local_control_separated": True,
            "current_S1_S2_new_requests": len(new_request_ids),
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    _write_json(private_root / "full_result.json", full, exclusive=True)
    role_summaries = [
        {
            "agent_id": agent_id,
            "status": role_bundles[agent_id]["status"],
            "provider_calls_attempted": role_bundles[agent_id]["execution"][
                "provider_calls_attempted"
            ],
            "predecessor_provider_calls_reused": role_bundles[agent_id][
                "execution"
            ]["predecessor_provider_calls_reused"],
            "resume_provider_captures_reused": role_bundles[agent_id][
                "execution"
            ].get("resume_provider_captures_reused", 0),
            "new_retrieval_rounds": role_bundles[agent_id]["execution"][
                "new_retrieval_rounds"
            ],
            "request_ids_executed": role_bundles[agent_id]["execution"][
                "request_ids_executed"
            ],
            "workpaper_source": role_bundles[agent_id]["workpaper_source"],
            "workpaper": deepcopy(role_bundles[agent_id]["workpaper"]),
        }
        for agent_id in SPECIALIST_AGENT_IDS
    ]
    public_body = {
        "schema_version": SUBMISSION_SUCCESSOR_LIVE_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "model": research_profile.model,
        "frontier": frontier,
        "execution": full["execution"],
        "role_summaries": role_summaries,
        "lead_summary": {
            "round_count": len(lead_rounds),
            "decisions": [
                deepcopy(row["decision"]) for row in lead_rounds
            ],
        },
        "repair_summaries": [
            {
                "agent_id": row["agent_id"],
                "challenge_ids": row["challenge_ids"],
                "prior_workpaper_digest": row["prior_workpaper_digest"],
                "repaired_workpaper_digest": row["repaired_workpaper"][
                    "workpaper_digest"
                ],
                "authority_refs_unchanged": row[
                    "authority_refs_unchanged"
                ],
            }
            for row in repairs
        ],
        "claims": full["claims"],
        "acceptance": {
            "dynamic_multi_agent_contract_pass": succeeded,
            "L1_assessment_pending": succeeded,
            "eight_dimension_content_assessment_pending": succeeded,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "private_full_result_ref": _relative(private_root / "full_result.json"),
        "private_full_result_sha256": _sha256(private_root / "full_result.json"),
        "known_boundary": authority["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_json(public_path, public, exclusive=True)
    return public


def _load_content_repair_inputs(
    *,
    predecessor_public_path: Path,
    predecessor_private_path: Path,
    assessment_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    public = _read_json(predecessor_public_path)
    private = _read_json(predecessor_private_path)
    assessment = _read_json(assessment_path)
    public_body = {
        key: deepcopy(value)
        for key, value in public.items()
        if key != "result_digest"
    }
    private_body = {
        key: deepcopy(value)
        for key, value in private.items()
        if key != "full_result_digest"
    }
    if not (
        public.get("status") == "completed_contract_valid_assessment_pending"
        and public.get("result_digest") == canonical_digest(public_body)
        and private.get("status") == "completed_contract_valid_assessment_pending"
        and private.get("full_result_digest") == canonical_digest(private_body)
        and public.get("private_full_result_sha256")
        == _sha256(predecessor_private_path)
        and assessment.get("source_result_sha256")
        == _sha256(predecessor_public_path)
        and assessment.get("private_full_result_sha256")
        == _sha256(predecessor_private_path)
        and assessment.get("source_result_digest") == public.get("result_digest")
        and assessment.get("private_full_result_digest")
        == private.get("full_result_digest")
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_content_repair_predecessor_invalid"
        )
    public_workpapers = {
        str(row["agent_id"]): row["workpaper"]
        for row in public.get("role_summaries") or ()
    }
    private_workpapers = {
        str(row["agent_id"]): row["workpaper"]
        for row in private.get("role_bundles") or ()
    }
    if not (
        set(public_workpapers) == set(SPECIALIST_AGENT_IDS)
        and set(private_workpapers) == set(SPECIALIST_AGENT_IDS)
        and all(
            public_workpapers[agent_id].get("workpaper_digest")
            == private_workpapers[agent_id].get("workpaper_digest")
            for agent_id in SPECIALIST_AGENT_IDS
        )
    ):
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_content_repair_workpaper_binding_invalid"
        )
    return public, private, assessment


def run_zero_call_content_repair(
    *,
    attempt_id: str,
    predecessor_public_path: Path,
    predecessor_private_path: Path,
    assessment_path: Path,
    private_output: Path,
    public_output: Path,
) -> dict[str, Any]:
    """Prove the independent-assessment repair frontier without Provider calls."""

    predecessor_public, predecessor, assessment = _load_content_repair_inputs(
        predecessor_public_path=predecessor_public_path,
        predecessor_private_path=predecessor_private_path,
        assessment_path=assessment_path,
    )
    workpapers = [deepcopy(row) for row in predecessor["final_workpapers"]]
    challenges = compile_independent_content_challenges(
        assessment=assessment,
        workpapers=workpapers,
    )
    by_target: dict[str, list[dict[str, Any]]] = {}
    for row in challenges:
        by_target.setdefault(str(row["target_agent_id"]), []).append(row)
    predecessor_by_agent = {
        str(row["agent_id"]): row for row in predecessor["role_bundles"]
    }
    role_proofs: list[dict[str, Any]] = []
    for agent_id, rows in sorted(by_target.items()):
        bundle = predecessor_by_agent[agent_id]
        rebound, migration = rebind_workpaper_context_semantic_rules(
            bundle["workpaper_context"], expected_agent_id=agent_id
        )
        receipts = [
            compile_cross_role_feedback_receipt(
                target_session_id=str(bundle["session"]["session_id"]),
                challenge=challenge,
                created_at=str(predecessor["recorded_at"]),
            )
            for challenge in rows
        ]
        repair_context = compile_workpaper_repair_context(
            context=rebound,
            prior_workpaper=bundle["workpaper"],
            feedback_receipts=receipts,
        )
        submission_view = compile_workpaper_submission_view(repair_context)
        role_proofs.append(
            {
                "agent_id": agent_id,
                "finding_ids": [str(row["assessment_issue_id"]) for row in rows],
                "challenge_ids": [str(row["challenge_id"]) for row in rows],
                "feedback_ids": [str(row["feedback_id"]) for row in receipts],
                "prior_workpaper_digest": str(
                    bundle["workpaper"]["workpaper_digest"]
                ),
                "source_context_digest": migration["source_context_digest"],
                "rebound_context_digest": migration["rebound_context_digest"],
                "rule_migration_receipt_digest": migration["receipt_digest"],
                "repair_context_digest": repair_context["context_digest"],
                "submission_view_digest": submission_view[
                    "submission_view_digest"
                ],
                "authority_expanded": False,
            }
        )
    target_set = set(by_target)
    checks = {
        "predecessor_public_and_private_digests_valid": True,
        "assessment_bound_to_exact_R5_result": True,
        "seven_material_findings_compiled": len(challenges) == 7,
        "exact_five_role_target_set": target_set
        == {
            "AGENT::DEMAND_QUALITY",
            "AGENT::OPERATING_PERFORMANCE",
            "AGENT::VALUE_CAPTURE",
            "AGENT::CASH_CONVERSION",
            "AGENT::COUNTEREVIDENCE",
        },
        "supply_role_not_repaired": "AGENT::SUPPLY_RELATIONSHIP" not in target_set,
        "all_repair_contexts_and_submission_views_compile": len(role_proofs) == 5,
        "semantic_rules_migrated_without_authority_expansion": all(
            not row["authority_expanded"] for row in role_proofs
        ),
        "zero_model_provider_network_or_paid_calls": True,
        "writer_publication_S3_acceptance_and_release_forbidden": True,
    }
    status = (
        "content_repair_zero_call_proven"
        if all(checks.values())
        else "content_repair_zero_call_failed"
    )
    private_body = {
        "schema_version": CONTENT_REPAIR_ZERO_SCHEMA,
        "status": status,
        "recorded_at": _now(),
        "attempt_id": attempt_id,
        "predecessor_public_ref": _relative(predecessor_public_path),
        "predecessor_public_sha256": _sha256(predecessor_public_path),
        "predecessor_public_result_digest": predecessor_public["result_digest"],
        "predecessor_private_ref": _relative(predecessor_private_path),
        "predecessor_private_sha256": _sha256(predecessor_private_path),
        "predecessor_private_full_result_digest": predecessor[
            "full_result_digest"
        ],
        "assessment_ref": _relative(assessment_path),
        "assessment_sha256": _sha256(assessment_path),
        "challenges": challenges,
        "role_proofs": role_proofs,
        "checks": checks,
        "execution": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "new_s1_s2_requests": 0,
            "candidate_promotions": 0,
        },
        "next_exact_frontier": "five_role_repair_then_one_lead_round",
    }
    private = {
        **private_body,
        "full_result_digest": canonical_digest(private_body),
    }
    _write_json(private_output, private, exclusive=True)
    public_body = {
        "schema_version": CONTENT_REPAIR_ZERO_SCHEMA,
        "status": status,
        "recorded_at": private["recorded_at"],
        "attempt_id": attempt_id,
        "predecessor_public_ref": private["predecessor_public_ref"],
        "predecessor_public_sha256": private["predecessor_public_sha256"],
        "predecessor_public_result_digest": private[
            "predecessor_public_result_digest"
        ],
        "assessment_ref": private["assessment_ref"],
        "assessment_sha256": private["assessment_sha256"],
        "role_proofs": role_proofs,
        "checks": checks,
        "execution": private["execution"],
        "private_result_ref": _relative(private_output),
        "private_result_sha256": _sha256(private_output),
        "next_exact_frontier": private["next_exact_frontier"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_json(public_output, public, exclusive=True)
    return public


def run_content_repair_live(
    *,
    authority_path: Path,
    research_executor: Callable[..., AgentToolStepResult] = (
        execute_agent_tool_step_exact_once
    ),
    submission_executor: Callable[..., AgentToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    """Repair only the five assessment-owned roles and run one fresh Lead review."""

    authority_path = authority_path.resolve()
    authority = _read_json(authority_path)
    paths = validate_content_repair_authority(
        authority, authority_path=authority_path
    )
    _, predecessor, assessment = _load_content_repair_inputs(
        predecessor_public_path=paths["predecessor_public_ref"],
        predecessor_private_path=paths["predecessor_private_ref"],
        assessment_path=paths["assessment_ref"],
    )
    output = dict(authority["output_contract"])
    run_id = str(output["run_id"])
    attempt_prefix = str(output["attempt_prefix"])
    capture_root = _resolve_repo_ref(str(output["capture_root_ref"]))
    private_root = _resolve_repo_ref(str(output["private_output_root_ref"]))
    public_path = _resolve_repo_ref(str(output["public_result_ref"]))
    recorded_at = _now()
    research_profile = load_agent_transport_profile(
        _read_json(paths["provider_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _read_json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_node_profile(
        submission_profile, node_class="workpaper_submission_non_thinking"
    )
    role_bundles = {
        str(row["agent_id"]): deepcopy(dict(row))
        for row in predecessor["role_bundles"]
    }
    challenges = compile_independent_content_challenges(
        assessment=assessment,
        workpapers=[role_bundles[key]["workpaper"] for key in SPECIALIST_AGENT_IDS],
    )
    by_target: dict[str, list[dict[str, Any]]] = {}
    for row in challenges:
        by_target.setdefault(str(row["target_agent_id"]), []).append(row)
    if len(by_target) != expected_content_repair_budget()["maximum_role_repairs"]:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_content_repair_target_count_invalid"
        )
    migrations: list[dict[str, Any]] = []
    for agent_id in sorted(by_target):
        rebound, receipt = rebind_workpaper_context_semantic_rules(
            role_bundles[agent_id]["workpaper_context"],
            expected_agent_id=agent_id,
        )
        role_bundles[agent_id]["workpaper_context"] = rebound
        migrations.append(receipt)
    repairs: list[dict[str, Any]] = []
    lead_bundle: dict[str, Any] = {}
    frontier = "content_repairs_in_progress"
    failure = {"phase": "", "code": "", "capture_ref": ""}
    private_root.mkdir(parents=True, exist_ok=False)
    checkpoint_path = private_root / "progress_checkpoint.json"

    def _checkpoint() -> None:
        body = {
            "schema_version": "fin_ia_s3_content_repair_progress_checkpoint_v1_0",
            "recorded_at": recorded_at,
            "run_id": run_id,
            "completed_repair_agents": [row["agent_id"] for row in repairs],
            "repair_workpaper_digests": [
                row["repaired_workpaper"]["workpaper_digest"] for row in repairs
            ],
            "frontier": frontier,
            "failure": failure,
        }
        _write_json(
            checkpoint_path,
            {**body, "checkpoint_digest": canonical_digest(body)},
            exclusive=False,
        )

    try:
        for repair_index, (agent_id, rows) in enumerate(
            sorted(by_target.items()), start=1
        ):
            repair = _execute_submission_successor_role_repair(
                role_bundle=role_bundles[agent_id],
                challenges=rows,
                research_profile=research_profile,
                submission_profile=submission_profile,
                capture_root=capture_root,
                run_id=run_id,
                attempt_prefix=attempt_prefix,
                repair_index=repair_index,
                recorded_at=recorded_at,
                research_executor=research_executor,
                submission_executor=submission_executor,
            )
            repairs.append(repair)
            role_bundles[agent_id]["workpaper"] = repair["repaired_workpaper"]
            role_bundles[agent_id]["events"] = repair["continued_events"]
            frontier = f"repair_completed:{agent_id}"
            _checkpoint()
        final_workpapers = [
            deepcopy(role_bundles[agent_id]["workpaper"])
            for agent_id in SPECIALIST_AGENT_IDS
        ]
        lead_session, lead_events = _create_lead_session(
            run_id=run_id,
            workpapers=final_workpapers,
            recorded_at=recorded_at,
        )
        lead_round = _execute_submission_successor_lead_round(
            workpapers=final_workpapers,
            local_failure_receipts=(),
            session=lead_session,
            events=lead_events,
            research_profile=research_profile,
            submission_profile=submission_profile,
            capture_root=capture_root,
            run_id=run_id,
            attempt_prefix=attempt_prefix,
            round_index=1,
            recorded_at=recorded_at,
            research_executor=research_executor,
            submission_executor=submission_executor,
        )
        lead_bundle = {
            "session": lead_session,
            "events": lead_events,
            "rounds": [lead_round],
            "failure": failure,
        }
        decision = lead_round["decision"]
        frontier = (
            "proceed_to_independent_reassessment"
            if not decision["accepted_challenge_ids"]
            and decision["next_state"] == "proceed_to_evaluation"
            else (
                "lead_paused_for_data_or_tool"
                if decision["next_state"] == "pause_for_data_or_tool"
                else "bounded_lead_frontier_requires_successor"
            )
        )
        status = (
            "completed_contract_valid_reassessment_pending"
            if frontier == "proceed_to_independent_reassessment"
            else "completed_bounded_frontier_preserved"
        )
    except (ModelGatewayError, DynamicMultiAgentLoopError, DynamicSingleUnitLoopError) as exc:
        failure = {
            "phase": (
                "provider_transport_or_response"
                if isinstance(exc, ModelGatewayError)
                else "local_contract_or_validation"
            ),
            "code": str(getattr(exc, "code", str(exc))),
            "capture_ref": str(getattr(exc, "capture_ref", "") or ""),
        }
        frontier = "terminal_content_repair_failure_preserved"
        status = "terminal_partial_content_repair_failure_preserved"
        final_workpapers = [
            deepcopy(role_bundles[agent_id]["workpaper"])
            for agent_id in SPECIALIST_AGENT_IDS
        ]
        _checkpoint()
    provider_calls = sum(
        len(row.get("provider_steps") or ()) for row in repairs
    ) + sum(
        len(row.get("provider_steps") or ())
        for row in lead_bundle.get("rounds") or ()
    )
    budget = expected_content_repair_budget()
    if provider_calls > budget["maximum_new_model_calls"]:
        raise DynamicMultiAgentLoopError(
            "dynamic_multi_agent_content_repair_budget_exceeded"
        )
    full_body = {
        "schema_version": CONTENT_REPAIR_FULL_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha256(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "predecessor_public_ref": authority["bound_inputs"][
            "predecessor_public_ref"
        ],
        "predecessor_private_ref": authority["bound_inputs"][
            "predecessor_private_ref"
        ],
        "assessment_ref": authority["bound_inputs"]["assessment_ref"],
        "semantic_rule_migration_receipts": migrations,
        "repairs": repairs,
        "lead_bundle": lead_bundle,
        "final_workpapers": final_workpapers,
        "frontier": frontier,
        "failure": failure,
        "execution": {
            "new_provider_calls_attempted": provider_calls,
            "maximum_new_provider_calls": budget["maximum_new_model_calls"],
            "role_repairs_executed": len(repairs),
            "lead_rounds_executed": len(lead_bundle.get("rounds") or ()),
            "new_s1_s2_requests": 0,
            "new_retrieval_rounds": 0,
            "external_source_network_calls": 0,
            "candidate_promotions": 0,
            "retries": 0,
            "fallbacks": 0,
        },
        "claims": {
            "R5_preserved_immutable": True,
            "exact_five_role_repair_scope": True,
            "supply_workpaper_reused_unchanged": role_bundles[
                "AGENT::SUPPLY_RELATIONSHIP"
            ]["workpaper"]["workpaper_digest"]
            == next(
                row["workpaper_digest"]
                for row in predecessor["final_workpapers"]
                if row["agent_id"] == "AGENT::SUPPLY_RELATIONSHIP"
            ),
            "authority_sets_unchanged": all(
                row["authority_refs_unchanged"] for row in repairs
            ),
            "writer_called": False,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    _write_json(private_root / "full_result.json", full, exclusive=True)
    public_body = {
        "schema_version": CONTENT_REPAIR_LIVE_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "model": research_profile.model,
        "frontier": frontier,
        "failure": failure,
        "execution": full["execution"],
        "role_summaries": [
            {
                "agent_id": agent_id,
                "workpaper": deepcopy(role_bundles[agent_id]["workpaper"]),
                "repaired_in_this_attempt": agent_id in by_target,
            }
            for agent_id in SPECIALIST_AGENT_IDS
        ],
        "lead_summary": {
            "round_count": len(lead_bundle.get("rounds") or ()),
            "decisions": [
                deepcopy(row["decision"])
                for row in lead_bundle.get("rounds") or ()
            ],
        },
        "repair_summaries": [
            {
                "agent_id": row["agent_id"],
                "challenge_ids": row["challenge_ids"],
                "prior_workpaper_digest": row["prior_workpaper_digest"],
                "repaired_workpaper_digest": row["repaired_workpaper"][
                    "workpaper_digest"
                ],
                "authority_refs_unchanged": row["authority_refs_unchanged"],
            }
            for row in repairs
        ],
        "claims": full["claims"],
        "acceptance": {
            "content_repair_contract_pass": status
            == "completed_contract_valid_reassessment_pending",
            "independent_L1_L2_reassessment_pending": status
            == "completed_contract_valid_reassessment_pending",
            "writer_entry_eligible": False,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "private_full_result_ref": _relative(private_root / "full_result.json"),
        "private_full_result_sha256": _sha256(private_root / "full_result.json"),
        "known_boundary": authority["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_json(public_path, public, exclusive=True)
    return public


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=(
            "zero-call",
            "zero-call-repair-successor",
            "zero-call-submission-successor",
            "zero-call-submission-repair-resume",
            "zero-call-content-repair",
            "live",
            "live-submission-successor",
            "live-content-repair",
        ),
        default="zero-call",
    )
    parser.add_argument("--attempt-id")
    parser.add_argument("--authority")
    parser.add_argument("--predecessor-private")
    parser.add_argument("--predecessor-public")
    parser.add_argument("--resume-private")
    parser.add_argument("--resume-public")
    parser.add_argument("--assessment")
    parser.add_argument("--private-output")
    parser.add_argument("--public-output")
    args = parser.parse_args()
    live_modes = {"live", "live-submission-successor", "live-content-repair"}
    if args.mode not in live_modes and not args.attempt_id:
        parser.error("--attempt-id is required for zero-call modes")
    runtime_paths = resolve_runtime_paths(ROOT)
    private_output = (
        Path(args.private_output).resolve()
        if args.private_output
        else runtime_paths.workbench_private_root
        / "fin_0_1_3_s3_current_dynamic_multi_agent"
        / str(args.attempt_id or "live-authority-bound")
        / (
            "zero_call_full_result.json"
            if args.mode == "zero-call"
            else (
                "zero_call_repair_successor_full_result.json"
                if args.mode == "zero-call-repair-successor"
                else (
                "zero_call_submission_successor_full_result.json"
                    if args.mode == "zero-call-submission-successor"
                    else (
                        "zero_call_submission_repair_resume_full_result.json"
                        if args.mode == "zero-call-submission-repair-resume"
                        else (
                            "zero_call_content_repair_full_result.json"
                            if args.mode == "zero-call-content-repair"
                            else "full_result.json"
                        )
                    )
                )
            )
        )
    )
    public_default = (
        DEFAULT_PUBLIC
        if args.mode == "zero-call"
        else (
            DEFAULT_REPAIR_PUBLIC
            if args.mode == "zero-call-repair-successor"
            else (
                DEFAULT_SUBMISSION_SUCCESSOR_ZERO_PUBLIC
                if args.mode
                in {
                    "zero-call-submission-successor",
                    "zero-call-submission-repair-resume",
                }
                else (
                    DEFAULT_CONTENT_REPAIR_ZERO_PUBLIC
                    if args.mode == "zero-call-content-repair"
                    else (
                        DEFAULT_CONTENT_REPAIR_LIVE_PUBLIC
                        if args.mode == "live-content-repair"
                        else (
                            DEFAULT_SUBMISSION_SUCCESSOR_LIVE_PUBLIC
                            if args.mode == "live-submission-successor"
                            else DEFAULT_LIVE_PUBLIC
                        )
                    )
                )
            )
        )
    )
    public_output = Path(args.public_output or public_default)
    if not public_output.is_absolute():
        public_output = ROOT / public_output
    if args.mode in live_modes:
        if not args.authority:
            parser.error("--authority is required for live")
        authority_path = Path(args.authority)
        if not authority_path.is_absolute():
            authority_path = ROOT / authority_path
        if args.mode == "live-submission-successor":
            result = run_submission_successor_live(authority_path=authority_path)
        elif args.mode == "live-content-repair":
            result = run_content_repair_live(authority_path=authority_path)
        else:
            result = run_live(authority_path=authority_path)
    elif args.mode == "zero-call":
        result = run_zero_call(
            attempt_id=args.attempt_id,
            private_output=private_output,
            public_output=public_output,
        )
    elif args.mode == "zero-call-repair-successor":
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
    elif args.mode == "zero-call-submission-repair-resume":
        if not (
            args.predecessor_private
            and args.predecessor_public
            and args.resume_private
            and args.resume_public
        ):
            parser.error(
                "predecessor and resume public/private refs are required "
                "for submission repair resume"
            )
        predecessor_private = _resolve_repo_ref(args.predecessor_private)
        predecessor_public = _resolve_repo_ref(args.predecessor_public)
        resume_private = _resolve_repo_ref(args.resume_private)
        resume_public = _resolve_repo_ref(args.resume_public)
        result = run_zero_call_submission_repair_resume(
            attempt_id=args.attempt_id,
            predecessor_public_path=predecessor_public.resolve(),
            predecessor_private_path=predecessor_private.resolve(),
            resume_public_path=resume_public.resolve(),
            resume_private_path=resume_private.resolve(),
            private_output=private_output,
            public_output=public_output,
        )
    elif args.mode == "zero-call-content-repair":
        if not (
            args.predecessor_private
            and args.predecessor_public
            and args.assessment
        ):
            parser.error(
                "predecessor public/private refs and --assessment are required "
                "for content repair"
            )
        result = run_zero_call_content_repair(
            attempt_id=args.attempt_id,
            predecessor_public_path=_resolve_repo_ref(
                args.predecessor_public
            ).resolve(),
            predecessor_private_path=_resolve_repo_ref(
                args.predecessor_private
            ).resolve(),
            assessment_path=_resolve_repo_ref(args.assessment).resolve(),
            private_output=private_output,
            public_output=public_output,
        )
    else:
        if not args.predecessor_private or not args.predecessor_public:
            parser.error(
                "--predecessor-private and --predecessor-public are required "
                "for submission successor"
            )
        predecessor_private = Path(args.predecessor_private)
        predecessor_public = Path(args.predecessor_public)
        if not predecessor_private.is_absolute():
            predecessor_private = ROOT / predecessor_private
        if not predecessor_public.is_absolute():
            predecessor_public = ROOT / predecessor_public
        result = run_zero_call_submission_successor(
            attempt_id=args.attempt_id,
            predecessor_public_path=predecessor_public.resolve(),
            predecessor_private_path=predecessor_private.resolve(),
            private_output=private_output,
            public_output=public_output,
            resume_public_path=(
                Path(args.resume_public).resolve()
                if args.resume_public
                else None
            ),
            resume_private_path=(
                Path(args.resume_private).resolve()
                if args.resume_private
                else None
            ),
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
