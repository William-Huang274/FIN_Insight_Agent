from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class InferenceTask:
    task_id: str
    route: str
    priority: int = 5
    requires_cuda_bge: bool = False
    can_spill_to_cpu: bool = True
    model_tier: str = "standard"


@dataclass(frozen=True)
class ScheduledTask:
    task_id: str
    route: str
    lane: str
    model_tier: str
    reason: str
    queue_position: int = 0
    estimated_wait_ms: int = 0


@dataclass(frozen=True)
class SchedulerAudit:
    schema_version: str
    status: str
    cuda_bge_slots: int
    cuda_bge_used: int
    cpu_spillover_allowed: bool
    token_budget_pressure: bool
    scheduled_tasks: list[dict[str, object]]
    lane_counts: dict[str, int]
    policy: str


def schedule_inference_tasks(
    tasks: Iterable[InferenceTask],
    *,
    cuda_bge_slots: int = 3,
    cpu_spillover_allowed: bool = True,
    token_budget_pressure: bool = False,
) -> list[ScheduledTask]:
    """Deterministic P9 resource scheduler.

    This does not execute models. It assigns work to CUDA BGE, CPU spillover, or
    low-cost model lanes so the runtime can audit resource decisions before
    falling back globally to CPU or expensive models.
    """

    ordered = sorted(tasks, key=lambda task: (task.priority, task.task_id))
    cuda_used = 0
    scheduled: list[ScheduledTask] = []
    for task in ordered:
        model_tier = _model_tier(task, token_budget_pressure=token_budget_pressure)
        if task.requires_cuda_bge and cuda_used < max(0, cuda_bge_slots):
            cuda_used += 1
            scheduled.append(ScheduledTask(task.task_id, task.route, "bge_cuda", model_tier, "cuda_slot_available"))
        elif task.requires_cuda_bge and task.can_spill_to_cpu and cpu_spillover_allowed:
            scheduled.append(ScheduledTask(task.task_id, task.route, "bge_cpu_spillover", model_tier, "cuda_queue_full_cpu_allowed"))
        elif task.requires_cuda_bge:
            scheduled.append(ScheduledTask(task.task_id, task.route, "queued_bge_cuda", model_tier, "cuda_queue_full_cpu_not_allowed"))
        else:
            scheduled.append(ScheduledTask(task.task_id, task.route, "non_bge_worker", model_tier, "no_cuda_bge_required"))
    return scheduled


def schedule_inference_tasks_with_audit(
    tasks: Iterable[InferenceTask],
    *,
    cuda_bge_slots: int = 3,
    cpu_spillover_allowed: bool = True,
    token_budget_pressure: bool = False,
    per_cuda_task_wait_ms: int = 250,
) -> SchedulerAudit:
    scheduled = schedule_inference_tasks(
        tasks,
        cuda_bge_slots=cuda_bge_slots,
        cpu_spillover_allowed=cpu_spillover_allowed,
        token_budget_pressure=token_budget_pressure,
    )
    lane_counts: dict[str, int] = {}
    cuda_queue_position = 0
    enriched: list[ScheduledTask] = []
    for item in scheduled:
        lane_counts[item.lane] = lane_counts.get(item.lane, 0) + 1
        if item.lane == "queued_bge_cuda":
            cuda_queue_position += 1
            enriched.append(
                ScheduledTask(
                    item.task_id,
                    item.route,
                    item.lane,
                    item.model_tier,
                    item.reason,
                    queue_position=cuda_queue_position,
                    estimated_wait_ms=cuda_queue_position * max(0, int(per_cuda_task_wait_ms)),
                )
            )
        else:
            enriched.append(item)
    return SchedulerAudit(
        schema_version="finsight_inference_resource_scheduler_audit_v0_1",
        status="pass",
        cuda_bge_slots=max(0, int(cuda_bge_slots)),
        cuda_bge_used=lane_counts.get("bge_cuda", 0),
        cpu_spillover_allowed=bool(cpu_spillover_allowed),
        token_budget_pressure=bool(token_budget_pressure),
        scheduled_tasks=[asdict(item) for item in enriched],
        lane_counts=lane_counts,
        policy="cuda_queue_first_cpu_spillover_explicit_model_tier_routing_v0_1",
    )


def coalesce_agent_tasks(tasks: Iterable[InferenceTask], *, max_group_size: int = 2) -> list[InferenceTask]:
    """Merge low-priority non-CUDA specialist tasks by route to reduce model calls."""

    groups: dict[tuple[str, str, bool], list[InferenceTask]] = {}
    passthrough: list[InferenceTask] = []
    for task in tasks:
        if task.requires_cuda_bge or task.priority <= 2 or task.route in {"memo_writer", "research_lead", "deterministic_gate"}:
            passthrough.append(task)
            continue
        key = (task.route, task.model_tier, task.can_spill_to_cpu)
        groups.setdefault(key, []).append(task)

    merged = list(passthrough)
    for (route, model_tier, can_spill), values in groups.items():
        for group_index in range(0, len(values), max(1, int(max_group_size))):
            chunk = values[group_index : group_index + max(1, int(max_group_size))]
            if len(chunk) == 1:
                merged.append(chunk[0])
                continue
            merged.append(
                InferenceTask(
                    task_id="+".join(task.task_id for task in chunk),
                    route=route,
                    priority=min(task.priority for task in chunk),
                    requires_cuda_bge=False,
                    can_spill_to_cpu=can_spill,
                    model_tier=model_tier,
                )
            )
    return sorted(merged, key=lambda task: (task.priority, task.task_id))


def _model_tier(task: InferenceTask, *, token_budget_pressure: bool) -> str:
    if task.route in {"exact_lookup", "deterministic_gate", "data_quality_eval"}:
        return "deterministic"
    if token_budget_pressure and task.model_tier in {"standard", "pro"}:
        return "flash_or_coalesced"
    return task.model_tier
