from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.contracts import load_financial_research_kernel
from retrieval.route_compiler import load_query_object_fact_route_policy

from sec_agent.runtime_bridge.paths import resolve_runtime_paths
from sec_agent.runtime_resource_registry import read_registered_runtime_json
from sec_agent.canonical_runtime import (
    append_session_event,
    canonical_digest,
    create_agent_session,
    validate_runtime_artifact,
)
from sec_agent.providers import (
    AgentToolStepResult,
    AgentTransportProfile,
    ChatCompletionProfile,
    ChatCompletionResult,
    ChatCompletionToolStepResult,
    ModelGatewayError,
    execute_agent_tool_step_exact_once,
    execute_chat_completion_exact_once,
    execute_chat_completion_tool_step_exact_once,
)

from .case_truth_reconciliation import compile_case_truth_packet
from .current_consumer import (
    compile_current_research_input,
    load_current_research_consumer_policy,
)
from .dynamic_truth_spine import (
    bind_dynamic_evidence_responses_to_research_input,
    compile_dynamic_evidence_responses,
    compile_dynamic_reviewed_pack_view,
)
from .multi_agent_preview import (
    compile_analysis_continuation_messages,
    compile_analyzed_node_messages,
    compile_analyzed_node_submission_messages,
    compile_planner_payload_from_role_opinions,
    compile_specialist_context,
    compile_token_budget_basis,
    merge_analysis_draft_fragments,
    validate_analysis_completion_checkpoint,
    validate_analysis_fragment_checkpoint,
)
from .planning import (
    compile_research_objective,
    compile_research_plan,
    load_research_planning_policy,
)


TRUTH_SPINE_REF = (
    "configs/research/"
    "fin_ia_0_1_3_s3_dynamic_truth_spine_policy_v1_1.json"
)
CONSUMER_OVERLAY_REF = (
    "configs/research/"
    "fin_ia_0_1_3_s3_multi_agent_preview_consumer_overlay_v1_0.json"
)
PLANNING_OVERLAY_REF = (
    "configs/research/"
    "fin_ia_0_1_3_s3_multi_agent_preview_planning_overlay_v1_0.json"
)


class MultiAgentPreviewRuntimeError(RuntimeError):
    """Raised when the local S1/S2/Harness spine is not safe to expose."""

    def __init__(self, code: str, *, attempts: Sequence[Mapping[str, Any]] = ()) -> None:
        self.code = code
        self.attempts = tuple(deepcopy(dict(row)) for row in attempts)
        super().__init__(code)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")


@dataclass
class PreviewAgentSessionState:
    agent_id: str
    session: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    resume_receipts: list[dict[str, Any]] = field(default_factory=list)
    feedback_receipts: list[dict[str, Any]] = field(default_factory=list)
    stop_decisions: list[dict[str, Any]] = field(default_factory=list)

    def append(
        self,
        *,
        event_type: str,
        actor_id: str,
        attempt_id: str | None = None,
        input_refs: Sequence[str] = (),
        output_refs: Sequence[str] = (),
        feedback_refs: Sequence[str] = (),
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        event = append_session_event(
            self.events,
            session_id=self.session["session_id"],
            event_type=event_type,
            actor_id=actor_id,
            attempt_id=attempt_id,
            input_refs=input_refs,
            output_refs=output_refs,
            feedback_refs=feedback_refs,
            occurred_at=occurred_at or _now(),
        )
        self.events.append(event)
        return event

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "session": deepcopy(self.session),
            "events": deepcopy(self.events),
            "checkpoints": deepcopy(self.checkpoints),
            "resume_receipts": deepcopy(self.resume_receipts),
            "feedback_receipts": deepcopy(self.feedback_receipts),
            "stop_decisions": deepcopy(self.stop_decisions),
        }


def start_preview_agent_session(
    *,
    agent_id: str,
    run_id: str,
    objective_ref: str,
    active_plan_ref: str,
    as_of_date: str = "2026-08-06",
    case_version: str = "fin-0.1.3-preview",
) -> PreviewAgentSessionState:
    timestamp = _now()
    session_id = f"SESSION::DELL::{_safe_id(run_id)}::{_safe_id(agent_id)}"
    session = create_agent_session(
        session_id=session_id,
        run_id=run_id,
        case_id="DELL",
        case_version=case_version,
        as_of_date=as_of_date,
        objective_ref=objective_ref,
        active_plan_ref=active_plan_ref,
        created_at=timestamp,
    )
    state = PreviewAgentSessionState(agent_id=agent_id, session=session)
    state.append(
        event_type="session_created",
        actor_id="HARNESS::MULTI_AGENT_PREVIEW",
        output_refs=(session_id,),
        occurred_at=timestamp,
    )
    state.append(
        event_type="plan_bound",
        actor_id="HARNESS::MULTI_AGENT_PREVIEW",
        input_refs=(objective_ref,),
        output_refs=(active_plan_ref,),
    )
    return state


def rebind_preview_session_plan(
    state: PreviewAgentSessionState,
    *,
    active_plan_ref: str,
) -> None:
    body = {
        key: deepcopy(value)
        for key, value in state.session.items()
        if key != "session_digest"
    }
    previous = str(body["active_plan_ref"])
    body["active_plan_ref"] = str(active_plan_ref)
    body["updated_at"] = _now()
    validated = validate_runtime_artifact("AgentSession", body)
    state.session = {
        **validated,
        "session_digest": canonical_digest(validated),
    }
    state.append(
        event_type="plan_bound",
        actor_id="AGENT::RESEARCH_LEAD",
        input_refs=(previous,),
        output_refs=(str(active_plan_ref),),
    )


@dataclass(frozen=True)
class PreviewNodeExecution:
    node_id: str
    agent_id: str
    tool_name: str
    validated_payload: Mapping[str, Any]
    token_budget_basis: Mapping[str, Any]
    attempts: tuple[Mapping[str, Any], ...]
    successor_attempt_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "validated_payload": deepcopy(dict(self.validated_payload)),
            "token_budget_basis": deepcopy(dict(self.token_budget_basis)),
            "attempts": [deepcopy(dict(row)) for row in self.attempts],
            "successor_attempt_count": self.successor_attempt_count,
        }


ToolTransport = Callable[..., AgentToolStepResult]
AnalysisTransport = Callable[..., ChatCompletionResult]
SubmissionTransport = Callable[..., ChatCompletionToolStepResult]
PayloadValidator = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def _execute_preview_submission(
    *,
    submission_profile: ChatCompletionProfile,
    session_state: PreviewAgentSessionState,
    analysis_draft: str,
    analysis_messages: Sequence[Mapping[str, Any]],
    analysis_messages_digest: str | None,
    analysis_draft_digest: str,
    tool: Mapping[str, Any],
    validator: PayloadValidator,
    capture_root: str | Path,
    run_id: str,
    node_id: str,
    purpose: str,
    required_outputs: Sequence[str],
    schema_burden: str,
    materiality_quality_risk: str,
    comparable_run_evidence: Sequence[str],
    submission_output_token_ceiling: int,
    maximum_submission_successor_attempts: int,
    prior_attempts: Sequence[Mapping[str, Any]],
    prior_token_budget_basis: Mapping[str, Any],
    submission_transport: SubmissionTransport,
) -> PreviewNodeExecution:
    """Map a completed analysis draft through one shared strict submission path."""

    if maximum_submission_successor_attempts not in {0, 1}:
        raise MultiAgentPreviewRuntimeError(
            "multi_agent_preview_submission_successor_budget_invalid"
        )
    tool_name = str(tool["function"]["name"])
    submission_messages = list(
        compile_analyzed_node_submission_messages(
            analysis_draft=analysis_draft,
            analysis_messages=analysis_messages,
            analysis_messages_digest=analysis_messages_digest,
            tool_name=tool_name,
            required_outputs=required_outputs,
        )
    )
    submission_basis = compile_token_budget_basis(
        node_id=f"{node_id}::SUBMISSION",
        purpose=(
            f"{purpose} 本阶段只把已形成草稿映射到唯一严格合同，不重新研究。"
        ),
        input_characters=sum(
            len(str(row.get("content") or "")) for row in submission_messages
        )
        + len(json.dumps(tool, ensure_ascii=False, sort_keys=True)),
        input_reference_count=sum(
            analysis_draft.count(prefix)
            for prefix in ("EV::", "NUM::", "REL::", "GAP::")
        ),
        required_outputs=required_outputs,
        schema_burden=schema_burden,
        materiality_quality_risk=materiality_quality_risk,
        comparable_run_evidence=(
            *comparable_run_evidence,
            "DELL fragment analysis/submission FAS-R1",
        ),
        reasoning_profile=(
            f"{submission_profile.model} non-thinking strict contract mapper"
        ),
        output_token_ceiling=submission_output_token_ceiling,
        stop_truncation_behavior=(
            "require exactly one named tool call and full local contract; preserve "
            "failure; at most one separately identified submission successor"
        ),
    )
    submission_defaults = dict(submission_profile.request_defaults)
    submission_defaults["max_tokens"] = submission_output_token_ceiling
    node_submission_profile = replace(
        submission_profile, request_defaults=submission_defaults
    )
    attempts = [deepcopy(dict(row)) for row in prior_attempts]
    maximum_attempts = 1 + maximum_submission_successor_attempts
    last_code = "multi_agent_preview_submission_not_executed"
    for index in range(1, maximum_attempts + 1):
        attempt_id = (
            f"{_safe_id(run_id)}-{_safe_id(node_id)}-SUBMISSION-ATTEMPT-{index:02d}"
        )
        session_state.append(
            event_type="provider_attempt_requested",
            actor_id=session_state.agent_id,
            attempt_id=attempt_id,
            input_refs=(
                f"messages://{canonical_digest(submission_messages)}",
                f"tool://{canonical_digest(tool)}",
                f"token-budget://{submission_basis['token_budget_basis_digest']}",
                f"analysis-draft://{analysis_draft_digest}",
            ),
        )
        try:
            step = submission_transport(
                profile=node_submission_profile,
                messages=submission_messages,
                tools=[tool],
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=attempt_id,
                tool_choice={
                    "type": "function",
                    "function": {"name": tool_name},
                },
            )
        except ModelGatewayError as exc:
            last_code = exc.code
            attempts.append(
                {
                    "phase": "submission",
                    "attempt_id": attempt_id,
                    "status": "provider_transport_failed",
                    "failure_code": exc.code,
                    "capture_ref": exc.capture_ref,
                }
            )
            session_state.append(
                event_type="provider_attempt_failed",
                actor_id="PROVIDER::" + submission_profile.provider_id.upper(),
                attempt_id=attempt_id,
                output_refs=((exc.capture_ref,) if exc.capture_ref else ()),
            )
            if index >= maximum_attempts:
                raise MultiAgentPreviewRuntimeError(
                    last_code, attempts=attempts
                ) from exc
            submission_messages.append(
                {
                    "role": "user",
                    "content": (
                        "The prior contract-mapping attempt ended before a valid "
                        f"response ({exc.code}). Use the unchanged analysis draft "
                        f"and issue exactly one {tool_name} call."
                    ),
                }
            )
            continue

        step_dict = {**step.as_dict(), "phase": "submission"}
        session_state.append(
            event_type="provider_attempt_completed",
            actor_id="PROVIDER::" + submission_profile.provider_id.upper(),
            attempt_id=attempt_id,
            output_refs=tuple(
                str(step_dict.get(key) or "")
                for key in ("request_capture_ref", "response_capture_ref")
                if str(step_dict.get(key) or "")
            ),
        )
        try:
            if len(step.tool_calls) != 1:
                raise MultiAgentPreviewRuntimeError(
                    "multi_agent_preview_exactly_one_tool_call_required"
                )
            call = step.tool_calls[0]
            function = call.get("function") or {}
            if str(function.get("name") or "") != tool_name:
                raise MultiAgentPreviewRuntimeError(
                    "multi_agent_preview_tool_name_mismatch"
                )
            raw_payload = json.loads(str(function.get("arguments") or ""))
            if not isinstance(raw_payload, Mapping):
                raise MultiAgentPreviewRuntimeError(
                    "multi_agent_preview_tool_arguments_not_object"
                )
            validated = deepcopy(dict(validator(raw_payload)))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, RuntimeError) as exc:
            last_code = str(
                getattr(exc, "code", "") or str(exc) or type(exc).__name__
            )
            attempts.append(
                {
                    **step_dict,
                    "attempt_id": attempt_id,
                    "status": "provider_completed_local_contract_failed",
                    "failure_code": last_code,
                }
            )
            if index >= maximum_attempts:
                raise MultiAgentPreviewRuntimeError(
                    last_code, attempts=attempts
                ) from exc
            feedback_ref = "contract-feedback://" + canonical_digest(
                {"node_id": node_id, "code": last_code, "attempt_id": attempt_id}
            )
            session_state.append(
                event_type="feedback_issued",
                actor_id="HARNESS::CONTRACT_VALIDATOR",
                feedback_refs=(feedback_ref,),
            )
            submission_messages.append(
                {
                    "role": "user",
                    "content": (
                        "The preserved contract submission was rejected with code "
                        f"{last_code}. Do not change the analysis or add facts. "
                        f"Correct only the mapping and issue exactly one {tool_name} call."
                    ),
                }
            )
            continue

        attempts.append(
            {
                **step_dict,
                "attempt_id": attempt_id,
                "status": "contract_valid",
                "validated_payload_digest": canonical_digest(validated),
            }
        )
        return PreviewNodeExecution(
            node_id=node_id,
            agent_id=session_state.agent_id,
            tool_name=tool_name,
            validated_payload=validated,
            token_budget_basis={
                **deepcopy(dict(prior_token_budget_basis)),
                "submission": submission_basis,
            },
            attempts=tuple(attempts),
            successor_attempt_count=index - 1,
        )
    raise MultiAgentPreviewRuntimeError(last_code, attempts=attempts)


def execute_validated_preview_node(
    *,
    profile: AgentTransportProfile,
    session_state: PreviewAgentSessionState,
    messages: Sequence[Mapping[str, Any]],
    tool: Mapping[str, Any],
    validator: PayloadValidator,
    capture_root: str | Path,
    run_id: str,
    node_id: str,
    purpose: str,
    input_reference_count: int,
    required_outputs: Sequence[str],
    schema_burden: str,
    materiality_quality_risk: str,
    comparable_run_evidence: Sequence[str],
    output_token_ceiling: int,
    maximum_successor_attempts: int = 1,
    transport: ToolTransport = execute_agent_tool_step_exact_once,
) -> PreviewNodeExecution:
    """Run one provider-neutral node with at most one explicit successor.

    A successor is allowed only to expose a transport or contract failure back
    to the same role.  It receives no new evidence and cannot expand authority.
    """

    if maximum_successor_attempts not in {0, 1}:
        raise MultiAgentPreviewRuntimeError(
            "multi_agent_preview_successor_attempt_budget_invalid"
        )
    tool_name = str(tool["function"]["name"])
    visible_messages = [deepcopy(dict(row)) for row in messages]
    basis = compile_token_budget_basis(
        node_id=node_id,
        purpose=purpose,
        input_characters=sum(len(str(row.get("content") or "")) for row in messages),
        input_reference_count=input_reference_count,
        required_outputs=required_outputs,
        schema_burden=schema_burden,
        materiality_quality_risk=materiality_quality_risk,
        comparable_run_evidence=comparable_run_evidence,
        reasoning_profile=f"{profile.model} thinking=max",
        output_token_ceiling=output_token_ceiling,
        stop_truncation_behavior=(
            "fail closed on truncation or invalid contract; preserve captures; "
            "at most one separately identified bounded successor attempt"
        ),
    )
    defaults = dict(profile.request_defaults)
    if "max_tokens" in defaults:
        defaults["max_tokens"] = output_token_ceiling
    elif "max_output_tokens" in defaults:
        defaults["max_output_tokens"] = output_token_ceiling
    node_profile = replace(profile, request_defaults=defaults)
    attempts: list[dict[str, Any]] = []
    last_code = "multi_agent_preview_node_not_executed"
    maximum_attempts = 1 + maximum_successor_attempts
    for index in range(1, maximum_attempts + 1):
        attempt_id = (
            f"{_safe_id(run_id)}-{_safe_id(node_id)}-ATTEMPT-{index:02d}"
        )
        message_digest = canonical_digest(visible_messages)
        tool_digest = canonical_digest(tool)
        session_state.append(
            event_type="provider_attempt_requested",
            actor_id=session_state.agent_id,
            attempt_id=attempt_id,
            input_refs=(
                f"messages://{message_digest}",
                f"tool://{tool_digest}",
                f"token-budget://{basis['token_budget_basis_digest']}",
            ),
        )
        try:
            step = transport(
                profile=node_profile,
                messages=visible_messages,
                tools=[tool],
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=attempt_id,
                tool_choice={
                    "type": "function",
                    "function": {"name": tool_name},
                },
            )
        except ModelGatewayError as exc:
            last_code = exc.code
            failed = {
                "attempt_id": attempt_id,
                "status": "provider_transport_failed",
                "failure_code": exc.code,
                "capture_ref": exc.capture_ref,
            }
            attempts.append(failed)
            session_state.append(
                event_type="provider_attempt_failed",
                actor_id="PROVIDER::" + profile.provider_id.upper(),
                attempt_id=attempt_id,
                output_refs=((exc.capture_ref,) if exc.capture_ref else ()),
            )
            if index >= maximum_attempts:
                raise MultiAgentPreviewRuntimeError(
                    last_code, attempts=attempts
                ) from exc
            visible_messages.append(
                {
                    "role": "user",
                    "content": (
                        "The prior provider attempt ended before a valid response was "
                        f"available ({exc.code}). This is a new bounded successor "
                        "attempt with identical evidence and authority. Submit the "
                        f"required {tool_name} call only."
                    ),
                }
            )
            continue

        step_dict = step.as_dict()
        session_state.append(
            event_type="provider_attempt_completed",
            actor_id="PROVIDER::" + profile.provider_id.upper(),
            attempt_id=attempt_id,
            output_refs=tuple(
                str(step_dict.get(key) or "")
                for key in ("request_capture_ref", "response_capture_ref")
                if str(step_dict.get(key) or "")
            ),
        )
        try:
            if len(step.tool_calls) != 1:
                raise MultiAgentPreviewRuntimeError(
                    "multi_agent_preview_exactly_one_tool_call_required"
                )
            call = step.tool_calls[0]
            function = call.get("function") or {}
            if str(function.get("name") or "") != tool_name:
                raise MultiAgentPreviewRuntimeError(
                    "multi_agent_preview_tool_name_mismatch"
                )
            raw_payload = json.loads(str(function.get("arguments") or ""))
            if not isinstance(raw_payload, Mapping):
                raise MultiAgentPreviewRuntimeError(
                    "multi_agent_preview_tool_arguments_not_object"
                )
            validated = deepcopy(dict(validator(raw_payload)))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, RuntimeError) as exc:
            last_code = str(getattr(exc, "code", "") or str(exc) or type(exc).__name__)
            attempts.append(
                {
                    **step_dict,
                    "attempt_id": attempt_id,
                    "status": "provider_completed_local_contract_failed",
                    "failure_code": last_code,
                }
            )
            if index >= maximum_attempts:
                raise MultiAgentPreviewRuntimeError(
                    last_code, attempts=attempts
                ) from exc
            feedback_ref = f"contract-feedback://{canonical_digest({'node_id': node_id, 'code': last_code, 'attempt_id': attempt_id})}"
            session_state.append(
                event_type="feedback_issued",
                actor_id="HARNESS::CONTRACT_VALIDATOR",
                feedback_refs=(feedback_ref,),
            )
            visible_messages.append(
                {
                    "role": "user",
                    "content": (
                        "The prior output was preserved but rejected by the local "
                        f"contract validator with code {last_code}. Do not change the "
                        "research authority or add facts. Correct only the contract "
                        f"submission and issue exactly one {tool_name} call."
                    ),
                }
            )
            continue

        attempts.append(
            {
                **step_dict,
                "attempt_id": attempt_id,
                "status": "contract_valid",
                "validated_payload_digest": canonical_digest(validated),
            }
        )
        return PreviewNodeExecution(
            node_id=node_id,
            agent_id=session_state.agent_id,
            tool_name=tool_name,
            validated_payload=validated,
            token_budget_basis=basis,
            attempts=tuple(attempts),
            successor_attempt_count=index - 1,
        )
    raise MultiAgentPreviewRuntimeError(last_code, attempts=attempts)


def execute_analyzed_preview_node(
    *,
    analysis_profile: ChatCompletionProfile,
    submission_profile: ChatCompletionProfile,
    session_state: PreviewAgentSessionState,
    messages: Sequence[Mapping[str, Any]],
    tool: Mapping[str, Any],
    validator: PayloadValidator,
    capture_root: str | Path,
    run_id: str,
    node_id: str,
    purpose: str,
    input_reference_count: int,
    required_outputs: Sequence[str],
    schema_burden: str,
    materiality_quality_risk: str,
    comparable_run_evidence: Sequence[str],
    analysis_output_token_ceiling: int,
    submission_output_token_ceiling: int,
    maximum_submission_successor_attempts: int = 1,
    analysis_checkpoint: Mapping[str, Any] | None = None,
    analysis_checkpoint_draft: str | None = None,
    analysis_continuation_profile: ChatCompletionProfile | None = None,
    analysis_transport: AnalysisTransport = execute_chat_completion_exact_once,
    submission_transport: SubmissionTransport = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> PreviewNodeExecution:
    """Run one logical Agent node as visible analysis then strict mapping.

    The analysis draft is private model data.  It cannot become Evidence or a
    validated output until a separate non-thinking submission passes the same
    canonical tool contract and local validator.
    """

    if maximum_submission_successor_attempts not in {0, 1}:
        raise MultiAgentPreviewRuntimeError(
            "multi_agent_preview_submission_successor_budget_invalid"
        )
    tool_name = str(tool["function"]["name"])
    checkpoint_mode = analysis_checkpoint is not None
    if checkpoint_mode:
        if analysis_checkpoint_draft is None or analysis_continuation_profile is None:
            raise MultiAgentPreviewRuntimeError(
                "multi_agent_preview_analysis_checkpoint_inputs_missing"
            )
        trusted_checkpoint = validate_analysis_fragment_checkpoint(
            analysis_checkpoint
        )
        if not (
            trusted_checkpoint["node_id"] == node_id
            and trusted_checkpoint["required_outputs"]
            == [str(item) for item in required_outputs]
            and trusted_checkpoint["continuation_policy"][
                "maximum_continuation_calls"
            ]
            == 1
        ):
            raise MultiAgentPreviewRuntimeError(
                "multi_agent_preview_analysis_checkpoint_scope_invalid"
            )
        analysis_messages = compile_analysis_continuation_messages(
            checkpoint=trusted_checkpoint,
            partial_draft=analysis_checkpoint_draft,
            tool_name=tool_name,
        )
        active_analysis_profile = analysis_continuation_profile
        analysis_phase = "analysis_continuation"
        analysis_purpose = (
            f"{purpose} 本阶段只续写 checkpoint 标明的未完成内容，不重做已完成分析、"
            "不提交合同、不晋升业务事实。"
        )
        analysis_required_outputs = (
            "visible_analysis_continuation",
            *trusted_checkpoint["partial_required_outputs"],
            *trusted_checkpoint["missing_required_outputs"],
        )
        reasoning_effort = str(
            active_analysis_profile.request_defaults.get("reasoning_effort")
            or "provider_default"
        )
        analysis_stop_behavior = (
            "require one non-empty continuation and finish_reason=stop; merge "
            "with the immutable partial draft; no second continuation or restart"
        )
        analysis_input_reference_count = 1 + sum(
            str(analysis_checkpoint_draft).count(prefix)
            for prefix in ("EV::", "NUM::", "REL::", "GAP::")
        )
    else:
        if analysis_checkpoint_draft is not None or analysis_continuation_profile is not None:
            raise MultiAgentPreviewRuntimeError(
                "multi_agent_preview_analysis_checkpoint_inputs_unbound"
            )
        trusted_checkpoint = None
        analysis_messages = compile_analyzed_node_messages(
            messages=messages,
            tool_name=tool_name,
            required_outputs=required_outputs,
        )
        active_analysis_profile = analysis_profile
        analysis_phase = "analysis"
        analysis_purpose = (
            f"{purpose} 本阶段只形成可见分析草稿，不提交合同、不晋升业务事实。"
        )
        analysis_required_outputs = ("visible_analysis_draft", *required_outputs)
        reasoning_effort = str(
            active_analysis_profile.request_defaults.get("reasoning_effort")
            or "provider_default"
        )
        analysis_stop_behavior = (
            "require non-empty visible draft and finish_reason=stop; fail closed "
            "on empty reasoning-only completion or truncation; no analysis retry"
        )
        analysis_input_reference_count = input_reference_count
    analysis_basis = compile_token_budget_basis(
        node_id=f"{node_id}::{analysis_phase.upper()}",
        purpose=analysis_purpose,
        input_characters=sum(
            len(str(row.get("content") or "")) for row in analysis_messages
        ),
        input_reference_count=analysis_input_reference_count,
        required_outputs=analysis_required_outputs,
        schema_burden="analysis-only projection; no tool or JSON submission",
        materiality_quality_risk=materiality_quality_risk,
        comparable_run_evidence=(
            *comparable_run_evidence,
            "DELL fragment analysis/submission FAS-R1",
            "DELL multi-agent preview R3 Lead capacity failure",
        ),
        reasoning_profile=(
            f"{active_analysis_profile.model} thinking={reasoning_effort} "
            f"visible {analysis_phase}"
        ),
        output_token_ceiling=analysis_output_token_ceiling,
        stop_truncation_behavior=analysis_stop_behavior,
    )
    analysis_defaults = dict(active_analysis_profile.request_defaults)
    analysis_defaults["max_tokens"] = analysis_output_token_ceiling
    node_analysis_profile = replace(
        active_analysis_profile, request_defaults=analysis_defaults
    )
    analysis_attempt_id = (
        f"{_safe_id(run_id)}-{_safe_id(node_id)}-"
        f"{analysis_phase.upper().replace('_', '-')}-ATTEMPT-01"
    )
    if checkpoint_mode and trusted_checkpoint is not None:
        checkpoint_ref = "analysis-checkpoint://" + str(
            trusted_checkpoint["checkpoint_digest"]
        )
        feedback_body = {
            "feedback_id": "FEEDBACK::"
            + canonical_digest(
                {
                    "checkpoint_digest": trusted_checkpoint["checkpoint_digest"],
                    "partial": trusted_checkpoint["partial_required_outputs"],
                    "missing": trusted_checkpoint["missing_required_outputs"],
                }
            )[:24].upper(),
            "session_id": session_state.session["session_id"],
            "source_node_id": node_id,
            "target_node_id": node_id,
            "failure_class": "visible_analysis_length_truncation",
            "failure_code": "analysis_finish_reason_length_with_partial_draft",
            "owning_plane": "agent_work_mode_plane",
            "owning_stage": "S3",
            "artifact_refs": [
                checkpoint_ref,
                str(trusted_checkpoint["response_capture_ref"]),
            ],
            "model_visible_summary": (
                "上一分析片段已保存但因长度截断，不能提交。只续写 partial/missing "
                "outputs，不重复 completed outputs，不增加事实或权限。"
            ),
            "permitted_next_actions": [
                "从截断句继续并补齐 checkpoint 标明的剩余字段",
                "完成后把合并草稿交给独立 non-thinking submission",
            ],
            "forbidden_interpretations": [
                "不得把 partial draft 当作已验证 Lead plan",
                "不得重跑六个 Specialist 或重做已完成章节",
                "不得添加 checkpoint 以外的新事实、来源或数字权限",
            ],
            "created_at": _now(),
        }
        validated_feedback = validate_runtime_artifact(
            "FeedbackReceipt", feedback_body
        )
        feedback_ref = str(validated_feedback["feedback_id"])
        session_state.feedback_receipts.append(
            {
                **validated_feedback,
                "feedback_digest": canonical_digest(validated_feedback),
            }
        )
        session_state.append(
            event_type="checkpoint_created",
            actor_id="HARNESS::ANALYSIS_CHECKPOINT",
            input_refs=(str(trusted_checkpoint["response_capture_ref"]),),
            output_refs=(checkpoint_ref,),
        )
        session_state.append(
            event_type="feedback_issued",
            actor_id="HARNESS::ANALYSIS_COMPLETION",
            feedback_refs=(feedback_ref,),
        )
        session_state.append(
            event_type="session_resumed",
            actor_id=session_state.agent_id,
            input_refs=(checkpoint_ref,),
            output_refs=(f"analysis-continuation://{node_id}",),
            feedback_refs=(feedback_ref,),
        )
    session_state.append(
        event_type="provider_attempt_requested",
        actor_id=session_state.agent_id,
        attempt_id=analysis_attempt_id,
        input_refs=(
            f"messages://{canonical_digest(list(analysis_messages))}",
            f"token-budget://{analysis_basis['token_budget_basis_digest']}",
        ),
    )
    attempts: list[dict[str, Any]] = []
    try:
        analysis = analysis_transport(
            profile=node_analysis_profile,
            messages=analysis_messages,
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=analysis_attempt_id,
        )
    except ModelGatewayError as exc:
        failed = {
            "phase": analysis_phase,
            "attempt_id": analysis_attempt_id,
            "status": "provider_transport_failed",
            "failure_code": exc.code,
            "capture_ref": exc.capture_ref,
        }
        attempts.append(failed)
        session_state.append(
            event_type="provider_attempt_failed",
            actor_id="PROVIDER::" + active_analysis_profile.provider_id.upper(),
            attempt_id=analysis_attempt_id,
            output_refs=((exc.capture_ref,) if exc.capture_ref else ()),
        )
        raise MultiAgentPreviewRuntimeError(
            exc.code, attempts=attempts
        ) from exc
    analysis_dict = {
        **analysis.as_dict(),
        "phase": analysis_phase,
        "attempt_id": analysis_attempt_id,
        "status": (
            "analysis_continuation_valid"
            if checkpoint_mode
            else "analysis_draft_valid"
        ),
        "analysis_draft_digest": canonical_digest(analysis.content),
    }
    attempts.append(analysis_dict)
    session_state.append(
        event_type="provider_attempt_completed",
        actor_id="PROVIDER::" + active_analysis_profile.provider_id.upper(),
        attempt_id=analysis_attempt_id,
        output_refs=tuple(
            str(analysis_dict.get(key) or "")
            for key in ("request_capture_ref", "response_capture_ref")
            if str(analysis_dict.get(key) or "")
        ),
    )
    if analysis.finish_reason != "stop":
        code = (
            "multi_agent_preview_"
            + analysis_phase
            + "_finish_reason_invalid:"
            + str(analysis.finish_reason or "missing")
        )
        attempts[-1] = {**attempts[-1], "status": "analysis_terminal_failed", "failure_code": code}
        raise MultiAgentPreviewRuntimeError(code, attempts=attempts)

    try:
        merged_analysis_draft = (
            merge_analysis_draft_fragments(
                checkpoint=trusted_checkpoint,
                partial_draft=str(analysis_checkpoint_draft),
                continuation_draft=analysis.content,
            )
            if checkpoint_mode and trusted_checkpoint is not None
            else analysis.content
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        code = str(getattr(exc, "code", "") or str(exc) or type(exc).__name__)
        attempts[-1] = {
            **attempts[-1],
            "status": "analysis_terminal_failed",
            "failure_code": code,
        }
        raise MultiAgentPreviewRuntimeError(code, attempts=attempts) from exc
    if checkpoint_mode and trusted_checkpoint is not None:
        analysis_dict["analysis_checkpoint_digest"] = trusted_checkpoint[
            "checkpoint_digest"
        ]
        analysis_dict["merged_analysis_draft_digest"] = canonical_digest(
            merged_analysis_draft
        )
    return _execute_preview_submission(
        submission_profile=submission_profile,
        session_state=session_state,
        analysis_draft=merged_analysis_draft,
        analysis_messages=analysis_messages,
        analysis_messages_digest=None,
        analysis_draft_digest=str(
            analysis_dict.get("merged_analysis_draft_digest")
            or analysis_dict["analysis_draft_digest"]
        ),
        tool=tool,
        validator=validator,
        capture_root=capture_root,
        run_id=run_id,
        node_id=node_id,
        purpose=purpose,
        required_outputs=required_outputs,
        schema_burden=schema_burden,
        materiality_quality_risk=materiality_quality_risk,
        comparable_run_evidence=comparable_run_evidence,
        submission_output_token_ceiling=submission_output_token_ceiling,
        maximum_submission_successor_attempts=(
            maximum_submission_successor_attempts
        ),
        prior_attempts=attempts,
        prior_token_budget_basis={"analysis": analysis_basis},
        submission_transport=submission_transport,
    )


def execute_checkpointed_preview_submission(
    *,
    submission_profile: ChatCompletionProfile,
    session_state: PreviewAgentSessionState,
    completed_analysis_checkpoint: Mapping[str, Any],
    merged_analysis_draft: str,
    tool: Mapping[str, Any],
    validator: PayloadValidator,
    capture_root: str | Path,
    run_id: str,
    node_id: str,
    purpose: str,
    required_outputs: Sequence[str],
    schema_burden: str,
    materiality_quality_risk: str,
    comparable_run_evidence: Sequence[str],
    submission_output_token_ceiling: int,
    maximum_submission_successor_attempts: int = 1,
    submission_transport: SubmissionTransport = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> PreviewNodeExecution:
    """Resume at strict submission from an immutable completed-analysis checkpoint.

    This path deliberately performs no analysis provider call.  The checkpoint
    binds the two preserved source captures and the exact merged draft; the only
    new model authority is strict contract mapping.
    """

    trusted = validate_analysis_completion_checkpoint(
        completed_analysis_checkpoint
    )
    draft = str(merged_analysis_draft or "").strip()
    expected_outputs = [str(item) for item in required_outputs]
    if not (
        trusted["node_id"] == node_id
        and trusted["case_key"] == session_state.session["case_id"]
        and trusted["required_outputs"] == expected_outputs
        and canonical_digest(draft) == trusted["merged_analysis_draft_digest"]
        and len(draft) == trusted["merged_analysis_draft_character_count"]
    ):
        raise MultiAgentPreviewRuntimeError(
            "multi_agent_preview_completed_analysis_checkpoint_scope_invalid"
        )

    checkpoint_ref = (
        "analysis-completion-checkpoint://" + trusted["checkpoint_digest"]
    )
    reuse_attempt_id = (
        f"{_safe_id(run_id)}-{_safe_id(node_id)}-"
        "ANALYSIS-CHECKPOINT-REUSE-01"
    )
    session_state.append(
        event_type="checkpoint_created",
        actor_id="HARNESS::ANALYSIS_COMPLETION_CHECKPOINT",
        input_refs=(
            str(trusted["fragment_checkpoint_ref"]),
            str(trusted["continuation_response_capture_ref"]),
        ),
        output_refs=(checkpoint_ref,),
    )
    session_state.append(
        event_type="session_resumed",
        actor_id=session_state.agent_id,
        attempt_id=reuse_attempt_id,
        input_refs=(checkpoint_ref,),
        output_refs=(f"strict-submission://{node_id}",),
    )
    reuse_receipt = {
        "phase": "analysis_checkpoint_reuse",
        "attempt_id": reuse_attempt_id,
        "status": "completed_analysis_checkpoint_reused",
        "provider_call": False,
        "checkpoint_ref": checkpoint_ref,
        "checkpoint_digest": trusted["checkpoint_digest"],
        "source_fragment_run_id": trusted["source_fragment_run_id"],
        "source_continuation_run_id": trusted["source_continuation_run_id"],
        "analysis_draft_digest": trusted["merged_analysis_draft_digest"],
    }
    return _execute_preview_submission(
        submission_profile=submission_profile,
        session_state=session_state,
        analysis_draft=draft,
        analysis_messages=(),
        analysis_messages_digest=trusted["continuation_messages_digest"],
        analysis_draft_digest=trusted["merged_analysis_draft_digest"],
        tool=tool,
        validator=validator,
        capture_root=capture_root,
        run_id=run_id,
        node_id=node_id,
        purpose=purpose,
        required_outputs=required_outputs,
        schema_burden=schema_burden,
        materiality_quality_risk=materiality_quality_risk,
        comparable_run_evidence=comparable_run_evidence,
        submission_output_token_ceiling=submission_output_token_ceiling,
        maximum_submission_successor_attempts=(
            maximum_submission_successor_attempts
        ),
        prior_attempts=(reuse_receipt,),
        prior_token_budget_basis={
            "source_analysis": trusted["source_analysis_token_budget_basis"],
        },
        submission_transport=submission_transport,
    )


def compile_cross_role_feedback_receipt(
    *,
    target_session_id: str,
    challenge: Mapping[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    timestamp = created_at or _now()
    challenge_id = str(challenge["challenge_id"])
    body = {
        "feedback_id": "FEEDBACK::" + canonical_digest(
            {
                "target_session_id": target_session_id,
                "challenge_id": challenge_id,
            }
        )[:24].upper(),
        "session_id": target_session_id,
        "source_node_id": str(challenge["source_agent_id"]),
        "target_node_id": str(challenge["target_agent_id"]),
        "failure_class": "material_cross_role_judgment_challenge",
        "failure_code": str(challenge["requested_action"]),
        "owning_plane": "agent_work_mode_plane",
        "owning_stage": "S3",
        "artifact_refs": [
            f"challenge://{challenge_id}",
            f"workpaper://{challenge['source_workpaper_digest']}",
        ],
        "model_visible_summary": (
            f"{challenge['challenge']} Material reason: "
            f"{challenge['material_reason']}"
        ),
        "permitted_next_actions": [
            "Re-read the existing role context and revise only the challenged judgment",
            "Preserve facts, authority refs and remaining gaps that are not affected",
            "If the challenge requires new data, return the existing typed gap rather than inventing evidence",
        ],
        "forbidden_interpretations": [
            "The challenge is not new Evidence or a NumericFact",
            "A role-local repair may not expand case, date, source or tool authority",
            "A retrieval failure is not proof of public non-disclosure",
        ],
        "created_at": timestamp,
    }
    validated = validate_runtime_artifact("FeedbackReceipt", body)
    return {**validated, "feedback_digest": canonical_digest(validated)}


def load_preview_consumer_policy(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    overlay = _json(root / CONSUMER_OVERLAY_REF)
    if set(overlay) != {
        "schema_version",
        "status",
        "base_policy_ref",
        "cell_overrides",
        "reason",
        "authority",
    }:
        raise MultiAgentPreviewRuntimeError(
            "multi_agent_preview_overlay_fields_invalid"
        )
    base_path = (root / str(overlay["base_policy_ref"])).resolve()
    base_path.relative_to(root)
    policy = _json(base_path)
    by_cell = {str(row["cell_id"]): row for row in policy["cell_contracts"]}
    for raw in overlay["cell_overrides"]:
        row = by_cell[str(raw["cell_id"])]
        maximum_override = raw.get("maximum_evidence_items_override")
        if maximum_override is not None:
            row["maximum_evidence_items"] = int(maximum_override)
        for slot_id in raw["append_supplemental_context_slot_ids"]:
            if slot_id not in row["supplemental_context_slot_ids"]:
                row["supplemental_context_slot_ids"].append(slot_id)
    load_current_research_consumer_policy(policy)
    return policy


def load_preview_planning_policy(
    repo_root: str | Path,
    *,
    route_policy: Any,
) -> Any:
    """Separate proposal capacity from the unchanged execution budget.

    The overlay is provider-neutral and preview-local.  It does not mutate the
    globally registered policy or any historical authority that binds it.
    """

    root = Path(repo_root).resolve()
    overlay = _json(root / PLANNING_OVERLAY_REF)
    expected = {
        "schema_version",
        "status",
        "base_policy_resource_id",
        "max_proposed_atoms_override",
        "max_evidence_requests_must_remain",
        "selection_strategy_must_remain",
        "authority",
        "reason",
    }
    authority = overlay.get("authority") or {}
    if not (
        set(overlay) == expected
        and overlay.get("schema_version")
        == "fin_ia_multi_agent_preview_planning_overlay_v1_0"
        and overlay.get("status")
        == "provider_neutral_preview_proposal_execution_budget_separation"
        and overlay.get("base_policy_resource_id")
        == "application.config.current_research_planning_policy"
        and overlay.get("max_proposed_atoms_override") == 20
        and overlay.get("max_evidence_requests_must_remain") == 12
        and overlay.get("selection_strategy_must_remain")
        == "required_slot_first_then_provider_neutral_facet_priority"
        and authority
        == {
            "changes_research_evidence_or_numeric_authority": False,
            "changes_execution_request_budget": False,
            "records_deferred_atoms": True,
            "provider_or_model_specific": False,
            "product_pointer_promotion": False,
        }
        and str(overlay.get("reason") or "").strip()
    ):
        raise MultiAgentPreviewRuntimeError(
            "multi_agent_preview_planning_overlay_invalid"
        )
    payload = read_registered_runtime_json(
        root, str(overlay["base_policy_resource_id"])
    )
    current_budget = payload.get("max_budget") or {}
    current_selection = payload.get("atom_selection") or {}
    if not (
        current_budget.get("max_evidence_requests")
        == overlay["max_evidence_requests_must_remain"]
        and current_selection.get("strategy")
        == overlay["selection_strategy_must_remain"]
    ):
        raise MultiAgentPreviewRuntimeError(
            "multi_agent_preview_planning_overlay_base_drift"
        )
    scoped = deepcopy(dict(payload))
    scoped["atom_selection"] = deepcopy(dict(current_selection))
    scoped["atom_selection"]["max_proposed_atoms"] = int(
        overlay["max_proposed_atoms_override"]
    )
    return load_research_planning_policy(scoped, route_policy)


@dataclass(frozen=True)
class MultiAgentPreviewMaterialization:
    objective: Any
    plan: Any
    compiled_planner_payload: Mapping[str, Any]
    controlled_plan: Mapping[str, Any]
    evidence_pack: Mapping[str, Any]
    evidence_responses: Mapping[str, Any]
    reviewed_pack_view: Mapping[str, Any]
    dynamic_research_input: Mapping[str, Any]
    research_input: Mapping[str, Any]
    case_truth_packet: Mapping[str, Any]
    specialist_contexts: tuple[Mapping[str, Any], ...]

    def context_by_agent(self) -> dict[str, dict[str, Any]]:
        return {
            str(row["agent"]["agent_id"]): deepcopy(dict(row))
            for row in self.specialist_contexts
        }

    def readiness_summary(self) -> dict[str, Any]:
        roles = []
        for context in self.specialist_contexts:
            cell = context["cell_analysis_view"]["cell"]
            roles.append(
                {
                    "agent_id": context["agent"]["agent_id"],
                    "role_slot_ids": list(
                        context["cell_analysis_view"]["projection_receipt"][
                            "role_slot_ids"
                        ]
                    ),
                    "reviewed_evidence_visible": len(
                        cell["cell_evidence_views"]
                    ),
                    "numeric_facts_visible": len(cell["allowed_numeric_refs"]),
                    "numeric_relations_visible": len(
                        cell["allowed_numeric_relation_refs"]
                    ),
                    "typed_gaps_visible": len(cell["residual_gap_cards"]),
                    "tool_execution_receipts_visible": len(
                        context["tool_execution_receipts"]
                    ),
                    "context_digest": context["context_digest"],
                }
            )
        return {
            "compiled_evidence_request_count": len(self.plan.evidence_requests),
            "controlled_plan_summary": deepcopy(
                dict(self.controlled_plan["summary"])
            ),
            "role_readiness": roles,
            "blocking_empty_role_ids": [
                row["agent_id"]
                for row in roles
                if row["reviewed_evidence_visible"] == 0
                and row["numeric_facts_visible"] == 0
            ],
        }


def compile_multi_agent_preview_materialization(
    *,
    repo_root: str | Path,
    topology: Mapping[str, Any],
    objective_payload: Mapping[str, Any],
    opinions: Sequence[Mapping[str, Any]],
    lead_plan: Mapping[str, Any],
) -> MultiAgentPreviewMaterialization:
    """Execute the canonical local S1/S2 preview spine once.

    Reviewed Evidence reading and dynamic candidate retrieval remain distinct:
    candidate ranking may produce tool receipts, but it may neither erase nor
    promote already-reviewed Evidence.
    """

    root = Path(repo_root).resolve()
    kernel_payload = read_registered_runtime_json(
        root, "application.config.current_financial_research_kernel"
    )
    route_payload = read_registered_runtime_json(
        root, "application.config.current_query_object_fact_route_policy"
    )
    kernel = load_financial_research_kernel(kernel_payload)
    route = load_query_object_fact_route_policy(route_payload, kernel)
    planning = load_preview_planning_policy(root, route_policy=route)
    objective = compile_research_objective(
        objective_payload, kernel=kernel, policy=planning
    )
    compiled = compile_planner_payload_from_role_opinions(
        objective_id=objective.objective_id,
        opinions=opinions,
        lead_plan=lead_plan,
        topology=topology,
    )
    plan = compile_research_plan(
        compiled["planner_payload"],
        objective=objective,
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
    )

    paths = resolve_runtime_paths(root)
    retrieval = ResearchRetrievalService.from_runtime_paths(root, paths)
    evidence_service = ResearchEvidencePackService.from_runtime_paths(root, paths)
    permissions = frozenset({"current_product:read"})
    controlled = retrieval.execute_controlled_plan(
        "DELL",
        objective_payload,
        compiled["planner_payload"],
        ResearchRetrievalPrincipal("current", permissions),
        planning_policy=planning,
    )
    pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", permissions)
    )
    responses = compile_dynamic_evidence_responses(
        policy=_json(root / TRUTH_SPINE_REF),
        controlled_plan=controlled,
        evidence_pack=pack,
    )
    reviewed_view = compile_dynamic_reviewed_pack_view(
        evidence_pack=pack,
        evidence_responses=responses,
    )
    policy = load_preview_consumer_policy(root)
    response_input = compile_current_research_input(
        policy=policy,
        evidence_pack=reviewed_view,
        controlled_plan=controlled,
    )
    visible_digests = {
        str(row.get("evidence_item_digest") or "")
        for row in response_input["evidence_cards"]
    }
    missing = set(responses["accepted_evidence_item_digests"]) - visible_digests
    if missing:
        raise MultiAgentPreviewRuntimeError(
            "multi_agent_preview_accepted_evidence_not_projected:"
            + ",".join(sorted(missing))
        )
    dynamic_input = bind_dynamic_evidence_responses_to_research_input(
        research_input=response_input,
        evidence_responses=responses,
    )
    if not dynamic_input:
        raise MultiAgentPreviewRuntimeError(
            "multi_agent_preview_no_reviewed_evidence_selected"
        )

    # Exact reading of reviewed Evidence is a separate authority surface from
    # dynamic S1 retrieval.  The latter is attached as a receipt only.
    research_input = compile_current_research_input(
        policy=policy,
        evidence_pack=pack,
        controlled_plan=controlled,
    )
    truth = compile_case_truth_packet(research_input)
    opinions_by_agent = {str(row["agent_id"]): row for row in opinions}
    contexts = tuple(
        compile_specialist_context(
            topology=topology,
            agent_id=agent_id,
            research_input=research_input,
            tool_execution_input=dynamic_input,
            case_truth_packet=truth,
            plan_opinion=opinions_by_agent[agent_id],
            lead_plan=lead_plan,
        )
        for agent_id in lead_plan["ordered_agent_ids"]
    )
    return MultiAgentPreviewMaterialization(
        objective=objective,
        plan=plan,
        compiled_planner_payload=compiled,
        controlled_plan=controlled,
        evidence_pack=pack,
        evidence_responses=responses,
        reviewed_pack_view=reviewed_view,
        dynamic_research_input=dynamic_input,
        research_input=research_input,
        case_truth_packet=truth,
        specialist_contexts=contexts,
    )


__all__ = [
    "CONSUMER_OVERLAY_REF",
    "PLANNING_OVERLAY_REF",
    "PreviewAgentSessionState",
    "PreviewNodeExecution",
    "MultiAgentPreviewMaterialization",
    "MultiAgentPreviewRuntimeError",
    "TRUTH_SPINE_REF",
    "compile_cross_role_feedback_receipt",
    "compile_multi_agent_preview_materialization",
    "execute_analyzed_preview_node",
    "execute_checkpointed_preview_submission",
    "execute_validated_preview_node",
    "load_preview_consumer_policy",
    "load_preview_planning_policy",
    "rebind_preview_session_plan",
    "start_preview_agent_session",
]
