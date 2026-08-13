from __future__ import annotations

from copy import deepcopy
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
from sec_agent.research.bounded_finance_loop import (
    BoundedFinanceLoopError,
    READ_NUMERIC_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_TOOL,
    SUBMIT_EVIDENCE_REQUEST_TOOL,
    SUBMIT_RESEARCH_JUDGMENT_TOOL,
    compile_finance_loop_messages,
    compile_finance_loop_tools,
    load_bounded_finance_loop_policy,
    run_bounded_finance_loop,
    validate_deepseek_ga_json_profile,
    validate_deepseek_ga_profile,
)
from sec_agent.research.current_consumer import (
    compile_current_research_input,
)
from sec_agent.research.planning import load_research_planning_policy
from sec_agent.runtime_bridge.paths import resolve_runtime_paths
from sec_agent.runtime_resource_registry import read_registered_runtime_json


READ = frozenset({"current_product:read"})
POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_bounded_finance_agent_loop_policy_v1_0.json"
)
CONSUMER_POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_current_research_consumer_policy_v1_1.json"
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
    "fin_ia_0_1_3_s3_dell_current_research_consumer_fake_payload_v1_1.json"
)


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _fake_judgment(cell_id: str) -> dict[str, object]:
    return deepcopy(
        next(row for row in _json(FAKE)["cells"] if row["cell_id"] == cell_id)
    )


def test_tool_compiler_emits_four_closed_finance_schemas(contracts) -> None:
    _, research_input, kernel, route, _ = contracts
    cell_id = "CELL::demand_quality"
    standard = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        strict=False,
    )
    strict = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
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
    )[1]["content"]) < 4000


def test_single_cell_fake_loop_reads_submits_gap_and_judgment(contracts) -> None:
    policy, research_input, kernel, route, planning = contracts
    cell_id = "CELL::demand_quality"
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        strict=True,
    )
    gap_ref = next(
        row["visible_gap_refs"][0]
        for row in research_input["cells"]
        if row["cell_id"] == cell_id
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
                "requested_facet_id": "conversion_and_durability",
                "metric_intents": ["orders"],
                "product_intents": ["order digestion and cancellation evidence"],
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


def test_five_cell_fake_loop_uses_budgets_not_fixed_nine_calls(contracts) -> None:
    policy, research_input, kernel, route, planning = contracts
    cell_ids = [row["cell_id"] for row in research_input["cells"]]
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=cell_ids,
        kernel=kernel,
        route_policy=route,
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
    _, research_input, kernel, route, _ = contracts
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=["CELL::operating_performance"],
        kernel=kernel,
        route_policy=route,
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
