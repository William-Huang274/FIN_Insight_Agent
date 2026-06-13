from __future__ import annotations

from dataclasses import dataclass
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


def _model_tier(task: InferenceTask, *, token_budget_pressure: bool) -> str:
    if task.route in {"exact_lookup", "deterministic_gate", "data_quality_eval"}:
        return "deterministic"
    if token_budget_pressure and task.model_tier in {"standard", "pro"}:
        return "flash_or_coalesced"
    return task.model_tier
