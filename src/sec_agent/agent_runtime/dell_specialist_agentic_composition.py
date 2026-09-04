"""Thin Wave-2 bridge from one Specialist loop to the approved Dell MCP data plane.

This module does not create a second retriever, MCP server, or runtime.  It
opens the existing Owner-approved composition and translates one semantic
Specialist action into the existing ``ToolLaneTask`` contract.  All physical
selector compilation remains inside ``DellMCPToolLaneAdapter`` and
``SourceFamilyCompiler``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Literal

from .dell_agent_server_data_composition import (
    DellApprovedDataCompositionError,
    open_dell_approved_data_composition,
)
from .dell_reference_vertical_contracts import (
    BoundBranchTask,
    ToolLaneResult,
    ToolLaneTask,
    canonical_sha256,
)
from .dell_agentic_contracts import canonical_digest
from .dell_specialist_agentic_graph import (
    DellSpecialistAgenticDependencies,
    ModelTurnPort,
    RequestEvidenceAction,
    RequestFinanceAction,
    SpecialistAgenticInput,
    SpecialistObservedReference,
    SpecialistRouteCompletion,
    SpecialistToolFailure,
    SpecialistToolObservation,
    SpecialistToolRequest,
    build_dell_specialist_agentic_state_graph,
)
from .dell_source_family_compiler import (
    HostOwnedBaselineSourcePlan,
    ReviewedEvidenceFilterReceipt,
    SourceFamilyCompilationReceipt,
)
from sec_agent.research_foundation.data_ports import (
    NumericFactProjection,
    ReviewedEvidenceProjection,
)


class DellSpecialistAgenticCompositionError(RuntimeError):
    """Typed zero-model composition failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


SpecialistToolPort = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class DellSpecialistScriptedQualificationComposition:
    """Explicitly non-product, zero-call graph qualification fixture."""

    graph_input: SpecialistAgenticInput
    graph: Any
    owner_data_gate_decision_digest: str
    inventory_snapshot_digest: str
    source_route_catalog_digest: str
    model_execution_state: Literal[
        "scripted_qualification_not_model_execution"
    ] = "scripted_qualification_not_model_execution"
    model_execution_receipts_authorized: Literal[False] = False
    provider_model_calls_authorized: Literal[False] = False
    network_calls_authorized: Literal[False] = False
    paid_calls_authorized: Literal[False] = False
    live_external_calls_authorized: Literal[False] = False

def _model_json(model: type[Any], value: Any, *, code: str) -> Any:
    try:
        return model.model_validate_json(
            json.dumps(value, ensure_ascii=False, allow_nan=False)
        )
    except Exception:
        raise DellSpecialistAgenticCompositionError(code) from None


def _required_routes(
    source_route_catalog: Mapping[str, Any],
    *,
    branch_id: str,
) -> tuple[Mapping[str, Any], ...]:
    routes = source_route_catalog.get("routes")
    if not isinstance(routes, list | tuple):
        raise DellSpecialistAgenticCompositionError(
            "specialist_source_route_catalog_invalid"
        )
    candidates = [
        row
        for row in routes
        if isinstance(row, Mapping)
        and row.get("coverage_obligation_id") == branch_id
        and row.get("requirement") == "required"
    ]
    if not candidates:
        raise DellSpecialistAgenticCompositionError(
            "specialist_required_route_missing"
        )
    ordered = tuple(
        sorted(
            candidates,
            key=lambda row: str(
                row.get("minimum_route_obligation_id") or ""
            ),
        )
    )
    # Wave 2 can only close a required route when existing S1 returns
    # writer-citable Reviewed Evidence. Other route kinds must wait for their
    # owning authority adapter instead of being treated as complete here.
    if any(row.get("intent_kind") != "reviewed_evidence" for row in ordered):
        raise DellSpecialistAgenticCompositionError(
            "specialist_required_route_authority_unsupported"
        )
    return ordered


def _build_graph_input(
    *,
    run_id: str,
    run_invocation_id: str,
    branch_id: str,
    foundation_binding: Any,
    source_route_catalog: Mapping[str, Any],
    owner_data_gate_decision_digest: str,
    inventory_snapshot_digest: str,
    max_model_turns: int,
    max_tool_actions: int,
) -> SpecialistAgenticInput:
    methods = {
        method.branch_id: method for method in foundation_binding.branch_methods
    }
    method = methods.get(branch_id)
    if method is None:
        raise DellSpecialistAgenticCompositionError(
            "specialist_branch_method_missing"
        )
    required_routes = _required_routes(
        source_route_catalog,
        branch_id=branch_id,
    )
    required_route_ids = tuple(
        str(route["minimum_route_obligation_id"])
        for route in required_routes
    )
    seeds = tuple(
        {
            "minimum_route_obligation_id": route[
                "minimum_route_obligation_id"
            ],
            "answer_free_intent_kind": str(route.get("intent_kind") or ""),
        }
        for route in required_routes
    )
    plan_basis = {
        "run_id": run_id,
        "run_invocation_id": run_invocation_id,
        "case_id": foundation_binding.case_id,
        "branch_id": branch_id,
        "research_as_of": foundation_binding.research_as_of,
        "snapshot_id": foundation_binding.snapshot_id,
        "foundation_digest": foundation_binding.foundation_digest,
        "method_digest": method.method_digest,
        "required_route_obligation_ids": required_route_ids,
    }
    task = BoundBranchTask(
        task_id=f"wave2:{branch_id}:{canonical_sha256(plan_basis)[:20]}",
        case_id=foundation_binding.case_id,
        branch_id=branch_id,
        revision=0,
        priority=method.priority,
        objective=method.objective,
        evidence_requests=seeds,
        fact_requests=(),
        research_as_of=foundation_binding.research_as_of,
        snapshot_id=foundation_binding.snapshot_id,
        foundation_digest=foundation_binding.foundation_digest,
        method_digest=method.method_digest,
        plan_digest=canonical_sha256(plan_basis),
    )
    l0_body = {
        "owner_data_gate_decision_digest": owner_data_gate_decision_digest,
        "source_route_catalog_digest": source_route_catalog["catalog_digest"],
        "inventory_snapshot_digest": inventory_snapshot_digest,
        "branch_id": branch_id,
        "available_tool_kinds": ["evidence", "finance"],
        "required_route_count": len(required_route_ids),
        "required_route_details_are_in_task_assignment": True,
        "optional_route_inventory_requires_disclosure": True,
        "answer_free": True,
        "grants_authority": False,
    }
    return SpecialistAgenticInput(
        run_id=run_id,
        run_invocation_id=run_invocation_id,
        agent_id=f"specialist:{branch_id}",
        task=task,
        required_route_obligation_ids=required_route_ids,
        l0_context={
            "owner_data_gate_decision_digest": (
                owner_data_gate_decision_digest
            ),
            "source_route_catalog_digest": source_route_catalog["catalog_digest"],
            "inventory_snapshot_digest": inventory_snapshot_digest,
            "disclosure_runtime_state": (
                "current_state_authority_unavailable_fail_closed"
            ),
            "capability_summaries": (l0_body,),
            "skill_summaries": (
                {
                    "skill_ref": f"skill:dell:{branch_id.lower()}",
                    "purpose": (
                        "Answer-free branch method pointer only; content "
                        "disclosure remains unavailable until current-state "
                        "authority ports are wired."
                    ),
                    "grants_authority": False,
                },
            ),
        },
        max_model_turns=max_model_turns,
        max_tool_actions=max_tool_actions,
    )


def _reference_from_item(item: Mapping[str, Any]) -> SpecialistObservedReference | None:
    state = str(item.get("result_state") or "")
    if state == "reviewed_evidence":
        projection = _model_json(
            ReviewedEvidenceProjection,
            {
                field_name: item.get(field_name)
                for field_name in ReviewedEvidenceProjection.model_fields
            },
            code="specialist_reviewed_evidence_projection_invalid",
        )
        ref_id = projection.evidence_id
        artifact_digest = projection.evidence_item_digest
        authority = "reviewed_evidence"
    elif state == "retrieval_candidate":
        ref_id = str(
            item.get("candidate_id")
            or item.get("node_id")
            or item.get("source_record_id")
            or f"candidate:{canonical_sha256(item)[:24]}"
        )
        artifact_digest = canonical_sha256(
            {
                key: value
                for key, value in item.items()
                if key not in {"mcp_receipt_chain", "source_tool_lane_receipt_id"}
            }
        )
        authority = "retrieval_candidate"
    elif state == "captured_source_candidate":
        ref_id = str(
            item.get("capture_id")
            or item.get("source_record_id")
            or f"capture:{canonical_sha256(item)[:24]}"
        )
        artifact_digest = canonical_sha256(
            {
                key: value
                for key, value in item.items()
                if key not in {"mcp_receipt_chain", "source_tool_lane_receipt_id"}
            }
        )
        authority = "captured_source_candidate"
    elif state == "numeric_fact":
        projection = _model_json(
            NumericFactProjection,
            {
                field_name: item.get(field_name)
                for field_name in NumericFactProjection.model_fields
            },
            code="specialist_numeric_fact_projection_invalid",
        )
        ref_id = projection.numeric_fact_id
        artifact_digest = canonical_sha256(projection)
        authority = "numeric_fact"
    elif state == "deterministic_derived_metric":
        ref_id = str(
            item.get("fact_id")
            or item.get("derived_metric_id")
            or f"metric:{canonical_sha256(item)[:24]}"
        )
        artifact_digest = canonical_sha256(
            {
                key: value
                for key, value in item.items()
                if key not in {"mcp_receipt_chain", "source_tool_lane_receipt_id"}
            }
        )
        authority = "non_authoritative_metric"
    elif state == "research_scenario":
        ref_id = str(
            item.get("scenario_id")
            or f"scenario:{canonical_sha256(item)[:24]}"
        )
        artifact_digest = canonical_sha256(
            {
                key: value
                for key, value in item.items()
                if key not in {"mcp_receipt_chain", "source_tool_lane_receipt_id"}
            }
        )
        authority = "research_scenario"
    else:
        return None
    if not ref_id:
        raise DellSpecialistAgenticCompositionError(
            "specialist_tool_reference_id_missing"
        )
    return SpecialistObservedReference(
        ref_id=ref_id,
        artifact_digest=artifact_digest,
        authority_state=authority,
        writer_citable=authority == "reviewed_evidence",
        numeric_fact_authority=authority == "numeric_fact",
    )


def _failure_from_result(
    result: ToolLaneResult,
) -> SpecialistToolFailure | None:
    if result.failure is None:
        return None
    owner = {
        "s1_tool": "s1_data",
        "s2_tool": "s2_data",
        "tool_transport": "tool_adapter",
        "runtime": "runtime_data_binding",
    }[result.failure.owner_layer]
    return SpecialistToolFailure(
        code=result.failure.code,
        owning_plane=owner,
        retryability=(
            "correctable_with_new_information"
            if result.failure.retryable
            else "owner_repair_required"
        ),
        public_information_gap_proved=False,
    )


def _route_completions_from_result(
    *,
    request: SpecialistToolRequest,
    result: ToolLaneResult,
    baseline_source_plan: HostOwnedBaselineSourcePlan,
) -> tuple[SpecialistRouteCompletion, ...]:
    action = request.action
    if not isinstance(action, RequestEvidenceAction):
        return ()
    route = next(
        (
            row
            for row in baseline_source_plan.source_plan.route_obligations
            if row.route_obligation_id
            == action.minimum_route_obligation_id
        ),
        None,
    )
    if (
        route is None
        or route.coverage_obligation_id != request.task.branch_id
        or route.route_kind != "reviewed_evidence"
    ):
        raise DellSpecialistAgenticCompositionError(
            "specialist_route_baseline_binding_invalid"
        )
    receipts: dict[str, SourceFamilyCompilationReceipt] = {}
    for item in result.items:
        chain = item.get("mcp_receipt_chain")
        if not isinstance(chain, list | tuple):
            continue
        for raw in chain:
            if not isinstance(raw, Mapping) or not raw.get(
                "compilation_receipt_id"
            ):
                continue
            receipt = _model_json(
                SourceFamilyCompilationReceipt,
                raw,
                code="specialist_source_compilation_receipt_invalid",
            )
            if (
                receipt.minimum_route_obligation_id
                != action.minimum_route_obligation_id
            ):
                continue
            receipts[receipt.receipt_digest] = receipt
    if not receipts:
        return ()
    if len(receipts) != 1:
        raise DellSpecialistAgenticCompositionError(
            "specialist_source_compilation_receipt_ambiguous"
        )
    receipt = next(iter(receipts.values()))
    if (
        receipt.intent_kind != "reviewed_evidence"
        or receipt.branch_id != request.task.branch_id
        or receipt.coverage_obligation_id != route.coverage_obligation_id
        or receipt.minimum_route_digest != route.route_digest
        or receipt.baseline_source_plan_digest
        != baseline_source_plan.source_plan.source_plan_digest
        or receipt.expected_inventory_snapshot_digest
        != baseline_source_plan.inventory_snapshot_digest
        or receipt.inventory_snapshot_digest
        != baseline_source_plan.inventory_snapshot_digest
        or receipt.intent_digest != canonical_digest(action.intent)
        or not set(route.required_authority_refs).issubset(
            receipt.task_authority_refs
        )
        or receipt.disposition != "accepted"
        or receipt.corrections
        or not receipt.tool_call_authorized
    ):
        return ()
    expected_targets = tuple(
        sorted(target.target_ref for target in receipt.reviewed_targets)
    )
    expected_families = tuple(
        sorted(target.source_family_ref for target in receipt.reviewed_targets)
    )
    if expected_families != tuple(sorted(route.semantic_source_family_refs)):
        return ()
    target_by_ref = {
        target.target_ref: target for target in receipt.reviewed_targets
    }
    observed_rows: list[Mapping[str, Any]] = []
    observed_filter_receipts: list[ReviewedEvidenceFilterReceipt] = []
    for item in result.items:
        target_ref = item.get("compiled_target_ref")
        evidence_id = item.get("evidence_id")
        target = target_by_ref.get(str(target_ref))
        if (
            item.get("result_state") != "reviewed_evidence"
            or item.get("writer_citable") is not True
            or target is None
            or item.get("source_family_ref") != target.source_family_ref
            or not evidence_id
        ):
            continue
        filter_receipts: dict[str, ReviewedEvidenceFilterReceipt] = {}
        chain = item.get("mcp_receipt_chain")
        if isinstance(chain, list | tuple):
            for raw in chain:
                if not isinstance(raw, Mapping) or not raw.get(
                    "filter_receipt_id"
                ):
                    continue
                filter_receipt = _model_json(
                    ReviewedEvidenceFilterReceipt,
                    raw,
                    code="specialist_reviewed_filter_receipt_invalid",
                )
                if filter_receipt.compiled_target_digest == target.target_digest:
                    filter_receipts[filter_receipt.receipt_digest] = filter_receipt
        if len(filter_receipts) != 1:
            continue
        filter_receipt = next(iter(filter_receipts.values()))
        if (
            not filter_receipt.strict_route_satisfied
            or str(evidence_id) not in filter_receipt.accepted_evidence_ids
            or filter_receipt.reviewed_index_digest
            != target.reviewed_index_digest
        ):
            continue
        observed_rows.append(item)
        observed_filter_receipts.append(filter_receipt)
    observed_targets = tuple(
        sorted(
            {
                str(item["compiled_target_ref"])
                for item in observed_rows
            }
        )
    )
    if not expected_targets or observed_targets != expected_targets:
        return ()
    evidence_ids = tuple(
        sorted(
            {
                str(item["evidence_id"])
                for item in observed_rows
                if item.get("evidence_id")
            }
        )
    )
    if not evidence_ids:
        return ()
    reviewed_index_digests = tuple(
        sorted({row.reviewed_index_digest for row in observed_filter_receipts})
    )
    filter_receipt_digests = tuple(
        sorted({row.receipt_digest for row in observed_filter_receipts})
    )
    if not reviewed_index_digests or not filter_receipt_digests:
        return ()
    completion_body = {
        "schema_version": "fin_ia_dell_specialist_route_completion_v1_0",
        "route_obligation_id": action.minimum_route_obligation_id,
        "owner_data_gate_decision_digest": (
            request.owner_data_gate_decision_digest
        ),
        "source_route_catalog_digest": request.source_route_catalog_digest,
        "inventory_snapshot_digest": request.inventory_snapshot_digest,
        "baseline_source_plan_digest": (
            baseline_source_plan.source_plan.source_plan_digest
        ),
        "compilation_receipt_digest": receipt.receipt_digest,
        "reviewed_index_digests": reviewed_index_digests,
        "filter_receipt_digests": filter_receipt_digests,
        "expected_target_refs": expected_targets,
        "observed_target_refs": observed_targets,
        "source_family_refs": tuple(sorted(set(expected_families))),
        "evidence_ids": evidence_ids,
        "authority_status": "reviewed_evidence_complete",
    }
    return (
        SpecialistRouteCompletion(
            **completion_body,
            completion_digest=canonical_sha256(completion_body),
        ),
    )


def _observation_from_result(
    *,
    request: SpecialistToolRequest,
    result: ToolLaneResult,
    kind: Literal["evidence", "finance"],
    baseline_source_plan: HostOwnedBaselineSourcePlan,
) -> dict[str, Any]:
    references = tuple(
        reference
        for item in result.items
        if (reference := _reference_from_item(item)) is not None
    )
    failure = _failure_from_result(result)
    status: Literal["success", "empty", "tool_failure"]
    if result.status == "tool_failure":
        status = "tool_failure"
    elif references:
        status = "success"
    else:
        status = "empty"
    source_receipt = result.runtime_receipt
    expected_source_body = {
        "status": result.status,
        "result_states": list(result.result_states),
        "items": [dict(item) for item in result.items],
        "failure": (
            result.failure.model_dump(mode="json")
            if result.failure is not None
            else None
        ),
    }
    if (
        source_receipt.kind != "tool"
        or source_receipt.actor != f"{kind}_tool"
        or source_receipt.request_digest
        != canonical_sha256(_bound_task_for_action(request, lane=kind))
        or source_receipt.output_digest
        != canonical_sha256(expected_source_body)
        or source_receipt.transport_attempts != 1
    ):
        raise DellSpecialistAgenticCompositionError(
            "specialist_mcp_source_receipt_binding_invalid"
        )
    content = tuple(
        {
            **dict(item),
            "source_tool_lane_receipt_id": source_receipt.receipt_id,
        }
        for item in result.items[:64]
    )
    route_completions = _route_completions_from_result(
        request=request,
        result=result,
        baseline_source_plan=baseline_source_plan,
    )
    output_body = {
        "schema_version": "fin_ia_dell_specialist_tool_observation_v1_0",
        "action_attempt_id": request.action_attempt_id,
        "kind": kind,
        "provenance_kind": "mcp_bridge",
        "status": status,
        "request_digest": request.request_digest,
        "references": [row.model_dump(mode="json") for row in references],
        "content": list(content),
        "route_completions": [
            row.model_dump(mode="json") for row in route_completions
        ],
        "failure": failure.model_dump(mode="json") if failure else None,
        "source_runtime_receipt": source_receipt.model_dump(mode="json"),
    }
    host_receipt = {
        "receipt_id": (
            f"specialist-bridge:{kind}:{request.request_digest[:24]}"
        ),
        "kind": "host",
        "actor": "dell_specialist_agentic_mcp_bridge",
        "status": "failure" if status == "tool_failure" else "success",
        "request_digest": request.request_digest,
        "output_digest": canonical_sha256(output_body),
        "elapsed_ms": source_receipt.elapsed_ms,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "usage_reported": None,
        "transport_attempts": source_receipt.transport_attempts,
    }
    body = {
        **output_body,
        "runtime_receipt": host_receipt,
    }
    observation = _model_json(
        SpecialistToolObservation,
        {**body, "observation_digest": canonical_sha256(body)},
        code="specialist_mcp_observation_invalid",
    )
    return observation.model_dump(mode="json")


def _bound_task_for_action(
    request: SpecialistToolRequest,
    *,
    lane: Literal["evidence", "finance"],
) -> ToolLaneTask:
    task = request.task
    if lane == "evidence":
        action = request.action
        if not isinstance(action, RequestEvidenceAction):
            raise DellSpecialistAgenticCompositionError(
                "specialist_evidence_action_mismatch"
            )
        evidence_requests = (
            {
                "minimum_route_obligation_id": action.minimum_route_obligation_id,
                "intent": action.intent.model_dump(mode="json"),
            },
        )
        fact_requests: tuple[dict[str, Any], ...] = ()
    else:
        action = request.action
        if not isinstance(action, RequestFinanceAction):
            raise DellSpecialistAgenticCompositionError(
                "specialist_finance_action_mismatch"
            )
        evidence_requests = task.evidence_requests
        fact_requests = (action.intent.model_dump(mode="json"),)
    rebound_body = task.model_dump(mode="json")
    rebound_body.update(
        {
            "evidence_requests": evidence_requests,
            "fact_requests": fact_requests,
        }
    )
    rebound = _model_json(
        BoundBranchTask,
        rebound_body,
        code="specialist_rebound_branch_task_invalid",
    )
    return ToolLaneTask(lane=lane, task=rebound)


def _mcp_port(
    *,
    expected_task: BoundBranchTask,
    baseline_source_plan: HostOwnedBaselineSourcePlan,
    owner_data_gate_decision_digest: str,
    inventory_snapshot_digest: str,
    source_route_catalog_digest: str,
    lane: Literal["evidence", "finance"],
    tool: SpecialistToolPort,
) -> SpecialistToolPort:
    def execute(value: Mapping[str, Any]) -> Mapping[str, Any]:
        request = _model_json(
            SpecialistToolRequest,
            value,
            code="specialist_tool_request_invalid",
        )
        if canonical_sha256(request.task) != canonical_sha256(expected_task):
            raise DellSpecialistAgenticCompositionError(
                "specialist_tool_task_binding_mismatch"
            )
        if (
            request.owner_data_gate_decision_digest
            != owner_data_gate_decision_digest
            or request.inventory_snapshot_digest != inventory_snapshot_digest
            or request.source_route_catalog_digest
            != source_route_catalog_digest
        ):
            raise DellSpecialistAgenticCompositionError(
                "specialist_tool_current_authority_binding_mismatch"
            )
        if isinstance(request.action, RequestEvidenceAction):
            assigned_route_ids = {
                str(row.get("minimum_route_obligation_id") or "")
                for row in expected_task.evidence_requests
            }
            if request.action.minimum_route_obligation_id not in assigned_route_ids:
                raise DellSpecialistAgenticCompositionError(
                    "specialist_evidence_route_not_assigned"
                )
        lane_task = _bound_task_for_action(request, lane=lane)
        raw = tool(lane_task.model_dump(mode="json"))
        result = _model_json(
            ToolLaneResult,
            raw,
            code="specialist_mcp_tool_result_invalid",
        )
        rebound = lane_task.task
        if (
            result.lane != lane
            or result.task_id != rebound.task_id
            or result.case_id != rebound.case_id
            or result.branch_id != rebound.branch_id
            or result.revision != rebound.revision
            or result.research_as_of != rebound.research_as_of
            or result.snapshot_id != rebound.snapshot_id
            or result.foundation_digest != rebound.foundation_digest
            or result.method_digest != rebound.method_digest
            or result.plan_digest != rebound.plan_digest
        ):
            raise DellSpecialistAgenticCompositionError(
                "specialist_mcp_tool_result_binding_mismatch"
            )
        return _observation_from_result(
            request=request,
            result=result,
            kind=lane,
            baseline_source_plan=baseline_source_plan,
        )

    return execute


@contextmanager
def open_dell_specialist_scripted_qualification_composition(
    *,
    run_id: str,
    run_invocation_id: str,
    branch_id: str,
    max_model_turns: int = 8,
    max_tool_actions: int = 12,
    environment: Mapping[str, str] | None = None,
    scripted_model_turn: ModelTurnPort,
) -> Iterator[DellSpecialistScriptedQualificationComposition]:
    """Open a scripted, zero-call qualification over the approved local MCP.

    This is deliberately not a production/model composition.  The scripted
    semantic action port creates no model execution receipt or paid authority.
    """

    try:
        with open_dell_approved_data_composition(
            run_invocation_id=run_invocation_id,
            environment=environment,
        ) as approved:
            graph_input = _build_graph_input(
                run_id=run_id,
                run_invocation_id=run_invocation_id,
                branch_id=branch_id,
                foundation_binding=approved.foundation_binding,
                source_route_catalog=approved.source_route_catalog,
                owner_data_gate_decision_digest=approved.decision_digest,
                inventory_snapshot_digest=approved.inventory_snapshot_digest,
                max_model_turns=max_model_turns,
                max_tool_actions=max_tool_actions,
            )
            task = graph_input.task
            dependencies = DellSpecialistAgenticDependencies(
                model_turn=scripted_model_turn,
                evidence_tool=_mcp_port(
                    expected_task=task,
                    baseline_source_plan=approved.baseline_source_plan,
                    owner_data_gate_decision_digest=approved.decision_digest,
                    inventory_snapshot_digest=approved.inventory_snapshot_digest,
                    source_route_catalog_digest=approved.source_route_catalog_digest,
                    lane="evidence",
                    tool=approved.dependencies.evidence_tool,
                ),
                finance_tool=_mcp_port(
                    expected_task=task,
                    baseline_source_plan=approved.baseline_source_plan,
                    owner_data_gate_decision_digest=approved.decision_digest,
                    inventory_snapshot_digest=approved.inventory_snapshot_digest,
                    source_route_catalog_digest=approved.source_route_catalog_digest,
                    lane="finance",
                    tool=approved.dependencies.finance_tool,
                ),
            )
            yield DellSpecialistScriptedQualificationComposition(
                graph_input=graph_input,
                graph=build_dell_specialist_agentic_state_graph(
                    dependencies=dependencies
                ).compile(),
                owner_data_gate_decision_digest=approved.decision_digest,
                inventory_snapshot_digest=approved.inventory_snapshot_digest,
                source_route_catalog_digest=approved.source_route_catalog_digest,
            )
    except DellSpecialistAgenticCompositionError:
        raise
    except DellApprovedDataCompositionError as exc:
        raise DellSpecialistAgenticCompositionError(exc.code) from None


__all__ = [
    "DellSpecialistAgenticCompositionError",
    "DellSpecialistScriptedQualificationComposition",
    "open_dell_specialist_scripted_qualification_composition",
]
