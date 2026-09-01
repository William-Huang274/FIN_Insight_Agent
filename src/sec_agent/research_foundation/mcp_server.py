from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
import inspect
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel

from sec_agent.research.finance_tool_contract import (
    READ_NUMERIC_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_TOOL,
)

from .contracts import (
    DEFAULT_DELL_REFERENCE_VERTICAL_FOUNDATION_PATH,
    DellReferenceVerticalFoundation,
    DellResearchMethodBinding,
    DellResearchRunScope,
    bind_dell_research_method,
    load_dell_reference_vertical_foundation,
)
from .external_sources import (
    CaptureReceipt,
    DiscoveryReceipt,
    ExternalCaptureRequest,
    ExternalSearchRequest,
    ExternalSourceCapture,
    ExternalSourceDiscovery,
)
from .data_ports import (
    CompanyFinancialFactQuery,
    CompanyFinancialFactQueryResult,
    LocalKnowledgeReadResult,
    ReviewedEvidenceReadResult,
    ReviewedEvidenceSearchResult,
)


GET_RESEARCH_METHOD_TOOL = "get_dell_research_method"
SEARCH_LOCAL_KNOWLEDGE_TOOL = "search_local_knowledge"
SEARCH_REVIEWED_EVIDENCE_TOOL = "search_reviewed_evidence"
READ_REVIEWED_EVIDENCE_BY_ID_TOOL = "read_reviewed_evidence"
QUERY_COMPANY_FINANCIAL_FACTS_TOOL = "query_company_financial_facts"
SEARCH_EXTERNAL_SOURCES_TOOL = "search_external_sources"
CAPTURE_EXTERNAL_SOURCE_TOOL = "capture_external_source"


class MethodReader(Protocol):
    def __call__(
        self,
        *,
        branch_ids: Sequence[str],
        research_as_of: datetime,
        data_snapshot_id: str,
        execution_attempt_id: str,
        source_policy: str,
    ) -> DellResearchMethodBinding | Awaitable[DellResearchMethodBinding]: ...


class LocalKnowledgeReader(Protocol):
    def __call__(
        self,
        *,
        query: str,
        branch_id: str,
        limit: int,
        run_scope: DellResearchRunScope,
    ) -> LocalKnowledgeReadResult | Awaitable[LocalKnowledgeReadResult]: ...


class CellReader(Protocol):
    def __call__(
        self, *, cell_id: str
    ) -> Mapping[str, Any] | Awaitable[Mapping[str, Any]]: ...


class EvidenceReader(Protocol):
    def __call__(
        self,
        *,
        evidence_ids: Sequence[str],
        branch_id: str,
        run_scope: DellResearchRunScope,
    ) -> ReviewedEvidenceReadResult | Awaitable[ReviewedEvidenceReadResult]: ...


class EvidenceSearchReader(Protocol):
    def __call__(
        self,
        *,
        query: str,
        branch_id: str,
        limit: int,
        run_scope: DellResearchRunScope,
    ) -> ReviewedEvidenceSearchResult | Awaitable[ReviewedEvidenceSearchResult]: ...


class FinancialFactReader(Protocol):
    def __call__(
        self,
        *,
        request: CompanyFinancialFactQuery,
        branch_id: str,
        run_scope: DellResearchRunScope,
    ) -> CompanyFinancialFactQueryResult | Awaitable[CompanyFinancialFactQueryResult]: ...


@dataclass(frozen=True)
class DellFoundationMethodReader:
    """Adapter from the frozen foundation contract to an MCP method port."""

    foundation: DellReferenceVerticalFoundation

    @classmethod
    def from_default_contract(cls) -> "DellFoundationMethodReader":
        return cls(
            foundation=load_dell_reference_vertical_foundation(
                DEFAULT_DELL_REFERENCE_VERTICAL_FOUNDATION_PATH
            )
        )

    def __call__(
        self,
        *,
        branch_ids: Sequence[str],
        research_as_of: datetime,
        data_snapshot_id: str,
        execution_attempt_id: str,
        source_policy: str,
    ) -> DellResearchMethodBinding:
        if source_policy != "frozen_local_reviewed_plus_public_web_locator_only":
            raise ValueError("research_source_policy_invalid")
        return bind_dell_research_method(
            self.foundation,
            branch_ids,
            research_as_of=research_as_of,
            data_snapshot_id=data_snapshot_id,
            execution_attempt_id=execution_attempt_id,
            source_policy="frozen_local_reviewed_plus_public_web_locator_only",
        )


@dataclass(frozen=True)
class ResearchDataMCPDependencies:
    """Ports supplied by FIN domain services; this module owns transport only."""

    method_reader: MethodReader
    local_knowledge_reader: LocalKnowledgeReader
    reviewed_evidence_search_reader: EvidenceSearchReader
    reviewed_evidence_reader: EvidenceReader
    financial_fact_reader: FinancialFactReader
    external_discovery: ExternalSourceDiscovery
    external_capture: ExternalSourceCapture
    legacy_reviewed_evidence_cell_reader: CellReader | None = None
    legacy_numeric_fact_cell_reader: CellReader | None = None


def build_research_data_mcp_server(
    dependencies: ResearchDataMCPDependencies,
) -> Any:
    """Build the thin MCP v2 surface used by the DELL reference vertical.

    Evidence admission, NumericFact authority and local knowledge ranking remain in
    the injected FIN services. External discovery and capture return candidates,
    never writer-citable Evidence.
    """

    try:
        from mcp.server import MCPServer
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("mcp_v2_dependency_missing") from exc

    server = MCPServer(
        name="fin-insight-research-data",
        title="FIN Insight Research Data",
        version="0.1.0",
        instructions=(
            "Use only the active question branch. Retrieval and captured-source "
            "candidates are not Evidence. Read reviewed Evidence or NumericFacts "
            "through their ID- and query-based typed tools before citing or "
            "calculating. Cell-bound tools are legacy compatibility only."
        ),
    )

    @server.tool(
        name=GET_RESEARCH_METHOD_TOOL,
        description=(
            "Read the answer-free DELL question method, formula contracts and "
            "source boundaries for selected branches."
        ),
        structured_output=True,
    )
    async def get_dell_research_method(
        branch_ids: list[str],
        research_as_of: datetime,
        data_snapshot_id: str,
        execution_attempt_id: str,
        source_policy: Literal[
            "frozen_local_reviewed_plus_public_web_locator_only"
        ] = "frozen_local_reviewed_plus_public_web_locator_only",
    ) -> DellResearchMethodBinding:
        return await _invoke_model(
            dependencies.method_reader,
            DellResearchMethodBinding,
            branch_ids=tuple(branch_ids),
            research_as_of=research_as_of,
            data_snapshot_id=data_snapshot_id,
            execution_attempt_id=execution_attempt_id,
            source_policy=source_policy,
        )

    @server.tool(
        name=SEARCH_LOCAL_KNOWLEDGE_TOOL,
        description=(
            "Search the versioned local knowledge base for the active research "
            "branch. The injected FIN reader owns ranking and authority labels."
        ),
        structured_output=True,
    )
    async def search_local_knowledge(
        query: str,
        branch_id: str,
        run_scope: DellResearchRunScope,
        limit: int = 8,
    ) -> LocalKnowledgeReadResult:
        if not 1 <= limit <= 12:
            raise ValueError("local_knowledge_limit_invalid")
        await _validate_scope(
            dependencies.method_reader,
            run_scope=run_scope,
            branch_id=branch_id,
        )
        return await _invoke_model(
            dependencies.local_knowledge_reader,
            LocalKnowledgeReadResult,
            query=query.strip(),
            branch_id=branch_id.strip(),
            limit=limit,
            run_scope=run_scope,
        )

    @server.tool(
        name=SEARCH_REVIEWED_EVIDENCE_TOOL,
        description=(
            "Discover stable IDs for already-reviewed, writer-citable Evidence. "
            "The result is an ID locator set and never promotes a retrieval or "
            "capture candidate; call read_reviewed_evidence before citation."
        ),
        structured_output=True,
    )
    async def search_reviewed_evidence(
        query: str,
        branch_id: str,
        run_scope: DellResearchRunScope,
        limit: int = 8,
    ) -> ReviewedEvidenceSearchResult:
        if not 1 <= limit <= 12:
            raise ValueError("reviewed_evidence_search_limit_invalid")
        await _validate_scope(
            dependencies.method_reader,
            run_scope=run_scope,
            branch_id=branch_id,
        )
        return await _invoke_model(
            dependencies.reviewed_evidence_search_reader,
            ReviewedEvidenceSearchResult,
            query=query.strip(),
            branch_id=branch_id.strip(),
            limit=limit,
            run_scope=run_scope,
        )

    @server.tool(
        name=READ_REVIEWED_EVIDENCE_BY_ID_TOOL,
        description=(
            "Read selected writer-citable Evidence by stable evidence IDs from "
            "the injected FIN authority service."
        ),
        structured_output=True,
    )
    async def read_reviewed_evidence(
        evidence_ids: list[str],
        branch_id: str,
        run_scope: DellResearchRunScope,
    ) -> ReviewedEvidenceReadResult:
        if (
            not evidence_ids
            or len(evidence_ids) > 24
            or len(set(evidence_ids)) != len(evidence_ids)
        ):
            raise ValueError("evidence_id_count_invalid")
        await _validate_scope(
            dependencies.method_reader,
            run_scope=run_scope,
            branch_id=branch_id,
        )
        return await _invoke_model(
            dependencies.reviewed_evidence_reader,
            ReviewedEvidenceReadResult,
            evidence_ids=tuple(evidence_ids),
            branch_id=branch_id.strip(),
            run_scope=run_scope,
        )

    @server.tool(
        name=QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
        description=(
            "Query company financial facts through the injected typed SQL/domain "
            "port. Every query field is explicit in the MCP schema; there is no "
            "free-form request object or narrative numeric fallback."
        ),
        structured_output=True,
    )
    async def query_company_financial_facts(
        branch_id: str,
        run_scope: DellResearchRunScope,
        ticker: str,
        metric_ids: list[str],
        research_as_of: date,
        granularity: str,
        period_start: date | None = None,
        period_end: date | None = None,
        fiscal_years: list[int] | None = None,
        requested_unit: str = "reported_source_unit",
        unit_family: str | None = None,
    ) -> CompanyFinancialFactQueryResult:
        await _validate_scope(
            dependencies.method_reader,
            run_scope=run_scope,
            branch_id=branch_id,
        )
        request = CompanyFinancialFactQuery(
            ticker=ticker,
            metric_ids=tuple(metric_ids),
            research_as_of=research_as_of,
            period_start=period_start,
            period_end=period_end,
            fiscal_years=tuple(fiscal_years or ()),
            granularity=granularity,
            requested_unit=requested_unit,
            unit_family=unit_family,
        )
        return await _invoke_model(
            dependencies.financial_fact_reader,
            CompanyFinancialFactQueryResult,
            request=request,
            branch_id=branch_id.strip(),
            run_scope=run_scope,
        )

    if dependencies.legacy_reviewed_evidence_cell_reader is not None:

        @server.tool(
            name=READ_REVIEWED_EVIDENCE_TOOL,
            description=(
                "Legacy compatibility: read reviewed Evidence for an existing "
                "cell-bound workflow. New agents should use read_reviewed_evidence."
            ),
            structured_output=True,
        )
        async def read_reviewed_evidence_for_cell(
            cell_id: str,
            branch_id: str,
            run_scope: DellResearchRunScope,
        ) -> dict[str, Any]:
            await _validate_scope(
                dependencies.method_reader,
                run_scope=run_scope,
                branch_id=branch_id,
            )
            return await _invoke_mapping(
                dependencies.legacy_reviewed_evidence_cell_reader,
                cell_id=cell_id.strip(),
            )

    if dependencies.legacy_numeric_fact_cell_reader is not None:

        @server.tool(
            name=READ_NUMERIC_FACTS_TOOL,
            description=(
                "Legacy compatibility: read NumericFacts for an existing "
                "cell-bound workflow. New agents should use "
                "query_company_financial_facts."
            ),
            structured_output=True,
        )
        async def read_numeric_facts_for_cell(
            cell_id: str,
            branch_id: str,
            run_scope: DellResearchRunScope,
        ) -> dict[str, Any]:
            await _validate_scope(
                dependencies.method_reader,
                run_scope=run_scope,
                branch_id=branch_id,
            )
            return await _invoke_mapping(
                dependencies.legacy_numeric_fact_cell_reader,
                cell_id=cell_id.strip(),
            )

    @server.tool(
        name=SEARCH_EXTERNAL_SOURCES_TOOL,
        description=(
            "Discover public external locators for one branch. Results and snippets "
            "are retrieval candidates, not source text or Evidence."
        ),
        structured_output=True,
    )
    async def search_external_sources(
        query: str,
        branch_id: str,
        run_scope: DellResearchRunScope,
        purpose: str,
        max_results: int = 5,
        include_domains: list[str] | None = None,
    ) -> DiscoveryReceipt:
        await _validate_scope(
            dependencies.method_reader,
            run_scope=run_scope,
            branch_id=branch_id,
        )
        request = ExternalSearchRequest(
            query=query,
            branch_id=branch_id,
            run_scope=run_scope,
            purpose=purpose,
            max_results=max_results,
            include_domains=tuple(include_domains or ()),
        )
        return await dependencies.external_discovery.search(request)

    @server.tool(
        name=CAPTURE_EXTERNAL_SOURCE_TOOL,
        description=(
            "Transition-capture one public locator with trafilatura and an optional "
            "Playwright fallback. This tool does not enforce robots or create WARC/"
            "archive-grade records; the result remains a candidate until FIN "
            "evidence admission."
        ),
        structured_output=True,
    )
    async def capture_external_source(
        discovery_receipt: DiscoveryReceipt,
        candidate_id: str,
        branch_id: str,
        run_scope: DellResearchRunScope,
        max_characters: int = 12_000,
        render_policy: Literal["auto", "static", "browser"] = "auto",
    ) -> CaptureReceipt:
        await _validate_scope(
            dependencies.method_reader,
            run_scope=run_scope,
            branch_id=branch_id,
        )
        request = ExternalCaptureRequest(
            discovery_receipt=discovery_receipt,
            candidate_id=candidate_id,
            branch_id=branch_id,
            run_scope=run_scope,
            max_characters=max_characters,
            render_policy=render_policy,
        )
        return await dependencies.external_capture.capture(request)

    return server


async def _invoke_mapping(
    callable_port: Callable[..., Any],
    **kwargs: Any,
) -> dict[str, Any]:
    result = callable_port(**kwargs)
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, Mapping):
        return dict(result)
    model_dump = getattr(result, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, Mapping):
            return dict(dumped)
    as_dict = getattr(result, "as_dict", None)
    if callable(as_dict):
        dumped = as_dict()
        if isinstance(dumped, Mapping):
            return dict(dumped)
    raise TypeError("research_mcp_port_result_not_mapping")


_ModelT = TypeVar("_ModelT", bound=BaseModel)


async def _invoke_model(
    callable_port: Callable[..., Any],
    model_type: type[_ModelT],
    **kwargs: Any,
) -> _ModelT:
    result = callable_port(**kwargs)
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, model_type):
        return result
    if isinstance(result, BaseModel):
        return model_type.model_validate(result.model_dump(mode="json"))
    if isinstance(result, Mapping):
        return model_type.model_validate(dict(result))
    as_dict = getattr(result, "as_dict", None)
    if callable(as_dict):
        return model_type.model_validate(as_dict())
    raise TypeError("research_mcp_port_result_model_invalid")


async def _validate_scope(
    method_reader: MethodReader,
    *,
    run_scope: DellResearchRunScope,
    branch_id: str,
) -> None:
    normalized_branch = str(branch_id).strip()
    if normalized_branch not in run_scope.selected_branch_ids:
        raise ValueError("research_branch_outside_run_scope")
    expected = await _invoke_model(
        method_reader,
        DellResearchMethodBinding,
        branch_ids=run_scope.selected_branch_ids,
        research_as_of=run_scope.research_as_of,
        data_snapshot_id=run_scope.data_snapshot_id,
        execution_attempt_id=run_scope.execution_attempt_id,
        source_policy=run_scope.source_policy,
    )
    if expected.run_scope != run_scope:
        raise ValueError("research_run_scope_not_bound_to_method")


__all__ = [
    "CAPTURE_EXTERNAL_SOURCE_TOOL",
    "DellFoundationMethodReader",
    "GET_RESEARCH_METHOD_TOOL",
    "QUERY_COMPANY_FINANCIAL_FACTS_TOOL",
    "READ_REVIEWED_EVIDENCE_BY_ID_TOOL",
    "SEARCH_REVIEWED_EVIDENCE_TOOL",
    "SEARCH_EXTERNAL_SOURCES_TOOL",
    "SEARCH_LOCAL_KNOWLEDGE_TOOL",
    "ResearchDataMCPDependencies",
    "build_research_data_mcp_server",
]
