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
    StructuredLocalKnowledgeReader,
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
STRUCTURED_NODES_PATH = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/rag_mature_stack/"
    "retrieval_qualification/dell_rag_full_stack_preview_attempt_20260902_03/"
    "retrieval_nodes.jsonl"
)
STRUCTURED_NODES_SHA256 = (
    "f7fbf9f43a68933bad52146c3a8aa3c9a1b52bba81e4e804c2b05a0aff9d0817"
)
STRUCTURED_NODE_COUNT = 1_025
pytestmark = pytest.mark.local_data_integration
if not STRUCTURED_NODES_PATH.is_file():
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
        local_knowledge_reader=StructuredLocalKnowledgeReader(
            nodes_path=STRUCTURED_NODES_PATH,
            expected_sha256=STRUCTURED_NODES_SHA256,
            expected_node_count=STRUCTURED_NODE_COUNT,
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
                    "query": (
                        "Dell FY2027 Q1 cash flow accounts receivable inventories "
                        "accounts payable working capital changes"
                    ),
                    "branch_id": "Q1_ISSUER_TRUTH",
                    "run_scope": scope,
                    "limit": 6,
                    "issuer_ids": ["DELL"],
                    "fiscal_periods": ["FY2027_Q1"],
                    "source_roles": ["issuer_filing_narrative"],
                    "route_ids": ["dell_fy2027_q1_10q_narrative"],
                    "lanes": ["table_leaf"],
                },
            )
            transcript = await client.call_tool(
                SEARCH_LOCAL_KNOWLEDGE_TOOL,
                {
                    "query": (
                        "Dell FY2027 Q1 pull forward buy ahead durable underlying "
                        "demand installed base refresh AI share gains"
                    ),
                    "branch_id": "Q2_DEMAND_QUALITY",
                    "run_scope": scope,
                    "limit": 6,
                    "issuer_ids": ["DELL"],
                    "fiscal_periods": ["FY2027_Q1"],
                    "source_roles": ["issuer_management_disclosure"],
                    "route_ids": ["dell_fy2027_q1_transcript"],
                    "lanes": ["prose_leaf"],
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
                    "selection_mode": "exact_period_end",
                    "fiscal_years": [2027],
                    "granularity": "quarter_discrete",
                },
            )

            assert method.is_error is False
            assert local.is_error is False
            assert evidence.is_error is False
            assert evidence_search.is_error is False
            assert facts.is_error is False
            assert transcript.is_error is False
            assert local.structured_content["authority_state"] == (
                "retrieval_candidate_set"
            )
            assert local.structured_content["candidates"]
            assert local.structured_content["retrieval_strategy"] == (
                "metadata_prefilter_bm25"
            )
            assert local.structured_content["metadata_prefilter_applied"] is True
            assert local.structured_content["candidates"][0]["source_record_id"] == (
                "BLOCK::C46E0FD5E2F8AA3DCA4B20F5"
            )
            assert local.structured_content["candidates"][0]["citation_eligible"] is False
            assert transcript.structured_content["candidates"][0][
                "source_record_id"
            ] == "CHUNK::C555524A6CE91A096CFFF279"
            assert transcript.structured_content["candidates"][0][
                "delivered_context_node_ids"
            ] == [
                "CHUNK::ABE94E8163EE4AA265D214CD",
                "CHUNK::C555524A6CE91A096CFFF279",
                "CHUNK::2FEB7579E112C8CF854CA682",
            ]
            assert evidence.structured_content["evidence"][0]["evidence_id"] == (
                discovered_evidence_id
            )
            assert facts.structured_content["resolved_metric_count"] == 2
            assert {
                row["metric_id"] for row in facts.structured_content["results"]
            } == {"revenue", "gross_profit"}
            assert "cell_id" not in json.dumps(
                {
                    "method": method.structured_content,
                    "local": local.structured_content,
                    "transcript": transcript.structured_content,
                    "evidence": evidence.structured_content,
                    "evidence_search": evidence_search.structured_content,
                    "facts": facts.structured_content,
                },
                ensure_ascii=False,
            )
            assert "D:\\FIN_Insight_Agent" not in json.dumps(
                {
                    "local": local.structured_content,
                    "transcript": transcript.structured_content,
                    "evidence": evidence.structured_content,
                    "facts": facts.structured_content,
                },
                ensure_ascii=False,
            )

    asyncio.run(exercise())
