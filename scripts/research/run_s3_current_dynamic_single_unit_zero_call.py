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
from retrieval.cuda_execution import required_cuda_fp16_receipt  # noqa: E402
from sec_agent.canonical_runtime.session import (  # noqa: E402
    CanonicalRuntimeError,
    append_session_event,
    apply_accepted_plan_delta,
    canonical_digest,
    create_agent_session,
    create_context_checkpoint,
    resume_agent_session,
)
from sec_agent.research.dynamic_single_unit_loop import (  # noqa: E402
    DynamicSingleUnitLoopError,
    REFLECTION_PAYLOAD_SCHEMA_VERSION,
    REQUEST_PAYLOAD_SCHEMA_VERSION,
    compile_controlled_batch_projection,
    compile_initial_messages,
    compile_material_requirement_blueprints,
    compile_reflection_artifacts,
    compile_request_catalog,
    compile_round_feedback_receipts,
    compile_round_response,
    compile_workpaper_context,
    load_dynamic_single_unit_policy,
    public_round_response,
    reflection_tool,
    request_evidence_tool,
    validate_reflection_payload,
    validate_request_selection,
)
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    SPECIALIST_WORKPAPER_SCHEMA_VERSION,
    specialist_workpaper_tool,
    validate_specialist_workpaper,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402


POLICY_REF = Path(
    "configs/research/fin_ia_0_1_3_s3_dell_dynamic_single_unit_loop_policy_v1_0.json"
)
DEFAULT_PUBLIC = Path(
    "configs/research/evals/fin_ia_0_1_3_s3_dell_dynamic_single_unit_zero_call_result_v1_0.json"
)


def _read_json(path: Path) -> dict[str, Any]:
    target = path if path.is_absolute() else ROOT / path
    return json.loads(target.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    target = path if path.is_absolute() else ROOT / path
    return hashlib.sha256(target.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _write_json(path: Path, value: Mapping[str, Any], *, exclusive: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8", newline="\n") as handle:
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


def _request_rows(
    program: Mapping[str, Any], request_ids: Sequence[str]
) -> list[dict[str, Any]]:
    by_id = {
        str(row.get("request_id") or ""): deepcopy(dict(row))
        for row in program.get("evidence_requests") or ()
        if isinstance(row, Mapping)
    }
    return [by_id[request_id] for request_id in request_ids]


def _fake_request_payload(
    *, round_index: int, request_ids: Sequence[str]
) -> dict[str, Any]:
    return {
        "schema_version": REQUEST_PAYLOAD_SCHEMA_VERSION,
        "round_id": f"ROUND::{round_index}",
        "request_ids": list(request_ids),
        "research_rationale": (
            "优先覆盖价格数量组合、客户需求、供应约束、价值池和发行人反方，确保最终判断不是只看一条收入披露。"
        ),
        "expected_information_gain": (
            "确认哪些桥已有 reviewed Evidence 和 typed NumericFact，哪些只是候选、旁证或尚未证明的材料缺口。"
        ),
    }


def _fake_reflection_payload(
    *,
    round_index: int,
    feedback_refs: Sequence[str],
    next_request_ids: Sequence[str],
    accepted_evidence_refs: Sequence[str],
    decision: str,
) -> dict[str, Any]:
    graph_hypotheses = []
    if accepted_evidence_refs:
        graph_hypotheses = [
            {
                "source_entity": "UPSTREAM_SUPPLY_ECOSYSTEM",
                "relationship_direction": "may_constrain_or_enable",
                "target_entity": "DELL_AI_SERVER_DELIVERY",
                "evidence_refs": [accepted_evidence_refs[0]],
                "research_use": (
                    "仅作为下一轮供应关系和时间表查询方向，不证明 Dell 已获得具体配额、良率或供给改善。"
                ),
            }
        ]
    return {
        "schema_version": REFLECTION_PAYLOAD_SCHEMA_VERSION,
        "round_id": f"ROUND::{round_index}",
        "reflection_summary": (
            "本轮已得到部分公司收入、分部利润、需求或供应背景，但产品级价格、销量、组合和供应分配桥仍需逐项区分。"
            "下一步只执行尚未覆盖且可能改变利润获取判断的请求；未审候选和路线失败继续保留为反馈，不能升级为事实或公共信息边界。"
        ),
        "answered_questions": [
            "已识别当前可引用的发行人事实、上游背景和数值权威。",
            "已区分产品收入、分部利润和公司利润并非同一口径。",
        ],
        "unresolved_questions": [
            "Dell 产品级价格、销量和 PVM 仍缺完整直接桥。",
            "上游产能方向仍不能证明 Dell 获得具体分配或利润改善。",
        ],
        "feedback_refs": list(feedback_refs),
        "next_request_ids": list(next_request_ids),
        "graph_hypotheses": graph_hypotheses,
        "proposed_stop_decision": decision,
        "reason_codes": [
            (
                "material_unexecuted_routes_remain"
                if decision == "continue"
                else "all_proposition_groups_examined_with_explicit_boundaries"
            )
        ],
    }


def _fake_workpaper(
    *, context: Mapping[str, Any]
) -> dict[str, Any]:
    cell = context["cell_analysis_view"]["cell"]
    evidence_refs = [
        str(row["evidence_ref"])
        for row in cell.get("cell_evidence_views") or ()
    ]
    numeric_refs = list(cell.get("allowed_numeric_refs") or ())
    relation_refs = list(cell.get("allowed_numeric_relation_refs") or ())
    gap_refs = [
        str(row["gap_ref"]) for row in cell.get("residual_gap_cards") or ()
    ]
    return {
        "schema_version": SPECIALIST_WORKPAPER_SCHEMA_VERSION,
        "agent_id": "AGENT::VALUE_CAPTURE",
        "thesis": (
            "这是一份零模型合同夹具，只证明当前动态循环可把已审证据、数值、反馈和缺口送入价值获取工作底稿合同；它不代表研究结论。"
        ),
        "confidence": "insufficient_evidence",
        "sourced_claims": [
            {
                "claim": "零模型夹具不生成新的金融事实，只验证引用边界。",
                "authority": "sourced_fact" if evidence_refs else "not_inferable",
                "evidence_refs": evidence_refs[:1],
                "numeric_refs": numeric_refs[:1],
                "numeric_relation_refs": relation_refs[:1],
            }
        ],
        "mechanism": (
            "真实模型必须先选择研究请求、消费工具反馈并修改计划，随后才能把已审 Evidence、typed NumericFact、区间和显式缺口组织成判断。"
        ),
        "alternative_explanations": [
            "公司和分部利润变化可能来自 AI 服务器之外的业务、定价、成本或组合因素。"
        ],
        "strongest_counterarguments": [
            "没有产品级价格数量组合和成本桥时，不能把同时发生的利润改善全部归因于 AI 服务器。"
        ],
        "remaining_gap_refs": gap_refs,
        "what_would_change": [
            "若出现可审计的产品级价格、销量、组合和利润桥，应重新裁决价值获取判断。"
        ],
        "cross_role_challenges": [],
        "stop_reason": (
            "零调用证明到此只验证结构和权限；自然模型研究质量必须由独立 live 验证。"
        ),
    }


def run(
    *,
    attempt_id: str,
    private_output: Path,
    public_output: Path,
    policy_ref: Path = POLICY_REF,
) -> dict[str, Any]:
    if private_output.exists() or public_output.exists():
        raise FileExistsError(
            "dynamic_single_unit_zero_call_output_exists:"
            + ",".join(
                str(path)
                for path in (private_output, public_output)
                if path.exists()
            )
        )
    recorded_at = _now()
    resolved_policy_ref = policy_ref if policy_ref.is_absolute() else ROOT / policy_ref
    policy = load_dynamic_single_unit_policy(_read_json(resolved_policy_ref))
    source_refs = policy["source_refs"]
    program = _read_json(Path(source_refs["request_program_ref"]))
    task_readiness = _read_json(Path(source_refs["task_readiness_ref"]))
    truth_policy = _read_json(Path(source_refs["truth_spine_policy_ref"]))
    consumer_policy_ref = str(source_refs["consumer_policy_ref"])
    consumer_policy = _read_json(Path(consumer_policy_ref))
    task_quantitative = _read_json(
        Path(source_refs["task_quantitative_result_ref"])
    )
    product_value_bridge = None
    product_value_bridge_ref = str(
        source_refs.get("product_value_bridge_result_ref") or ""
    )
    if product_value_bridge_ref:
        bridge_binding = dict(
            task_readiness.get("source_bindings", {}).get(
                "product_value_bridge_public_result", {}
            )
        )
        if (
            bridge_binding.get("ref") != product_value_bridge_ref
            or bridge_binding.get("sha256")
            != _sha256(Path(product_value_bridge_ref))
        ):
            raise DynamicSingleUnitLoopError(
                "dynamic_single_unit_product_value_bridge_binding_invalid"
            )
        product_value_bridge = _read_json(Path(product_value_bridge_ref))
    catalog = compile_request_catalog(
        policy=policy,
        program=program,
        task_readiness=task_readiness,
    )
    paths = resolve_runtime_paths(ROOT)
    permissions = frozenset({"current_product:read"})
    retrieval_principal = ResearchRetrievalPrincipal("current", permissions)
    evidence_principal = ResearchEvidencePackPrincipal("current", permissions)
    retrieval = ResearchRetrievalService.from_runtime_paths(ROOT, paths)
    evidence_service = ResearchEvidencePackService.from_runtime_paths(ROOT, paths)
    evidence_pack = evidence_service.get_case("DELL", evidence_principal)
    _expected_pack_digest = str(
        task_readiness.get("evidence_pack_payload_digest") or ""
    )
    if evidence_pack.get("pack_payload_digest") != _expected_pack_digest:
        raise DynamicSingleUnitLoopError(
            "dynamic_single_unit_task_readiness_pack_drift"
        )
    cuda = required_cuda_fp16_receipt(
        purpose="DELL current dynamic single-unit S1/S2 zero-call proof"
    )

    initial_messages = compile_initial_messages(
        policy=policy, request_catalog=catalog
    )
    initial_rendered = json.dumps(initial_messages, ensure_ascii=False)
    session_seed = {
        "attempt_id": attempt_id,
        "policy_digest": canonical_digest(policy),
        "catalog_digest": catalog["catalog_digest"],
        "pack_payload_digest": evidence_pack["pack_payload_digest"],
        "product_value_bridge_result_digest": (
            product_value_bridge.get("result_digest")
            if product_value_bridge is not None
            else None
        ),
    }
    session_id = "SESSION::" + canonical_digest(session_seed)[:24].upper()
    base_plan_body = {
        "case_key": "DELL",
        "objective_id": policy["objective"]["objective_id"],
        "executed_request_ids": [],
        "next_request_ids": [],
        "latest_reflection_digest": None,
        "latest_feedback_refs": [],
    }
    base_plan = {
        **base_plan_body,
        "plan_digest": canonical_digest(base_plan_body),
    }
    base_graph_digest = canonical_digest(
        {
            "case_key": "DELL",
            "state": "current_reviewed_graph_plus_run_local_hypotheses",
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
        actor_id="S3.DynamicSingleUnitHarness",
        occurred_at=recorded_at,
        input_refs=(catalog["catalog_digest"],),
        output_refs=(session["active_plan_ref"],),
    )

    round_ids = [
        [
            "REQ::DELL::PRICE_CONFIGURATION::V1",
            "REQ::DELL::PVM_BRIDGE::V1",
            "REQ::DELL::CUSTOMER_DEMAND_ISSUER::V1",
            "REQ::DELL::SUPPLY_SUBJECT_EXECUTION::V1",
            "REQ::DELL::VALUE_POOL_MARGIN::V1",
            "REQ::DELL::COUNTER_ISSUER::V1",
        ],
        [
            "REQ::DELL::UNIT_VOLUME::V1",
            "REQ::DELL::CUSTOMER_DEMAND_DOWNSTREAM::V1",
            "REQ::DELL::SUPPLY_UPSTREAM_CAPACITY::V1",
            "REQ::DELL::SUPPLY_RELATIONSHIP::V1",
            "REQ::DELL::VALUE_POOL_COUNTERPARTY::V1",
            "REQ::DELL::COUNTER_ECOSYSTEM::V1",
        ],
    ]
    executed_ids: list[str] = []
    accumulated_evidence_refs: set[str] = set()
    all_feedback: list[dict[str, Any]] = []
    round_responses: list[dict[str, Any]] = []
    reflections: list[dict[str, Any]] = []
    reflection_artifacts: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []
    replay_digests: list[str] = []

    for round_index, selected_ids in enumerate(round_ids, start=1):
        request_evidence_tool(
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=executed_ids,
            round_index=round_index,
        )
        selection = validate_request_selection(
            _fake_request_payload(
                round_index=round_index, request_ids=selected_ids
            ),
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=executed_ids,
            round_index=round_index,
        )
        requests = _request_rows(program, selection["request_ids"])
        blueprints = compile_material_requirement_blueprints(
            program=program, request_ids=selection["request_ids"]
        )
        tool_attempt_id = f"{attempt_id}-tool-round-{round_index}"
        _event(
            events,
            session_id=session_id,
            event_type="tool_execution_requested",
            actor_id="AGENT::VALUE_CAPTURE",
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
        batches.append(batch)
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
            product_value_bridge_result=product_value_bridge,
        )
        replay = compile_round_response(
            policy=policy,
            controlled_plan=controlled,
            evidence_pack=evidence_pack,
            truth_spine_policy=truth_policy,
            consumer_policy=consumer_policy,
            task_quantitative_result=task_quantitative,
            round_index=round_index,
            product_value_bridge_result=product_value_bridge,
        )
        if response["round_response_digest"] != replay["round_response_digest"]:
            raise DynamicSingleUnitLoopError(
                "dynamic_single_unit_round_replay_not_deterministic"
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
        feedback = compile_round_feedback_receipts(
            session_id=session_id,
            round_response=response,
            request_catalog=catalog,
            created_at=recorded_at,
        )
        all_feedback.extend(feedback)
        feedback_refs = [str(row["feedback_id"]) for row in feedback]
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
        accumulated_evidence_refs.update(
            str(row["evidence_ref"])
            for row in response.get("reviewed_evidence") or ()
        )
        next_ids = round_ids[round_index] if round_index < len(round_ids) else []
        decision = "continue" if next_ids else "stop_sufficient"
        reflection_tool(
            policy=policy,
            request_catalog=catalog,
            feedback_receipts=feedback,
            accepted_evidence_refs=sorted(accumulated_evidence_refs),
            executed_request_ids=executed_ids,
            round_index=round_index,
        )
        reflection = validate_reflection_payload(
            _fake_reflection_payload(
                round_index=round_index,
                feedback_refs=feedback_refs,
                next_request_ids=next_ids,
                accepted_evidence_refs=sorted(accumulated_evidence_refs),
                decision=decision,
            ),
            policy=policy,
            request_catalog=catalog,
            feedback_receipts=feedback,
            accepted_evidence_refs=sorted(accumulated_evidence_refs),
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
            agent_id="AGENT::VALUE_CAPTURE",
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
            actor_id="AGENT::VALUE_CAPTURE",
            occurred_at=recorded_at,
            input_refs=feedback_refs,
            output_refs=(artifacts["plan_delta"]["plan_delta_id"],),
            feedback_refs=feedback_refs,
        )
        _event(
            events,
            session_id=session_id,
            event_type="plan_delta_accepted",
            actor_id="S3.DynamicSingleUnitHarness",
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
            actor_id="AGENT::VALUE_CAPTURE",
            occurred_at=recorded_at,
            input_refs=(reflection["reflection_digest"],),
            output_refs=(artifacts["graph_delta"]["graph_delta_id"],),
        )
        _event(
            events,
            session_id=session_id,
            event_type="graph_delta_accepted",
            actor_id="S3.DynamicSingleUnitHarness",
            occurred_at=recorded_at,
            input_refs=(artifacts["graph_delta"]["graph_delta_id"],),
            output_refs=(artifacts["graph_delta"]["graph_delta_digest"],),
        )
        base_graph_digest = artifacts["graph_delta"]["graph_delta_digest"]
        _event(
            events,
            session_id=session_id,
            event_type="stop_decided",
            actor_id="AGENT::VALUE_CAPTURE",
            occurred_at=recorded_at,
            input_refs=(reflection["reflection_digest"],),
            output_refs=(artifacts["stop_decision"]["stop_decision_id"],),
            feedback_refs=feedback_refs,
        )

    workpaper_context = compile_workpaper_context(
        policy=policy,
        round_responses=round_responses,
        feedback_receipts=all_feedback,
        reflections=reflections,
        stop_decision=reflection_artifacts[-1]["stop_decision"],
    )
    workpaper_evidence_cards = list(
        workpaper_context["cell_analysis_view"]["cell"][
            "cell_evidence_views"
        ]
    )
    public_pdf_cards = [
        row
        for row in workpaper_evidence_cards
        if row.get("source_type") == "PUBLIC_PDF"
    ]
    accepted_source_type_counts: dict[str, int] = {}
    for row in workpaper_evidence_cards:
        source_type = str(row.get("source_type") or "")
        accepted_source_type_counts[source_type] = (
            accepted_source_type_counts.get(source_type, 0) + 1
        )
    workpaper_tool = specialist_workpaper_tool(
        agent_id="AGENT::VALUE_CAPTURE", context=workpaper_context
    )
    validated_fixture = validate_specialist_workpaper(
        _fake_workpaper(context=workpaper_context),
        context=workpaper_context,
        expected_agent_id="AGENT::VALUE_CAPTURE",
    )
    validated_fixture["workpaper_digest"] = canonical_digest(validated_fixture)

    accepted_refs = sorted(accumulated_evidence_refs)
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
        {str(row["feedback_id"]) for row in all_feedback}
    )
    checkpoint_id = "CHECKPOINT::" + canonical_digest(
        {
            "session_id": session_id,
            "plan_digest": base_plan["plan_digest"],
            "accepted_evidence_refs": accepted_refs,
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
    checkpoint = create_context_checkpoint(
        session=session,
        events=events,
        checkpoint_id=checkpoint_id,
        objective_digest=canonical_digest(policy["objective"]),
        plan_digest=base_plan["plan_digest"],
        research_graph_digest=base_graph_digest,
        accepted_evidence_refs=accepted_refs,
        numeric_fact_refs=numeric_refs,
        open_gap_refs=open_gap_refs,
        unresolved_feedback_refs=unresolved_feedback_refs,
        agent_local_state_refs=[
            str(row["reflection_digest"]) for row in reflections
        ],
        authority_refs=[
            str(evidence_pack["pack_payload_digest"]),
            str(task_readiness["result_digest"]),
        ],
        counterevidence_refs=sorted(
            {
                str(row["evidence_ref"])
                for current in round_responses
                for row in current.get("reviewed_evidence") or ()
                if any(
                    "counter" in str(binding.get("slot_id") or "")
                    for binding in row.get("slot_bindings") or ()
                )
            }
        ),
        open_question_refs=[
            f"QUESTION::DELL::VALUE-CAPTURE::{index}"
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
        required_counterevidence_refs=checkpoint["counterevidence_refs"],
        required_open_question_refs=checkpoint["open_question_refs"],
    )

    mutation_checks: dict[str, bool] = {}
    cross_case = _fake_request_payload(
        round_index=1, request_ids=["REQ::MU::PVM_BRIDGE::V1"]
    )
    try:
        validate_request_selection(
            cross_case,
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=(),
            round_index=1,
        )
    except DynamicSingleUnitLoopError as exc:
        mutation_checks["cross_case_request_fails_closed"] = (
            exc.code == "dynamic_single_unit_request_selection_scope_invalid"
        )
    repeated = _fake_request_payload(
        round_index=1, request_ids=[round_ids[0][0]]
    )
    try:
        validate_request_selection(
            repeated,
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=[round_ids[0][0]],
            round_index=1,
        )
    except DynamicSingleUnitLoopError as exc:
        mutation_checks["repeated_request_fails_closed"] = (
            exc.code == "dynamic_single_unit_request_selection_scope_invalid"
        )
    mutated_program = deepcopy(program)
    mutated_program["research_as_of"] = "2026-08-07"
    try:
        compile_request_catalog(
            policy=policy,
            program=mutated_program,
            task_readiness=task_readiness,
        )
    except DynamicSingleUnitLoopError as exc:
        mutation_checks["date_mutation_fails_closed"] = (
            exc.code == "dynamic_single_unit_catalog_case_or_date_invalid"
        )
    incomplete_reflection = validate_reflection_payload(
        _fake_reflection_payload(
            round_index=1,
            feedback_refs=[],
            next_request_ids=[],
            accepted_evidence_refs=[],
            decision="stop_sufficient",
        ),
        policy=policy,
        request_catalog=catalog,
        feedback_receipts=[],
        accepted_evidence_refs=[],
        executed_request_ids=["REQ::DELL::PVM_BRIDGE::V1"],
        round_index=1,
    )
    premature_artifacts = compile_reflection_artifacts(
        policy=policy,
        reflection=incomplete_reflection,
        session_id=session_id,
        agent_id="AGENT::VALUE_CAPTURE",
        base_plan=base_plan,
        base_graph_digest=base_graph_digest,
        executed_request_ids=["REQ::DELL::PVM_BRIDGE::V1"],
        open_gap_refs=["GAP::TEST"],
        model_calls_used=0,
    )
    premature_receipt = premature_artifacts["stop_compilation_receipt"]
    mutation_checks["premature_stop_compiles_to_no_progress"] = (
        incomplete_reflection["proposed_stop_decision"] == "stop_sufficient"
        and premature_artifacts["stop_decision"]["decision"]
        == "stop_no_progress"
        and premature_receipt["proposed_stop_decision"] == "stop_sufficient"
        and premature_receipt["effective_stop_decision"] == "stop_no_progress"
        and premature_receipt["model_research_judgment_changed"] is False
    )
    try:
        resume_agent_session(
            session=session,
            events=events,
            checkpoint=checkpoint,
            expected_case_id="case_mu_current",
            expected_case_version="FIN_0_1_3",
            expected_as_of_date="2026-08-06",
            expected_active_plan_ref=session["active_plan_ref"],
            resumed_at=recorded_at,
        )
    except CanonicalRuntimeError:
        mutation_checks["cross_case_resume_fails_closed"] = True

    permutation = deepcopy(program)
    permutation["evidence_requests"] = list(
        reversed(permutation["evidence_requests"])
    )
    permutation_catalog = compile_request_catalog(
        policy=policy,
        program=permutation,
        task_readiness=task_readiness,
    )
    mutation_checks["request_catalog_permutation_stable"] = (
        permutation_catalog["catalog_digest"] == catalog["catalog_digest"]
    )

    checks = {
        "initial_message_contains_only_question_identity_as_of_and_capabilities": (
            all(
                marker not in initial_rendered.lower()
                for marker in (
                    "evidence_ref",
                    "numeric_ref",
                    "source_url",
                    "source_visible_fact_excerpt",
                )
            )
            and "$43.8" not in initial_rendered
        ),
        "two_real_current_runtime_rounds_executed": (
            len(batches) == 2
            and all(
                batch["status"]
                == "current_runtime_request_batch_zero_call_executed"
                for batch in batches
            )
        ),
        "second_round_differs_from_first": set(round_ids[0]).isdisjoint(
            round_ids[1]
        ),
        "all_twelve_requests_executed_once": (
            len(executed_ids) == 12 and len(set(executed_ids)) == 12
        ),
        "all_seven_proposition_groups_covered": reflection_artifacts[-1][
            "coverage_state"
        ]["all_required_groups_covered"],
        "first_feedback_changed_plan": (
            reflection_artifacts[0]["stop_decision"]["decision"] == "continue"
            and reflection_artifacts[0]["accepted_plan"]["next_request_ids"]
            == round_ids[1]
        ),
        "candidate_never_promoted": (
            all(
                current["authority"]["candidate_promotions"] == 0
                for current in round_responses
            )
            and all(
                result["hybrid_object_retrieval"]["candidate_state"]
                == "candidate_not_evidence"
                for batch in batches
                for result in batch["request_results"]
            )
        ),
        "graph_delta_hypothesis_only": all(
            not artifact["graph_delta"]["edge_additions"]
            and artifact["graph_delta"]["fact_authority_granted"] is False
            for artifact in reflection_artifacts
        ),
        "round_replay_deterministic": replay_digests
        == [row["round_response_digest"] for row in round_responses],
        "checkpoint_resume_preserves_state": (
            resume["status"] == "resume_replay_verified"
            and set(checkpoint["accepted_evidence_refs"]) == set(accepted_refs)
            and set(checkpoint["open_gap_refs"]) == set(open_gap_refs)
            and set(checkpoint["unresolved_feedback_refs"])
            == set(unresolved_feedback_refs)
        ),
        "workpaper_contract_compiles_from_dynamic_state": (
            workpaper_tool["function"]["name"] == "submit_specialist_workpaper"
            and bool(validated_fixture["workpaper_digest"])
        ),
        "product_value_bridge_reaches_workpaper_fail_closed": (
            product_value_bridge is None
            or (
                workpaper_context.get("product_value_bridge", {})
                .get("bridge_readiness", {})
                .get("reported_product_revenue_bridge_available")
                is True
                and workpaper_context.get("product_value_bridge", {})
                .get("bridge_readiness", {})
                .get("target_company_pvm_calculable")
                is False
                and workpaper_context.get("product_value_bridge", {})
                .get("bridge_readiness", {})
                .get("product_profit_bridge_calculable")
                is False
                and workpaper_context.get("product_value_bridge", {})
                .get("pvm_bridge", {})
                .get("price_effect_value")
                is None
                and workpaper_context.get("product_value_bridge", {})
                .get("product_profit_bridge", {})
                .get("implied_product_operating_profit_value")
                is None
            )
        ),
        "reviewed_public_pdf_reaches_workpaper_under_successor_policy": (
            "PUBLIC_PDF"
            not in consumer_policy["reviewed_source_policy"][
                "allowed_source_types"
            ]
            or (
                bool(public_pdf_cards)
                and all(
                    row.get("reviewed_anchor_receipt")
                    and "numeric_ref" not in row
                    and (
                        (
                            row.get("evidence_role")
                            == "issuer_direct_source"
                            and row.get("source_tier")
                            == "issuer_regulator_or_government_primary"
                        )
                        or (
                            row.get("evidence_role")
                            == "counterparty_or_ecosystem_readthrough"
                            and row.get(
                                "bounded_context_source_receipt", {}
                            ).get("causal_attribution_authorized")
                            is False
                        )
                    )
                    for row in public_pdf_cards
                )
            )
        ),
        "cuda_fp16_required": (
            str(cuda.get("execution_device") or "").startswith("cuda:")
            and cuda.get("embedding_precision") == "fp16"
            and cuda.get("reranker_precision") == "fp16"
            and cuda.get("cpu_fallback_allowed") is False
        ),
        "all_mutations_fail_closed_or_stable": all(mutation_checks.values())
        and len(mutation_checks) == 6,
    }
    if not all(checks.values()):
        failed = [key for key, passed in checks.items() if not passed]
        failed_mutations = [
            key for key, passed in mutation_checks.items() if not passed
        ]
        failure_private_body = {
            "schema_version": "fin_ia_s3_dynamic_single_unit_zero_call_failure_full_v1_0",
            "status": "terminal_failed_current_dynamic_single_unit_zero_call_gate",
            "attempt_id": attempt_id,
            "recorded_at": recorded_at,
            "policy_ref": _relative(resolved_policy_ref),
            "policy_digest": canonical_digest(policy),
            "pack_payload_digest": evidence_pack["pack_payload_digest"],
            "task_readiness_result_digest": task_readiness["result_digest"],
            "product_value_bridge_result_digest": (
                product_value_bridge.get("result_digest")
                if product_value_bridge is not None
                else None
            ),
            "failed_checks": failed,
            "failed_mutation_checks": failed_mutations,
            "checks": checks,
            "mutation_checks": mutation_checks,
            "execution_summary": {
                "retrieval_round_count": len(round_responses),
                "executed_request_count": len(executed_ids),
                "accepted_reviewed_evidence_count": len(accepted_refs),
                "accepted_reviewed_source_type_counts": dict(
                    sorted(accepted_source_type_counts.items())
                ),
                "public_pdf_card_count": len(public_pdf_cards),
                "public_pdf_reviewed_anchor_receipt_count": sum(
                    bool(row.get("reviewed_anchor_receipt"))
                    for row in public_pdf_cards
                ),
                "public_pdf_bounded_context_receipt_count": sum(
                    bool(row.get("bounded_context_source_receipt"))
                    for row in public_pdf_cards
                ),
                "numeric_fact_count": len(numeric_refs),
                "open_gap_count": len(open_gap_refs),
            },
            "authority": {
                "network_calls": 0,
                "provider_calls": 0,
                "generation_model_calls": 0,
                "failed_attempt_relabelled": False,
                "S1_pass": False,
                "S2_pass": False,
                "S3_pass": False,
                "release": False,
            },
        }
        failure_private = {
            **failure_private_body,
            "result_digest": canonical_digest(failure_private_body),
        }
        _write_json(private_output, failure_private, exclusive=True)
        failure_public_body = {
            "schema_version": "fin_ia_s3_dynamic_single_unit_zero_call_failure_result_v1_0",
            "status": failure_private["status"],
            "attempt_id": attempt_id,
            "recorded_at": recorded_at,
            "failed_checks": failed,
            "failed_mutation_checks": failed_mutations,
            "private_result_ref": _relative(private_output),
            "private_result_sha256": _sha256(private_output),
            "authority": failure_private["authority"],
            "known_boundary": (
                "This immutable attempt failed its local control gate and grants no "
                "S1, S2, S3, product, publication or release authority."
            ),
        }
        failure_public = {
            **failure_public_body,
            "result_digest": canonical_digest(failure_public_body),
        }
        _write_json(public_output, failure_public, exclusive=True)
        raise DynamicSingleUnitLoopError(
            "dynamic_single_unit_zero_call_checks_failed:"
            + ",".join(failed)
            + ":mutations="
            + ",".join(failed_mutations)
        )

    private_body = {
        "schema_version": "fin_ia_s3_dynamic_single_unit_zero_call_full_v1_0",
        "status": "current_dynamic_single_unit_zero_call_proven",
        "attempt_id": attempt_id,
        "recorded_at": recorded_at,
        "policy_ref": _relative(resolved_policy_ref),
        "policy": policy,
        "request_catalog": catalog,
        "initial_messages": initial_messages,
        "session": session,
        "events": events,
        "round_selections": round_ids,
        "round_batches": batches,
        "round_responses": [
            public_round_response(row) for row in round_responses
        ],
        "feedback_receipts": all_feedback,
        "reflections": reflections,
        "reflection_artifacts": reflection_artifacts,
        "workpaper_context": workpaper_context,
        "workpaper_tool": workpaper_tool,
        "zero_call_workpaper_contract_fixture": validated_fixture,
        "checkpoint": checkpoint,
        "resume_receipt": resume,
        "cuda_receipt": cuda,
        "mutation_checks": mutation_checks,
        "checks": checks,
        "authority": {
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "candidate_promotions": 0,
            "natural_agent_reflection_quality_proven": False,
            "S1_pass": False,
            "S2_pass": False,
            "S3_pass": False,
            "release": False,
        },
    }
    private_result = {
        **private_body,
        "result_digest": canonical_digest(private_body),
    }
    _write_json(private_output, private_result, exclusive=True)
    current_runtime_binding = {
        "evidence_pack_payload_digest": evidence_pack["pack_payload_digest"],
        "reviewed_evidence_count": evidence_pack["summary"][
            "accepted_evidence_items"
        ],
        "task_readiness_result_digest": task_readiness["result_digest"],
        "task_readiness_status": task_readiness["status"],
        "consumer_policy": {
            "ref": consumer_policy_ref,
            "sha256": _sha256(Path(consumer_policy_ref)),
            "policy_digest": canonical_digest(consumer_policy),
            "reviewed_public_pdf_enabled": (
                "PUBLIC_PDF"
                in consumer_policy["reviewed_source_policy"][
                    "allowed_source_types"
                ]
            ),
        },
    }
    if product_value_bridge is not None:
        bridge_context = workpaper_context["product_value_bridge"]
        current_runtime_binding["product_value_bridge"] = {
            "ref": product_value_bridge_ref,
            "sha256": _sha256(Path(product_value_bridge_ref)),
            "result_digest": product_value_bridge["result_digest"],
            "context_digest": bridge_context[
                "product_value_bridge_context_digest"
            ],
            "source_numeric_observation_count": len(
                bridge_context["source_numeric_observations"]
            ),
            "deterministic_derivation_count": len(
                bridge_context["deterministic_source_surface_derivations"]
            ),
            "open_bridge_gap_count": len(
                bridge_context["bridge_gap_receipts"]
            ),
            "target_company_pvm_calculable": False,
            "product_profit_bridge_calculable": False,
        }
    public_body = {
        "schema_version": "fin_ia_s3_dynamic_single_unit_zero_call_result_v1_0",
        "status": "current_dynamic_single_unit_zero_call_proven",
        "recorded_at": recorded_at,
        "attempt_id": attempt_id,
        "policy_binding": {
            "ref": _relative(resolved_policy_ref),
            "sha256": _sha256(resolved_policy_ref),
            "policy_digest": canonical_digest(policy),
        },
        "current_runtime_binding": current_runtime_binding,
        "execution_summary": {
            "retrieval_round_count": len(round_responses),
            "executed_request_count": len(executed_ids),
            "accepted_reviewed_evidence_count": len(accepted_refs),
            "accepted_reviewed_evidence_source_type_counts": dict(
                sorted(accepted_source_type_counts.items())
            ),
            "numeric_fact_count": len(numeric_refs),
            "open_gap_count": len(open_gap_refs),
            "feedback_receipt_count": len(unresolved_feedback_refs),
            "plan_delta_count": len(reflection_artifacts),
            "graph_hypothesis_count": sum(
                len(row["graph_delta"]["hypothesis_only_edges"])
                for row in reflection_artifacts
            ),
            "final_stop_decision": reflection_artifacts[-1]["stop_decision"][
                "decision"
            ],
            "session_event_count": len(events),
            "cuda_device": cuda.get("device_name"),
            "cuda_execution_device": cuda.get("execution_device"),
            "cuda_embedding_precision": cuda.get("embedding_precision"),
            "cuda_reranker_precision": cuda.get("reranker_precision"),
        },
        "round_summaries": [
            {
                "round_id": row["round_id"],
                "request_ids": round_ids[index],
                "reviewed_evidence_count": len(row["reviewed_evidence"]),
                "numeric_fact_count": len(row["numeric_facts"]),
                "numeric_relation_count": len(row["numeric_relations"]),
                "residual_gap_count": len(row["residual_gaps"]),
                "candidate_promotion_count": row["authority"][
                    "candidate_promotions"
                ],
                "round_response_digest": row["round_response_digest"],
            }
            for index, row in enumerate(round_responses)
        ],
        "checks": checks,
        "mutation_checks": mutation_checks,
        "private_result_ref": _relative(private_output),
        "private_result_sha256": _sha256(private_output),
        "authority": private_result["authority"],
        "known_boundary": (
            "This proves the policy-bound current S1/S2 runtime, reviewed-Evidence gate, "
            "typed feedback, plan/graph deltas, checkpoint/resume and final workpaper "
            "contract in a two-round deterministic loop. When the policy binds an S2 "
            "product-value bridge, the exact revenue surface and typed null PVM/profit "
            "boundary reach the workpaper context without creating NumericFacts. The request and reflection "
            "payloads are zero-model fixtures; natural DeepSeek planning, reflection "
            "and content quality require a separately signed exact-once live run."
        ),
    }
    public_result = {
        **public_body,
        "result_digest": canonical_digest(public_body),
    }
    _write_json(public_output, public_result, exclusive=True)
    return public_result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--policy", default=str(POLICY_REF))
    parser.add_argument("--private-output")
    parser.add_argument("--public-output", default=str(DEFAULT_PUBLIC))
    args = parser.parse_args()
    runtime_paths = resolve_runtime_paths(ROOT)
    private_output = (
        Path(args.private_output).resolve()
        if args.private_output
        else runtime_paths.workbench_private_root
        / "fin_0_1_3_s3_dynamic_single_unit_zero_call"
        / args.attempt_id
        / "full_result.json"
    )
    public_output = Path(args.public_output)
    if not public_output.is_absolute():
        public_output = ROOT / public_output
    result = run(
        attempt_id=args.attempt_id,
        private_output=private_output,
        public_output=public_output,
        policy_ref=Path(args.policy),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
