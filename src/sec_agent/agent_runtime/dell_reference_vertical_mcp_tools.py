"""Official MCP Client adapter for the synchronous DELL graph tool lanes.

Runtime composition owns this context manager. AnyIO only bridges the graph's
sync callable boundary to MCP's async Client; no scheduler, retry engine, cell
binding, or direct data-port access is implemented here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
import json
from threading import RLock
from time import perf_counter
from typing import Any, Literal

from anyio.from_thread import BlockingPortal, start_blocking_portal

from sec_agent.research_foundation.contracts import (
    DellReferenceVerticalFoundation,
    DellResearchRunScope,
    project_dell_research_method,
)
from sec_agent.research_foundation.mcp_server import (
    CAPTURE_EXTERNAL_SOURCE_TOOL,
    GET_RESEARCH_METHOD_TOOL,
    QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_BY_ID_TOOL,
    SEARCH_EXTERNAL_SOURCES_TOOL,
    SEARCH_LOCAL_KNOWLEDGE_TOOL,
    SEARCH_REVIEWED_EVIDENCE_TOOL,
)
from .dell_reference_vertical_contracts import (
    AgentRuntimeScopeCeiling,
    BranchMethodBinding,
    CaseFoundationBinding,
    EvidenceRequest,
    RuntimeReceipt,
    ToolFailure,
    ToolLaneResult,
    ToolLaneTask,
    canonical_sha256,
)


_TOOLS = frozenset(
    {
        GET_RESEARCH_METHOD_TOOL,
        SEARCH_REVIEWED_EVIDENCE_TOOL,
        READ_REVIEWED_EVIDENCE_BY_ID_TOOL,
        SEARCH_LOCAL_KNOWLEDGE_TOOL,
        QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
        SEARCH_EXTERNAL_SOURCES_TOOL,
        CAPTURE_EXTERNAL_SOURCE_TOOL,
    }
)
_EVIDENCE_KEYS = frozenset(EvidenceRequest.model_fields)
_FACT_KEYS = frozenset(
    {
        "ticker", "metric_id", "metric_ids", "research_as_of", "granularity",
        "period_start", "period_end", "fiscal_years", "requested_unit", "unit_family",
    }
)


class DellMCPToolAdapterError(RuntimeError):
    """The lifecycle, request, or graph-to-MCP binding is invalid."""


class _MCPTransportError(DellMCPToolAdapterError):
    pass


@dataclass(frozen=True)
class DellMCPRunBinding:
    """Composition-time bridge for graph branch digests and MCP method scope.

    Graph ``method_digest`` is branch-local; MCP ``method_sha256`` seals the whole
    selected package. They are not interchangeable, so composition must supply
    branch digests from the same foundation binder.
    """

    case_id: str
    foundation_digest: str
    selected_branch_ids: tuple[str, ...]
    branch_method_digests: Mapping[str, str]
    execution_attempt_id: str
    source_policy: Literal[
        "frozen_local_reviewed_plus_public_web_locator_only"
    ] = "frozen_local_reviewed_plus_public_web_locator_only"

    def __post_init__(self) -> None:
        branches = self.selected_branch_ids
        digests = (self.foundation_digest, *self.branch_method_digests.values())
        if (
            not self.case_id.strip()
            or not self.execution_attempt_id.strip()
            or not branches
            or len(branches) != len(set(branches))
            or set(self.branch_method_digests) != set(branches)
            or any(not _digest(value) for value in digests)
        ):
            raise ValueError("mcp_run_binding_invalid")


@dataclass(frozen=True)
class DellMCPGraphRunComposition:
    """One foundation-derived binding shared by graph and MCP composition."""

    foundation_binding: CaseFoundationBinding
    mcp_run_binding: DellMCPRunBinding

    def foundation_binder(self, request: Mapping[str, Any]) -> dict[str, Any]:
        expected = self.foundation_binding
        for field in ("case_id", "research_as_of", "snapshot_id", "foundation_digest"):
            if request.get(field) != getattr(expected, field):
                raise DellMCPToolAdapterError(
                    f"mcp_graph_foundation_request_{field}_mismatch"
                )
        return expected.model_dump(mode="json")


def compose_dell_mcp_graph_run(
    foundation: DellReferenceVerticalFoundation,
    *,
    branch_ids: Sequence[str],
    research_as_of: str,
    snapshot_id: str,
    execution_attempt_id: str,
) -> DellMCPGraphRunComposition:
    """Atomically derive graph branch methods and the matching MCP run binding."""

    _as_of(research_as_of)
    package = project_dell_research_method(foundation, branch_ids)
    selected = package.method.selected_branch_ids
    branch_catalog = {row.branch_id: row for row in foundation.question_branches}
    branch_methods: list[BranchMethodBinding] = []
    branch_digests: dict[str, str] = {}
    for branch_id in selected:
        branch = branch_catalog[branch_id]
        branch_package = project_dell_research_method(foundation, (branch_id,))
        context = branch_package.method.model_dump(mode="json")
        branch_digests[branch_id] = branch_package.method_sha256
        branch_methods.append(
            BranchMethodBinding(
                branch_id=branch_id,
                priority=branch.priority,
                objective=branch.objective,
                method_digest=branch_package.method_sha256,
                method_context=context,
            )
        )
    foundation_digest = canonical_sha256(foundation)
    foundation_binding = CaseFoundationBinding(
        case_id=foundation.case_identity.case_id,
        research_as_of=research_as_of,
        snapshot_id=snapshot_id,
        foundation_digest=foundation_digest,
        scope_ceiling=AgentRuntimeScopeCeiling(
            maximum_external_search_rounds_per_high_materiality_branch=(
                foundation.scope_ceiling.maximum_external_search_rounds_per_high_materiality_branch
            ),
            maximum_results_per_search=(
                foundation.scope_ceiling.maximum_results_per_search
            ),
            maximum_captured_pages_per_branch=(
                foundation.scope_ceiling.maximum_captured_pages_per_branch
            ),
            maximum_live_pages_per_run=(
                foundation.scope_ceiling.maximum_live_pages_per_run
            ),
            maximum_sources_visible_per_agent_step=(
                foundation.scope_ceiling.maximum_sources_visible_per_agent_step
            ),
            maximum_targeted_counter_reroutes=(
                foundation.scope_ceiling.maximum_targeted_counter_reroutes
            ),
        ),
        branch_methods=tuple(branch_methods),
        required_branch_ids=selected,
    )
    return DellMCPGraphRunComposition(
        foundation_binding=foundation_binding,
        mcp_run_binding=DellMCPRunBinding(
            case_id=foundation_binding.case_id,
            foundation_digest=foundation_digest,
            selected_branch_ids=selected,
            branch_method_digests=branch_digests,
            execution_attempt_id=execution_attempt_id,
        ),
    )


@dataclass(frozen=True)
class _Call:
    content: dict[str, Any] | None
    receipt: dict[str, Any]
    error: bool
    failure_kind: Literal[
        "transport",
        "mcp_server_error",
        "semantic_tool_failure",
    ] | None = None


class DellMCPToolLaneAdapter(AbstractContextManager["DellMCPToolLaneAdapter"]):
    """Long-lived official MCP Client exposed as two graph sync callables."""

    def __init__(
        self,
        server: Any,
        *,
        run_binding: DellMCPRunBinding,
        subject_ticker: str = "DELL",
        default_financial_granularity: str = "quarter_discrete",
        read_timeout_seconds: float = 60.0,
    ) -> None:
        self._server = server
        self._binding = run_binding
        self._ticker = subject_ticker.strip().upper()
        self._granularity = default_financial_granularity.strip()
        self._timeout = read_timeout_seconds
        if not self._ticker or not self._granularity:
            raise ValueError("mcp_adapter_default_empty")
        self._portal_cm: Any | None = None
        self._portal: BlockingPortal | None = None
        self._client_cm: Any | None = None
        self._client: Any | None = None
        self._discovery_digest: str | None = None
        self._lock = RLock()
        self._call_sequence = 0

    def __enter__(self) -> "DellMCPToolLaneAdapter":
        with self._lock:
            if self._portal is not None:
                raise DellMCPToolAdapterError("mcp_adapter_already_open")
            try:
                from mcp import Client
            except ImportError as exc:  # pragma: no cover - optional extra
                raise DellMCPToolAdapterError("mcp_v2_dependency_missing") from exc
            portal_cm = start_blocking_portal(name="fin-insight-dell-mcp-client")
            portal = portal_cm.__enter__()
            client = Client(
                self._server, raise_exceptions=False, read_timeout_seconds=self._timeout
            )
            client_cm = portal.wrap_async_context_manager(client)
            client_entered = False
            try:
                client_cm.__enter__()
                client_entered = True
                listed = portal.call(client.list_tools)
                discovered = tuple(
                    sorted(
                        (tool.name, tool.input_schema, tool.output_schema)
                        for tool in listed.tools
                    )
                )
                missing = sorted(_TOOLS.difference(row[0] for row in discovered))
                if missing:
                    raise DellMCPToolAdapterError(
                        f"mcp_required_tools_missing:{','.join(missing)}"
                    )
            except Exception:
                if client_entered:
                    client_cm.__exit__(None, None, None)
                portal_cm.__exit__(None, None, None)
                raise
            self._portal_cm, self._portal = portal_cm, portal
            self._client_cm, self._client = client_cm, client
            self._discovery_digest = canonical_sha256(discovered)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        with self._lock:
            portal_cm, client_cm = self._portal_cm, self._client_cm
            self._portal_cm = self._portal = self._client_cm = self._client = None
            self._discovery_digest = None
            if client_cm is None or portal_cm is None:
                return
            try:
                client_cm.__exit__(exc_type, exc, traceback)
            finally:
                portal_cm.__exit__(exc_type, exc, traceback)

    @property
    def evidence_tool(self):
        return self.execute_evidence

    @property
    def finance_tool(self):
        return self.execute_finance

    def execute_evidence(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return self._execute(value, "evidence").model_dump(mode="json")

    def execute_finance(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return self._execute(value, "finance").model_dump(mode="json")

    def _execute(self, value: Mapping[str, Any], lane: str) -> ToolLaneResult:
        started, task, calls, recoverable_calls, partial_items = (
            perf_counter(),
            None,
            [],
            [],
            [],
        )
        states: set[str] = set()
        try:
            task = ToolLaneTask.model_validate_json(
                json.dumps(value, ensure_ascii=False, allow_nan=False)
            )
            if task.lane != lane:
                raise DellMCPToolAdapterError("mcp_lane_callable_mismatch")
            self._validate_binding(task)
            method_call = self._method_call(task)
            calls.append(method_call)
            scope = self._scope(task, method_call)
            if lane == "evidence":
                self._evidence(
                    task,
                    scope,
                    items=partial_items,
                    states=states,
                    calls=calls,
                    recoverable_calls=recoverable_calls,
                )
            else:
                self._finance(
                    task,
                    scope,
                    items=partial_items,
                    states=states,
                    calls=calls,
                )
            if lane == "evidence" and states == {"tool_failure"}:
                failed_calls = [*calls, *recoverable_calls]
                error_owner = self._error_owner(failed_calls, lane)
                return self._failure(
                    task,
                    started,
                    failed_calls,
                    "mcp_all_required_evidence_routes_failed",
                    error_owner,
                    retryable=error_owner == "tool_transport",
                    partial_items=partial_items,
                )
            if any(call.error for call in calls):
                error_owner = self._error_owner(calls, lane)
                return self._failure(
                    task,
                    started,
                    calls,
                    "mcp_tool_returned_error",
                    error_owner,
                    retryable=error_owner == "tool_transport",
                    partial_items=partial_items,
                )
            for item in partial_items:
                item["mcp_receipt_chain"] = [
                    method_call.receipt, *item["mcp_receipt_chain"]
                ]
            return self._result(
                task,
                started,
                "success",
                states or {"typed_gap"},
                partial_items,
                None,
            )
        except Exception as exc:
            if task is None:
                raise DellMCPToolAdapterError("mcp_tool_lane_task_invalid") from exc
            owner = (
                "tool_transport"
                if isinstance(exc, (_MCPTransportError, OSError, TimeoutError))
                else self._error_owner(calls, lane)
            )
            return self._failure(
                task, started, calls, str(exc)[:240] or "mcp_adapter_failure", owner,
                retryable=owner == "tool_transport", exception_type=type(exc).__name__,
                partial_items=partial_items,
            )

    @staticmethod
    def _error_owner(
        calls: Sequence[_Call],
        lane: str,
    ) -> Literal["tool_transport", "s1_tool", "s2_tool"]:
        if any(call.failure_kind == "transport" for call in calls):
            return "tool_transport"
        return "s1_tool" if lane == "evidence" else "s2_tool"

    def _validate_binding(self, lane_task: ToolLaneTask) -> None:
        task, binding = lane_task.task, self._binding
        checks = {
            "mcp_task_case_binding_mismatch": task.case_id == binding.case_id,
            "mcp_task_foundation_binding_mismatch": (
                task.foundation_digest == binding.foundation_digest
            ),
            "mcp_task_branch_outside_run_binding": (
                task.branch_id in binding.selected_branch_ids
            ),
            "mcp_task_branch_method_binding_mismatch": (
                task.method_digest == binding.branch_method_digests.get(task.branch_id)
            ),
        }
        for code, valid in checks.items():
            if not valid:
                raise DellMCPToolAdapterError(code)

    def _method_call(self, lane_task: ToolLaneTask) -> _Call:
        task, binding = lane_task.task, self._binding
        return self._call(
            GET_RESEARCH_METHOD_TOOL,
            {
                "branch_ids": list(binding.selected_branch_ids),
                "research_as_of": task.research_as_of,
                "data_snapshot_id": task.snapshot_id,
                "execution_attempt_id": binding.execution_attempt_id,
                "source_policy": binding.source_policy,
            },
        )

    def _scope(
        self, lane_task: ToolLaneTask, call: _Call
    ) -> DellResearchRunScope:
        task, binding = lane_task.task, self._binding
        if call.error or call.content is None:
            raise DellMCPToolAdapterError("mcp_method_binding_failed")
        scope = DellResearchRunScope.model_validate(call.content.get("run_scope"))
        package = call.content.get("method_package")
        method = package.get("method") if isinstance(package, Mapping) else None
        if not isinstance(method, Mapping):
            raise DellMCPToolAdapterError("mcp_method_projection_missing")
        if (
            scope.case_id != task.case_id
            or scope.data_snapshot_id != task.snapshot_id
            or tuple(scope.selected_branch_ids) != binding.selected_branch_ids
            or tuple(method.get("selected_branch_ids", ())) != binding.selected_branch_ids
            or _as_of(scope.research_as_of) != _as_of(task.research_as_of)
        ):
            raise DellMCPToolAdapterError("mcp_method_run_scope_binding_mismatch")
        return scope

    def _evidence(
        self,
        lane_task: ToolLaneTask,
        scope: DellResearchRunScope,
        *,
        items: list[dict[str, Any]],
        states: set[str],
        calls: list[_Call],
        recoverable_calls: list[_Call],
    ) -> None:
        for raw_request in lane_task.task.evidence_requests:
            request = EvidenceRequest.model_validate(raw_request)
            if request.source_route == "external_required":
                self._external(
                    lane_task,
                    scope,
                    request,
                    items=items,
                    states=states,
                    calls=calls,
                    recoverable_calls=recoverable_calls,
                )
                continue

            common = {
                "query": request.query,
                "branch_id": lane_task.task.branch_id,
                "run_scope": scope.model_dump(mode="json"),
                "limit": request.limit,
            }
            if request.source_route == "local_only":
                self._local(
                    lane_task,
                    common,
                    receipt_prefix=[],
                    items=items,
                    states=states,
                    calls=calls,
                )
                continue

            search = self._call(SEARCH_REVIEWED_EVIDENCE_TOOL, common)
            calls.append(search)
            if search.error or search.content is None:
                continue
            hits = search.content.get("hits")
            if not isinstance(hits, list):
                raise DellMCPToolAdapterError("mcp_evidence_search_hits_invalid")
            ids = [
                str(hit["evidence_id"])
                for hit in hits
                if isinstance(hit, Mapping) and hit.get("evidence_id")
            ]
            if ids:
                read = self._call(
                    READ_REVIEWED_EVIDENCE_BY_ID_TOOL,
                    {
                        "evidence_ids": ids, "branch_id": lane_task.task.branch_id,
                        "run_scope": scope.model_dump(mode="json"),
                    },
                )
                calls.append(read)
                if read.error or read.content is None:
                    continue
                evidence = read.content.get("evidence")
                if not isinstance(evidence, list):
                    raise DellMCPToolAdapterError("mcp_evidence_read_items_invalid")
                for row in evidence:
                    if not isinstance(row, Mapping) or row.get("writer_citable") is not True:
                        raise DellMCPToolAdapterError("mcp_evidence_authority_failed")
                    items.append(
                        {
                            **row, "result_state": "reviewed_evidence",
                            "mcp_receipt_chain": [search.receipt, read.receipt],
                            "cell_binding_used": False,
                        }
                    )
                    states.add("reviewed_evidence")
                missing = read.content.get("missing_evidence_ids", [])
                if missing:
                    items.append(
                        self._gap(
                            "reviewed_evidence_id_missing",
                            [search.receipt, read.receipt],
                            missing_evidence_ids=list(missing),
                        )
                    )
                    states.add("typed_gap")
                continue
            self._local(
                lane_task,
                common,
                receipt_prefix=[search.receipt],
                items=items,
                states=states,
                calls=calls,
            )

    def _local(
        self,
        lane_task: ToolLaneTask,
        arguments: Mapping[str, Any],
        *,
        receipt_prefix: list[dict[str, Any]],
        items: list[dict[str, Any]],
        states: set[str],
        calls: list[_Call],
    ) -> None:
        local = self._call(SEARCH_LOCAL_KNOWLEDGE_TOOL, arguments)
        calls.append(local)
        if local.error or local.content is None:
            return
        candidates = local.content.get("candidates")
        if not isinstance(candidates, list):
            raise DellMCPToolAdapterError("mcp_local_candidates_invalid")
        receipts = [*receipt_prefix, local.receipt]
        for row in candidates:
            if (
                not isinstance(row, Mapping)
                or row.get("candidate_is_not_evidence") is not True
                or row.get("citation_eligible") is not False
            ):
                raise DellMCPToolAdapterError("mcp_candidate_authority_failed")
            items.append(
                {
                    **row,
                    "result_state": "retrieval_candidate",
                    "mcp_receipt_chain": receipts,
                    "cell_binding_used": False,
                }
            )
            states.add("retrieval_candidate")
        if not candidates:
            items.append(
                self._gap(
                    (
                        "no_reviewed_evidence_or_local_candidate"
                        if receipt_prefix
                        else "no_local_candidate"
                    ),
                    receipts,
                    query=str(arguments["query"]),
                )
            )
            states.add("typed_gap")

    def _external(
        self,
        lane_task: ToolLaneTask,
        scope: DellResearchRunScope,
        request: EvidenceRequest,
        *,
        items: list[dict[str, Any]],
        states: set[str],
        calls: list[_Call],
        recoverable_calls: list[_Call],
    ) -> None:
        discovery = self._call(
            SEARCH_EXTERNAL_SOURCES_TOOL,
            {
                "query": request.query,
                "branch_id": lane_task.task.branch_id,
                "run_scope": scope.model_dump(mode="json"),
                "purpose": request.purpose,
                "max_results": request.limit,
                "include_domains": list(request.include_domains),
            },
        )
        if discovery.error or discovery.content is None:
            recoverable_calls.append(discovery)
            items.append(
                self._external_failure_diagnostic(
                    discovery,
                    stage="discovery",
                    query=request.query,
                )
            )
            states.add("tool_failure")
            return
        calls.append(discovery)
        status = discovery.content.get("status")
        candidates = discovery.content.get("candidates")
        if status not in {"ok", "zero_results"} or not isinstance(candidates, list):
            raise DellMCPToolAdapterError("mcp_external_discovery_invalid")
        if len(candidates) > request.limit:
            raise DellMCPToolAdapterError("mcp_external_discovery_limit_exceeded")

        for row in candidates:
            if not isinstance(row, Mapping) or row.get("candidate_is_not_evidence") is not True:
                raise DellMCPToolAdapterError("mcp_external_candidate_authority_failed")
            items.append(
                {
                    **row,
                    "result_state": "retrieval_candidate",
                    "citation_eligible": False,
                    "mcp_receipt_chain": [discovery.receipt],
                    "cell_binding_used": False,
                }
            )
            states.add("retrieval_candidate")

        for row in candidates[: request.capture_limit]:
            capture = self._call(
                CAPTURE_EXTERNAL_SOURCE_TOOL,
                {
                    "discovery_receipt": discovery.content,
                    "candidate_id": row["candidate_id"],
                    "branch_id": lane_task.task.branch_id,
                    "run_scope": scope.model_dump(mode="json"),
                    "max_characters": 12_000,
                    "render_policy": "auto",
                },
            )
            if capture.error or capture.content is None:
                recoverable_calls.append(capture)
                items.append(
                    self._external_failure_diagnostic(
                        capture,
                        stage="capture",
                        query=request.query,
                        candidate_id=str(row["candidate_id"]),
                    )
                )
                states.add("tool_failure")
                continue
            calls.append(capture)
            if (
                capture.content.get("status") != "captured"
                or capture.content.get("authority_state") != "captured_source_candidate"
                or capture.content.get("captured_candidate_is_not_evidence") is not True
                or capture.content.get("admission_required_before_citation") is not True
                or capture.content.get("source_capture_authority") is not False
            ):
                raise DellMCPToolAdapterError("mcp_external_capture_authority_failed")
            items.append(
                {
                    **capture.content,
                    "result_state": "captured_source_candidate",
                    "citation_eligible": False,
                    "mcp_receipt_chain": [discovery.receipt, capture.receipt],
                    "cell_binding_used": False,
                }
            )
            states.add("captured_source_candidate")

        if not candidates:
            items.append(
                self._gap(
                    "no_external_candidate",
                    [discovery.receipt],
                    query=request.query,
                )
            )
            states.add("typed_gap")

    @staticmethod
    def _external_failure_diagnostic(
        call: _Call,
        *,
        stage: Literal["discovery", "capture"],
        query: str,
        candidate_id: str | None = None,
    ) -> dict[str, Any]:
        """Preserve one external failure without turning it into a data gap.

        The caller may continue only when another result in the same Evidence
        lane remains available.  If these diagnostics are the lane's only
        result, ``_execute`` promotes the aggregate to a typed lane failure.
        """

        return {
            "result_state": "tool_failure",
            "failure_scope": f"external_{stage}",
            "query": query,
            "candidate_id": candidate_id,
            "mcp_receipt_chain": [call.receipt],
            "structured_output_projection": _bounded_diagnostic(call.content),
            "tool_failure_is_not_information_gap": True,
            "partial_result_may_continue": True,
            "cell_binding_used": False,
        }

    def _finance(
        self,
        lane_task: ToolLaneTask,
        scope: DellResearchRunScope,
        *,
        items: list[dict[str, Any]],
        states: set[str],
        calls: list[_Call],
    ) -> None:
        for request in lane_task.task.fact_requests:
            self._keys(request, _FACT_KEYS, "mcp_fact_request")
            metric_ids = request.get("metric_ids")
            if metric_ids is None and request.get("metric_id") is not None:
                metric_ids = [request["metric_id"]]
            if not isinstance(metric_ids, Sequence) or isinstance(metric_ids, (str, bytes)):
                raise DellMCPToolAdapterError("mcp_fact_metric_ids_invalid")
            arguments = {
                "branch_id": lane_task.task.branch_id,
                "run_scope": scope.model_dump(mode="json"),
                "ticker": request.get("ticker", self._ticker),
                "metric_ids": list(metric_ids),
                "research_as_of": request.get(
                    "research_as_of", _as_of(lane_task.task.research_as_of)[:10]
                ),
                "granularity": request.get("granularity", self._granularity),
            }
            for key in _FACT_KEYS.difference(
                {"ticker", "metric_id", "metric_ids", "research_as_of", "granularity"}
            ):
                if key in request:
                    arguments[key] = request[key]
            call = self._call(QUERY_COMPANY_FINANCIAL_FACTS_TOOL, arguments)
            calls.append(call)
            if call.error or call.content is None:
                continue
            results = call.content.get("results")
            if not isinstance(results, list):
                raise DellMCPToolAdapterError("mcp_financial_results_invalid")
            for row in results:
                if not isinstance(row, Mapping):
                    raise DellMCPToolAdapterError("mcp_financial_result_invalid")
                if row.get("status") == "resolved":
                    for fact in row.get("facts", []):
                        if (
                            not isinstance(fact, Mapping)
                            or fact.get("numeric_fact_authority") is not True
                        ):
                            raise DellMCPToolAdapterError("mcp_numeric_fact_authority_failed")
                        items.append(
                            {
                                **fact, "fact_id": fact.get("numeric_fact_id"),
                                "result_state": "numeric_fact",
                                "mcp_receipt_chain": [call.receipt],
                                "cell_binding_used": False,
                            }
                        )
                        states.add("numeric_fact")
                elif row.get("status") == "typed_gap":
                    items.append(
                        self._gap(
                            "financial_fact_unresolved", [call.receipt],
                            metric_id=row.get("metric_id"),
                            typed_gap=row.get("typed_gap"),
                        )
                    )
                    states.add("typed_gap")
                elif row.get("status") == "typed_conflict":
                    items.append(
                        self._conflict(
                            [call.receipt],
                            metric_id=row.get("metric_id"),
                            typed_conflict=row.get("typed_conflict"),
                        )
                    )
                    states.add("typed_conflict")
                else:
                    raise DellMCPToolAdapterError("mcp_financial_status_invalid")

    def _call(self, name: str, arguments: Mapping[str, Any]) -> _Call:
        if self._portal is None or self._client is None or self._discovery_digest is None:
            raise DellMCPToolAdapterError("mcp_adapter_not_open")
        args, started = dict(arguments), perf_counter()
        with self._lock:
            self._call_sequence += 1
            call_id = (
                f"mcp:{self._binding.execution_attempt_id}:"
                f"{self._call_sequence:05d}"
            )
        try:
            result = self._portal.call(self._client.call_tool, name, args)
        except Exception as exc:
            diagnostic = {
                "status": "tool_failure",
                "error_code": "mcp_transport_exception",
                "exception_type": type(exc).__name__,
                "retryable": True,
            }
            return _Call(
                content=diagnostic,
                error=True,
                failure_kind="transport",
                receipt={
                    "schema_version": "fin_ia_mcp_tool_call_receipt_v1_0",
                    "call_id": call_id,
                    "tool_name": name,
                    "request_digest": canonical_sha256(args),
                    "output_digest": canonical_sha256(diagnostic),
                    "tool_discovery_digest": self._discovery_digest,
                    "is_error": True,
                    "semantic_tool_failure": False,
                    "failure_kind": "transport",
                    "transport_exception": True,
                    "exception_type": type(exc).__name__,
                    "elapsed_ms": round((perf_counter() - started) * 1_000, 3),
                },
            )
        content = result.structured_content
        if content is not None and not isinstance(content, Mapping):
            output = {
                "status": "tool_failure",
                "error_code": "mcp_structured_content_invalid",
                "returned_type": type(content).__name__,
                "retryable": False,
            }
        else:
            output = dict(content) if isinstance(content, Mapping) else None
        if output is None and bool(result.is_error):
            output = {
                "status": "tool_failure",
                "error_code": "mcp_server_error",
                "content_projection": _mcp_error_content_projection(
                    result.content
                ),
                "retryable": False,
            }
        semantic_tool_failure = bool(
            isinstance(output, Mapping) and output.get("status") == "tool_failure"
        )
        invalid_structured_content = content is not None and not isinstance(
            content, Mapping
        )
        call_error = (
            bool(result.is_error)
            or semantic_tool_failure
            or invalid_structured_content
        )
        failure_kind: Literal[
            "transport",
            "mcp_server_error",
            "semantic_tool_failure",
        ] | None = None
        if bool(result.is_error) or invalid_structured_content:
            failure_kind = "mcp_server_error"
        elif semantic_tool_failure:
            failure_kind = "semantic_tool_failure"
        return _Call(
            content=output,
            error=call_error,
            failure_kind=failure_kind,
            receipt={
                "schema_version": "fin_ia_mcp_tool_call_receipt_v1_0",
                "call_id": call_id,
                "tool_name": name,
                "request_digest": canonical_sha256(args),
                "output_digest": canonical_sha256(output) if output is not None else None,
                "tool_discovery_digest": self._discovery_digest,
                "is_error": bool(result.is_error),
                "semantic_tool_failure": semantic_tool_failure,
                "failure_kind": failure_kind,
                "transport_exception": False,
                "structured_content_invalid": invalid_structured_content,
                "elapsed_ms": round((perf_counter() - started) * 1_000, 3),
            },
        )

    def _failure(
        self, task: ToolLaneTask, started: float, calls: Sequence[_Call], code: str,
        owner: Literal["tool_transport", "s1_tool", "s2_tool"], *,
        retryable: bool = False, exception_type: str | None = None,
        partial_items: Sequence[Mapping[str, Any]] = (),
    ) -> ToolLaneResult:
        failure = ToolFailure(
            code=code, owner_layer=owner, retryable=retryable,
            exception_type=exception_type,
        )
        items = [
            {
                "result_state": "tool_failure", "mcp_receipt": call.receipt,
                "structured_output_projection": _bounded_diagnostic(call.content),
                "call_returned_error": call.error,
                "cell_binding_used": False,
            }
            for call in calls
        ]
        if partial_items:
            items.append(
                {
                    "result_state": "tool_failure",
                    "partial_success_item_count": len(partial_items),
                    "partial_success_projection": _bounded_diagnostic(
                        list(partial_items)
                    ),
                    "partial_success_not_promoted": True,
                    "cell_binding_used": False,
                }
            )
        return self._result(task, started, "tool_failure", {"tool_failure"}, items, failure)

    def _result(
        self, task: ToolLaneTask, started: float, status: str, states: set[str],
        items: list[dict[str, Any]], failure: ToolFailure | None,
    ) -> ToolLaneResult:
        body = {
            "status": status, "result_states": sorted(states), "items": items,
            "failure": failure.model_dump(mode="json") if failure else None,
        }
        receipt = RuntimeReceipt(
            receipt_id=f"{task.task.task_id}:{task.lane}:mcp", kind="tool",
            actor=f"{task.lane}_tool", status="failure" if failure else "success",
            request_digest=canonical_sha256(task),
            output_digest=None if failure else canonical_sha256(body),
            elapsed_ms=round((perf_counter() - started) * 1_000, 3),
        )
        branch = task.task
        return ToolLaneResult(
            lane=task.lane, task_id=branch.task_id, case_id=branch.case_id,
            branch_id=branch.branch_id, revision=branch.revision,
            research_as_of=branch.research_as_of, snapshot_id=branch.snapshot_id,
            foundation_digest=branch.foundation_digest,
            method_digest=branch.method_digest, plan_digest=branch.plan_digest,
            status=status, result_states=tuple(sorted(states)), items=tuple(items),
            failure=failure, runtime_receipt=receipt,
        )

    @staticmethod
    def _keys(request: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
        unexpected = sorted(set(request).difference(allowed))
        if unexpected:
            raise DellMCPToolAdapterError(f"{label}_keys_invalid:{','.join(unexpected)}")

    @staticmethod
    def _gap(code: str, receipts: list[dict[str, Any]], **detail: Any) -> dict[str, Any]:
        return {
            "result_state": "typed_gap", "gap_code": code, **detail,
            "mcp_receipt_chain": receipts, "public_information_gap_proved": False,
            "cell_binding_used": False,
        }

    @staticmethod
    def _conflict(receipts: list[dict[str, Any]], **detail: Any) -> dict[str, Any]:
        return {
            "result_state": "typed_conflict",
            **detail,
            "mcp_receipt_chain": receipts,
            "public_information_gap_proved": False,
            "cell_binding_used": False,
        }


def _digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _bounded_diagnostic(value: Any, *, depth: int = 0) -> Any:
    """Keep a bounded structured failure projection for same-stage diagnosis."""

    if depth >= 6:
        return "[depth-truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:2_000]
    if isinstance(value, Mapping):
        return {
            str(key): _bounded_diagnostic(item, depth=depth + 1)
            for key, item in list(sorted(value.items(), key=lambda row: str(row[0])))[:32]
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _bounded_diagnostic(item, depth=depth + 1)
            for item in list(value)[:16]
        ]
    return str(value)[:2_000]


def _mcp_error_content_projection(value: Any) -> Any:
    blocks: list[Any] = []
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        source = list(value)[:8]
    else:
        source = [value]
    for block in source:
        if hasattr(block, "model_dump"):
            try:
                blocks.append(block.model_dump(mode="json"))
                continue
            except Exception:
                pass
        if isinstance(block, Mapping):
            blocks.append(dict(block))
        elif block is None:
            blocks.append(None)
        else:
            blocks.append(
                {
                    "content_type": type(block).__name__,
                    "bounded_text": str(block)[:2_000],
                }
            )
    return _bounded_diagnostic(blocks)


def _as_of(value: Any) -> str:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
        str(value).replace("Z", "+00:00")
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DellMCPToolAdapterError("mcp_research_as_of_timezone_required")
    return parsed.isoformat()


__all__ = [
    "DellMCPGraphRunComposition",
    "DellMCPRunBinding",
    "DellMCPToolAdapterError",
    "DellMCPToolLaneAdapter",
    "compose_dell_mcp_graph_run",
]
