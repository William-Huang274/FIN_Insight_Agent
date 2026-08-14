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
    READ_NUMERIC_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_TOOL,
    SUBMIT_EVIDENCE_REQUEST_TOOL,
    SUBMIT_RESEARCH_JUDGMENT_TOOL,
    compile_finance_loop_messages,
    compile_finance_loop_tools,
    load_bounded_finance_loop_policy,
    run_bounded_finance_loop,
    scope_bounded_finance_loop_policy,
    validate_deepseek_ga_json_profile,
    validate_deepseek_ga_profile,
)
from sec_agent.research.current_consumer import (
    compile_current_research_input,
)
from sec_agent.research.planning import load_research_planning_policy
from sec_agent.research.live_transport_lane import (
    execute_finance_loop_transport_lane,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths
from sec_agent.runtime_resource_registry import read_registered_runtime_json


READ = frozenset({"current_product:read"})
POLICY = ROOT / (
    "configs/research/fin_ia_0_1_3_s3_bounded_finance_agent_loop_policy_v1_1.json"
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
    )[1]["content"]) < 4000
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
    cell_id = "CELL::demand_quality"
    tools = compile_finance_loop_tools(
        research_input=research_input,
        required_cell_ids=[cell_id],
        kernel=kernel,
        route_policy=route,
        policy=policy,
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
    )
    allowed_metrics = pricing_branch["properties"]["metric_intents"]["items"][
        "enum"
    ]
    assert "average_selling_price" in allowed_metrics
    assert "shipments" not in allowed_metrics

    gap_ref = next(
        row["visible_gap_refs"][0]
        for row in research_input["cells"]
        if row["cell_id"] == cell_id
    )
    r2_invalid = {
        "cell_id": cell_id,
        "gap_ref": gap_ref,
        "target_entity": "DELL",
        "requested_facet_id": "pricing_and_mix",
        "metric_intents": ["shipments", "capacity", "orders", "backlog"],
        "product_intents": [
            "AI-optimized server unit shipments or equivalent compute capacity "
            "disclosed by Dell in earnings materials, investor presentations, or "
            "industry shipment trackers, to anchor whether revenue growth is "
            "volume-led or price-led."
        ],
    }
    repaired = {
        "cell_id": cell_id,
        "gap_ref": gap_ref,
        "target_entity": "DELL",
        "requested_facet_id": "pricing_and_mix",
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
        "finance_loop_evidence_request_intents_invalid"
    )
    assert observed_repair["retrieval_executed"] is False
    assert observed_repair["gap_status"] == "open"
    assert len(result.proposed_evidence_requests) == 1
    assert result.proposed_evidence_requests[0]["status"] == "recorded_not_executed"
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
    tools[2]["function"]["parameters"]["properties"]["product_intents"][
        "items"
    ]["maxLength"] += 1
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
