from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
import json
from pathlib import Path

import pytest


pytest.importorskip("mcp", reason="agent-runtime optional dependency")

from mcp import Client

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from sec_agent.research_foundation.contracts import (
    DEFAULT_DELL_REFERENCE_VERTICAL_FOUNDATION_PATH,
    load_dell_reference_vertical_foundation,
)
from sec_agent.research_foundation.data_ports import (
    CurrentReviewedEvidenceReader,
    ExistingS2FinancialFactReader,
    FrozenLegacyLocalKnowledgeReader,
)
from sec_agent.research_foundation.mcp_server import (
    GET_RESEARCH_METHOD_TOOL,
    QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_BY_ID_TOOL,
    SEARCH_LOCAL_KNOWLEDGE_TOOL,
    SEARCH_REVIEWED_EVIDENCE_TOOL,
    DellFoundationMethodReader,
    ResearchDataMCPDependencies,
    build_research_data_mcp_server,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.local_data_integration
if not (
    ROOT
    / "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v5/records.jsonl"
).is_file():
    pytest.skip("current DELL local data mounts are unavailable", allow_module_level=True)


class _UnusedExternalDiscovery:
    async def search(self, _request):  # pragma: no cover - defensive sentinel
        raise AssertionError("external_discovery_not_expected")


class _UnusedExternalCapture:
    async def capture(self, _request):  # pragma: no cover - defensive sentinel
        raise AssertionError("external_capture_not_expected")


def test_real_frozen_local_evidence_and_s2_flow_through_non_cell_mcp() -> None:
    paths = resolve_runtime_paths(ROOT)
    foundation = load_dell_reference_vertical_foundation(
        DEFAULT_DELL_REFERENCE_VERTICAL_FOUNDATION_PATH
    )
    evidence_service = ResearchEvidencePackService.from_runtime_paths(ROOT, paths)
    evidence_principal = ResearchEvidencePackPrincipal(
        "current", frozenset({"current_product:read"})
    )
    reviewed_reader = CurrentReviewedEvidenceReader(
        case_reader=lambda case_key: evidence_service.get_case(
            case_key, evidence_principal
        )
    )
    dependencies = ResearchDataMCPDependencies(
        method_reader=DellFoundationMethodReader(foundation),
        local_knowledge_reader=FrozenLegacyLocalKnowledgeReader(
            records_path=(
                ROOT
                / "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v5/records.jsonl"
            ),
            expected_sha256=(
                "d4c7e51790713d32fc10a9d0382b617f8ebd60861a3741d3adcee34392045d45"
            ),
            expected_record_count=1_888,
            research_as_of=date.fromisoformat("2026-09-02"),
            allowed_branch_ids=tuple(
                row.branch_id for row in foundation.question_branches
            ),
        ),
        reviewed_evidence_search_reader=reviewed_reader.search,
        reviewed_evidence_reader=reviewed_reader,
        financial_fact_reader=ExistingS2FinancialFactReader(
            paths.company_financial_fact_mart_path
        ),
        external_discovery=_UnusedExternalDiscovery(),
        external_capture=_UnusedExternalCapture(),
    )

    async def exercise() -> None:
        async with Client(build_research_data_mcp_server(dependencies)) as client:
            method = await client.call_tool(
                GET_RESEARCH_METHOD_TOOL,
                {
                    "branch_ids": ["Q1_ISSUER_TRUTH", "Q2_DEMAND_QUALITY"],
                    "research_as_of": datetime(
                        2026, 9, 2, tzinfo=timezone.utc
                    ).isoformat(),
                    "data_snapshot_id": "DELL-REAL-DATA-SNAPSHOT-01",
                    "execution_attempt_id": "DELL-REAL-MCP-A01",
                },
            )
            scope = method.structured_content["run_scope"]
            local = await client.call_tool(
                SEARCH_LOCAL_KNOWLEDGE_TOOL,
                {
                    "query": "Dell AI optimized server orders revenue backlog",
                    "branch_id": "Q1_ISSUER_TRUTH",
                    "run_scope": scope,
                    "limit": 4,
                },
            )
            evidence_search = await client.call_tool(
                SEARCH_REVIEWED_EVIDENCE_TOOL,
                {
                    "query": "Dell AI optimized server orders revenue backlog",
                    "branch_id": "Q1_ISSUER_TRUTH",
                    "run_scope": scope,
                    "limit": 4,
                },
            )
            discovered_evidence_id = evidence_search.structured_content["hits"][
                0
            ]["evidence_id"]
            evidence = await client.call_tool(
                READ_REVIEWED_EVIDENCE_BY_ID_TOOL,
                {
                    "evidence_ids": [discovered_evidence_id],
                    "branch_id": "Q1_ISSUER_TRUTH",
                    "run_scope": scope,
                },
            )
            facts = await client.call_tool(
                QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
                {
                    "branch_id": "Q1_ISSUER_TRUTH",
                    "run_scope": scope,
                    "ticker": "DELL",
                    "metric_ids": ["revenue", "gross_profit"],
                    "research_as_of": "2026-06-24",
                    "period_start": "2026-01-31",
                    "period_end": "2026-05-01",
                    "fiscal_years": [2027],
                    "granularity": "quarter_discrete",
                },
            )

            assert method.is_error is False
            assert local.is_error is False
            assert evidence.is_error is False
            assert evidence_search.is_error is False
            assert facts.is_error is False
            assert local.structured_content["authority_state"] == (
                "retrieval_candidate_set"
            )
            assert local.structured_content["candidates"]
            assert evidence.structured_content["evidence"][0]["evidence_id"] == (
                discovered_evidence_id
            )
            assert facts.structured_content["resolved_metric_count"] == 2
            assert "cell_id" not in json.dumps(
                {
                    "method": method.structured_content,
                    "local": local.structured_content,
                    "evidence": evidence.structured_content,
                    "evidence_search": evidence_search.structured_content,
                    "facts": facts.structured_content,
                },
                ensure_ascii=False,
            )
            assert "D:\\FIN_Insight_Agent" not in json.dumps(
                {
                    "local": local.structured_content,
                    "evidence": evidence.structured_content,
                    "facts": facts.structured_content,
                },
                ensure_ascii=False,
            )

    asyncio.run(exercise())
