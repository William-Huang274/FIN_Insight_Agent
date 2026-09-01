from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import SecretStr, ValidationError

import sec_agent.agent_runtime.deepseek_structured_agents as adapter_module
from sec_agent.agent_runtime.deepseek_structured_agents import (
    DeepSeekStructuredAgentAdapter,
    DeepSeekStructuredAgentError,
    FinancialFactRequestPayload,
    load_deepseek_structured_agent_config,
)
from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
    BranchWorkpaper,
    CounterDecision,
    LeadOutput,
    PlannerOutput,
    canonical_sha256,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    ROOT
    / "configs"
    / "research"
    / "fin_ia_0_1_3_dell_reference_vertical_deepseek_structured_agents_v1_0.json"
)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
DIGEST_D = "d" * 64


class FakeStructuredModel:
    def __init__(self, response: dict[str, Any], *, parse_error: bool = False) -> None:
        self.response = response
        self.parse_error = parse_error
        self.calls = 0
        self.schemas: list[type[Any]] = []
        self.options: list[dict[str, Any]] = []
        self.inputs: list[Any] = []

    def with_structured_output(
        self,
        schema: type[Any],
        *,
        method: str,
        include_raw: bool,
        strict: bool | None,
    ) -> "FakeStructuredModel":
        self.schemas.append(schema)
        self.options.append(
            {
                "method": method,
                "include_raw": include_raw,
                "strict": strict,
            }
        )
        return self

    def invoke(self, value: Any) -> dict[str, Any]:
        self.calls += 1
        self.inputs.append(value)
        schema = self.schemas[-1]
        if self.parse_error:
            return {
                "raw": AIMessage(content="invalid"),
                "parsed": None,
                "parsing_error": ValueError("fixture parse failure"),
            }
        parsed = schema.model_validate_json(json.dumps(self.response))
        return {
            "raw": AIMessage(
                content="",
                usage_metadata={
                    "input_tokens": 101,
                    "output_tokens": 37,
                    "total_tokens": 138,
                },
            ),
            "parsed": parsed,
            "parsing_error": None,
        }


def _config():
    return load_deepseek_structured_agent_config(CONFIG_PATH)


def _evidence_request(query: str) -> dict[str, Any]:
    return {
        "query": query,
        "purpose": "Test one material branch mechanism.",
        "include_domains": ["dell.com"],
        "limit": 6,
        "source_route": "reviewed_first",
        "capture_limit": 2,
    }


def _fact_request() -> dict[str, Any]:
    return {
        "ticker": "DELL",
        "metric_ids": ["revenue"],
        "granularity": "quarter_discrete",
        "period_start": None,
        "period_end": None,
        "fiscal_years": [2026],
        "requested_unit": "reported_source_unit",
        "unit_family": None,
    }


def _planner_request() -> dict[str, Any]:
    capabilities = {
        "schema_version": "fin_ia_dell_planner_tool_capabilities_v1_0",
        "supported_tickers": ["DELL", "NVDA"],
        "canonical_granularities": ["quarter_discrete", "fiscal_year"],
        "projection_digest": DIGEST_D,
    }
    return {
        "agent_id": "planner:global:host-owned",
        "graph_contract_version": "graph-v1",
        "run_id": "run-secret-binding",
        "case_id": "DELL_REFERENCE_VERTICAL",
        "research_question": "Can Dell convert AI infrastructure demand profitably?",
        "research_as_of": "2026-09-02T00:00:00+08:00",
        "snapshot_id": "snapshot-host-owned",
        "foundation_digest": DIGEST_A,
        "branch_catalog": [
            {
                "branch_id": "Q1_ISSUER_TRUTH",
                "priority": "high",
                "objective": "Establish issuer truth.",
                "method_digest": DIGEST_B,
                "method_context": {"rule": "candidate_is_not_evidence"},
            }
        ],
        "required_branch_ids": ["Q1_ISSUER_TRUTH"],
        "planner_tool_capabilities": capabilities,
        "planner_tool_capabilities_digest": DIGEST_D,
    }


def _tool_result(*, lane: str, receipt_id: str) -> dict[str, Any]:
    is_evidence = lane == "evidence"
    return {
        "lane": lane,
        "task_id": "task-host-owned",
        "case_id": "DELL_REFERENCE_VERTICAL",
        "branch_id": "Q1_ISSUER_TRUTH",
        "revision": 0,
        "research_as_of": "2026-09-02T00:00:00+08:00",
        "snapshot_id": "snapshot-host-owned",
        "foundation_digest": DIGEST_A,
        "method_digest": DIGEST_B,
        "plan_digest": DIGEST_C,
        "status": "success",
        "result_states": ["reviewed_evidence" if is_evidence else "numeric_fact"],
        "items": [
            (
                {"evidence_id": "E-1", "excerpt": "Reviewed evidence."}
                if is_evidence
                else {"fact_id": "F-1", "value": "100", "unit": "USD"}
            )
        ],
        "failure": None,
        "runtime_receipt": {
            "receipt_id": receipt_id,
            "kind": "tool",
            "actor": f"{lane}_tool",
            "status": "success",
            "request_digest": DIGEST_D,
            "output_digest": DIGEST_A,
            "elapsed_ms": 1.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "transport_attempts": 1,
        },
    }


def _specialist_request() -> dict[str, Any]:
    return {
        "agent_id": "specialist:Q1:host-owned",
        "turn_index": 1,
        "context_digest": DIGEST_D,
        "task": {
            "task_id": "task-host-owned",
            "case_id": "DELL_REFERENCE_VERTICAL",
            "branch_id": "Q1_ISSUER_TRUTH",
            "revision": 0,
            "priority": "high",
            "objective": "Establish issuer truth.",
            "evidence_requests": [_evidence_request("Dell AI server backlog")],
            "fact_requests": [_fact_request()],
            "research_as_of": "2026-09-02T00:00:00+08:00",
            "snapshot_id": "snapshot-host-owned",
            "foundation_digest": DIGEST_A,
            "method_digest": DIGEST_B,
            "plan_digest": DIGEST_C,
        },
        "method_context": {"rule": "candidate_is_not_evidence"},
        "evidence_result": _tool_result(
            lane="evidence", receipt_id="evidence-receipt-host-owned"
        ),
        "finance_result": _tool_result(
            lane="finance", receipt_id="finance-receipt-host-owned"
        ),
        "prior_workpaper": None,
        "counter_challenge": None,
    }


def _workpaper() -> dict[str, Any]:
    return {
        "branch_id": "Q1_ISSUER_TRUTH",
        "revision": 0,
        "agent_id": "specialist:Q1:host-owned",
        "context_digest": DIGEST_D,
        "snapshot_id": "snapshot-host-owned",
        "foundation_digest": DIGEST_A,
        "method_digest": DIGEST_B,
        "plan_digest": DIGEST_C,
        "terminal_state": "supported",
        "thesis": "Dell has demand visibility.",
        "mechanism": "Backlog converts through rack-scale shipments.",
        "counterevidence": ["Conversion timing remains uncertain."],
        "what_would_change": ["A sustained order decline."],
        "evidence_ids": ["E-1"],
        "fact_ids": ["F-1"],
        "open_gaps": [],
        "tool_receipt_ids": [
            "evidence-receipt-host-owned",
            "finance-receipt-host-owned",
        ],
        "runtime_receipt": {
            "receipt_id": "model-receipt-host-owned",
            "kind": "model",
            "actor": "specialist:Q1:host-owned",
            "status": "success",
            "request_digest": DIGEST_A,
            "output_digest": DIGEST_B,
            "elapsed_ms": 1.0,
            "input_tokens": 1,
            "output_tokens": 1,
            "total_tokens": 2,
            "transport_attempts": 1,
        },
    }


def _counter_request() -> dict[str, Any]:
    return {
        "agent_id": "counter:global:host-owned",
        "run_id": "run-secret-binding",
        "case_id": "DELL_REFERENCE_VERTICAL",
        "research_question": "Can Dell convert AI infrastructure demand profitably?",
        "research_as_of": "2026-09-02T00:00:00+08:00",
        "snapshot_id": "snapshot-host-owned",
        "foundation_digest": DIGEST_A,
        "plan_digest": DIGEST_C,
        "context_digest": DIGEST_D,
        "workpapers": [_workpaper()],
    }


def _lead_request() -> dict[str, Any]:
    return {
        **_counter_request(),
        "agent_id": "lead:global:host-owned",
        "counter_decision": {
            "agent_id": "counter:global:host-owned",
            "context_digest": DIGEST_D,
            "snapshot_id": "snapshot-host-owned",
            "foundation_digest": DIGEST_A,
            "plan_digest": DIGEST_C,
            "strongest_counter_thesis": "Margins may lag demand.",
            "challenges": ["Test conversion economics."],
            "what_would_change": ["Higher gross margin."],
            "reroute": None,
            "runtime_receipt": _workpaper()["runtime_receipt"],
        },
    }


def _models() -> dict[str, FakeStructuredModel]:
    return {
        "planner": FakeStructuredModel(
            {
                "tasks": [
                    {
                        "branch_id": "Q1_ISSUER_TRUTH",
                        "objective": "Establish issuer truth.",
                        "evidence_requests": [
                            _evidence_request("Dell AI server backlog")
                        ],
                        "fact_requests": [_fact_request()],
                    }
                ]
            }
        ),
        "specialist": FakeStructuredModel(
            {
                "terminal_state": "supported",
                "thesis": "Dell has source-linked demand visibility.",
                "mechanism": "Backlog converts through rack-scale shipments.",
                "counterevidence": ["Conversion timing remains uncertain."],
                "what_would_change": ["A sustained order decline."],
                "evidence_ids": ["E-1"],
                "fact_ids": ["F-1"],
                "open_gaps": [],
            }
        ),
        "counter": FakeStructuredModel(
            {
                "strongest_counter_thesis": "Margins may lag demand.",
                "challenges": ["Test conversion economics."],
                "what_would_change": ["Higher gross margin."],
                "reroute": {
                    "target_branch_id": "Q1_ISSUER_TRUTH",
                    "reason": "One refreshed conversion cohort could change the view.",
                    "evidence_requests": [
                        _evidence_request("Dell backlog conversion cohort")
                    ],
                    "fact_requests": [_fact_request()],
                },
            }
        ),
        "lead": FakeStructuredModel(
            {
                "verdict": "mixed_positive",
                "confidence": 68,
                "headline": "Demand is visible while conversion economics remain mixed.",
                "executive_summary": "The bounded source set supports a mixed-positive view.",
                "branch_conclusions": [
                    {
                        "branch_id": "Q1_ISSUER_TRUTH",
                        "conclusion": "Issuer disclosures support demand visibility.",
                        "evidence_ids": ["E-1"],
                        "fact_ids": ["F-1"],
                    }
                ],
                "counter_response": "Margin conversion remains an explicit monitor.",
            }
        ),
    }


def _assert_receipt(output: dict[str, Any], request: dict[str, Any]) -> None:
    receipt = output["runtime_receipt"]
    body = dict(output)
    body.pop("runtime_receipt")
    assert receipt["request_digest"] == canonical_sha256(request)
    assert receipt["output_digest"] == canonical_sha256(body)
    assert receipt["input_tokens"] == 101
    assert receipt["output_tokens"] == 37
    assert receipt["total_tokens"] == 138
    assert receipt["usage_reported"] is True
    assert receipt["transport_attempts"] == 1


def _schema_property_names(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            names.update(str(key) for key in properties)
        for child in value.values():
            names.update(_schema_property_names(child))
    elif isinstance(value, list):
        for child in value:
            names.update(_schema_property_names(child))
    return names


def test_budget_config_is_strict_complete_and_reasonably_wide(tmp_path: Path) -> None:
    config = _config()
    assert config.model == "deepseek-v4-pro"
    assert config.max_retries == 0
    assert config.thinking == "disabled"
    assert set(config.token_budget_basis) == {
        "planner",
        "specialist",
        "counter",
        "lead",
    }
    assert config.token_budget_basis["specialist"].max_output_tokens == 10_000
    assert config.token_budget_basis["lead"].max_output_tokens == 12_000
    assert config.token_budget_basis["specialist"].max_input_characters == 160_000

    invalid = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    invalid["token_budget_basis"]["lead"]["max_transport_attempts"] = 2
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(
        DeepSeekStructuredAgentError,
        match="deepseek_structured_agent_config_invalid",
    ):
        load_deepseek_structured_agent_config(invalid_path)


def test_factory_uses_four_chatdeepseek_clients_without_env_lookup(monkeypatch) -> None:
    created: list[dict[str, Any]] = []

    class FakeChatDeepSeek:
        def __init__(self, **kwargs: Any) -> None:
            created.append(kwargs)

    monkeypatch.setattr(adapter_module, "ChatDeepSeek", FakeChatDeepSeek)
    adapter = DeepSeekStructuredAgentAdapter.from_config(
        config=_config(), api_key=SecretStr("fixture-only-not-a-real-key")
    )

    assert isinstance(adapter, DeepSeekStructuredAgentAdapter)
    assert len(created) == 4
    assert {row["max_tokens"] for row in created} == {6_000, 10_000, 12_000}
    for row in created:
        assert row["model"] == "deepseek-v4-pro"
        assert row["max_retries"] == 0
        assert row["extra_body"] == {"thinking": {"type": "disabled"}}
        assert row["use_responses_api"] is False
        assert isinstance(row["api_key"], SecretStr)


def test_adapter_maps_semantic_payloads_to_host_bound_graph_contracts() -> None:
    models = _models()
    adapter = DeepSeekStructuredAgentAdapter(config=_config(), chat_models=models)

    planner_request = _planner_request()
    planner = adapter.planner(planner_request)
    PlannerOutput.model_validate_json(json.dumps(planner))
    _assert_receipt(planner, planner_request)
    planner_visible = str(models["planner"].inputs[0][1].content)
    assert "tool_capabilities" in planner_visible
    assert '"supported_tickers":["DELL","NVDA"]' in planner_visible
    assert "projection_digest" not in planner_visible

    specialist_request = _specialist_request()
    specialist = adapter.specialist(specialist_request)
    BranchWorkpaper.model_validate_json(json.dumps(specialist))
    _assert_receipt(specialist, specialist_request)
    assert specialist["agent_id"] == specialist_request["agent_id"]
    assert specialist["context_digest"] == specialist_request["context_digest"]
    assert specialist["snapshot_id"] == specialist_request["task"]["snapshot_id"]
    assert specialist["method_digest"] == specialist_request["task"]["method_digest"]
    assert specialist["tool_receipt_ids"] == [
        "evidence-receipt-host-owned",
        "finance-receipt-host-owned",
    ]

    counter_request = _counter_request()
    counter = adapter.counter(counter_request)
    CounterDecision.model_validate_json(json.dumps(counter))
    _assert_receipt(counter, counter_request)
    assert counter["agent_id"] == counter_request["agent_id"]
    assert counter["reroute"]["owner_layer"] == "agent"
    assert counter["reroute"]["challenge_id"].startswith("counter-challenge:")

    lead_request = _lead_request()
    lead = adapter.lead(lead_request)
    LeadOutput.model_validate_json(json.dumps(lead))
    _assert_receipt(lead, lead_request)
    assert lead["agent_id"] == lead_request["agent_id"]
    assert lead["context_digest"] == lead_request["context_digest"]
    assert lead["snapshot_id"] == lead_request["snapshot_id"]

    forbidden_schema_fields = {
        "runtime_receipt",
        "receipt_id",
        "agent_id",
        "snapshot_id",
        "foundation_digest",
        "method_digest",
        "plan_digest",
        "context_digest",
        "challenge_id",
        "tool_receipt_ids",
    }
    for role, model in models.items():
        assert model.calls == 1, role
        assert model.options == [
            {"method": "function_calling", "include_raw": True, "strict": False}
        ]
        schema_names = _schema_property_names(model.schemas[0].model_json_schema())
        assert not forbidden_schema_fields.intersection(schema_names), role
        messages = model.inputs[0]
        assert len(messages) == 2
        assert isinstance(messages[1], HumanMessage)
        model_visible = str(messages[1].content)
        assert "snapshot-host-owned" not in model_visible
        assert "host-owned" not in model_visible
        assert DIGEST_A not in model_visible
        assert DIGEST_B not in model_visible
        assert DIGEST_C not in model_visible
        assert DIGEST_D not in model_visible


def test_parse_failure_is_single_call_and_never_promoted() -> None:
    models = _models()
    failure = FakeStructuredModel({}, parse_error=True)
    models["planner"] = failure
    adapter = DeepSeekStructuredAgentAdapter(config=_config(), chat_models=models)

    with pytest.raises(
        DeepSeekStructuredAgentError, match="model_structured_parse_failed"
    ):
        adapter.planner(_planner_request())
    assert failure.calls == 1


def test_model_call_audit_records_exact_input_raw_usage_and_parse_failure() -> None:
    success_events: list[dict[str, Any]] = []
    models = _models()
    adapter = DeepSeekStructuredAgentAdapter(
        config=_config(),
        chat_models=models,
        audit_sink=lambda event: success_events.append(dict(event)),
    )
    adapter.planner(_planner_request())

    assert [event["event"] for event in success_events] == ["started", "outcome"]
    assert success_events[0]["semantic_input_digest"] == canonical_sha256(
        success_events[0]["semantic_input"]
    )
    assert success_events[1]["status"] == "success"
    assert success_events[1]["total_tokens"] == 138
    assert success_events[1]["raw_response"]["usage_metadata"]["input_tokens"] == 101
    assert success_events[1]["parsed_payload"]["tasks"][0]["branch_id"] == (
        "Q1_ISSUER_TRUTH"
    )

    failure_events: list[dict[str, Any]] = []
    failed_models = _models()
    failed_models["planner"] = FakeStructuredModel({}, parse_error=True)
    failed_adapter = DeepSeekStructuredAgentAdapter(
        config=_config(),
        chat_models=failed_models,
        audit_sink=lambda event: failure_events.append(dict(event)),
    )
    with pytest.raises(
        DeepSeekStructuredAgentError, match="model_structured_parse_failed"
    ):
        failed_adapter.planner(_planner_request())
    assert [event["event"] for event in failure_events] == ["started", "outcome"]
    assert failure_events[1]["status"] == "structured_parse_failed"
    assert failure_events[1]["raw_response"]["content"] == "invalid"


def test_input_character_ceiling_blocks_before_provider_transport() -> None:
    events: list[dict[str, Any]] = []
    models = _models()
    config = _config()
    planner_basis = config.token_budget_basis["planner"].model_copy(
        update={"max_input_characters": 10_000}
    )
    config = config.model_copy(
        update={
            "token_budget_basis": {
                **config.token_budget_basis,
                "planner": planner_basis,
            }
        }
    )
    adapter = DeepSeekStructuredAgentAdapter(
        config=config,
        chat_models=models,
        audit_sink=lambda event: events.append(dict(event)),
    )
    request = _planner_request()
    request["research_question"] = "x" * 20_000

    with pytest.raises(
        DeepSeekStructuredAgentError,
        match="deepseek_planner_input_character_limit_exceeded",
    ):
        adapter.planner(request)
    assert models["planner"].calls == 0
    assert len(events) == 1
    assert events[0]["status"] == "blocked_before_transport_input_limit"
    assert events[0]["provider_call_attempted"] is False


@pytest.mark.parametrize(
    "update",
    [
        {"granularity": "quarterly"},
        {"fiscal_years": [2023, 2024, 2025, 2026, 2027]},
        {"fiscal_years": [2026, 2026]},
        {"period_start": "2026-08-01", "period_end": "2026-07-01"},
        {"metric_ids": ["Revenue"]},
    ],
)
def test_financial_fact_request_rejects_shapes_the_s2_port_cannot_accept(
    update: dict[str, Any],
) -> None:
    value = _fact_request()
    value.update(update)
    with pytest.raises(ValidationError):
        FinancialFactRequestPayload.model_validate_json(json.dumps(value))
