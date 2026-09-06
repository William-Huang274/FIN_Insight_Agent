from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json

import pytest


pytest.importorskip("mcp", reason="agent-runtime optional dependency")

from mcp import Client

from sec_agent.research.finance_tool_contract import (
    READ_NUMERIC_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_TOOL,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.research_foundation.data_ports import (
    CompanyFinancialFactQuery,
    CompanyFinancialFactQueryResult,
    FinancialMetricResult,
    LocalKnowledgeReadResult,
    ReviewedEvidenceReadResult,
    ReviewedEvidenceSearchResult,
    TypedFinancialGap,
    TypedFinancialConflict,
)
from sec_agent.research_foundation.external_sources import (
    ExternalSearchRequest,
    ExternalSourceCapture,
    ExternalSourceDiscovery,
    FetchedPage,
    ProviderHit,
    PublicURLGuard,
)
from sec_agent.research_foundation.mcp_server import (
    CAPTURE_EXTERNAL_SOURCE_TOOL,
    GET_RESEARCH_METHOD_TOOL,
    QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_BY_ID_TOOL,
    SEARCH_EXTERNAL_SOURCES_TOOL,
    SEARCH_LOCAL_KNOWLEDGE_TOOL,
    SEARCH_REVIEWED_EVIDENCE_TOOL,
    DellFoundationMethodReader,
    ResearchDataMCPDependencies,
    build_research_data_mcp_server,
)


_NOW = datetime(2026, 9, 2, 2, 0, tzinfo=timezone.utc)
_SNAPSHOT = "DELL-MCP-TEST-SNAPSHOT-01"
_ATTEMPT = "DELL-MCP-TEST-A01"


def test_company_financial_fact_query_rejects_unimplemented_unit_conversion() -> None:
    with pytest.raises(ValueError, match="reported_source_unit"):
        CompanyFinancialFactQuery.model_validate(
            {
                "ticker": "DELL",
                "metric_ids": ["revenue"],
                "research_as_of": "2026-09-02",
                "selection_mode": "exact_period_end",
                "period_end": "2026-05-01",
                "granularity": "quarter_discrete",
                "requested_unit": "USD_millions",
            }
        )


class _Provider:
    provider_id = "fake_discovery"

    async def search(self, request: ExternalSearchRequest) -> tuple[ProviderHit, ...]:
        return (
            ProviderHit(
                title="Official Dell result",
                url="https://investors.delltechnologies.com/results",
                snippet="locator only",
            ),
        )


class _Fetcher:
    async def fetch(self, url: str, *, timeout_seconds: float) -> FetchedPage:
        return FetchedPage(
            final_url=url,
            html="<html><main>Issuer source body for bounded capture.</main></html>",
            status_code=200,
            content_type="text/html",
        )


def _digest_model_body(body: dict) -> str:
    return canonical_digest(body)


def _build_server(
    *,
    include_legacy: bool = False,
    financial_status: str = "typed_gap",
    case_artifacts=None,
):
    guard = PublicURLGuard(resolver=lambda _host: ("93.184.216.34",))
    discovery = ExternalSourceDiscovery(
        primary=_Provider(),
        clock=lambda: _NOW,
        monotonic=lambda: 1.0,
    )
    capture = ExternalSourceCapture(
        guard=guard,
        static_fetcher=_Fetcher(),
        browser_fetcher=None,
        extractor=lambda _html: (
            "Issuer source body for bounded capture with publication identity, "
            "fiscal-period context, metric definitions, source boundaries and "
            "counterevidence instructions. This repeated fixture text is long "
            "enough to clear the minimum extraction threshold in qualification."
        ),
        clock=lambda: _NOW,
        monotonic=lambda: 1.0,
    )

    def local_reader(*, query, branch_id, limit, run_scope, retrieval_scope):
        body = {
            "schema_version": "fin_ia_structured_local_knowledge_read_v1_0",
            "authority_state": "retrieval_candidate_set",
            "branch_id": branch_id,
            "run_scope_digest": run_scope.run_scope_digest,
            "query": query,
            "research_as_of": "2026-09-02",
            "snapshot_sha256": "1" * 64,
            "physical_record_count": 0,
            "visible_record_count": 0,
            "eligible_candidate_count": 0,
            "retrieval_scope": retrieval_scope.model_dump(mode="json"),
            "metadata_prefilter_applied": True,
            "retrieval_strategy": "metadata_prefilter_bm25",
            "candidates": [],
            "candidate_is_not_evidence": True,
            "evidence_admission_performed": False,
            "target_route": "structured_metadata_prefilter_bm25",
        }
        return LocalKnowledgeReadResult(**body, read_digest=_digest_model_body(body))

    def evidence_search_reader(*, query, branch_id, limit, run_scope):
        body = {
            "schema_version": "fin_ia_reviewed_evidence_search_v1_0",
            "authority_state": "reviewed_evidence_locator_set",
            "case_key": "DELL",
            "branch_id": branch_id,
            "run_scope_digest": run_scope.run_scope_digest,
            "query": query,
            "hits": [],
            "writer_citable_sources_only": True,
            "candidate_promotion_performed": False,
            "source_pack_projection_digest": "projection-test",
        }
        return ReviewedEvidenceSearchResult(
            **body, search_digest=_digest_model_body(body)
        )

    def evidence_reader(*, evidence_ids, branch_id, run_scope):
        body = {
            "schema_version": "fin_ia_reviewed_evidence_id_read_v1_0",
            "authority_state": "reviewed_evidence_read",
            "case_key": "DELL",
            "branch_id": branch_id,
            "run_scope_digest": run_scope.run_scope_digest,
            "requested_evidence_ids": list(evidence_ids),
            "evidence": [],
            "missing_evidence_ids": list(evidence_ids),
            "missing_id_is_not_public_information_gap": True,
            "candidate_promotion_performed": False,
            "source_pack_projection_digest": "projection-test",
        }
        return ReviewedEvidenceReadResult(**body, read_digest=_digest_model_body(body))

    def financial_fact_reader(*, request, branch_id, run_scope):
        results = []
        for metric_id in request.metric_ids:
            detail_json = "{}"
            conflict_body = {"left": "100", "right": "101"}
            is_conflict = financial_status == "typed_conflict"
            results.append(
                FinancialMetricResult(
                    schema_version="fin_ia_typed_fact_execution_result_v1_0",
                    status="typed_conflict" if is_conflict else "typed_gap",
                    fact_request_id=f"MCPFACT::{metric_id}",
                    ticker=request.ticker,
                    metric_id=metric_id,
                    facts=(),
                    typed_gap=(
                        None
                        if is_conflict
                        else TypedFinancialGap(
                            gap_code="fixture_gap",
                            detail_json=detail_json,
                            detail_sha256=canonical_digest({}),
                        )
                    ),
                    typed_conflict=(
                        TypedFinancialConflict(
                            conflict_code="fixture_conflict",
                            conflicts_json=json.dumps(
                                conflict_body, sort_keys=True, separators=(",", ":")
                            ),
                            conflicts_sha256=canonical_digest(conflict_body),
                        )
                        if is_conflict
                        else None
                    ),
                    fact_request_is_not_numeric_fact=True,
                )
            )
        body = {
            "schema_version": "fin_ia_company_financial_fact_query_v1_0",
            "authority_state": "s2_numeric_fact_query_result",
            "branch_id": branch_id,
            "run_scope_digest": run_scope.run_scope_digest,
            "query": request.model_dump(mode="json"),
            "results": [row.model_dump(mode="json") for row in results],
            "resolved_metric_count": 0,
            "typed_gap_count": 0 if financial_status == "typed_conflict" else len(results),
            "typed_conflict_count": len(results) if financial_status == "typed_conflict" else 0,
            "read_only": True,
            "query_is_not_numeric_fact": True,
            "narrative_numeric_fallback_performed": False,
            "fact_mart_sha256_before": "2" * 64,
            "fact_mart_sha256_after": "2" * 64,
        }
        return CompanyFinancialFactQueryResult(
            **body, query_digest=_digest_model_body(body)
        )

    def legacy_evidence_reader(*, cell_id: str):
        return {"authority_state": "reviewed_evidence", "cell_id": cell_id}

    def legacy_numeric_reader(*, cell_id: str):
        return {"authority_state": "numeric_fact", "cell_id": cell_id}

    return build_research_data_mcp_server(
        ResearchDataMCPDependencies(
            method_reader=DellFoundationMethodReader.from_default_contract(),
            local_knowledge_reader=local_reader,
            reviewed_evidence_search_reader=evidence_search_reader,
            reviewed_evidence_reader=evidence_reader,
            financial_fact_reader=financial_fact_reader,
            external_discovery=discovery,
            external_capture=capture,
            case_artifacts=case_artifacts,
            legacy_reviewed_evidence_cell_reader=(
                legacy_evidence_reader if include_legacy else None
            ),
            legacy_numeric_fact_cell_reader=(
                legacy_numeric_reader if include_legacy else None
            ),
        )
    )


def _method_arguments(branches: list[str]) -> dict:
    return {
        "branch_ids": branches,
        "research_as_of": _NOW.isoformat(),
        "data_snapshot_id": _SNAPSHOT,
        "execution_attempt_id": _ATTEMPT,
    }


def test_mcp_exposes_strong_typed_non_cell_surface_and_scope() -> None:
    async def exercise() -> None:
        async with Client(_build_server()) as client:
            listed = await client.list_tools()
            by_name = {tool.name: tool for tool in listed.tools}
            assert set(by_name) == {
                "get_research_method",
                GET_RESEARCH_METHOD_TOOL,
                SEARCH_LOCAL_KNOWLEDGE_TOOL,
                SEARCH_REVIEWED_EVIDENCE_TOOL,
                READ_REVIEWED_EVIDENCE_BY_ID_TOOL,
                QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
                SEARCH_EXTERNAL_SOURCES_TOOL,
                CAPTURE_EXTERNAL_SOURCE_TOOL,
            }
            assert READ_REVIEWED_EVIDENCE_TOOL not in by_name
            assert READ_NUMERIC_FACTS_TOOL not in by_name

            finance_schema = by_name[QUERY_COMPANY_FINANCIAL_FACTS_TOOL].input_schema
            properties = finance_schema["properties"]
            assert "request" not in properties
            assert {"ticker", "metric_ids", "research_as_of", "granularity"} <= set(
                properties
            )
            assert "selection_mode" in properties
            assert "selection_mode" in finance_schema["required"]
            local_properties = by_name[SEARCH_LOCAL_KNOWLEDGE_TOOL].input_schema[
                "properties"
            ]
            assert {
                "issuer_ids",
                "fiscal_periods",
                "source_roles",
                "route_ids",
                "lanes",
            } <= set(local_properties)
            assert by_name[
                QUERY_COMPANY_FINANCIAL_FACTS_TOOL
            ].output_schema.get("additionalProperties") is False

            method = await client.call_tool(
                GET_RESEARCH_METHOD_TOOL,
                _method_arguments(["Q1_ISSUER_TRUTH", "Q9_COUNTEREVIDENCE_WWC"]),
            )
            assert method.is_error is False
            scope = method.structured_content["run_scope"]
            assert scope["method_sha256"] == method.structured_content[
                "method_package"
            ]["method_sha256"]

            common = {"branch_id": "Q1_ISSUER_TRUTH", "run_scope": scope}
            local = await client.call_tool(
                SEARCH_LOCAL_KNOWLEDGE_TOOL,
                {
                    **common,
                    "query": "AI server backlog definition",
                    "limit": 4,
                    "issuer_ids": ["DELL"],
                    "fiscal_periods": ["FY2027_Q1"],
                    "source_roles": ["issuer_management_disclosure"],
                    "lanes": ["prose_leaf"],
                },
            )
            evidence_search = await client.call_tool(
                SEARCH_REVIEWED_EVIDENCE_TOOL,
                {**common, "query": "AI server backlog definition", "limit": 4},
            )
            evidence = await client.call_tool(
                READ_REVIEWED_EVIDENCE_BY_ID_TOOL,
                {**common, "evidence_ids": ["EV::MISSING0000000"]},
            )
            numeric = await client.call_tool(
                QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
                {
                    **common,
                    "ticker": "DELL",
                    "metric_ids": ["revenue"],
                    "research_as_of": "2026-06-24",
                    "period_end": "2026-05-01",
                    "selection_mode": "exact_period_end",
                    "granularity": "quarter_discrete",
                },
            )
            assert local.is_error is False
            assert evidence_search.is_error is False
            assert evidence.is_error is False
            assert numeric.is_error is False
            assert evidence_search.structured_content[
                "candidate_promotion_performed"
            ] is False
            assert numeric.structured_content["typed_gap_count"] == 1

            wrong_branch = await client.call_tool(
                SEARCH_LOCAL_KNOWLEDGE_TOOL,
                {**common, "branch_id": "Q2_DEMAND_QUALITY", "query": "demand"},
            )
            assert wrong_branch.is_error is True

    asyncio.run(exercise())


def test_finance_metric_schema_and_anticipated_validation_feedback() -> None:
    async def exercise():
        async with Client(_build_server(), raise_exceptions=False) as client:
            specs = await client.list_tools()
            schema = next(t.input_schema for t in specs.tools if t.name == QUERY_COMPANY_FINANCIAL_FACTS_TOOL)
            assert "lowercase" in schema["properties"]["metric_ids"]["description"]
            method = await client.call_tool(GET_RESEARCH_METHOD_TOOL, _method_arguments(["Q1_ISSUER_TRUTH"]))
            args = {"branch_id": "Q1_ISSUER_TRUTH", "run_scope": method.structured_content["run_scope"],
                "ticker": "DELL", "metric_ids": ["REVENUE", "GAAP_OPERATING_INCOME"],
                "research_as_of": "2026-09-02", "granularity": "quarter_discrete",
                "selection_mode": "exact_period_end", "period_end": "2026-05-01"}
            rejected = await client.call_tool(QUERY_COMPANY_FINANCIAL_FACTS_TOOL, args)
            error = " ".join(c.text for c in rejected.content if c.type == "text")
            assert rejected.is_error and "financial_fact_metric_ids_invalid" in error
            assert "revenue and operating_income" in error and "No SQL query was executed" in error
            assert "Traceback" not in error and "GAAP_OPERATING_INCOME" not in error
            corrected = await client.call_tool(QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
                {**args, "metric_ids": ["revenue", "operating_income"]})
            assert not corrected.is_error and corrected.structured_content["typed_gap_count"] == 2
    asyncio.run(exercise())


def test_mcp_capture_requires_discovery_receipt_and_preserves_lineage() -> None:
    async def exercise() -> None:
        async with Client(_build_server()) as client:
            method = await client.call_tool(
                GET_RESEARCH_METHOD_TOOL,
                _method_arguments(["Q1_ISSUER_TRUTH"]),
            )
            scope = method.structured_content["run_scope"]
            discovery = await client.call_tool(
                SEARCH_EXTERNAL_SOURCES_TOOL,
                {
                    "query": "official Dell earnings result",
                    "branch_id": "Q1_ISSUER_TRUTH",
                    "run_scope": scope,
                    "purpose": "Locate official issuer earnings material.",
                    "max_results": 3,
                    "include_domains": ["delltechnologies.com"],
                },
            )
            assert discovery.is_error is False
            candidate = discovery.structured_content["candidates"][0]
            capture = await client.call_tool(
                CAPTURE_EXTERNAL_SOURCE_TOOL,
                {
                    "discovery_receipt": discovery.structured_content,
                    "candidate_id": candidate["candidate_id"],
                    "branch_id": "Q1_ISSUER_TRUTH",
                    "run_scope": scope,
                    "max_characters": 500,
                    "render_policy": "static",
                },
            )
            assert capture.is_error is False
            output = capture.structured_content
            assert output["candidate_id"] == candidate["candidate_id"]
            assert output["discovery_receipt_digest"] == discovery.structured_content[
                "receipt_digest"
            ]
            assert output["run_scope_digest"] == scope["run_scope_digest"]
            assert output["transport_authority"] == "qualification_only"
            assert output["production_status"] == "HOLD"
            assert "decoded_html_utf8_sha256" in output
            assert "raw_html_digest" not in output

            listed = await client.list_tools()
            capture_tool = next(
                row for row in listed.tools if row.name == CAPTURE_EXTERNAL_SOURCE_TOOL
            )
            assert "url" not in capture_tool.input_schema["properties"]

    asyncio.run(exercise())


def test_mcp_registers_cell_tools_only_in_explicit_legacy_profile() -> None:
    async def exercise() -> None:
        async with Client(_build_server(include_legacy=True)) as client:
            listed = await client.list_tools()
            names = {tool.name for tool in listed.tools}
            assert READ_REVIEWED_EVIDENCE_TOOL in names
            assert READ_NUMERIC_FACTS_TOOL in names
            assert len(names) == 10

    asyncio.run(exercise())
