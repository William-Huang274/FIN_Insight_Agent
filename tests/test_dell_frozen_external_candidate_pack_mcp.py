from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest


pytest.importorskip("mcp", reason="agent-runtime optional dependency")

from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
    BoundBranchTask,
    ToolLaneTask,
)
from sec_agent.agent_runtime.dell_reference_vertical_mcp_tools import (
    DellMCPToolLaneAdapter,
    compose_dell_mcp_graph_run,
)
from sec_agent.research_foundation.contracts import (
    bind_dell_research_method,
    load_dell_reference_vertical_foundation,
)
from sec_agent.research_foundation.external_sources import (
    ExternalSearchRequest,
    ExternalSourceCapture,
    ExternalSourceDiscovery,
    ExternalSourceError,
    FetchedPage,
    ProviderHit,
    PublicURLGuard,
)
from sec_agent.research_foundation.frozen_external_candidate_pack import (
    FROZEN_REPLAY_METHOD,
    FrozenExternalCandidatePack,
    FrozenExternalCandidatePackProvider,
    FrozenFirstExternalSourceCapture,
)
from sec_agent.research_foundation.mcp_server import (
    DellFoundationMethodReader,
    ResearchDataMCPDependencies,
    build_research_data_mcp_server,
)


_PACK_MANIFEST = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
    "external_exact_url_qualification/"
    "dell_external_exact_url_zero_model_20260902_r12/manifest.json"
)
_PACK_FILE_SHA256 = (
    "db7eae9aaa8108faadbe7ff07404dd25414e0191b7f62af0c7a42b85a0938b94"
)
_BRANCH = "Q6_MODEL_COMPUTE_DEMAND"
_CASE = "DELL_AI_INFRA_REFERENCE_VERTICAL"
_AS_OF = datetime(2026, 9, 2, 23, 59, 59, tzinfo=timezone.utc)


class _NoLiveSearch:
    provider_id = "live_search_must_not_run_for_frozen_candidate"

    def __init__(self) -> None:
        self.invocations = 0

    async def search(self, request: ExternalSearchRequest):
        del request
        self.invocations += 1
        raise AssertionError("live discovery ran for a frozen same-branch route")


class _NoLiveFetch:
    def __init__(self) -> None:
        self.invocations = 0

    async def fetch(self, url: str, *, timeout_seconds: float) -> FetchedPage:
        del url, timeout_seconds
        self.invocations += 1
        raise AssertionError("live capture ran for a frozen exact-URL route")


class _LiveSearchFallback:
    provider_id = "live_search_fallback_fixture"

    def __init__(self) -> None:
        self.invocations = 0

    async def search(self, request: ExternalSearchRequest):
        self.invocations += 1
        return (
            ProviderHit(
                title="Official fallback result",
                url="https://example.com/official-fallback",
                snippet="locator only",
            ),
        )


class _LiveSupplement:
    provider_id = "live_search_supplement_fixture"

    def __init__(self, duplicate_url: str) -> None:
        self.duplicate_url = duplicate_url
        self.invocations = 0

    async def search(self, request: ExternalSearchRequest):
        del request
        self.invocations += 1
        return (
            ProviderHit(
                title="Duplicate frozen locator",
                url=self.duplicate_url,
                snippet="must be deduplicated",
            ),
            ProviderHit(
                title="First live supplement",
                url="https://example.com/live-supplement-one",
                snippet="accepted until the global limit is full",
            ),
            ProviderHit(
                title="Second live supplement",
                url="https://example.org/live-supplement-two",
                snippet="must remain outside the full result set",
            ),
        )


def test_frozen_exact_url_pack_flows_through_agent_mcp_as_candidate_only() -> None:
    if not _PACK_MANIFEST.is_file():
        pytest.skip("immutable external exact-URL qualification pack unavailable")

    pack = FrozenExternalCandidatePack.load(
        _PACK_MANIFEST,
        expected_sha256=_PACK_FILE_SHA256,
    )
    foundation = load_dell_reference_vertical_foundation()
    branch_ids = tuple(row.branch_id for row in foundation.question_branches)
    composition = compose_dell_mcp_graph_run(
        foundation,
        branch_ids=branch_ids,
        research_as_of=_AS_OF.isoformat(),
        snapshot_id="DELL-FROZEN-EXTERNAL-MCP-TEST-SNAPSHOT",
        execution_attempt_id="DELL-FROZEN-EXTERNAL-MCP-TEST-A01",
    )
    with pytest.raises(
        ExternalSourceError,
        match="frozen_candidate_pack_runtime_branch_mismatch",
    ):
        pack.validate_runtime_binding(
            case_id=_CASE,
            branch_ids=(_BRANCH,),
            research_as_of=_AS_OF,
        )
    pack.validate_runtime_binding(
        case_id=_CASE,
        branch_ids=branch_ids,
        research_as_of=_AS_OF,
    )
    pack_binding = pack.manifest_binding()
    assert pack_binding["route_count"] == 12
    assert pack_binding["evidence_admission_authorized"] is False
    assert pack_binding["mcp_promotion_authorized"] is False
    assert pack_binding["s2_write_authorized"] is False
    assert pack_binding["numeric_fact_authority"] is False

    live_search = _NoLiveSearch()
    discovery = ExternalSourceDiscovery(
        primary=live_search,
        frozen_candidate_provider=FrozenExternalCandidatePackProvider(pack),
    )
    live_fetch = _NoLiveFetch()
    guard = PublicURLGuard(resolver=lambda _host: ("93.184.216.34",))
    live_capture = ExternalSourceCapture(
        guard=guard,
        static_fetcher=live_fetch,
        browser_fetcher=None,
    )
    capture = FrozenFirstExternalSourceCapture(
        pack=pack,
        fallback=live_capture,
    )
    server = build_research_data_mcp_server(
        ResearchDataMCPDependencies(
            method_reader=DellFoundationMethodReader(foundation),
            local_knowledge_reader=None,  # not invoked by this external-only task
            reviewed_evidence_search_reader=None,
            reviewed_evidence_reader=None,
            financial_fact_reader=None,
            external_discovery=discovery,
            external_capture=capture,
        )
    )

    branch_binding = next(
        row
        for row in composition.foundation_binding.branch_methods
        if row.branch_id == _BRANCH
    )
    task = ToolLaneTask(
        lane="evidence",
        task=BoundBranchTask(
            task_id="task:Q6_MODEL_COMPUTE_DEMAND:r0:frozen-pack",
            case_id=_CASE,
            branch_id=_BRANCH,
            revision=0,
            priority="high",
            objective="Consume one frozen official compute-demand candidate.",
            evidence_requests=(
                {
                    "query": "OpenAI current model compute demand",
                    "purpose": (
                        "Read the frozen official candidate without granting "
                        "Evidence or citation authority."
                    ),
                    "include_domains": ["openai.com"],
                    "limit": 1,
                    "source_route": "external_required",
                    "capture_limit": 1,
                },
            ),
            fact_requests=(),
            research_as_of=_AS_OF.isoformat(),
            snapshot_id="DELL-FROZEN-EXTERNAL-MCP-TEST-SNAPSHOT",
            foundation_digest=composition.foundation_binding.foundation_digest,
            method_digest=branch_binding.method_digest,
            plan_digest="f" * 64,
        ),
    )

    with DellMCPToolLaneAdapter(
        server,
        run_binding=composition.mcp_run_binding,
    ) as adapter:
        result = adapter.evidence_tool(task.model_dump(mode="json"))

    assert result["status"] == "success"
    assert result["result_states"] == [
        "captured_source_candidate",
        "retrieval_candidate",
    ]
    captured = next(
        row
        for row in result["items"]
        if row.get("result_state") == "captured_source_candidate"
    )
    assert captured["capture_method"] == FROZEN_REPLAY_METHOD
    assert captured["captured_candidate_is_not_evidence"] is True
    assert captured["admission_required_before_citation"] is True
    assert captured["source_capture_authority"] is False
    assert captured["citation_eligible"] is False
    assert captured["production_status"] == "HOLD"
    assert captured["provider_id"] == pack.provider_id
    assert pack.manifest_digest in captured["provider_id"]
    assert live_search.invocations == 0
    assert live_fetch.invocations == 0


def test_frozen_provider_miss_preserves_live_discovery_fallback() -> None:
    if not _PACK_MANIFEST.is_file():
        pytest.skip("immutable external exact-URL qualification pack unavailable")

    pack = FrozenExternalCandidatePack.load(
        _PACK_MANIFEST,
        expected_sha256=_PACK_FILE_SHA256,
    )
    foundation = load_dell_reference_vertical_foundation()
    fallback = _LiveSearchFallback()
    discovery = ExternalSourceDiscovery(
        primary=fallback,
        frozen_candidate_provider=FrozenExternalCandidatePackProvider(pack),
    )
    receipt = asyncio.run(
        discovery.search(
            ExternalSearchRequest(
                query="official source outside the frozen domains",
                branch_id=_BRANCH,
                run_scope=bind_dell_research_method(
                    foundation,
                    (_BRANCH,),
                    research_as_of=_AS_OF,
                    data_snapshot_id=(
                        "DELL-FROZEN-EXTERNAL-FALLBACK-TEST-SNAPSHOT"
                    ),
                    execution_attempt_id=(
                        "DELL-FROZEN-EXTERNAL-FALLBACK-TEST-A01"
                    ),
                ).run_scope,
                purpose="Prove a frozen domain miss still reaches live discovery.",
                max_results=2,
                include_domains=("example.com",),
            )
        )
    )

    assert receipt.status == "ok"
    assert fallback.invocations == 1
    assert [attempt.provider_id for attempt in receipt.attempted_providers] == [
        pack.provider_id,
        fallback.provider_id,
    ]
    assert receipt.candidates[0].provider_id == fallback.provider_id


def test_partial_frozen_candidates_are_supplemented_and_globally_bounded() -> None:
    if not _PACK_MANIFEST.is_file():
        pytest.skip("immutable external exact-URL qualification pack unavailable")

    pack = FrozenExternalCandidatePack.load(
        _PACK_MANIFEST,
        expected_sha256=_PACK_FILE_SHA256,
    )
    branch_id = "Q5_SUPPLY_AND_PRICE"
    frozen_routes = pack.routes_for_branch(branch_id)
    assert len(frozen_routes) == 3
    assert [route.route_id for route in frozen_routes] == [
        "E02_TSMC_2Q26_TRANSCRIPT",
        "E03_MICRON_Q3_FY26_PREPARED_REMARKS",
        "E13_WDC_Q4_FY26_RESULTS",
    ]
    foundation = load_dell_reference_vertical_foundation()
    supplement = _LiveSupplement(frozen_routes[0].official_url)
    diagnostic = _NoLiveSearch()
    discovery = ExternalSourceDiscovery(
        primary=supplement,
        frozen_candidate_provider=FrozenExternalCandidatePackProvider(pack),
        diagnostic_fallback=diagnostic,
    )
    receipt = asyncio.run(
        discovery.search(
            ExternalSearchRequest(
                query="GPU memory storage supply and price constraints",
                branch_id=branch_id,
                run_scope=bind_dell_research_method(
                    foundation,
                    (branch_id,),
                    research_as_of=_AS_OF,
                    data_snapshot_id=(
                        "DELL-FROZEN-EXTERNAL-SUPPLEMENT-TEST-SNAPSHOT"
                    ),
                    execution_attempt_id=(
                        "DELL-FROZEN-EXTERNAL-SUPPLEMENT-TEST-A01"
                    ),
                ).run_scope,
                purpose="Fill the remaining exact-URL candidate budget.",
                max_results=4,
            )
        )
    )

    assert receipt.status == "ok"
    assert supplement.invocations == 1
    assert diagnostic.invocations == 0
    assert len(receipt.candidates) == 4
    urls = [candidate.canonical_url for candidate in receipt.candidates]
    assert len(urls) == len(set(urls))
    assert urls.count(frozen_routes[0].official_url) == 1
    assert "https://example.com/live-supplement-one" in urls
    assert "https://example.org/live-supplement-two" not in urls
    assert [attempt.provider_id for attempt in receipt.attempted_providers] == [
        pack.provider_id,
        supplement.provider_id,
    ]
    assert receipt.attempted_providers[1].returned_hits == 3
    assert receipt.attempted_providers[1].accepted_hits == 1
