from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json

import pytest


pytest.importorskip("mcp", reason="agent-runtime optional dependency")

import sec_agent.agent_runtime.research_mcp_tools as mcp_tools_module

from sec_agent.agent_runtime.research_graph_contracts import (
    BoundBranchTask,
    EvidenceRequest,
    ToolLaneResult,
    ToolLaneTask,
    canonical_sha256,
)
from sec_agent.agent_runtime.deepseek_structured_agents import (
    PlannerSemanticPayload,
)
from sec_agent.agent_runtime.source_family_compiler import SourceFamilyCompiler
from sec_agent.agent_runtime.research_mcp_tools import (
    MCPToolLaneAdapter,
    compose_mcp_graph_run,
)
from sec_agent.agent_runtime.research_graph import _validate_tool_result
from sec_agent.research_foundation.mcp_server import (
    CAPTURE_EXTERNAL_SOURCE_TOOL,
    GET_RESEARCH_METHOD_TOOL,
    QUERY_COMPANY_FINANCIAL_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_BY_ID_TOOL,
    SEARCH_EXTERNAL_SOURCES_TOOL,
    SEARCH_LOCAL_KNOWLEDGE_TOOL,
    SEARCH_REVIEWED_EVIDENCE_TOOL,
)
from sec_agent.research_foundation.contracts import (
    load_research_graph_foundation,
    project_research_method,
)
from test_research_mcp import _build_server


_BRANCH = "Q1_ISSUER_TRUTH"
_BRANCHES = (_BRANCH, "Q2_DEMAND_QUALITY")
_CASE = "DELL_AI_INFRA_REFERENCE_VERTICAL"
_SNAPSHOT = "DELL-MCP-TEST-SNAPSHOT-01"
_PLAN_DIGEST = "c" * 64
_AS_OF = datetime(2026, 9, 2, 2, 0, tzinfo=timezone.utc).isoformat()
_FOUNDATION = load_research_graph_foundation()
_COMPOSITION = compose_mcp_graph_run(
    _FOUNDATION,
    branch_ids=_BRANCHES,
    research_as_of=_AS_OF,
    snapshot_id=_SNAPSHOT,
    execution_attempt_id="DELL-MCP-ADAPTER-A01",
)
_FOUNDATION_DIGEST = _COMPOSITION.foundation_binding.foundation_digest
_FULL_METHOD_DIGEST = project_research_method(
    _FOUNDATION, _BRANCHES
).method_sha256


def _binding():
    return _COMPOSITION.mcp_run_binding


def test_run_composition_projects_foundation_specialist_round_authority() -> None:
    ceiling = _COMPOSITION.foundation_binding.scope_ceiling

    assert ceiling.maximum_specialist_model_rounds == 2
    assert ceiling.maximum_specialist_model_rounds == (
        1 + ceiling.maximum_targeted_counter_reroutes
    )


def test_local_evidence_request_requires_bounded_issuer_and_source_role() -> None:
    with pytest.raises(ValueError, match="local_evidence_request_scope_underbounded"):
        EvidenceRequest(
            query="unbounded local query",
            purpose="This must not silently search the full corpus.",
            source_route="local_only",
        )

    normalized = EvidenceRequest(
        query="bounded local query",
        purpose="Canonicalize issuer identity before MCP dispatch.",
        source_route="local_only",
        issuer_ids=["dell"],
        source_roles=["issuer_management_disclosure"],
    )
    assert normalized.issuer_ids == ("DELL",)


def test_canonical_evidence_request_enforces_per_request_capture_ceiling() -> None:
    with pytest.raises(ValueError, match="less than or equal to 3"):
        EvidenceRequest(
            query="official Dell evidence",
            purpose="Bound one request.",
            source_route="external_required",
            capture_limit=4,
        )
