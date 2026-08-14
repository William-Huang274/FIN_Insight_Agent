from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from retrieval.contracts import FinancialResearchKernel
from retrieval.route_compiler import QueryObjectFactRoutePolicy

from sec_agent.providers import (
    AgentToolStepResult,
    AgentTransportProfile,
    ModelGatewayError,
    execute_agent_tool_step_exact_once,
    validate_deepseek_ga_live_transport,
)

from .bounded_finance_loop import (
    BoundedFinanceLoopError,
    BoundedFinanceLoopPolicy,
    compile_finance_loop_tools,
    run_bounded_finance_loop,
)
from .planning import ResearchPlanningPolicy


ToolStepTransport = Callable[..., AgentToolStepResult]


@dataclass(frozen=True)
class FinanceLoopTransportLaneResult:
    lane: str
    wire_api: str
    status: str
    model_calls_attempted: int
    attempted_provider_steps: tuple[Mapping[str, Any], ...]
    receipts: tuple[Mapping[str, Any], ...]
    loop_result: Mapping[str, Any]
    failure_phase: str
    failure_code: str
    failure_capture_ref: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "wire_api": self.wire_api,
            "status": self.status,
            "model_calls_attempted": self.model_calls_attempted,
            "attempted_provider_steps": [
                deepcopy(dict(row)) for row in self.attempted_provider_steps
            ],
            "receipts": [deepcopy(dict(row)) for row in self.receipts],
            "loop_result": deepcopy(dict(self.loop_result)),
            "failure_phase": self.failure_phase,
            "failure_code": self.failure_code,
            "failure_capture_ref": self.failure_capture_ref,
            "retries": 0,
            "fallbacks": 0,
            "external_retrieval_calls": 0,
            "embedding_calls": 0,
            "product_publication": False,
            "private_reasoning_persisted": False,
        }


def execute_finance_loop_transport_lane(
    *,
    lane: str,
    profile: AgentTransportProfile,
    policy: BoundedFinanceLoopPolicy,
    research_input: Mapping[str, Any],
    required_cell_ids: Sequence[str],
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    planning_policy: ResearchPlanningPolicy,
    visible_execution_budget: Mapping[str, int],
    capture_root: str | Path,
    run_id: str,
    attempt_prefix: str,
    transport: ToolStepTransport = execute_agent_tool_step_exact_once,
) -> FinanceLoopTransportLaneResult:
    """Execute one independent, no-retry finance loop transport lane."""

    validate_deepseek_ga_live_transport(profile)
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=required_cell_ids,
        kernel=kernel,
        route_policy=route_policy,
        policy=policy,
        strict=False,
    )
    attempted: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    model_calls = 0
    failure_capture_ref = ""

    def execute_step(
        messages: Sequence[Mapping[str, Any]],
        step_tools: Sequence[Mapping[str, Any]],
        step_index: int,
    ) -> AgentToolStepResult:
        nonlocal model_calls, failure_capture_ref
        model_calls += 1
        try:
            step = transport(
                profile=profile,
                messages=messages,
                tools=step_tools,
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=f"{attempt_prefix}-{step_index:02d}-ATTEMPT-01",
                tool_choice=None,
            )
        except ModelGatewayError as exc:
            failure_capture_ref = exc.capture_ref
            raise
        attempted.append(step.as_dict())
        return step

    loop_result: Mapping[str, Any] = {}
    failure_phase = ""
    failure_code = ""
    try:
        loop_result = run_bounded_finance_loop(
            policy=policy,
            research_input=research_input,
            required_cell_ids=required_cell_ids,
            kernel=kernel,
            route_policy=route_policy,
            planning_policy=planning_policy,
            tools=tools,
            step_executor=execute_step,
            receipt_recorder=lambda value: receipts.append(deepcopy(dict(value))),
            visible_execution_budget=visible_execution_budget,
        ).as_dict()
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
    except BoundedFinanceLoopError as exc:
        failure_phase = "local_finance_loop_validation"
        failure_code = exc.code
        if attempted and not failure_capture_ref:
            failure_capture_ref = str(attempted[-1]["response_capture_ref"])

    return FinanceLoopTransportLaneResult(
        lane=lane,
        wire_api=profile.wire_api,
        status=(
            "completed_contract_valid_content_assessment_pending"
            if loop_result
            else "terminal_failed_no_retry"
        ),
        model_calls_attempted=model_calls,
        attempted_provider_steps=tuple(attempted),
        receipts=tuple(receipts),
        loop_result=loop_result,
        failure_phase=failure_phase,
        failure_code=failure_code,
        failure_capture_ref=failure_capture_ref,
    )


__all__ = [
    "FinanceLoopTransportLaneResult",
    "execute_finance_loop_transport_lane",
]
