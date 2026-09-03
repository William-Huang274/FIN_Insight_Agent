from __future__ import annotations

import asyncio
import operator
import time
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class CounterState(TypedDict, total=False):
    case_id: str
    delta: int
    total: int
    observations: Annotated[list[dict[str, Any]], operator.add]


def increment_counter(state: CounterState) -> CounterState:
    previous_total = int(state.get("total", 0))
    delta = int(state.get("delta", 1))
    new_total = previous_total + delta
    return {
        "total": new_total,
        "observations": [
            {
                "kind": "counter_incremented",
                "previous_total": previous_total,
                "delta": delta,
                "new_total": new_total,
            }
        ],
    }


counter_builder = StateGraph(CounterState)
counter_builder.add_node("increment_counter", increment_counter)
counter_builder.add_edge(START, "increment_counter")
counter_builder.add_edge("increment_counter", END)
counter_graph = counter_builder.compile()


class ApprovalState(TypedDict, total=False):
    case_id: str
    proposed_action: dict[str, Any]
    approval: dict[str, Any]
    result: dict[str, Any]
    steps: Annotated[list[str], operator.add]


def prepare_approval(state: ApprovalState) -> ApprovalState:
    return {"steps": ["proposal_prepared"]}


def await_approval(state: ApprovalState) -> ApprovalState:
    approval = interrupt(
        {
            "kind": "fin_exact_action_approval",
            "case_id": state.get("case_id"),
            "proposed_action": state.get("proposed_action", {}),
        }
    )
    if not isinstance(approval, dict):
        raise TypeError("approval resume value must be an object")
    return {"approval": approval, "steps": ["approval_received"]}


def finalize_approval(state: ApprovalState) -> ApprovalState:
    approved = bool(state.get("approval", {}).get("approved"))
    return {
        "result": {
            "approved": approved,
            "disposition": "execute_allowed" if approved else "execute_denied",
        },
        "steps": ["approval_finalized"],
    }


approval_builder = StateGraph(ApprovalState)
approval_builder.add_node("prepare_approval", prepare_approval)
approval_builder.add_node("await_approval", await_approval)
approval_builder.add_node("finalize_approval", finalize_approval)
approval_builder.add_edge(START, "prepare_approval")
approval_builder.add_edge("prepare_approval", "await_approval")
approval_builder.add_edge("await_approval", "finalize_approval")
approval_builder.add_edge("finalize_approval", END)
approval_graph = approval_builder.compile()


class SlowState(TypedDict, total=False):
    case_id: str
    duration_seconds: float
    completed: bool
    execution_window: dict[str, float]
    steps: Annotated[list[str], operator.add]


async def slow_operation(state: SlowState) -> SlowState:
    duration = max(1.0, min(float(state.get("duration_seconds", 8.0)), 30.0))
    started = time.monotonic()
    await asyncio.sleep(duration)
    finished = time.monotonic()
    return {
        "completed": True,
        "execution_window": {"started": started, "finished": finished},
        "steps": ["slow_operation_completed"],
    }


slow_builder = StateGraph(SlowState)
slow_builder.add_node("slow_operation", slow_operation)
slow_builder.add_edge(START, "slow_operation")
slow_builder.add_edge("slow_operation", END)
slow_graph = slow_builder.compile()


class ParallelState(TypedDict, total=False):
    case_id: str
    branch_duration_seconds: float
    branch_windows: Annotated[list[dict[str, Any]], operator.add]
    completed: bool


async def _parallel_branch(state: ParallelState, branch: str) -> ParallelState:
    duration = max(
        0.5, min(float(state.get("branch_duration_seconds", 1.5)), 10.0)
    )
    started = time.monotonic()
    await asyncio.sleep(duration)
    finished = time.monotonic()
    return {
        "branch_windows": [
            {"branch": branch, "started": started, "finished": finished}
        ]
    }


async def parallel_left(state: ParallelState) -> ParallelState:
    return await _parallel_branch(state, "left")


async def parallel_right(state: ParallelState) -> ParallelState:
    return await _parallel_branch(state, "right")


def parallel_join(state: ParallelState) -> ParallelState:
    return {"completed": len(state.get("branch_windows", [])) == 2}


parallel_builder = StateGraph(ParallelState)
parallel_builder.add_node("parallel_left", parallel_left)
parallel_builder.add_node("parallel_right", parallel_right)
parallel_builder.add_node("parallel_join", parallel_join)
parallel_builder.add_edge(START, "parallel_left")
parallel_builder.add_edge(START, "parallel_right")
parallel_builder.add_edge(["parallel_left", "parallel_right"], "parallel_join")
parallel_builder.add_edge("parallel_join", END)
parallel_graph = parallel_builder.compile()
