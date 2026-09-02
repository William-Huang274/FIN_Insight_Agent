from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command


pytest.importorskip("mcp", reason="agent-runtime optional dependency")
pytest.importorskip(
    "langgraph.checkpoint.sqlite",
    reason="SQLite qualification checkpointer optional dependency",
)

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from sec_agent.agent_runtime.deepseek_structured_agents import (
    DeepSeekStructuredAgentAdapter,
    load_deepseek_structured_agent_config,
)
from sec_agent.agent_runtime.dell_reference_vertical_graph import (
    DellReferenceVerticalDependencies,
    build_dell_reference_vertical_graph,
)
from sec_agent.agent_runtime.dell_reference_vertical_mcp_tools import (
    DellMCPToolLaneAdapter,
    compose_dell_mcp_graph_run,
)
from sec_agent.agent_runtime.planner_tool_capabilities import (
    derive_planner_tool_capabilities,
)
from sec_agent.agent_runtime.runtime_foundation import (
    DellRuntimeFoundation,
    open_runtime_checkpointer,
)
from sec_agent.research_foundation.contracts import (
    load_dell_reference_vertical_foundation,
)
from sec_agent.research_foundation.data_ports import (
    CurrentReviewedEvidenceReader,
    ExistingS2FinancialFactReader,
    StructuredLocalKnowledgeReader,
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
    DellFoundationMethodReader,
    ResearchDataMCPDependencies,
    build_research_data_mcp_server,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths


ROOT = Path(__file__).resolve().parents[1]
FOUNDATION_PATH = (
    ROOT
    / "configs/research/fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
)
AGENT_CONFIG_PATH = (
    ROOT
    / "configs/research/fin_ia_0_1_3_dell_reference_vertical_deepseek_structured_agents_v1_0.json"
)
STRUCTURED_NODES_PATH = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/rag_mature_stack/"
    "retrieval_qualification/dell_rag_full_stack_preview_attempt_20260902_03/"
    "retrieval_nodes.jsonl"
)
STRUCTURED_NODES_SHA256 = (
    "f7fbf9f43a68933bad52146c3a8aa3c9a1b52bba81e4e804c2b05a0aff9d0817"
)
STRUCTURED_NODE_COUNT = 1_025
FRESH_S2_MART_PATH = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/s2/"
    "s2_exact_period_contract_successor_20260902_r1/"
    "company_financial_facts.sqlite"
)
FRESH_S2_MART_SHA256 = (
    "363780c076d0f8766c0ceaafdb8b93d308d339636504b2a263127bb6ca365ac4"
)

RUN_ID = "20260902-dell-real-nine-branch-composition-a01"
SNAPSHOT_ID = "20260902-dell-a02-a04-reviewed-evidence-composition"
RESEARCH_AS_OF = datetime(2026, 9, 2, 4, 35, tzinfo=timezone.utc).isoformat()
QUESTION = (
    "Can public sources support Dell AI infrastructure demand quality, supply and "
    "architecture execution, price-volume-mix transmission, financial conversion, "
    "and the strongest counterevidence?"
)

pytestmark = pytest.mark.local_data_integration


def _stream_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _DeterministicExternalProvider:
    """In-process locator fake: it records no DNS, HTTP, browser, or paid call."""

    provider_id = "deterministic_no_network_external_fixture"

    def __init__(self) -> None:
        self.invocations = 0
        self.network_calls = 0

    async def search(
        self, request: ExternalSearchRequest
    ) -> tuple[ProviderHit, ...]:
        self.invocations += 1
        return (
            ProviderHit(
                title="Deterministic Dell counterevidence locator",
                url="https://www.dell.com/reference-composition-counterevidence",
                snippet=(
                    "Qualification-only locator; it is not source text and is not "
                    "reviewed Evidence."
                ),
                published_at="2026-09-01",
            ),
        )


class _DeterministicExternalFetcher:
    """In-process capture fake whose output must remain a non-citable candidate."""

    def __init__(self) -> None:
        self.invocations = 0
        self.network_calls = 0

    async def fetch(self, url: str, *, timeout_seconds: float) -> FetchedPage:
        del timeout_seconds
        self.invocations += 1
        body = (
            "This deterministic qualification fixture represents captured source "
            "text for a counterevidence route. It intentionally carries no factual "
            "authority and cannot be promoted by this composition test. "
        ) * 3
        return FetchedPage(
            final_url=url,
            html=f"<html><main>{body}</main></html>",
            status_code=200,
            content_type="text/html",
        )


class _DeterministicStructuredModel:
    """Schema-aware fake used behind the real DeepSeek host-binding adapter."""

    def __init__(self, role: str) -> None:
        self.role = role
        self.schema: type[Any] | dict[str, Any] | None = None
        self.invocations = 0
        self.paid_provider_calls = 0
        self.network_calls = 0
        self.options: list[dict[str, Any]] = []

    def with_structured_output(
        self,
        schema: type[Any] | dict[str, Any],
        *,
        method: str,
        include_raw: bool,
        strict: bool | None,
    ) -> _DeterministicStructuredModel:
        self.schema = schema
        self.options.append(
            {"method": method, "include_raw": include_raw, "strict": strict}
        )
        return self

    def invoke(self, messages: list[Any]) -> dict[str, Any]:
        assert self.schema is not None
        self.invocations += 1
        semantic_input = json.loads(str(messages[-1].content))
        response = self._response(semantic_input)
        parsed = (
            response
            if isinstance(self.schema, dict)
            else self.schema.model_validate_json(
                json.dumps(response, ensure_ascii=False, allow_nan=False)
            )
        )
        return {
            "raw": AIMessage(
                content="",
                usage_metadata={
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                },
            ),
            "parsed": parsed,
            "parsing_error": None,
        }

    def _response(self, value: Mapping[str, Any]) -> dict[str, Any]:
        if self.role == "planner":
            return self._planner_response(value)
        if self.role == "specialist":
            return self._specialist_response(value)
        if self.role == "counter":
            return self._counter_response(value)
        if self.role == "lead":
            return self._lead_response(value)
        raise AssertionError(f"unexpected fake role: {self.role}")

    @staticmethod
    def _fact_request() -> dict[str, Any]:
        return {
            "ticker": "DELL",
            "metric_ids": ["revenue"],
            "granularity": "quarter_discrete",
            "selection_mode": "latest_on_or_before",
            "period_start": None,
            "period_end": None,
            "fiscal_years": [],
            "requested_unit": "reported_source_unit",
            "unit_family": None,
        }

    @classmethod
    def _planner_response(cls, value: Mapping[str, Any]) -> dict[str, Any]:
        branches = value["branches"]
        tasks: list[dict[str, Any]] = []
        for branch in reversed(branches):
            branch_id = branch["branch_id"]
            if branch_id == "Q1_ISSUER_TRUTH":
                query = "Dell AI optimized server orders revenue backlog"
                source_route = "reviewed_first"
            elif branch_id == "Q9_COUNTEREVIDENCE_WWC":
                query = "Dell AI infrastructure counterevidence"
                source_route = "external_required"
            else:
                query = f"Dell AI server {branch['objective']}"
                source_route = "local_only"
            tasks.append(
                {
                    "branch_id": branch_id,
                    "objective": branch["objective"],
                    "evidence_requests": [
                        {
                            "query": query,
                            "purpose": f"Bound evidence for {branch_id}.",
                            "include_domains": (
                                ["dell.com"]
                                if source_route == "external_required"
                                else []
                            ),
                            **(
                                {}
                                if source_route == "external_required"
                                else {
                                    "issuer_ids": ["DELL"],
                                    "source_roles": [
                                        "issuer_management_disclosure"
                                    ],
                                }
                            ),
                            "limit": 3,
                            "source_route": source_route,
                            # The canonical request schema keeps a positive ceiling
                            # even when the selected route never performs capture.
                            "capture_limit": 1,
                        }
                    ],
                    "fact_requests": [cls._fact_request()],
                }
            )
        return {"tasks": tasks}

    @staticmethod
    def _specialist_response(value: Mapping[str, Any]) -> dict[str, Any]:
        branch = value["branch"]
        evidence_ids = sorted(
            {
                str(item["evidence_id"])
                for item in value["evidence_result"]["items"]
                if isinstance(item, Mapping) and item.get("evidence_id")
            }
        )
        fact_ids = sorted(
            {
                str(item["fact_id"])
                for item in value["finance_result"]["items"]
                if isinstance(item, Mapping) and item.get("fact_id")
            }
        )
        has_authoritative_reference = bool(evidence_ids or fact_ids)
        return {
            "terminal_state": (
                "supported" if has_authoritative_reference else "bounded_gap"
            ),
            "thesis": (
                f"Deterministic contract-valid thesis for {branch['branch_id']} "
                f"revision {branch['revision']}."
            ),
            "mechanism": (
                "The conclusion uses only IDs exposed by the branch-local MCP "
                "results; retrieval and captured candidates remain non-evidence."
            ),
            "counterevidence": [
                "A branch-local contradictory authoritative source would narrow it."
            ],
            "what_would_change": [
                "A later reviewed source or aligned NumericFact would change it."
            ],
            "evidence_ids": evidence_ids,
            "fact_ids": fact_ids,
            "open_gaps": (
                []
                if has_authoritative_reference
                else ["No reviewed Evidence or NumericFact in the bounded result."]
            ),
        }

    @classmethod
    def _counter_response(cls, value: Mapping[str, Any]) -> dict[str, Any]:
        assert {row["branch_id"] for row in value["workpapers"]} >= {
            "Q2_DEMAND_QUALITY"
        }
        return {
            "strongest_counter_thesis": (
                "Backlog or generic capex may not convert at the assumed timing or "
                "economics."
            ),
            "challenges": [
                "Refresh one demand-quality branch without rerunning other branches."
            ],
            "what_would_change": [
                "A source-bound conversion cohort and matching revenue observation."
            ],
            "reroute": {
                "target_branch_id": "Q2_DEMAND_QUALITY",
                "reason": "One bounded demand-quality refresh is material.",
                "evidence_requests": [
                    {
                        "query": "Dell AI server backlog conversion demand quality",
                        "purpose": "Refresh only the challenged branch.",
                        "include_domains": [],
                        "issuer_ids": ["DELL"],
                        "source_roles": ["issuer_management_disclosure"],
                        "limit": 3,
                        "source_route": "local_only",
                        "capture_limit": 1,
                    }
                ],
                "fact_requests": [cls._fact_request()],
            },
        }

    @staticmethod
    def _lead_response(value: Mapping[str, Any]) -> dict[str, Any]:
        conclusions = [
            {
                "branch_id": row["branch_id"],
                "conclusion": f"Bounded conclusion for {row['branch_id']}.",
                "evidence_ids": list(row["evidence_ids"]),
                "fact_ids": list(row["fact_ids"]),
            }
            for row in value["workpapers"]
        ]
        return {
            "verdict": "neutral",
            "confidence": 50,
            "headline": "Nine branches completed with explicit authority boundaries.",
            "executive_summary": (
                "This is a zero-paid-call composition proof over real local data, "
                "not a model-quality or product-release judgment."
            ),
            "branch_conclusions": conclusions,
            "counter_response": (
                "The targeted demand-quality refresh is retained in the final state."
            ),
        }


def _build_external_fakes() -> tuple[
    _DeterministicExternalProvider,
    _DeterministicExternalFetcher,
    ExternalSourceDiscovery,
    ExternalSourceCapture,
]:
    provider = _DeterministicExternalProvider()
    fetcher = _DeterministicExternalFetcher()
    now = datetime(2026, 9, 2, 2, 0, tzinfo=timezone.utc)
    discovery = ExternalSourceDiscovery(
        primary=provider,
        clock=lambda: now,
        monotonic=lambda: 1.0,
    )
    capture = ExternalSourceCapture(
        guard=PublicURLGuard(resolver=lambda _host: ("93.184.216.34",)),
        static_fetcher=fetcher,
        browser_fetcher=None,
        extractor=lambda html: html,
        clock=lambda: now,
        monotonic=lambda: 1.0,
    )
    return provider, fetcher, discovery, capture


def _agent_models() -> dict[str, _DeterministicStructuredModel]:
    return {
        role: _DeterministicStructuredModel(role)
        for role in ("planner", "specialist", "counter", "lead")
    }


def _mcp_dependencies(
    *,
    foundation: Any,
    discovery: ExternalSourceDiscovery,
    capture: ExternalSourceCapture,
) -> ResearchDataMCPDependencies:
    paths = resolve_runtime_paths(ROOT)
    evidence_service = ResearchEvidencePackService.from_runtime_paths(ROOT, paths)
    principal = ResearchEvidencePackPrincipal(
        "current", frozenset({"current_product:read"})
    )
    reviewed = CurrentReviewedEvidenceReader(
        case_reader=lambda case_key: evidence_service.get_case(case_key, principal)
    )
    return ResearchDataMCPDependencies(
        method_reader=DellFoundationMethodReader(foundation),
        local_knowledge_reader=StructuredLocalKnowledgeReader(
            nodes_path=STRUCTURED_NODES_PATH,
            expected_sha256=STRUCTURED_NODES_SHA256,
            expected_node_count=STRUCTURED_NODE_COUNT,
            research_as_of=date(2026, 9, 2),
            allowed_branch_ids=tuple(
                row.branch_id for row in foundation.question_branches
            ),
        ),
        reviewed_evidence_search_reader=reviewed.search,
        reviewed_evidence_reader=reviewed,
        financial_fact_reader=ExistingS2FinancialFactReader(FRESH_S2_MART_PATH),
        external_discovery=discovery,
        external_capture=capture,
    )


def _tool_states_by_branch(values: list[Mapping[str, Any]]) -> dict[str, set[str]]:
    return {
        str(row["branch_id"]): set(row["result_states"])
        for row in values
    }


def test_real_nine_branch_zero_paid_call_composition_and_sqlite_resume(
    tmp_path: Path,
) -> None:
    """Accept the real-data composition seam, not research or release quality."""

    assert FOUNDATION_PATH.is_file()
    assert STRUCTURED_NODES_PATH.is_file()
    assert FRESH_S2_MART_PATH.is_file()
    assert _stream_sha256(STRUCTURED_NODES_PATH) == STRUCTURED_NODES_SHA256
    assert sum(1 for _ in STRUCTURED_NODES_PATH.open(encoding="utf-8")) == (
        STRUCTURED_NODE_COUNT
    )
    assert _stream_sha256(FRESH_S2_MART_PATH) == FRESH_S2_MART_SHA256

    foundation = load_dell_reference_vertical_foundation(FOUNDATION_PATH)
    branch_ids = tuple(row.branch_id for row in foundation.question_branches)
    assert branch_ids == tuple(
        f"Q{index}_{suffix}"
        for index, suffix in (
            (1, "ISSUER_TRUTH"),
            (2, "DEMAND_QUALITY"),
            (3, "UNITS_ASP_PVM"),
            (4, "ARCHITECTURE_RAMP"),
            (5, "SUPPLY_AND_PRICE"),
            (6, "MODEL_COMPUTE_DEMAND"),
            (7, "EXPORT_CONTROL_CHINA"),
            (8, "COMPETITION_VALUE_POOL"),
            (9, "COUNTEREVIDENCE_WWC"),
        )
    )
    composition = compose_dell_mcp_graph_run(
        foundation,
        branch_ids=branch_ids,
        research_as_of=RESEARCH_AS_OF,
        snapshot_id=SNAPSHOT_ID,
        execution_attempt_id=RUN_ID,
    )
    capabilities = derive_planner_tool_capabilities(
        sqlite_path=FRESH_S2_MART_PATH,
        expected_mart_sha256=FRESH_S2_MART_SHA256,
        snapshot_id=SNAPSHOT_ID,
    )
    assert capabilities.mart_sha256 == FRESH_S2_MART_SHA256
    assert "DELL" in capabilities.finance.supported_tickers
    assert "revenue" in {row.metric_id for row in capabilities.finance.metrics}

    provider, fetcher, discovery, capture = _build_external_fakes()
    mcp_dependencies = _mcp_dependencies(
        foundation=foundation,
        discovery=discovery,
        capture=capture,
    )
    models = _agent_models()
    agents = DeepSeekStructuredAgentAdapter(
        config=load_deepseek_structured_agent_config(AGENT_CONFIG_PATH),
        chat_models=models,
    )
    runtime = DellRuntimeFoundation.from_environment(
        {
            "FINSIGHT_DELL_RUNTIME_PROFILE": "sqlite_qualification",
            "FINSIGHT_AGENT_RUNTIME_SQLITE_PATH": str(
                tmp_path / "dell-real-composition-checkpoints.sqlite3"
            ),
        },
        default_state_root=tmp_path,
    )
    assert runtime.public_projection()["checkpoint_backend"] == (
        "langgraph_sqlite_saver"
    )
    assert runtime.public_projection()["product_pilot_eligible"] is False

    config = {"configurable": {"thread_id": RUN_ID}}
    start = {
        "run_id": RUN_ID,
        "case_id": foundation.case_identity.case_id,
        "research_question": QUESTION,
        "research_as_of": RESEARCH_AS_OF,
        "snapshot_id": SNAPSHOT_ID,
        "foundation_digest": composition.foundation_binding.foundation_digest,
    }

    # Phase one deliberately closes both the MCP client and SQLite saver at HITL.
    with DellMCPToolLaneAdapter(
        build_research_data_mcp_server(mcp_dependencies),
        run_binding=composition.mcp_run_binding,
    ) as tools:
        dependencies = DellReferenceVerticalDependencies(
            foundation_binder=composition.foundation_binder,
            planner_tool_capabilities=capabilities.model_dump(mode="json"),
            planner_agent=agents.planner,
            evidence_tool=tools.evidence_tool,
            finance_tool=tools.finance_tool,
            specialist_agent=agents.specialist,
            counter_agent=agents.counter,
            lead_agent=agents.lead,
        )
        with open_runtime_checkpointer(runtime) as checkpointer:
            graph = build_dell_reference_vertical_graph(
                dependencies=dependencies,
                checkpointer=checkpointer,
            )
            interrupted = graph.invoke(start, config)

    assert runtime.sqlite_path is not None
    assert runtime.sqlite_path.is_file()
    assert runtime.sqlite_path.stat().st_size > 0
    assert interrupted["phase"] == "awaiting_review"
    assert "__interrupt__" in interrupted
    assert interrupted["verification"] == {"passed": True, "errors": []}
    assert len(interrupted["branch_tasks"]) == 9
    assert set(interrupted["effective_workpapers_by_branch"]) == set(branch_ids)
    assert interrupted["reroute_count"] == 1
    assert interrupted["effective_workpapers_by_branch"]["Q2_DEMAND_QUALITY"][
        "revision"
    ] == 1
    assert all(
        row["revision"] == 0
        for branch_id, row in interrupted["effective_workpapers_by_branch"].items()
        if branch_id != "Q2_DEMAND_QUALITY"
    )
    assert len(interrupted["initial_evidence_results"]) == 9
    assert len(interrupted["initial_finance_results"]) == 9
    assert _tool_states_by_branch(interrupted["initial_evidence_results"])[
        "Q1_ISSUER_TRUTH"
    ] >= {"reviewed_evidence"}
    assert _tool_states_by_branch(interrupted["initial_evidence_results"])[
        "Q9_COUNTEREVIDENCE_WWC"
    ] == {"captured_source_candidate", "retrieval_candidate"}
    assert all(
        "numeric_fact" in states
        for states in _tool_states_by_branch(
            interrupted["initial_finance_results"]
        ).values()
    )

    serialized_tool_results = json.dumps(
        {
            "evidence": interrupted["initial_evidence_results"],
            "finance": interrupted["initial_finance_results"],
            "rework_evidence": interrupted["rework_evidence_result"],
            "rework_finance": interrupted["rework_finance_result"],
        },
        ensure_ascii=False,
    )
    # The public MCP projection intentionally omits source file paths and their
    # private binding digest.  Structured S1 and fresh S2 identity are proved
    # above at the port construction boundary; lane output proves those ports
    # were consumed.
    assert any(
        item.get("structured_document_tree") is True
        for result in interrupted["initial_evidence_results"]
        for item in result["items"]
    )
    assert all(
        item.get("legacy_read_only_bridge") is False
        for result in interrupted["initial_evidence_results"]
        for item in result["items"]
        if "legacy_read_only_bridge" in item
    )
    assert all(
        item.get("numeric_fact_authority") is True
        for result in interrupted["initial_finance_results"]
        for item in result["items"]
        if item.get("result_state") == "numeric_fact"
    )
    assert "cell_id" not in serialized_tool_results
    assert "Z:\\FIN_Insight_Agent_qualification" not in serialized_tool_results

    external_items = next(
        row["items"]
        for row in interrupted["initial_evidence_results"]
        if row["branch_id"] == "Q9_COUNTEREVIDENCE_WWC"
    )
    captured = next(
        row
        for row in external_items
        if row["result_state"] == "captured_source_candidate"
    )
    assert captured["captured_candidate_is_not_evidence"] is True
    assert captured["admission_required_before_citation"] is True
    assert captured["source_capture_authority"] is False
    assert captured["citation_eligible"] is False
    assert provider.invocations == 1
    assert fetcher.invocations == 1
    assert provider.network_calls == fetcher.network_calls == 0

    calls_at_interrupt = {
        role: model.invocations for role, model in models.items()
    }
    assert calls_at_interrupt == {
        "planner": 1,
        "specialist": 10,
        "counter": 1,
        "lead": 1,
    }
    assert sum(model.paid_provider_calls for model in models.values()) == 0
    assert sum(model.network_calls for model in models.values()) == 0

    # Reconstruct the graph and MCP lifecycle, then resume only from SQLite state.
    with DellMCPToolLaneAdapter(
        build_research_data_mcp_server(mcp_dependencies),
        run_binding=composition.mcp_run_binding,
    ) as resumed_tools:
        resumed_dependencies = DellReferenceVerticalDependencies(
            foundation_binder=composition.foundation_binder,
            planner_tool_capabilities=capabilities.model_dump(mode="json"),
            planner_agent=agents.planner,
            evidence_tool=resumed_tools.evidence_tool,
            finance_tool=resumed_tools.finance_tool,
            specialist_agent=agents.specialist,
            counter_agent=agents.counter,
            lead_agent=agents.lead,
        )
        with open_runtime_checkpointer(runtime) as checkpointer:
            resumed_graph = build_dell_reference_vertical_graph(
                dependencies=resumed_dependencies,
                checkpointer=checkpointer,
            )
            persisted = resumed_graph.get_state(config)
            assert persisted.values["phase"] == "awaiting_review"
            completed = resumed_graph.invoke(
                Command(
                    resume={
                        "action": "approve",
                        "reason": "Deterministic composition acceptance only.",
                    }
                ),
                config,
            )

    assert completed["phase"] == "completed"
    report = completed["final_report"]
    assert report["reroute_count"] == 1
    assert [row["branch_id"] for row in report["branch_workpapers"]] == sorted(
        branch_ids
    )
    runtime_summary = report["runtime_summary"]
    assert runtime_summary["node_receipt_count"] == 33
    assert runtime_summary["model_receipt_count"] == 13
    assert runtime_summary["successful_model_call_count"] == 13
    assert runtime_summary["failed_model_call_count"] == 0
    assert runtime_summary["model_usage_reported_count"] == 13
    assert runtime_summary["model_usage_missing_count"] == 0
    assert runtime_summary["tool_lane_receipt_count"] == 20
    assert runtime_summary["host_receipt_count"] == 0
    assert runtime_summary["mcp_call_count"] > 0
    assert runtime_summary["mcp_error_call_count"] == 0
    assert runtime_summary["mcp_tool_call_counts"]
    assert runtime_summary["input_tokens"] == 0
    assert runtime_summary["output_tokens"] == 0
    assert runtime_summary["total_tokens"] == 0
    assert runtime_summary["node_receipt_elapsed_ms_sum_not_wall_clock"] >= 0
    assert runtime_summary["mcp_call_elapsed_ms_sum_not_wall_clock"] >= 0
    assert runtime_summary["failed_node_receipt_count"] == 0
    assert {role: model.invocations for role, model in models.items()} == (
        calls_at_interrupt
    )
    assert provider.invocations == 1
    assert fetcher.invocations == 1
    assert sum(model.paid_provider_calls for model in models.values()) == 0
    assert sum(model.network_calls for model in models.values()) == 0
    assert {
        (row["branch_id"], row["revision"])
        for row in report["branch_workpapers"]
    } == {
        (branch_id, 1 if branch_id == "Q2_DEMAND_QUALITY" else 0)
        for branch_id in branch_ids
    }
