from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from retrieval.contracts import load_financial_research_kernel
from retrieval.route_compiler import load_query_object_fact_route_policy
from sec_agent.providers import ChatCompletionToolStepResult, load_chat_completion_profile
from sec_agent.providers.agent_protocol import (
    ANTHROPIC_MESSAGES_WIRE,
    CHAT_COMPLETIONS_WIRE,
    RESPONSES_WIRE,
    canonicalize_tool_definitions,
    project_tool_definitions,
    load_agent_transport_profile,
)
from sec_agent.research.bounded_finance_loop import (
    BoundedFinanceLoopError,
    MICRO_JUDGMENT_TOOL_NAMES,
    READ_NUMERIC_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_TOOL,
    SUBMIT_EVIDENCE_REQUEST_TOOL,
    SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
    SUBMIT_RESEARCH_JUDGMENT_TOOL,
    SUBMIT_RESEARCH_MECHANISM_TOOL,
    SUBMIT_RESEARCH_THESIS_TOOL,
    compile_finance_micro_fragment_analysis_messages,
    compile_finance_micro_fragment_context,
    compile_finance_micro_fragment_submission_messages,
    compile_finance_micro_judgment_tools,
    compile_finance_loop_messages,
    compile_finance_loop_tools,
    load_bounded_finance_loop_policy,
    load_fixed_pack_micro_judgment_policy,
    run_bounded_finance_loop,
    scope_bounded_finance_micro_judgment_policy,
    scope_bounded_finance_loop_policy,
    validate_deepseek_ga_json_profile,
    validate_deepseek_ga_node_profile,
    validate_deepseek_ga_profile,
    validate_finance_micro_judgment_fragment,
)
from sec_agent.research.current_consumer import (
    compile_current_research_input,
)
from sec_agent.research.claim_authority import (
    compile_claim_authority_research_input,
)
from sec_agent.research.claim_surface_authority import (
    compile_claim_surface_authority_research_input,
)
from sec_agent.research.planning import (
    compile_research_objective,
    load_research_planning_policy,
)
from sec_agent.research.live_transport_lane import (
    execute_finance_loop_transport_lane,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from sec_agent.runtime_bridge.paths import resolve_runtime_paths
from sec_agent.runtime_resource_registry import read_registered_runtime_json


READ = frozenset({"current_product:read"})
POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_bounded_finance_agent_loop_policy_v1_1.json"
)
MICRO_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_fixed_pack_micro_judgment_policy_v1_0.json"
)
CONSUMER_POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_current_research_consumer_policy_v1_2.json"
)
OBJECTIVE = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
)
ATOMS = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
)
FAKE = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_current_research_consumer_fake_payload_v1_2.json"
)
CLAIM_AUTHORITY_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_claim_authority_v1_0.json"
)
CLAIM_RELATION_ALIAS_POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_v1_1.json"
)
CLAIM_RELATION_ALIAS_FAKE = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_alias_fake_payload_v1_0.json"
)
CLAIM_SURFACE_R1_CAPACITY_ASSESSMENT = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_"
    "claim_surface_authority_chat_live_capacity_assessment_v1_0.json"
)


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _zero_call_runner():
    path = ROOT / "scripts/research/run_s3_bounded_finance_loop_zero_call.py"
    spec = importlib.util.spec_from_file_location(
        "s3_bounded_finance_loop_zero_call_runner",
        path,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def contracts():
    paths = resolve_runtime_paths(ROOT)
    kernel_payload = read_registered_runtime_json(
        ROOT, "application.config.current_financial_research_kernel"
    )
    route_payload = read_registered_runtime_json(
        ROOT, "application.config.current_query_object_fact_route_policy"
    )
    planning_payload = read_registered_runtime_json(
        ROOT, "application.config.current_research_planning_policy"
    )
    kernel = load_financial_research_kernel(kernel_payload)
    route = load_query_object_fact_route_policy(route_payload, kernel)
    planning = load_research_planning_policy(planning_payload, route)
    evidence_config = read_registered_runtime_json(
        ROOT, "application.config.current_research_evidence_pack_projection"
    )
    evidence_service = ResearchEvidencePackService(
        config=evidence_config,
        result=read_registered_runtime_json(
            ROOT, str(evidence_config["source_result_resource_id"])
        ),
        private_object_root=(
            paths.reviewed_evidence_root
            / str(evidence_config["private_object_root_relative"])
        ),
        private_root_base=paths.reviewed_evidence_root,
    )
    evidence_pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", READ)
    )
    retrieval = ResearchRetrievalService(
        snapshot=read_registered_runtime_json(
            ROOT, "application.result.current_research_retrieval_snapshot"
        ),
        ranking_comparison=read_registered_runtime_json(
            ROOT, "application.result.current_s1c_ranking_comparison_projection"
        ),
        kernel=kernel_payload,
        route_policy=route_payload,
        planning_policy=planning_payload,
        hybrid_candidate_runtime=None,
        company_financial_fact_mart_path=paths.company_financial_fact_mart_path,
    )
    controlled = retrieval.execute_controlled_plan(
        "DELL",
        _json(OBJECTIVE),
        _json(ATOMS),
        ResearchRetrievalPrincipal("current", READ),
    )
    research_input = compile_current_research_input(
        policy=_json(CONSUMER_POLICY),
        evidence_pack=evidence_pack,
        controlled_plan=controlled,
    )
    return (
        load_bounded_finance_loop_policy(_json(POLICY)),
        research_input,
        kernel,
        route,
        planning,
    )


def _step(
    index: int,
    name: str,
    arguments: dict[str, object],
) -> ChatCompletionToolStepResult:
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="fixture_provider",
        model="fixture-model",
        content="",
        reasoning_content=f"private-step-{index}",
        tool_calls=(
            {
                "id": f"call-{index}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            },
        ),
        finish_reason="tool_calls",
        usage={"total_tokens": index},
        request_capture_ref=f"capture/request-{index}.json",
        response_capture_ref=f"capture/response-{index}.json",
        request_digest=f"request-{index}",
        response_digest=f"response-{index}",
        private_reasoning_fields_redacted=1,
    )


def _parallel_step(
    index: int,
    calls: list[tuple[str, dict[str, object]]],
) -> ChatCompletionToolStepResult:
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="fixture_provider",
        model="fixture-model",
        content="",
        reasoning_content=f"private-step-{index}",
        tool_calls=tuple(
            {
                "id": f"call-{index}-{offset}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            }
            for offset, (name, arguments) in enumerate(calls)
        ),
        finish_reason="tool_calls",
        usage={"total_tokens": index},
        request_capture_ref=f"capture/request-{index}.json",
        response_capture_ref=f"capture/response-{index}.json",
        request_digest=f"request-{index}",
        response_digest=f"response-{index}",
        private_reasoning_fields_redacted=1,
    )


def _fake_judgment(cell_id: str) -> dict[str, object]:
    return deepcopy(
        next(row for row in _json(FAKE)["cells"] if row["cell_id"] == cell_id)
    )


def _claim_authority_judgment() -> dict[str, object]:
    row = _fake_judgment("CELL::value_capture")
    row.update(
        {
            "claim_scope": "multi_scope",
            "financial_scope": "multi_scope_financial",
            "causal_bridge_authority": "multi_driver_context_only",
            "thesis_atom": (
                "Dell company and segment profit improved while AI server mix "
                "pressured gross margin, but the reviewed evidence does not "
                "isolate the product contribution."
            ),
            "mechanism_atom": (
                "Management describes product profitability, storage "
                "profitability, traditional server margins and revenue scale as "
                "separate factors, so the current pack cannot allocate the "
                "company change to one product."
            ),
            "counterargument_atom": (
                "The product target is unaudited and the missing product profit, "
                "unit, price and mix bridge leaves the value-capture conclusion "
                "bounded."
            ),
        }
    )
    return row


def test_fixed_pack_claim_authority_loop_uses_zero_request_budget(contracts) -> None:
    base_policy, research_input, kernel, route, planning = contracts
    claim_input = compile_claim_authority_research_input(
        research_input,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    cell_id = "CELL::value_capture"
    scoped = scope_bounded_finance_loop_policy(
        base_policy,
        cell_count=1,
        maximum_evidence_requests=0,
    )
    tools = compile_finance_loop_tools(
        research_input=claim_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    judgment = next(
        row
        for row in tools
        if row["function"]["name"] == SUBMIT_RESEARCH_JUDGMENT_TOOL
    )
    properties = judgment["function"]["parameters"]["properties"]
    assert properties["claim_scope"]["enum"] == [
        "product",
        "segment",
        "company",
        "multi_scope",
    ]
    assert "direct_cross_scope_bridge" not in properties[
        "causal_bridge_authority"
    ]["enum"]
    budget = {
        "maximum_steps": scoped.maximum_steps,
        "maximum_evidence_requests": 0,
        "maximum_reads_per_cell": 1,
        "maximum_parallel_read_tools": 2,
        "maximum_judgments_per_cell": 1,
        "retry_count": 0,
    }
    messages = compile_finance_loop_messages(
        research_input=claim_input,
        required_cell_ids=[cell_id],
        execution_budget=budget,
    )
    visible = json.loads(messages[1]["content"])
    assert visible["execution_budget"]["maximum_evidence_requests"] == 0
    assert visible["claim_authority_contract"]["agentic_research_claimed"] is False
    result = run_bounded_finance_loop(
        policy=scoped,
        research_input=claim_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=lambda _messages, _tools, index: (
            _parallel_step(
                index,
                [
                    (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                    (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
                ],
            )
            if index == 1
            else _step(
                index,
                SUBMIT_RESEARCH_JUDGMENT_TOOL,
                _claim_authority_judgment(),
            )
        ),
        visible_execution_budget=budget,
    )
    assert result.status == "completed_all_required_cells"
    assert result.step_count == 2
    assert result.tool_call_count == 3
    assert result.tool_counts.get(SUBMIT_EVIDENCE_REQUEST_TOOL, 0) == 0
    assert result.structured_deliverable["fixed_pack_experiment_boundary"][
        "agentic_research_claimed"
    ] is False


def test_claim_relation_alias_loop_compacts_wire_and_retains_private_lineage(
    contracts,
) -> None:
    base_policy, research_input, kernel, route, planning = contracts
    claim_input = compile_claim_authority_research_input(
        research_input,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    alias_input = compile_claim_surface_authority_research_input(
        claim_input,
        policy=_json(CLAIM_RELATION_ALIAS_POLICY),
    )
    cell_id = "CELL::value_capture"
    scoped = scope_bounded_finance_loop_policy(
        base_policy,
        cell_count=1,
        maximum_evidence_requests=0,
    )
    tools = compile_finance_loop_tools(
        research_input=alias_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    assert [row["function"]["name"] for row in tools] == [
        READ_REVIEWED_EVIDENCE_TOOL,
        READ_NUMERIC_FACTS_TOOL,
        SUBMIT_RESEARCH_JUDGMENT_TOOL,
    ]
    budget = {
        "maximum_steps": scoped.maximum_steps,
        "maximum_evidence_requests": 0,
        "maximum_reads_per_cell": 1,
        "maximum_parallel_read_tools": 2,
        "maximum_judgments_per_cell": 1,
        "retry_count": 0,
    }
    observed: dict[str, object] = {}
    fake = deepcopy(_json(CLAIM_RELATION_ALIAS_FAKE)["cells"][0])

    def execute(messages, _tools, index):
        if index == 1:
            return _parallel_step(
                index,
                [
                    (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                    (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
                ],
            )
        observed["messages"] = deepcopy(messages)
        return _step(index, SUBMIT_RESEARCH_JUDGMENT_TOOL, fake)

    result = run_bounded_finance_loop(
        policy=scoped,
        research_input=alias_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=execute,
        visible_execution_budget=budget,
    )
    messages = observed["messages"]
    message_chars = sum(
        len(str(row.get("content") or "")) for row in messages
    )
    tool_chars = len(
        json.dumps(
            tools,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    prior = _json(CLAIM_SURFACE_R1_CAPACITY_ASSESSMENT)["observed"]
    assert message_chars < prior["step_two_model_visible_message_chars"] / 2
    assert tool_chars < prior["step_two_tool_schema_chars"] * 0.55

    tool_results = [
        json.loads(row["content"])
        for row in messages
        if row.get("role") == "tool"
    ]
    numeric_result = next(
        row
        for row in tool_results
        if row.get("status") == "authoritative_numeric_facts_read"
    )
    compact_fact = numeric_result["numeric_facts"][0]
    assert "source_digests" not in compact_fact
    assert "citation_urls" not in compact_fact
    assert "source_observation_ids" not in compact_fact
    assert any(
        "source_digests" in row and "citation_urls" in row
        for row in alias_input["numeric_fact_cards"]
    )
    assert result.status == "completed_all_required_cells"
    assert result.step_count == 2
    assert result.tool_call_count == 3
    assert result.structured_deliverable["schema_version"] == (
        "fin_ia_current_research_deliverable_v1_5"
    )
    assert all(
        "claim_subject" in row and "claim_relation_ref" in row
        for row in result.structured_deliverable["cells"][0][
            "claim_relations"
        ]
    )


def _micro_alias_fragments() -> dict[str, dict[str, object]]:
    row = deepcopy(_json(CLAIM_RELATION_ALIAS_FAKE)["cells"][0])
    relation_by_atom = {
        item["atom_field"]: item["claim_relation_ref"]
        for item in row["claim_relations"]
    }
    common_refs = {
        "numeric_refs": list(row["numeric_refs"]),
        "method_step_refs": list(row["method_step_refs"]),
        "graph_edge_refs": list(row["graph_edge_refs"]),
    }
    return {
        SUBMIT_RESEARCH_THESIS_TOOL: {
            "cell_id": row["cell_id"],
            "claim_relation_ref": relation_by_atom["thesis_atom"],
            "evidence_uses": row["evidence_uses"][:2],
            **common_refs,
            "numeric_relation_refs": [],
            "qualitative_fact_refs": list(row["qualitative_fact_refs"]),
            "judgment_status": row["judgment_status"],
            "confidence_basis": row["confidence_basis"],
            "inference_authority": row["inference_authority"],
            "claim_scope": row["claim_scope"],
            "financial_scope": row["financial_scope"],
            "causal_bridge_authority": row["causal_bridge_authority"],
            "thesis_atom": row["thesis_atom"],
        },
        SUBMIT_RESEARCH_MECHANISM_TOOL: {
            "cell_id": row["cell_id"],
            "claim_relation_ref": relation_by_atom["mechanism_atom"],
            "evidence_uses": row["evidence_uses"][2:3],
            "numeric_refs": [],
            "numeric_relation_refs": [],
            "qualitative_fact_refs": [],
            "method_step_refs": [],
            "graph_edge_refs": [],
            "inference_authority": row["inference_authority"],
            "mechanism_atom": row["mechanism_atom"],
        },
        SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL: {
            "cell_id": row["cell_id"],
            "claim_relation_ref": relation_by_atom["counterargument_atom"],
            "evidence_uses": row["evidence_uses"][3:],
            "numeric_refs": [],
            "numeric_relation_refs": list(row["numeric_relation_refs"]),
            "qualitative_fact_refs": [],
            "method_step_refs": [],
            "graph_edge_refs": [],
            "inference_authority": row["inference_authority"],
            "counterargument_atom": row["counterargument_atom"],
            "what_would_change": {
                **row["what_would_change"],
                "threshold_numeric_ref": "",
            },
        },
    }


def test_micro_judgment_loop_keeps_model_authorship_and_compiles_terminal_cell(
    contracts,
) -> None:
    base_policy, research_input, kernel, route, planning = contracts
    claim_input = compile_claim_authority_research_input(
        research_input,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    alias_input = compile_claim_surface_authority_research_input(
        claim_input,
        policy=_json(CLAIM_RELATION_ALIAS_POLICY),
    )
    cell_id = "CELL::value_capture"
    scoped = scope_bounded_finance_micro_judgment_policy(
        base_policy,
        micro_policy=load_fixed_pack_micro_judgment_policy(
            _json(MICRO_POLICY)
        ),
        cell_count=1,
        maximum_evidence_requests=0,
    )
    tools = compile_finance_micro_judgment_tools(
        research_input=alias_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    names = [row["function"]["name"] for row in tools]
    assert names == [
        READ_REVIEWED_EVIDENCE_TOOL,
        READ_NUMERIC_FACTS_TOOL,
        *MICRO_JUDGMENT_TOOL_NAMES,
    ]
    assert SUBMIT_RESEARCH_JUDGMENT_TOOL not in names
    thesis_schema = next(
        row["function"]["parameters"]
        for row in tools
        if row["function"]["name"] == SUBMIT_RESEARCH_THESIS_TOOL
    )
    mechanism_schema = next(
        row["function"]["parameters"]
        for row in tools
        if row["function"]["name"] == SUBMIT_RESEARCH_MECHANISM_TOOL
    )
    counter_schema = next(
        row["function"]["parameters"]
        for row in tools
        if row["function"]["name"]
        == SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
    )
    assert "thesis_atom" in thesis_schema["properties"]
    assert "mechanism_atom" not in thesis_schema["properties"]
    assert set(mechanism_schema["properties"]).isdisjoint(
        {"thesis_atom", "counterargument_atom", "what_would_change"}
    )
    assert "inference_authority" in mechanism_schema["properties"]
    assert "counterargument_atom" in counter_schema["properties"]
    assert "inference_authority" in counter_schema["properties"]
    assert "what_would_change" in counter_schema["properties"]

    fragments = _micro_alias_fragments()
    observed_active_tools: list[list[str]] = []

    def execute(_messages, active_tools, index):
        active_names = [row["function"]["name"] for row in active_tools]
        observed_active_tools.append(active_names)
        if index == 1:
            return _parallel_step(
                index,
                [
                    (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                    (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
                ],
            )
        name = MICRO_JUDGMENT_TOOL_NAMES[index - 2]
        return _step(index, name, fragments[name])

    result = run_bounded_finance_loop(
        policy=scoped,
        research_input=alias_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=execute,
        visible_execution_budget={
            "maximum_steps": scoped.maximum_steps,
            "maximum_evidence_requests": 0,
            "maximum_reads_per_cell": 1,
            "maximum_parallel_read_tools": 2,
            "maximum_judgments_per_cell": 1,
            "retry_count": 0,
        },
    )
    assert observed_active_tools == [
        [READ_REVIEWED_EVIDENCE_TOOL, READ_NUMERIC_FACTS_TOOL],
        [SUBMIT_RESEARCH_THESIS_TOOL],
        [SUBMIT_RESEARCH_MECHANISM_TOOL],
        [SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL],
    ]
    assert result.status == "completed_all_required_cells"
    assert result.step_count == 4
    assert result.tool_call_count == 5
    assert result.tool_counts == {
        READ_REVIEWED_EVIDENCE_TOOL: 1,
        READ_NUMERIC_FACTS_TOOL: 1,
        SUBMIT_RESEARCH_THESIS_TOOL: 1,
        SUBMIT_RESEARCH_MECHANISM_TOOL: 1,
        SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL: 1,
    }
    cell = result.structured_deliverable["cells"][0]
    assert cell["thesis_atom"] == fragments[SUBMIT_RESEARCH_THESIS_TOOL][
        "thesis_atom"
    ]
    assert cell["mechanism_atom"] == fragments[
        SUBMIT_RESEARCH_MECHANISM_TOOL
    ]["mechanism_atom"]
    assert cell["counterargument_atom"] == fragments[
        SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
    ]["counterargument_atom"]
    assert all(
        "claim_subject" in relation and "claim_relation_ref" in relation
        for relation in cell["claim_relations"]
    )
    assert {
        relation["atom_field"]: relation["inference_authority"]
        for relation in cell["claim_relations"]
    } == {
        "thesis_atom": fragments[SUBMIT_RESEARCH_THESIS_TOOL][
            "inference_authority"
        ],
        "mechanism_atom": fragments[SUBMIT_RESEARCH_MECHANISM_TOOL][
            "inference_authority"
        ],
        "counterargument_atom": fragments[
            SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
        ]["inference_authority"],
    }
    assert all(
        receipt["private_reasoning_persisted"] is False
        for receipt in result.step_receipts
    )


def test_micro_fragment_projection_is_authority_complete_without_selecting_answer(
    contracts,
) -> None:
    _, research_input, _, _, _ = contracts
    claim_input = compile_claim_authority_research_input(
        research_input,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    alias_input = compile_claim_surface_authority_research_input(
        claim_input,
        policy=_json(CLAIM_RELATION_ALIAS_POLICY),
    )
    context = compile_finance_micro_fragment_context(
        research_input=alias_input,
        cell_id="CELL::value_capture",
        tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
    )

    assert context["projection_manifest"] == {
        "candidate_claim_relation_refs": [
            "CR::DELL::MULTI_DRIVER_CONTEXT",
            "CR::DELL::PRODUCT_TARGET",
        ],
        "evidence_refs": [
            "EV::0063F22F643B94ED",
            "EV::7F4D7E6762C21D83",
        ],
        "numeric_refs": [],
        "numeric_relation_refs": [],
        "qualitative_fact_refs": [
            "QF::DELL::AI_SERVER_OPERATING_INCOME_RATE_TARGET::FY2027Q1"
        ],
        "gap_refs": [],
        "method_step_refs": [
            "METHOD::VC::CAUSAL_BOUNDARY",
            "METHOD::VC::COUNTERREAD",
            "METHOD::VC::MATERIAL_GAP_ROUTE",
            "METHOD::VC::PERIOD_BASIS",
            "METHOD::VC::PRODUCT_FINANCIAL_BRIDGE",
            "METHOD::VC::WHAT_WOULD_CHANGE",
        ],
        "graph_edge_refs": ["GRAPH::2B17375548682087"],
        "expected_prior_fragment_tools": [],
        "accepted_prior_fragment_digests": [],
        "projection_selects_answer": False,
        "all_legal_relation_options_preserved": True,
    }
    assert {
        row["evidence_ref"] for row in context["reviewed_evidence"]
    } == {"EV::0063F22F643B94ED", "EV::7F4D7E6762C21D83"}
    assert context["authoritative_numeric_facts"] == []
    assert context["same_basis_numeric_relations"] == []
    assert context == compile_finance_micro_fragment_context(
        research_input=alias_input,
        cell_id="CELL::value_capture",
        tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
    )

    analysis_messages = compile_finance_micro_fragment_analysis_messages(context)
    submission_messages = compile_finance_micro_fragment_submission_messages(
        fragment_context=context,
        analysis_draft="选择受约束的多因素判断，并明确产品到公司利润桥尚未建立。",
    )
    assert len(analysis_messages) == 2
    assert len(submission_messages) == 2
    assert "analysis_draft_is_untrusted_model_data" in submission_messages[1][
        "content"
    ]
    assert "EV::5388E016C17032C1" not in analysis_messages[1]["content"]

    fragment = _micro_alias_fragments()[SUBMIT_RESEARCH_THESIS_TOOL]
    validated = validate_finance_micro_judgment_fragment(
        tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
        arguments=fragment,
        research_input=alias_input,
        cell_id="CELL::value_capture",
    )
    assert validated["thesis_atom"] == fragment["thesis_atom"]


def test_micro_fragment_projection_extends_through_mechanism_and_counter_wwc(
    contracts,
) -> None:
    _, research_input, _, _, _ = contracts
    claim_input = compile_claim_authority_research_input(
        research_input,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    alias_input = compile_claim_surface_authority_research_input(
        claim_input,
        policy=_json(CLAIM_RELATION_ALIAS_POLICY),
    )
    fragments = _micro_alias_fragments()
    thesis = validate_finance_micro_judgment_fragment(
        tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
        arguments=fragments[SUBMIT_RESEARCH_THESIS_TOOL],
        research_input=alias_input,
        cell_id="CELL::value_capture",
    )
    mechanism_context = compile_finance_micro_fragment_context(
        research_input=alias_input,
        cell_id="CELL::value_capture",
        tool_name=SUBMIT_RESEARCH_MECHANISM_TOOL,
        accepted_fragments={SUBMIT_RESEARCH_THESIS_TOOL: thesis},
    )
    mechanism_manifest = mechanism_context["projection_manifest"]
    assert mechanism_manifest["expected_prior_fragment_tools"] == [
        SUBMIT_RESEARCH_THESIS_TOOL
    ]
    assert mechanism_manifest["accepted_prior_fragment_digests"] == [
        canonical_digest(thesis)
    ]
    assert len(mechanism_manifest["candidate_claim_relation_refs"]) == 4
    assert len(mechanism_context["same_basis_numeric_relations"]) == 1
    assert len(mechanism_context["authoritative_numeric_facts"]) == 2
    assert len(mechanism_context["source_bound_qualitative_facts"]) == 1
    assert len(mechanism_context["typed_residual_gaps"]) == 3
    mechanism_analysis = compile_finance_micro_fragment_analysis_messages(
        mechanism_context
    )
    assert "不得重复 thesis" in mechanism_analysis[0]["content"]
    mechanism_submission = compile_finance_micro_fragment_submission_messages(
        fragment_context=mechanism_context,
        analysis_draft="公司毛利变化是可观察事实，但当前资料未建立产品到公司利润桥。",
    )
    assert SUBMIT_RESEARCH_MECHANISM_TOOL in mechanism_submission[1][
        "content"
    ]
    mechanism = validate_finance_micro_judgment_fragment(
        tool_name=SUBMIT_RESEARCH_MECHANISM_TOOL,
        arguments=fragments[SUBMIT_RESEARCH_MECHANISM_TOOL],
        research_input=alias_input,
        cell_id="CELL::value_capture",
        thesis_fragment=thesis,
    )

    counter_context = compile_finance_micro_fragment_context(
        research_input=alias_input,
        cell_id="CELL::value_capture",
        tool_name=SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
        accepted_fragments={
            SUBMIT_RESEARCH_THESIS_TOOL: thesis,
            SUBMIT_RESEARCH_MECHANISM_TOOL: mechanism,
        },
    )
    counter_manifest = counter_context["projection_manifest"]
    assert counter_manifest["expected_prior_fragment_tools"] == [
        SUBMIT_RESEARCH_THESIS_TOOL,
        SUBMIT_RESEARCH_MECHANISM_TOOL,
    ]
    assert counter_manifest["accepted_prior_fragment_digests"] == [
        canonical_digest(thesis),
        canonical_digest(mechanism),
    ]
    assert len(counter_manifest["candidate_claim_relation_refs"]) == 3
    assert len(counter_context["same_basis_numeric_relations"]) == 1
    assert len(counter_context["authoritative_numeric_facts"]) == 2
    assert counter_context["source_bound_qualitative_facts"] == []
    assert len(counter_context["typed_residual_gaps"]) == 3
    counter_analysis = compile_finance_micro_fragment_analysis_messages(
        counter_context
    )
    assert "What-Would-Change" in counter_analysis[0]["content"]
    counter_submission = compile_finance_micro_fragment_submission_messages(
        fragment_context=counter_context,
        analysis_draft="最强反方是多因素共同作用；需要可审计的产品利润桥才会改变判断。",
    )
    assert SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL in counter_submission[1][
        "content"
    ]
    counter = validate_finance_micro_judgment_fragment(
        tool_name=SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
        arguments=fragments[SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL],
        research_input=alias_input,
        cell_id="CELL::value_capture",
        thesis_fragment=thesis,
    )
    assert counter["what_would_change"] == fragments[
        SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL
    ]["what_would_change"]


def test_micro_fragments_allow_direct_thesis_with_bounded_or_abstaining_followups(
    contracts,
) -> None:
    base_policy, research_input, kernel, route, planning = contracts
    claim_input = compile_claim_authority_research_input(
        research_input,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    alias_input = compile_claim_surface_authority_research_input(
        claim_input,
        policy=_json(CLAIM_RELATION_ALIAS_POLICY),
    )
    fragments = _micro_alias_fragments()
    thesis = fragments[SUBMIT_RESEARCH_THESIS_TOOL]
    thesis["inference_authority"] = "directly_supported"

    mechanism = fragments[SUBMIT_RESEARCH_MECHANISM_TOOL]
    mechanism.update(
        {
            "claim_relation_ref": "CR::DELL::PROFIT_BRIDGE_GAP",
            "evidence_uses": [],
            "numeric_refs": [],
            "numeric_relation_refs": [],
            "qualitative_fact_refs": [],
            "method_step_refs": [],
            "graph_edge_refs": [],
            "inference_authority": "not_inferable",
            "mechanism_atom": (
                "当前资料没有建立人工智能服务器产品到分部或公司的利润桥。"
            ),
        }
    )

    counter = fragments[SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL]
    counter.update(
        {
            "evidence_uses": [],
            "inference_authority": "bounded_inference",
            "counterargument_atom": (
                "公司毛利率变化只支持同口径观察，不能据此把利润变化归因于"
                "人工智能服务器。"
            ),
        }
    )

    scoped = scope_bounded_finance_micro_judgment_policy(
        base_policy,
        micro_policy=load_fixed_pack_micro_judgment_policy(_json(MICRO_POLICY)),
        cell_count=1,
        maximum_evidence_requests=0,
    )
    tools = compile_finance_micro_judgment_tools(
        research_input=alias_input,
        required_cell_ids=["CELL::value_capture"],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    sequence = [
        _parallel_step(
            1,
            [
                (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": "CELL::value_capture"}),
                (READ_NUMERIC_FACTS_TOOL, {"cell_id": "CELL::value_capture"}),
            ],
        ),
        *[
            _step(index + 2, name, fragments[name])
            for index, name in enumerate(MICRO_JUDGMENT_TOOL_NAMES)
        ],
    ]
    result = run_bounded_finance_loop(
        policy=scoped,
        research_input=alias_input,
        required_cell_ids=["CELL::value_capture"],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=lambda _messages, _tools, index: sequence[index - 1],
        visible_execution_budget={
            "maximum_steps": scoped.maximum_steps,
            "maximum_evidence_requests": 0,
            "maximum_reads_per_cell": 1,
            "maximum_parallel_read_tools": 2,
            "maximum_judgments_per_cell": 1,
            "retry_count": 0,
        },
    )
    assert result.status == "completed_all_required_cells"
    assert {
        row["atom_field"]: row["inference_authority"]
        for row in result.structured_deliverable["cells"][0]["claim_relations"]
    } == {
        "thesis_atom": "directly_supported",
        "mechanism_atom": "not_inferable",
        "counterargument_atom": "bounded_inference",
    }


def test_micro_fragment_projection_fails_closed_on_scope_and_prior_mutation(
    contracts,
) -> None:
    _, research_input, _, _, _ = contracts
    claim_input = compile_claim_authority_research_input(
        research_input,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    alias_input = compile_claim_surface_authority_research_input(
        claim_input,
        policy=_json(CLAIM_RELATION_ALIAS_POLICY),
    )
    contaminated = deepcopy(alias_input)
    cell = next(
        row
        for row in contaminated["cells"]
        if row["cell_id"] == "CELL::value_capture"
    )
    cell["claim_relation_card"]["allowed_combinations"][0][
        "required_evidence_refs"
    ].append("EV::734A9C177164E08E")
    with pytest.raises(
        BoundedFinanceLoopError,
        match="finance_loop_fragment_authority_out_of_scope",
    ):
        compile_finance_micro_fragment_context(
            research_input=contaminated,
            cell_id="CELL::value_capture",
            tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
        )

    wrong_case = deepcopy(alias_input)
    cell = next(
        row
        for row in wrong_case["cells"]
        if row["cell_id"] == "CELL::value_capture"
    )
    cell["claim_relation_card"]["case_key"] = "MU"
    with pytest.raises(
        BoundedFinanceLoopError,
        match="finance_loop_fragment_relation_scope_invalid",
    ):
        compile_finance_micro_fragment_context(
            research_input=wrong_case,
            cell_id="CELL::value_capture",
            tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
        )

    with pytest.raises(
        BoundedFinanceLoopError,
        match="finance_loop_fragment_prior_context_invalid",
    ):
        compile_finance_micro_fragment_context(
            research_input=alias_input,
            cell_id="CELL::value_capture",
            tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
            accepted_fragments={
                SUBMIT_RESEARCH_THESIS_TOOL: _micro_alias_fragments()[
                    SUBMIT_RESEARCH_THESIS_TOOL
                ]
            },
        )

    fragments = _micro_alias_fragments()
    thesis = validate_finance_micro_judgment_fragment(
        tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
        arguments=fragments[SUBMIT_RESEARCH_THESIS_TOOL],
        research_input=alias_input,
        cell_id="CELL::value_capture",
    )
    with pytest.raises(
        BoundedFinanceLoopError,
        match="finance_loop_fragment_prior_context_invalid",
    ):
        compile_finance_micro_fragment_context(
            research_input=alias_input,
            cell_id="CELL::value_capture",
            tool_name=SUBMIT_RESEARCH_COUNTERARGUMENT_WWC_TOOL,
            accepted_fragments={SUBMIT_RESEARCH_THESIS_TOOL: thesis},
        )

    contaminated_thesis = deepcopy(thesis)
    contaminated_thesis["cell_id"] = "CELL::cash_conversion"
    with pytest.raises(
        BoundedFinanceLoopError,
        match="finance_loop_micro_fragment_fields_invalid",
    ):
        compile_finance_micro_fragment_context(
            research_input=alias_input,
            cell_id="CELL::value_capture",
            tool_name=SUBMIT_RESEARCH_MECHANISM_TOOL,
            accepted_fragments={
                SUBMIT_RESEARCH_THESIS_TOOL: contaminated_thesis
            },
        )


@pytest.mark.parametrize(
    ("case_key", "legal_name"),
    (("MU", "Micron Technology, Inc."), ("NVDA", "NVIDIA Corporation")),
)
def test_micro_fragment_projection_has_no_dell_case_hardcoding(
    contracts,
    case_key: str,
    legal_name: str,
) -> None:
    _, research_input, _, _, _ = contracts
    claim_input = compile_claim_authority_research_input(
        research_input,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    alias_input = compile_claim_surface_authority_research_input(
        claim_input,
        policy=_json(CLAIM_RELATION_ALIAS_POLICY),
    )
    serialized = json.dumps(alias_input, ensure_ascii=False)
    serialized = serialized.replace("Dell Technologies Inc.", legal_name)
    serialized = serialized.replace("DELL", case_key).replace("Dell", case_key)
    cloned = json.loads(serialized)
    context = compile_finance_micro_fragment_context(
        research_input=cloned,
        cell_id="CELL::value_capture",
        tool_name=SUBMIT_RESEARCH_THESIS_TOOL,
    )
    assert context["case_identity"]["case_key"] == case_key
    assert all(
        ref.startswith(f"CR::{case_key}::")
        for ref in context["projection_manifest"][
            "candidate_claim_relation_refs"
        ]
    )
    assert "CR::DELL::" not in json.dumps(context, ensure_ascii=False)


def test_micro_judgment_fragments_fail_closed_on_order_authority_and_causality(
    contracts,
) -> None:
    base_policy, research_input, kernel, route, planning = contracts
    claim_input = compile_claim_authority_research_input(
        research_input,
        policy=_json(CLAIM_AUTHORITY_POLICY),
    )
    alias_input = compile_claim_surface_authority_research_input(
        claim_input,
        policy=_json(CLAIM_RELATION_ALIAS_POLICY),
    )
    cell_id = "CELL::value_capture"
    scoped = scope_bounded_finance_micro_judgment_policy(
        base_policy,
        micro_policy=load_fixed_pack_micro_judgment_policy(
            _json(MICRO_POLICY)
        ),
        cell_count=1,
        maximum_evidence_requests=0,
    )
    tools = compile_finance_micro_judgment_tools(
        research_input=alias_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    reads = _parallel_step(
        1,
        [
            (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
            (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
        ],
    )
    fragments = _micro_alias_fragments()

    with pytest.raises(
        BoundedFinanceLoopError,
        match="finance_loop_micro_judgment_order_invalid",
    ):
        run_bounded_finance_loop(
            policy=scoped,
            research_input=alias_input,
            required_cell_ids=[cell_id],
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
            tools=tools,
            step_executor=lambda _messages, _tools, index: (
                reads
                if index == 1
                else _step(
                    index,
                    SUBMIT_RESEARCH_MECHANISM_TOOL,
                    fragments[SUBMIT_RESEARCH_MECHANISM_TOOL],
                )
            ),
        )

    missing_support = deepcopy(fragments)
    missing_support[SUBMIT_RESEARCH_THESIS_TOOL]["evidence_uses"] = []
    with pytest.raises(
        BoundedFinanceLoopError,
        match="finance_loop_micro_required_authority_missing",
    ):
        run_bounded_finance_loop(
            policy=scoped,
            research_input=alias_input,
            required_cell_ids=[cell_id],
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
            tools=tools,
            step_executor=lambda _messages, _tools, index: (
                reads
                if index == 1
                else _step(
                    index,
                    MICRO_JUDGMENT_TOOL_NAMES[index - 2],
                    missing_support[MICRO_JUDGMENT_TOOL_NAMES[index - 2]],
                )
            ),
        )

    causal = deepcopy(fragments)
    causal[SUBMIT_RESEARCH_MECHANISM_TOOL]["mechanism_atom"] = (
        "AI servers drove Dell company profit through direct operating leverage."
    )
    sequence = [
        reads,
        *[
            _step(index + 2, name, causal[name])
            for index, name in enumerate(MICRO_JUDGMENT_TOOL_NAMES)
        ],
    ]
    with pytest.raises(
        BoundedFinanceLoopError,
        match="claim_surface_narrative_relation_conflict",
    ):
        run_bounded_finance_loop(
            policy=scoped,
            research_input=alias_input,
            required_cell_ids=[cell_id],
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
            tools=tools,
            step_executor=lambda _messages, _tools, index: sequence[index - 1],
        )


def _case_specific_plan(
    *,
    case_key: str,
    kernel,
    planning,
) -> tuple[dict[str, object], dict[str, object]]:
    objective = _json(OBJECTIVE)
    objective["case_key"] = case_key
    objective["raw_question"] = (
        f"{case_key} 的核心需求、利润和现金转换是否可持续，"
        "哪些供应约束和反方证据会改变判断？"
    )
    compiled = compile_research_objective(
        objective,
        kernel=kernel,
        policy=planning,
    )
    atoms = _json(ATOMS)
    atoms["objective_id"] = compiled.objective_id
    subject = kernel.cases[case_key].subject_ticker
    product_intents = {
        "orders_and_backlog": [
            f"{subject} demand signals",
            "backlog composition",
            "customer concentration",
        ],
        "conversion_and_durability": [
            "order conversion",
            "channel inventory risk",
            "demand durability",
        ],
        "reported_results": [
            "current product revenue contribution",
            "segment profitability",
            "earnings contribution",
        ],
        "guidance_and_outlook": [
            "margin guidance",
            "supply constraint outlook",
        ],
        "pricing_and_mix": ["pricing trend", "product mix shift"],
        "margin_and_incremental_profit": [
            "incremental product margin",
            "operating leverage",
        ],
        "cash_generation": ["cash conversion", "capacity investment"],
        "working_capital_risk": [
            "component inventory buildup",
            "customer receivable risk",
        ],
        "issuer_counterevidence": [
            "management demand caution",
            "inventory impairment risk",
        ],
        "upstream_or_demand_counterevidence": [
            "upstream supply constraints",
            "end demand slowdown",
        ],
    }
    for atom in atoms["atoms"]:
        atom["target_entity"] = subject
        atom["product_intents"] = product_intents[atom["facet_id"]]
    return objective, atoms


def _synthetic_context_judgment(
    research_input: dict[str, object],
    cell_id: str,
) -> dict[str, object]:
    cell = next(row for row in research_input["cells"] if row["cell_id"] == cell_id)
    evidence_refs = list(cell["allowed_evidence_refs"])
    gap_refs = list(cell["visible_gap_refs"])
    assert evidence_refs or gap_refs
    if evidence_refs and gap_refs:
        status = "mixed"
        inference = "bounded_inference"
        confidence = "mixed_source_strength"
    elif evidence_refs:
        status = "supported"
        inference = "directly_supported"
        confidence = "direct_source_only"
    else:
        status = "insufficient_evidence"
        inference = "not_inferable"
        confidence = "gap_dominated"
    method_pack = cell.get("role_method_pack") or {}
    method_minimum = int(cell["context_consumption_contract"]["minimum_method_step_refs"])
    graph_minimum = int(cell["context_consumption_contract"]["minimum_graph_edge_refs"])
    return {
        "cell_id": cell_id,
        "judgment_status": status,
        "confidence_basis": confidence,
        "inference_authority": inference,
        "evidence_uses": (
            [{"evidence_ref": evidence_refs[0], "use_role": "support"}]
            if evidence_refs
            else []
        ),
        "numeric_refs": [],
        "numeric_relation_refs": [],
        "method_step_refs": [
            row["method_step_ref"]
            for row in method_pack.get("method_steps", [])[:method_minimum]
        ],
        "graph_edge_refs": [
            row["graph_edge_ref"]
            for row in cell["graph_context_pack"]["edges"][:graph_minimum]
        ],
        "thesis_atom": "当前研究单元有已审资料支持，但结论仍受已登记证据边界约束。",
        "mechanism_atom": "经营表现、产品组合与供需条件共同作用，单一现象不能独立证明因果。",
        "counterargument_atom": "替代业务、时点差异与尚未补齐的资料可能解释当前观察。",
        "what_would_change": {
            "observable": "后续正式披露补齐当前关键证据缺口",
            "direction": "resolve_gap" if gap_refs else "persist",
            "time_horizon": "后续连续披露期",
            "evidence_route": "公司正式披露与已审证据复核",
            "threshold_numeric_ref": None,
        },
    }


def test_tool_compiler_emits_four_closed_finance_schemas(contracts) -> None:
    policy, research_input, kernel, route, _ = contracts
    cell_id = "CELL::demand_quality"
    standard = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=False,
    )
    strict = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=True,
    )

    assert [row["function"]["name"] for row in standard] == [
        READ_REVIEWED_EVIDENCE_TOOL,
        READ_NUMERIC_FACTS_TOOL,
        SUBMIT_EVIDENCE_REQUEST_TOOL,
        SUBMIT_RESEARCH_JUDGMENT_TOOL,
    ]
    assert all("strict" not in row["function"] for row in standard)
    assert all(row["function"]["strict"] is True for row in strict)

    def closed_objects(value: object) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value["additionalProperties"] is False
                assert set(value["required"]) == set(value["properties"])
            for child in value.values():
                closed_objects(child)
        elif isinstance(value, list):
            for child in value:
                closed_objects(child)

    for row in strict:
        closed_objects(row["function"]["parameters"])
    judgment = next(
        row
        for row in strict
        if row["function"]["name"] == SUBMIT_RESEARCH_JUDGMENT_TOOL
    )
    assert judgment["function"]["parameters"]["properties"]["numeric_refs"][
        "items"
    ]["pattern"] == "^$"
    assert len(compile_finance_loop_messages(
        research_input=research_input,
        required_cell_ids=[cell_id],
    )[1]["content"]) < 6500
    budgeted = compile_finance_loop_messages(
        research_input=research_input,
        required_cell_ids=[cell_id],
        execution_budget={
            "maximum_steps": 6,
            "maximum_evidence_requests": 3,
            "maximum_reads_per_cell": 1,
            "maximum_parallel_read_tools": 2,
            "maximum_judgments_per_cell": 1,
            "retry_count": 0,
        },
    )
    assert '"maximum_steps":6' in budgeted[1]["content"]
    assert '"retry_count":0' in budgeted[1]["content"]


def test_three_case_contract_projection_preserves_identity_and_wire_equivalence(
    contracts,
) -> None:
    policy, dell_input, kernel, route, _ = contracts
    cell_id = "CELL::value_capture"
    subjects = {"DELL": "DELL", "MU": "MU", "NVDA": "NVDA"}

    for case_key, subject_ticker in subjects.items():
        research_input = deepcopy(dell_input)
        research_input["case_identity"]["case_key"] = case_key
        research_input["case_identity"]["subject_ticker"] = subject_ticker
        chat_tools = compile_finance_loop_tools(
            research_input=research_input,
            required_cell_ids=[cell_id],
            kernel=kernel,
            route_policy=route,
            policy=policy,
            strict=False,
        )
        canonical = canonicalize_tool_definitions(
            chat_tools, wire_api=CHAT_COMPLETIONS_WIRE
        )
        for wire_api in (
            CHAT_COMPLETIONS_WIRE,
            RESPONSES_WIRE,
            ANTHROPIC_MESSAGES_WIRE,
        ):
            projected = project_tool_definitions(
                canonical, wire_api=wire_api
            )
            assert canonicalize_tool_definitions(
                projected, wire_api=wire_api
            ) == canonical

        proposal = next(
            row
            for row in canonical
            if row["name"] == SUBMIT_EVIDENCE_REQUEST_TOOL
        )
        branches = proposal["input_schema"]["oneOf"]
        pricing = next(
            row
            for row in branches
            if row["properties"]["requested_facet_id"].get("const")
            == "pricing_and_mix"
        )
        assert pricing["properties"]["target_entity"]["enum"] == [
            subject_ticker
        ]


def test_three_case_current_context_full_fake_has_no_identity_or_graph_pollution(
    contracts,
) -> None:
    base_policy, _, kernel, route, planning = contracts
    paths = resolve_runtime_paths(ROOT)
    kernel_payload = read_registered_runtime_json(
        ROOT, "application.config.current_financial_research_kernel"
    )
    route_payload = read_registered_runtime_json(
        ROOT, "application.config.current_query_object_fact_route_policy"
    )
    planning_payload = read_registered_runtime_json(
        ROOT, "application.config.current_research_planning_policy"
    )
    evidence_config = read_registered_runtime_json(
        ROOT, "application.config.current_research_evidence_pack_projection"
    )
    evidence_service = ResearchEvidencePackService(
        config=evidence_config,
        result=read_registered_runtime_json(
            ROOT, str(evidence_config["source_result_resource_id"])
        ),
        private_object_root=(
            paths.reviewed_evidence_root
            / str(evidence_config["private_object_root_relative"])
        ),
        private_root_base=paths.reviewed_evidence_root,
    )
    retrieval = ResearchRetrievalService(
        snapshot=read_registered_runtime_json(
            ROOT, "application.result.current_research_retrieval_snapshot"
        ),
        ranking_comparison=read_registered_runtime_json(
            ROOT, "application.result.current_s1c_ranking_comparison_projection"
        ),
        kernel=kernel_payload,
        route_policy=route_payload,
        planning_policy=planning_payload,
        hybrid_candidate_runtime=None,
        company_financial_fact_mart_path=paths.company_financial_fact_mart_path,
    )
    read = frozenset({"current_product:read"})
    value_graph_refs: dict[str, set[str]] = {}

    for case_key in ("DELL", "MU", "NVDA"):
        objective, atoms = _case_specific_plan(
            case_key=case_key,
            kernel=kernel,
            planning=planning,
        )
        pack = evidence_service.get_case(
            case_key,
            ResearchEvidencePackPrincipal("current", read),
        )
        controlled = retrieval.execute_controlled_plan(
            case_key,
            objective,
            atoms,
            ResearchRetrievalPrincipal("current", read),
        )
        research_input = compile_current_research_input(
            policy=_json(CONSUMER_POLICY),
            evidence_pack=pack,
            controlled_plan=controlled,
        )
        subject = kernel.cases[case_key].subject_ticker
        assert research_input["case_identity"]["case_key"] == case_key
        assert research_input["case_identity"]["subject_ticker"] == subject
        assert all(
            relation["ticker"] == subject
            for relation in research_input["numeric_relation_cards"]
        )
        assert research_input["research_context_receipts"]["compression"] == {
            "method_steps_omitted_after_selection": 0,
            "archived_skill_or_graph_rows_loaded": 0,
            "only_cell_local_current_context_retained": True,
        }
        value_cell = next(
            row
            for row in research_input["cells"]
            if row["cell_id"] == "CELL::value_capture"
        )
        assert value_cell["role_method_pack"]["pack_id"] == (
            "ROLE_METHOD::VALUE_CAPTURE::V1"
        )
        assert value_cell["graph_context_pack"]["case_key"] == case_key
        assert {row["entity_id"] for row in value_cell["graph_context_pack"]["nodes"]} == {
            subject
        }
        assert value_cell["graph_context_pack"]["authority"][
            "archived_graph_rows_used"
        ] is False
        value_graph_refs[case_key] = {
            row["graph_edge_ref"]
            for row in value_cell["graph_context_pack"]["edges"]
        }
        assert all(
            route["source_class"] != "commercial_or_industry_data"
            for decision in research_input["evidence_request_route_catalog"][
                "gap_route_decisions"
            ]
            for route in decision["available_source_routes"]
        )

        cell_ids = [str(row["cell_id"]) for row in research_input["cells"]]
        scoped = scope_bounded_finance_loop_policy(
            base_policy,
            cell_count=len(cell_ids),
            maximum_evidence_requests=0,
        )
        tools = compile_finance_loop_tools(
            research_input=research_input,
            required_cell_ids=cell_ids,
            kernel=kernel,
            route_policy=route,
            policy=scoped,
            strict=False,
        )
        result = run_bounded_finance_loop(
            policy=scoped,
            research_input=research_input,
            required_cell_ids=cell_ids,
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
            tools=tools,
            step_executor=lambda _messages, _tools, index: (
                _parallel_step(
                    index,
                    [
                        (
                            READ_REVIEWED_EVIDENCE_TOOL,
                            {"cell_id": cell_ids[(index - 1) // 2]},
                        ),
                        (
                            READ_NUMERIC_FACTS_TOOL,
                            {"cell_id": cell_ids[(index - 1) // 2]},
                        ),
                    ],
                )
                if index % 2 == 1
                else _step(
                    index,
                    SUBMIT_RESEARCH_JUDGMENT_TOOL,
                    _synthetic_context_judgment(
                        research_input,
                        cell_ids[(index - 1) // 2],
                    ),
                )
            ),
        )
        assert result.status == "completed_all_required_cells"
        assert result.tool_call_count == 15
        assert result.structured_deliverable["case_identity"]["case_key"] == case_key
        assert all(
            cell["context_consumption_receipt"]["graph_context_digest"]
            for cell in result.structured_deliverable["cells"]
        )

    assert value_graph_refs["DELL"].isdisjoint(value_graph_refs["MU"])
    assert value_graph_refs["DELL"].isdisjoint(value_graph_refs["NVDA"])
    assert value_graph_refs["MU"].isdisjoint(value_graph_refs["NVDA"])


def test_zero_call_runner_materializes_three_case_result_digests() -> None:
    runner = _zero_call_runner()
    result = runner._three_case_context_matrix(
        paths={
            "consumer_policy_ref": CONSUMER_POLICY,
            "objective_ref": OBJECTIVE,
            "planner_atoms_ref": ATOMS,
        },
        base_policy=load_bounded_finance_loop_policy(_json(POLICY)),
    )

    assert result["all_three_full_fake_pass"] is True
    assert result["case_identity_pollution_count"] == 0
    assert result["graph_context_pollution_count"] == 0
    assert all(
        row["full_fake_result_digest"] and row["full_fake_tool_calls"] == 15
        for row in result["cases"].values()
    )


def test_zero_call_runner_replays_r2_as_micro_judgments(contracts) -> None:
    runner = _zero_call_runner()
    base_policy, research_input, kernel, route, planning = contracts
    paths = {
        "consumer_policy_ref": CONSUMER_POLICY,
        "objective_ref": OBJECTIVE,
        "planner_atoms_ref": ATOMS,
        "claim_authority_policy_ref": CLAIM_AUTHORITY_POLICY,
        "claim_surface_authority_policy_ref": CLAIM_RELATION_ALIAS_POLICY,
        "micro_policy_ref": MICRO_POLICY,
        "micro_read_profile_ref": ROOT
        / "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_micro_read_profile_v1_0.json",
        "micro_judgment_profile_ref": ROOT
        / "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_micro_judgment_profile_v1_0.json",
        "corrected_fake_output_ref": CLAIM_RELATION_ALIAS_FAKE,
        "prior_live_result_ref": ROOT
        / "configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_claim_relation_alias_chat_live_result_v1_0.json",
        "prior_capacity_assessment_ref": ROOT
        / "configs/research/evals/fin_ia_0_1_3_s3_dell_value_capture_fixed_pack_claim_relation_alias_chat_live_capacity_assessment_v1_0.json",
        "prior_step_two_request_ref": ROOT
        / ".codex_runtime/model_runs/fin_0_1_3_s3_fixed_pack_claim_relation_alias_chat_successor/FIN013-S3-DELL-VALUE-CAPTURE-FIXED-PACK-CLAIM-RELATION-ALIAS-CHAT-R2/STEP-02-ATTEMPT-01/model_visible_request.json",
        "prior_step_two_response_ref": ROOT
        / ".codex_runtime/model_runs/fin_0_1_3_s3_fixed_pack_claim_relation_alias_chat_successor/FIN013-S3-DELL-VALUE-CAPTURE-FIXED-PACK-CLAIM-RELATION-ALIAS-CHAT-R2/STEP-02-ATTEMPT-01/provider_response.json",
    }
    result = runner._run_micro_judgment_matrix(
        paths=paths,
        base_research_input=research_input,
        kernel=kernel,
        route=route,
        planning=planning,
        base_policy=base_policy,
    )

    assert result["step_count"] == 4
    assert result["tool_call_count"] == 5
    assert result["model_authored_narratives_preserved_exactly"] is True
    assert result["harness_generated_missing_claim_or_fragment"] is False
    assert result["private_reasoning_persisted"] is False
    assert result["largest_micro_to_prior_monolithic_ratio"] < 1
    assert result["node_profiles"] == {
        "mandatory_read_pair": {
            "reasoning_effort": "low",
            "max_tokens": 2000,
        },
        "micro_judgment": {
            "reasoning_effort": "high",
            "max_tokens": 8000,
        },
    }
    assert set(result["mutation_failure_codes"]) == {
        "wrong_fragment_order",
        "duplicate_fragment",
        "missing_fragment",
        "missing_required_authority",
        "unknown_or_cross_case_alias",
        "cross_fragment_evidence_role_conflict",
        "causal_overreach",
        "tool_schema_mutation",
    }
    assert set(result["cross_case_policy_rejection_codes"]) == {"MU", "NVDA"}


def test_chat_and_responses_lanes_share_one_finance_loop_core(contracts) -> None:
    base_policy, research_input, kernel, route, planning = contracts
    cell_id = "CELL::value_capture"
    policy = scope_bounded_finance_loop_policy(
        base_policy, cell_count=1, maximum_evidence_requests=3
    )
    profiles = [
        load_agent_transport_profile(
            _json(
                ROOT
                / "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_chat_control_transport_profile_v1_0.json"
            )
        ),
        load_agent_transport_profile(
            _json(
                ROOT
                / "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_responses_candidate_transport_profile_v1_0.json"
            )
        ),
    ]
    digests = []
    for profile in profiles:
        def transport(**kwargs):
            attempt_id = str(kwargs["attempt_id"])
            index = int(attempt_id.split("-")[-3])
            if index == 1:
                return _parallel_step(
                    index,
                    [
                        (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                        (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
                    ],
                )
            return _step(
                index,
                SUBMIT_RESEARCH_JUDGMENT_TOOL,
                _fake_judgment(cell_id),
            )

        lane = execute_finance_loop_transport_lane(
            lane=profile.wire_api,
            profile=profile,
            policy=policy,
            research_input=research_input,
            required_cell_ids=[cell_id],
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
            visible_execution_budget={
                "maximum_steps": policy.maximum_steps,
                "maximum_evidence_requests": 3,
                "maximum_reads_per_cell": 1,
                "maximum_parallel_read_tools": 2,
                "maximum_judgments_per_cell": 1,
                "retry_count": 0,
            },
            capture_root="unused",
            run_id=f"TEST-{profile.wire_api}",
            attempt_prefix="STEP",
            transport=transport,
        )
        assert lane.status == "completed_contract_valid_content_assessment_pending"
        assert lane.model_calls_attempted == 2
        digests.append(
            lane.loop_result["structured_deliverable"]["deliverable_digest"]
        )
    assert len(set(digests)) == 1


def test_policy_version_preserves_legacy_single_call_replay() -> None:
    current = load_bounded_finance_loop_policy(_json(POLICY))
    legacy = load_bounded_finance_loop_policy(
        _json(
            ROOT
            / "configs/research/"
            "fin_ia_0_1_3_s3_bounded_finance_agent_loop_policy_v1_0.json"
        )
    )
    assert current.maximum_parallel_tool_calls == 2
    assert legacy.maximum_parallel_tool_calls == 1

    invalid = deepcopy(_json(POLICY))
    invalid["budgets"]["maximum_parallel_tool_calls"] = 1
    with pytest.raises(
        BoundedFinanceLoopError,
        match="finance_loop_budgets_invalid",
    ):
        load_bounded_finance_loop_policy(invalid)


def test_single_cell_fake_loop_reads_submits_gap_and_judgment(contracts) -> None:
    policy, research_input, kernel, route, planning = contracts
    cell_id = "CELL::value_capture"
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=True,
    )
    gap_ref = next(
        row["gap_ref"]
        for row in research_input["residual_gap_cards"]
        if row["facet_id"] == "price_or_asp"
    )
    sequence = [
        (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
        (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
        (
            SUBMIT_EVIDENCE_REQUEST_TOOL,
            {
                "cell_id": cell_id,
                "gap_ref": gap_ref,
                "target_entity": "DELL",
                "requested_facet_id": "pricing_and_mix",
                "requested_source_class": "official_company_disclosure",
                "metric_intents": ["average_selling_price"],
                "product_intents": ["price and configuration mix evidence"],
            },
        ),
        (SUBMIT_RESEARCH_JUDGMENT_TOOL, _fake_judgment(cell_id)),
    ]
    observed_messages: list[list[dict[str, object]]] = []

    def executor(messages, _tools, step_index):
        observed_messages.append(deepcopy(list(messages)))
        name, arguments = sequence[step_index - 1]
        return _step(step_index, name, arguments)

    result = run_bounded_finance_loop(
        policy=policy,
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=executor,
    )
    payload = result.as_dict()

    assert result.status == "completed_all_required_cells"
    assert result.step_count == 4
    assert result.tool_call_count == 4
    assert result.proposed_evidence_requests[0]["gap_status"] == "open"
    assert result.proposed_evidence_requests[0]["retrieval_executed"] is False
    assert result.proposed_evidence_requests[0][
        "candidate_promoted_to_evidence"
    ] is False
    assert [row["cell_id"] for row in result.structured_deliverable["cells"]] == [
        cell_id
    ]
    assert "private-step" not in json.dumps(payload, ensure_ascii=False)
    assert observed_messages[1][-2]["reasoning_content"] == "private-step-1"
    assert all(row["private_reasoning_persisted"] is False for row in result.step_receipts)


def test_r2_invalid_proposal_is_rejected_without_execution_then_repaired(
    contracts,
) -> None:
    policy, research_input, kernel, route, planning = contracts
    cell_id = "CELL::value_capture"
    scoped = scope_bounded_finance_loop_policy(
        policy,
        cell_count=1,
        maximum_evidence_requests=3,
    )
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    proposal_schema = next(
        row["function"]["parameters"]
        for row in tools
        if row["function"]["name"] == SUBMIT_EVIDENCE_REQUEST_TOOL
    )
    assert proposal_schema["properties"]["product_intents"]["items"][
        "maxLength"
    ] == scoped.evidence_request_max_product_intent_chars
    pricing_branch = next(
        row
        for row in proposal_schema["oneOf"]
        if row["properties"]["requested_facet_id"].get("const")
        == "pricing_and_mix"
        and row["properties"]["requested_source_class"].get("const")
        == "official_company_disclosure"
        and row["properties"]["metric_intents"].get("items", {}).get("enum")
        == ["average_selling_price"]
    )
    allowed_metrics = pricing_branch["properties"]["metric_intents"]["items"][
        "enum"
    ]
    assert "average_selling_price" in allowed_metrics
    assert "shipments" not in allowed_metrics
    assert "commercial_or_industry_data" not in proposal_schema["properties"][
        "requested_source_class"
    ]["enum"]

    gap_ref = next(
        row["gap_ref"]
        for row in research_input["residual_gap_cards"]
        if row["facet_id"] == "price_or_asp"
    )
    r2_invalid = {
        "cell_id": cell_id,
        "gap_ref": gap_ref,
        "target_entity": "DELL",
        "requested_facet_id": "pricing_and_mix",
        "requested_source_class": "official_company_disclosure",
        "metric_intents": ["average_selling_price"],
        "product_intents": [
            "AI server price and configuration mix from industry data"
        ],
    }
    repaired = {
        "cell_id": cell_id,
        "gap_ref": gap_ref,
        "target_entity": "DELL",
        "requested_facet_id": "pricing_and_mix",
        "requested_source_class": "official_company_disclosure",
        "metric_intents": ["average_selling_price"],
        "product_intents": ["price and configuration mix evidence"],
    }
    sequence = [
        _parallel_step(
            1,
            [
                (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
            ],
        ),
        _step(2, SUBMIT_EVIDENCE_REQUEST_TOOL, r2_invalid),
        _step(3, SUBMIT_EVIDENCE_REQUEST_TOOL, repaired),
        _step(4, SUBMIT_RESEARCH_JUDGMENT_TOOL, _fake_judgment(cell_id)),
    ]
    observed_repair: dict[str, object] = {}

    def executor(messages, _tools, step_index):
        if step_index == 3:
            observed_repair.update(json.loads(messages[-1]["content"]))
        return sequence[step_index - 1]

    result = run_bounded_finance_loop(
        policy=scoped,
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=executor,
    )

    assert observed_repair["status"] == "rejected_not_executed"
    assert observed_repair["failure_code"] == (
        "finance_loop_evidence_request_forbidden_intent"
    )
    assert observed_repair["retrieval_executed"] is False
    assert observed_repair["gap_status"] == "open"
    assert len(result.proposed_evidence_requests) == 1
    assert result.proposed_evidence_requests[0]["status"] == "recorded_not_executed"
    assert result.proposed_evidence_requests[0]["compiled_route_projection"][
        "selected_executable_route_ids"
    ] == ["bm25_lexical"]
    assert result.tool_counts[SUBMIT_EVIDENCE_REQUEST_TOOL] == 2


def test_tool_definition_drift_fails_before_provider_execution(contracts) -> None:
    policy, research_input, kernel, route, planning = contracts
    cell_id = "CELL::demand_quality"
    tools = list(
        compile_finance_loop_tools(
            research_input=research_input,
            required_cell_ids=[cell_id],
            kernel=kernel,
            route_policy=route,
            policy=policy,
            strict=False,
        )
    )
    tools[2] = deepcopy(tools[2])
    tools[2]["function"]["parameters"]["properties"]["cell_id"][
        "pattern"
    ] = "^DRIFT$"
    called = False

    def executor(_messages, _tools, _step_index):
        nonlocal called
        called = True
        return _step(1, READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id})

    with pytest.raises(
        BoundedFinanceLoopError,
        match="finance_loop_tool_definition_contract_drift",
    ):
        run_bounded_finance_loop(
            policy=policy,
            research_input=research_input,
            required_cell_ids=[cell_id],
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
            tools=tools,
            step_executor=executor,
        )
    assert called is False


def test_scoped_policy_and_required_reads_prevent_cosmetic_agent_loop(
    contracts,
) -> None:
    policy, research_input, kernel, route, planning = contracts
    cell_id = "CELL::value_capture"
    scoped = scope_bounded_finance_loop_policy(
        policy,
        cell_count=1,
        maximum_evidence_requests=3,
    )
    assert scoped.maximum_steps == 6
    assert scoped.maximum_tool_calls == 6
    assert scoped.maximum_calls_by_tool == {
        READ_REVIEWED_EVIDENCE_TOOL: 1,
        READ_NUMERIC_FACTS_TOOL: 1,
        SUBMIT_EVIDENCE_REQUEST_TOOL: 3,
        SUBMIT_RESEARCH_JUDGMENT_TOOL: 1,
    }
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    with pytest.raises(
        BoundedFinanceLoopError,
        match="finance_loop_required_cell_reads_incomplete",
    ):
        run_bounded_finance_loop(
            policy=scoped,
            research_input=research_input,
            required_cell_ids=[cell_id],
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
            tools=tools,
            step_executor=lambda _messages, _tools, step_index: _step(
                step_index,
                SUBMIT_RESEARCH_JUDGMENT_TOOL,
                _fake_judgment(cell_id),
            ),
        )


def test_receipt_recorder_preserves_successful_prefix(contracts) -> None:
    policy, research_input, kernel, route, planning = contracts
    cell_id = "CELL::value_capture"
    scoped = scope_bounded_finance_loop_policy(
        policy,
        cell_count=1,
        maximum_evidence_requests=3,
    )
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    sequence = [
        (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
        (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
        (SUBMIT_RESEARCH_JUDGMENT_TOOL, _fake_judgment(cell_id)),
    ]
    receipts: list[dict[str, object]] = []
    result = run_bounded_finance_loop(
        policy=scoped,
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=lambda _messages, _tools, step_index: _step(
            step_index, *sequence[step_index - 1]
        ),
        receipt_recorder=receipts.append,
        visible_execution_budget={
            "maximum_steps": 6,
            "maximum_evidence_requests": 3,
            "maximum_reads_per_cell": 1,
            "maximum_parallel_read_tools": 2,
            "maximum_judgments_per_cell": 1,
            "retry_count": 0,
        },
    )
    assert result.step_count == 3
    assert [row["step_index"] for row in receipts] == [1, 2, 3]
    assert all(row["private_reasoning_persisted"] is False for row in receipts)


def test_safe_parallel_read_pair_is_the_only_two_call_step(contracts) -> None:
    policy, research_input, kernel, route, planning = contracts
    cell_id = "CELL::value_capture"
    scoped = scope_bounded_finance_loop_policy(
        policy,
        cell_count=1,
        maximum_evidence_requests=3,
    )
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=False,
    )
    sequence = [
        _parallel_step(
            1,
            [
                (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
                (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
            ],
        ),
        _step(2, SUBMIT_RESEARCH_JUDGMENT_TOOL, _fake_judgment(cell_id)),
    ]
    result = run_bounded_finance_loop(
        policy=scoped,
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=lambda _messages, _tools, step_index: sequence[
            step_index - 1
        ],
    )
    assert result.step_count == 2
    assert result.tool_call_count == 3
    assert [row["step_index"] for row in result.step_receipts] == [1, 1, 2]
    assert [row["receipt_sequence"] for row in result.step_receipts] == [
        1,
        2,
        3,
    ]

    forbidden = [
        [
            (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
            (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}),
        ],
        [
            (READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}),
            (
                SUBMIT_RESEARCH_JUDGMENT_TOOL,
                _fake_judgment(cell_id),
            ),
        ],
    ]
    for calls in forbidden:
        with pytest.raises(
            BoundedFinanceLoopError,
            match="finance_loop_parallel_tool_set_invalid",
        ):
            run_bounded_finance_loop(
                policy=scoped,
                research_input=research_input,
                required_cell_ids=[cell_id],
                kernel=kernel,
                route_policy=route,
                planning_policy=planning,
                tools=tools,
                step_executor=lambda _messages, _tools, _step_index, rows=calls: (
                    _parallel_step(1, rows)
                ),
            )

    two_cells = ["CELL::demand_quality", "CELL::value_capture"]
    two_cell_tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=two_cells,
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=False,
    )
    with pytest.raises(
        BoundedFinanceLoopError,
        match="finance_loop_parallel_read_cell_mismatch",
    ):
        run_bounded_finance_loop(
            policy=policy,
            research_input=research_input,
            required_cell_ids=two_cells,
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
            tools=two_cell_tools,
            step_executor=lambda _messages, _tools, _step_index: (
                _parallel_step(
                    1,
                    [
                        (
                            READ_REVIEWED_EVIDENCE_TOOL,
                            {"cell_id": two_cells[0]},
                        ),
                        (
                            READ_NUMERIC_FACTS_TOOL,
                            {"cell_id": two_cells[1]},
                        ),
                    ],
                )
            ),
        )


def test_five_cell_fake_loop_uses_budgets_not_fixed_nine_calls(contracts) -> None:
    policy, research_input, kernel, route, planning = contracts
    cell_ids = [row["cell_id"] for row in research_input["cells"]]
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=cell_ids,
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=False,
    )
    sequence: list[tuple[str, dict[str, object]]] = []
    for cell_id in cell_ids:
        sequence.append((READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": cell_id}))
        sequence.append((READ_NUMERIC_FACTS_TOOL, {"cell_id": cell_id}))
        sequence.append((SUBMIT_RESEARCH_JUDGMENT_TOOL, _fake_judgment(cell_id)))

    result = run_bounded_finance_loop(
        policy=policy,
        research_input=research_input,
        required_cell_ids=cell_ids,
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
        tools=tools,
        step_executor=lambda _messages, _tools, step_index: _step(
            step_index, *sequence[step_index - 1]
        ),
    )

    assert result.step_count == 15
    assert result.tool_call_count == 15
    assert len(result.structured_deliverable["cells"]) == 5
    assert result.tool_counts == {
        READ_REVIEWED_EVIDENCE_TOOL: 5,
        READ_NUMERIC_FACTS_TOOL: 5,
        SUBMIT_RESEARCH_JUDGMENT_TOOL: 5,
    }


def test_gapless_cell_schema_is_closed_without_an_empty_enum(contracts) -> None:
    policy, research_input, kernel, route, _ = contracts
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=["CELL::operating_performance"],
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=True,
    )
    request = next(
        row
        for row in tools
        if row["function"]["name"] == SUBMIT_EVIDENCE_REQUEST_TOOL
    )
    gap_schema = request["function"]["parameters"]["properties"]["gap_ref"]
    assert gap_schema["pattern"] == "^NO_VISIBLE_GAP$"
    assert "enum" not in gap_schema


@pytest.mark.parametrize(
    ("sequence", "code"),
    [
        (
            [
                (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": "CELL::demand_quality"}),
                (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": "CELL::demand_quality"}),
                (READ_REVIEWED_EVIDENCE_TOOL, {"cell_id": "CELL::demand_quality"}),
            ],
            "finance_loop_no_progress_stop",
        ),
        (
            [("made_up_tool", {"cell_id": "CELL::demand_quality"})],
            "finance_loop_tool_unknown",
        ),
        (
            [
                (
                    SUBMIT_RESEARCH_JUDGMENT_TOOL,
                    _fake_judgment("CELL::operating_performance"),
                )
            ],
            "finance_loop_judgment_cell_invalid_or_duplicate",
        ),
    ],
)
def test_loop_mutations_fail_closed(contracts, sequence, code: str) -> None:
    policy, research_input, kernel, route, planning = contracts
    cell_id = "CELL::demand_quality"
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=policy,
        strict=False,
    )

    with pytest.raises(BoundedFinanceLoopError, match=code):
        run_bounded_finance_loop(
            policy=policy,
            research_input=research_input,
            required_cell_ids=[cell_id],
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
            tools=tools,
            step_executor=lambda _messages, _tools, step_index: _step(
                step_index, *sequence[min(step_index - 1, len(sequence) - 1)]
            ),
        )


def test_deepseek_ga_profiles_keep_provider_details_outside_core() -> None:
    standard = load_chat_completion_profile(
        _json(
            ROOT
            / "configs/providers/"
            "fin_ia_0_1_3_deepseek_v4_pro_ga_agent_profile_v1_0.json"
        )
    )
    strict = load_chat_completion_profile(
        _json(
            ROOT
            / "configs/providers/"
            "fin_ia_0_1_3_deepseek_v4_pro_ga_strict_tool_profile_v1_0.json"
        )
    )
    json_control = load_chat_completion_profile(
        _json(
            ROOT
            / "configs/providers/"
            "fin_ia_0_1_3_deepseek_v4_pro_ga_json_profile_v1_0.json"
        )
    )
    validate_deepseek_ga_profile(standard, strict_tools=False)
    validate_deepseek_ga_profile(strict, strict_tools=True)
    validate_deepseek_ga_json_profile(json_control)

    replacement_strict = load_chat_completion_profile(
        _json(
            ROOT
            / "configs/providers/"
            "fin_ia_0_1_3_deepseek_v4_pro_ga_strict_tool_profile_v1_1.json"
        )
    )
    replacement_json = load_chat_completion_profile(
        _json(
            ROOT
            / "configs/providers/"
            "fin_ia_0_1_3_deepseek_v4_pro_ga_json_profile_v1_1.json"
        )
    )
    assert replacement_strict.request_defaults["max_tokens"] == 16000
    assert replacement_json.request_defaults["max_tokens"] == 16000
    validate_deepseek_ga_profile(replacement_strict, strict_tools=True)
    validate_deepseek_ga_json_profile(replacement_json)

    replacement_standard = load_chat_completion_profile(
        _json(
            ROOT
            / "configs/providers/"
            "fin_ia_0_1_3_deepseek_v4_pro_ga_agent_profile_v1_1.json"
        )
    )
    assert replacement_standard.request_defaults["max_tokens"] == 16000
    validate_deepseek_ga_profile(replacement_standard, strict_tools=False)

    micro_read = load_chat_completion_profile(
        _json(
            ROOT
            / "configs/providers/"
            "fin_ia_0_1_3_deepseek_v4_pro_ga_micro_read_profile_v1_0.json"
        )
    )
    micro_judgment = load_chat_completion_profile(
        _json(
            ROOT
            / "configs/providers/"
            "fin_ia_0_1_3_deepseek_v4_pro_ga_micro_judgment_profile_v1_0.json"
        )
    )
    validate_deepseek_ga_node_profile(
        micro_read,
        node_class="tool_routing",
    )
    validate_deepseek_ga_node_profile(
        micro_judgment,
        node_class="bounded_financial_judgment",
    )
    validate_deepseek_ga_node_profile(
        micro_judgment,
        node_class="bounded_financial_analysis",
    )
    validate_deepseek_ga_node_profile(
        micro_read,
        node_class="contract_submission",
    )
    with pytest.raises(
        BoundedFinanceLoopError,
        match="node_profile_invalid",
    ):
        validate_deepseek_ga_node_profile(
            micro_read,
            node_class="bounded_financial_judgment",
        )

    micro_policy_payload = _json(MICRO_POLICY)
    micro_policy = load_fixed_pack_micro_judgment_policy(
        micro_policy_payload
    )
    assert micro_policy.ordered_model_owned_phases == (
        MICRO_JUDGMENT_TOOL_NAMES
    )
    changed_micro_policy = deepcopy(micro_policy_payload)
    changed_micro_policy["authority"][
        "harness_may_invent_missing_fragment_or_claim"
    ] = True
    with pytest.raises(
        BoundedFinanceLoopError,
        match="micro_policy_authority_invalid",
    ):
        load_fixed_pack_micro_judgment_policy(changed_micro_policy)

    changed = deepcopy(_json(
        ROOT
        / "configs/providers/"
        "fin_ia_0_1_3_deepseek_v4_pro_ga_agent_profile_v1_0.json"
    ))
    changed["request_defaults"]["temperature"] = 0
    with pytest.raises(
        BoundedFinanceLoopError,
        match="profile_defaults_invalid",
    ):
        validate_deepseek_ga_profile(
            load_chat_completion_profile(changed), strict_tools=False
        )

    changed_json = deepcopy(_json(
        ROOT
        / "configs/providers/"
        "fin_ia_0_1_3_deepseek_v4_pro_ga_json_profile_v1_0.json"
    ))
    changed_json["request_defaults"]["top_p"] = 1
    with pytest.raises(
        BoundedFinanceLoopError,
        match="json_profile_defaults_invalid",
    ):
        validate_deepseek_ga_json_profile(
            load_chat_completion_profile(changed_json)
        )

    changed_json = deepcopy(_json(
        ROOT
        / "configs/providers/"
        "fin_ia_0_1_3_deepseek_v4_pro_ga_json_profile_v1_1.json"
    ))
    changed_json["request_defaults"]["max_tokens"] = 384001
    with pytest.raises(
        BoundedFinanceLoopError,
        match="json_profile_defaults_invalid",
    ):
        validate_deepseek_ga_json_profile(
            load_chat_completion_profile(changed_json)
        )
