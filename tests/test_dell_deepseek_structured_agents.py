from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
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
        self.schemas: list[type[Any] | dict[str, Any]] = []
        self.options: list[dict[str, Any]] = []
        self.inputs: list[Any] = []

    def with_structured_output(
        self,
        schema: type[Any] | dict[str, Any],
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
                "raw": AIMessage(
                    content="invalid",
                    usage_metadata={
                        "input_tokens": 101,
                        "output_tokens": 37,
                        "total_tokens": 138,
                    },
                ),
                "parsed": None,
                "parsing_error": ValueError("fixture parse failure"),
            }
        parsed = (
            self.response
            if isinstance(schema, dict)
            else schema.model_validate_json(json.dumps(self.response))
        )
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
        "minimum_route_obligation_id": (
            "route:Q1_ISSUER_TRUTH:required-reviewed"
        ),
        "intent": {
            "intent_kind": "reviewed_evidence",
            "query": query,
            "purpose": "Test one material branch mechanism.",
            "entity_refs": ["DELL"],
            "period_intents": [],
            "expected_information_gain": (
                "Determine whether reviewed evidence supports the mechanism."
            ),
            "limit": 6,
            "topic_refs": ["operating_performance"],
            "evidence_role_refs": [],
            "minimum_authority_tier": "reviewed",
        },
    }


def _fact_request() -> dict[str, Any]:
    return {
        "ticker": "DELL",
        "metric_ids": ["revenue"],
        "granularity": "quarter_discrete",
        "period_start": None,
        "period_end": None,
        "selection_mode": "latest_on_or_before",
        "fiscal_years": [],
        "requested_unit": "reported_source_unit",
        "unit_family": None,
    }


def _source_route_catalog() -> dict[str, Any]:
    return {
        "schema_version": "fin_ia_dell_provider_source_route_catalog_v1_0",
        "catalog_digest": DIGEST_C,
        "routes": [
            {
                "minimum_route_obligation_id": (
                    "route:Q1_ISSUER_TRUTH:required-reviewed"
                ),
                "coverage_obligation_id": "Q1_ISSUER_TRUTH",
                "requirement": "required",
                "intent_kind": "reviewed_evidence",
                "semantic_source_family_refs": ["F1_SEC_ISSUER_FACTS"],
                "entity_refs": [],
                "period_intents": [],
                "required_authority_refs": ["authority:reviewed-read"],
            }
        ],
        "physical_selectors_exposed": False,
        "answer_free": True,
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
        "source_route_catalog": _source_route_catalog(),
        "source_route_catalog_digest": DIGEST_C,
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


def _agentic_turn_request() -> dict[str, Any]:
    body = {
        "schema_version": "fin_ia_dell_specialist_agentic_graph_v1_0",
        "agent_id": "specialist:Q1:host-owned",
        "task": {
            "task_id": "task-host-owned",
            "case_id": "DELL_REFERENCE_VERTICAL",
            "branch_id": "Q1_ISSUER_TRUTH",
            "revision": 0,
            "priority": "high",
            "objective": "Establish issuer truth.",
            "evidence_requests": [
                {
                    "minimum_route_obligation_id": (
                        "route:Q1_ISSUER_TRUTH:required-reviewed"
                    ),
                    "answer_free_intent_kind": "reviewed_evidence",
                }
            ],
            "fact_requests": [],
            "research_as_of": "2026-09-02T00:00:00+08:00",
            "snapshot_id": "snapshot-host-owned",
            "foundation_digest": DIGEST_A,
            "method_digest": DIGEST_B,
            "plan_digest": DIGEST_C,
        },
        "l0_context": {
            "owner_data_gate_decision_digest": DIGEST_A,
            "source_route_catalog_digest": DIGEST_B,
            "inventory_snapshot_digest": DIGEST_C,
            "disclosure_runtime_state": (
                "current_state_authority_unavailable_fail_closed"
            ),
            "capability_summaries": [
                {
                    "capability_ref": "capability:dell:reviewed-evidence",
                    "purpose": "Read current reviewed issuer evidence.",
                    "authority_digest": DIGEST_D,
                }
            ],
            "skill_summaries": [],
        },
        "notebook": {
            "model_turn_count": 0,
            "required_route_obligation_ids": [
                "route:Q1_ISSUER_TRUTH:required-reviewed"
            ],
            "satisfied_route_obligation_ids": [],
            "model_turn_records": [],
            "observations": [],
            "feedback": [],
            "notebook_digest": DIGEST_D,
        },
        "execution_budget": {
            "max_model_turns": 8,
            "used_model_turns": 0,
            "remaining_model_turns": 8,
            "max_tool_actions": 12,
            "used_tool_actions": 0,
            "remaining_tool_actions": 12,
            "ceiling_semantics": "hard_anomaly_stop_not_completion_target",
        },
        "allowed_actions": [
            "request_evidence",
            "request_finance",
            "submit_workpaper",
            "request_human_review",
        ],
        "privacy_contract": {
            "return_structured_action_only": True,
            "hidden_reasoning_must_not_be_returned": True,
            "reason_summary_is_decision_rationale_not_chain_of_thought": True,
        },
    }
    return {**body, "context_digest": canonical_sha256(body)}


def _agentic_action(*, context_digest: str) -> dict[str, Any]:
    return {
        "action": "request_human_review",
        "context_digest": context_digest,
        "reason_summary": "Stop for an explicit bounded owner review.",
        "blocker_code": "saved_response_fixture_review",
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
        "source_route_catalog": _source_route_catalog(),
        "source_route_catalog_digest": DIGEST_C,
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


def test_profile_routing_uses_existing_sdk_clients_and_explicit_effort(monkeypatch):
    created = []

    class FakeChatDeepSeek:
        def __init__(self, **kwargs):
            created.append(kwargs)

    monkeypatch.setattr(adapter_module, "ReasoningPreservingChatDeepSeek", FakeChatDeepSeek)
    config = adapter_module.DeepSeekStructuredAgentConfig.model_validate({
        **_config().model_dump(), "agentic_message_history": True, "thinking": "enabled",
        "model_profiles": {
            "specialist": {"model": "deepseek-v4-flash", "reasoning_effort": "high"},
            "verifier": {"model": "deepseek-v4-pro", "reasoning_effort": "high"},
            "repair": {"model": "deepseek-v4-pro", "reasoning_effort": "low"},
        },
    })
    adapter = DeepSeekStructuredAgentAdapter.from_config(config=config, api_key=SecretStr("offline"))
    assert len(created) == 6
    assert created[1]["model"] == "deepseek-v4-flash"
    assert created[-1]["reasoning_effort"] == "low"
    assert all(row["max_retries"] == 0 for row in created)
    assert adapter._chat_models["specialist"] is not adapter._chat_models["verifier"]


def test_non_agentic_profile_selection_matches_public_model_record():
    config = adapter_module.DeepSeekStructuredAgentConfig.model_validate({**_config().model_dump(),
        "model_profiles": {"planner": {"model": "deepseek-v4-flash", "reasoning_effort": "low"}}})
    events, models = [], _models()
    adapter = DeepSeekStructuredAgentAdapter(config=config, chat_models=models, audit_sink=events.append)
    adapter.planner(_planner_request())
    assert events[0]["model"] == "deepseek-v4-flash"
    assert events[0]["model_purpose"] == "planner"
    assert models["planner"].calls == 1


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
        provider_schema = model.schemas[0]
        assert isinstance(provider_schema, dict)
        schema_names = _schema_property_names(provider_schema["parameters"])
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


def test_provider_dict_schema_preserves_langchain_pydantic_tool_contract() -> None:
    expected = convert_to_openai_tool(
        adapter_module.PlannerSemanticPayload,
        strict=False,
    )["function"]

    actual = adapter_module._provider_function_schema(
        adapter_module.PlannerSemanticPayload,
        strict=False,
    )

    assert actual["name"] == expected["name"]
    assert actual["description"] == expected["description"]
    assert actual.get("strict") == expected.get("strict")
    assert "$defs" not in json.dumps(actual)
    assert '"$ref"' not in json.dumps(actual)
    assert actual["parameters"] != (
        adapter_module.PlannerSemanticPayload.model_json_schema()
    )


def test_provider_planner_schema_rejects_physical_evidence_selectors() -> None:
    physical_request = {
        "query": "Dell AI server backlog",
        "purpose": "Test one material branch mechanism.",
        "include_domains": ["dell.com"],
        "issuer_ids": ["DELL"],
        "source_roles": ["issuer_management_disclosure"],
        "limit": 6,
        "source_route": "reviewed_first",
        "capture_limit": 2,
    }
    payload = _models()["planner"].response
    payload["tasks"][0]["evidence_requests"] = [physical_request]

    with pytest.raises(ValidationError):
        adapter_module.PlannerSemanticPayload.model_validate_json(
            json.dumps(payload)
        )


def test_specialist_projection_strips_host_compilation_receipts() -> None:
    request = _specialist_request()
    request["evidence_result"]["items"][0]["mcp_receipt_chain"] = [
        {
            "contract_version": "1.2",
            "local_scopes": [
                {
                    "issuer_ids": ["DELL"],
                    "fiscal_periods": ["FY2027_Q2"],
                    "route_ids": ["physical-route-secret"],
                    "lanes": ["local"],
                }
            ],
        }
    ]
    request["evidence_result"]["items"][0]["cell_binding_used"] = False

    projected = adapter_module._project_request("specialist", request)
    encoded = json.dumps(projected, ensure_ascii=False)

    assert "mcp_receipt_chain" not in encoded
    assert "cell_binding_used" not in encoded
    assert "physical-route-secret" not in encoded
    assert "issuer_ids" not in encoded
    assert projected["evidence_result"]["items"][0]["evidence_id"] == "E-1"


def test_specialist_projection_fails_closed_on_unwrapped_physical_selector() -> None:
    request = _specialist_request()
    request["evidence_result"]["items"][0]["route_ids"] = [
        "unwrapped-physical-route"
    ]

    with pytest.raises(
        DeepSeekStructuredAgentError,
        match="provider_tool_item_physical_selector_exposed",
    ):
        adapter_module._project_request("specialist", request)


def test_agentic_specialist_turn_uses_sanitized_action_contract_and_receipt() -> None:
    request = _agentic_turn_request()
    models = _models()
    specialist_model = FakeStructuredModel(
        {"action": _agentic_action(context_digest=request["context_digest"])}
    )
    models["specialist"] = specialist_model
    adapter = DeepSeekStructuredAgentAdapter(
        config=_config(),
        chat_models=models,
    )

    result = adapter.specialist_model_turn(request)

    assert specialist_model.calls == 1
    provider_schema = specialist_model.schemas[0]
    assert isinstance(provider_schema, dict)
    encoded_schema = json.dumps(provider_schema, ensure_ascii=False)
    assert "$defs" not in encoded_schema
    assert '"$ref"' not in encoded_schema
    for action_name in (
        "request_evidence",
        "request_finance",
        "request_human_review",
        "submit_workpaper",
    ):
        assert action_name in encoded_schema
    assert "request_disclosure" not in encoded_schema
    schema_names = _schema_property_names(provider_schema["parameters"])
    assert not {
        "runtime_receipt",
        "receipt_id",
        "action_attempt_id",
        "issuer_ids",
        "route_ids",
    }.intersection(schema_names)

    action = result["action"]
    receipt = result["runtime_receipt"]
    assert action["action"] == "request_human_review"
    assert action["context_digest"] == request["context_digest"]
    assert receipt["kind"] == "model"
    assert receipt["actor"] == request["agent_id"]
    assert receipt["request_digest"] == canonical_sha256(request)
    assert receipt["output_digest"] == canonical_sha256(action)
    assert (receipt["input_tokens"], receipt["output_tokens"]) == (101, 37)
    assert receipt["total_tokens"] == 138
    assert receipt["usage_reported"] is True
    assert receipt["transport_attempts"] == 1

    model_visible = str(specialist_model.inputs[0][1].content)
    assert request["context_digest"] in model_visible
    assert "snapshot-host-owned" not in model_visible
    assert "specialist:Q1:host-owned" not in model_visible
    assert DIGEST_A not in model_visible
    assert DIGEST_B not in model_visible
    assert DIGEST_C not in model_visible
    assert DIGEST_D not in model_visible
    assert "runtime_receipt" not in model_visible
    assert "notebook_digest" not in model_visible
    assert '"remaining_model_turns":8' in model_visible
    assert '"remaining_tool_actions":12' in model_visible


def test_agentic_provider_function_has_object_root_not_union_root() -> None:
    schema = adapter_module._provider_function_schema(
        adapter_module.SpecialistActionPayload, strict=False
    )
    parameters = schema["parameters"]

    assert parameters.get("type") == "object"
    assert parameters["required"] == ["action"]
    assert parameters["additionalProperties"] is False
    assert set(parameters["properties"]) == {"action"}
    assert "oneOf" not in parameters and "anyOf" not in parameters
    assert len(parameters["properties"]["action"]["oneOf"]) == 5


def test_agentic_object_envelope_preserves_closed_host_validation() -> None:
    action = _agentic_action(context_digest=DIGEST_A)
    valid = adapter_module.SpecialistActionPayload.model_validate_json(
        json.dumps({"action": action})
    )
    assert valid.action.model_dump(mode="json") == action
    for invalid in (
        action,
        {"action": action, "runtime_receipt": {}},
        {"action": {**action, "action": "request_disclosure"}},
        {"action": {**action, "context_digest": "invalid"}},
    ):
        with pytest.raises(ValidationError):
            adapter_module.SpecialistActionPayload.model_validate_json(
                json.dumps(invalid)
            )


def test_agentic_real_sdk_wire_uses_object_envelope_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    request = _agentic_turn_request()
    action = _agentic_action(context_digest=request["context_digest"])
    wire_payloads: list[dict[str, Any]] = []

    def respond(wire_request: httpx.Request) -> httpx.Response:
        payload = json.loads(wire_request.content)
        wire_payloads.append(payload)
        function = payload["tools"][0]["function"]
        assert function["name"] == "SpecialistActionPayload"
        assert function["parameters"]["type"] == "object"
        assert function["parameters"]["required"] == ["action"]
        assert payload["thinking"] == {"type": "disabled"}
        return httpx.Response(
            200,
            json={
                "id": "offline-specialist-wire-test",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-v4-pro",
                "choices": [{
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "offline-action",
                            "type": "function",
                            "function": {
                                "name": function["name"],
                                "arguments": json.dumps({"action": action}),
                            },
                        }],
                    },
                }],
                "usage": {
                    "prompt_tokens": 101,
                    "completion_tokens": 37,
                    "total_tokens": 138,
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        models = _models()
        models["specialist"] = adapter_module.ChatDeepSeek(
            model="deepseek-v4-pro",
            api_key=SecretStr("dummy-key-no-network-call"),
            base_url="https://api.deepseek.com",
            http_client=client,
            max_retries=0,
            use_responses_api=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        adapter = DeepSeekStructuredAgentAdapter(
            config=_config(), chat_models=models
        )
        result = adapter.specialist_model_turn(request)

    assert len(wire_payloads) == 1
    assert result["action"] == action
    assert result["runtime_receipt"]["output_digest"] == canonical_sha256(action)
    assert result["runtime_receipt"]["transport_attempts"] == 1
    assert result["runtime_receipt"]["total_tokens"] == 138


@pytest.mark.parametrize("status_code", [402, 429, 503])
def test_agentic_provider_failure_audit_keeps_http_status_without_error_body(
    monkeypatch: pytest.MonkeyPatch, status_code: int,
) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    events: list[dict[str, Any]] = []
    calls: list[str] = []
    private_error = "Insufficient Balance; private-provider-body-do-not-publish"

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(
            status_code,
            json={"error": {"message": private_error, "type": "unknown_error"}},
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        models = _models()
        models["specialist"] = adapter_module.ChatDeepSeek(
            model="deepseek-v4-pro",
            api_key=SecretStr("dummy-key-no-network-call"),
            base_url="https://api.deepseek.com",
            http_client=client,
            max_retries=0,
            use_responses_api=False,
        )
        adapter = DeepSeekStructuredAgentAdapter(
            config=_config(), chat_models=models,
            audit_sink=lambda event: events.append(dict(event)),
        )
        with pytest.raises(
            DeepSeekStructuredAgentError, match="deepseek_specialist_single_call_failed"
        ):
            adapter.specialist_model_turn(_agentic_turn_request())

    assert calls == ["POST"]
    assert [event["event"] for event in events] == ["started", "outcome"]
    outcome = events[-1]
    assert outcome["status"] == "provider_call_failed"
    assert outcome["http_status_code"] == status_code
    assert outcome["error_message"] == "provider_call_failed"
    assert outcome["usage_available"] is False
    encoded = json.dumps(events)
    assert private_error not in encoded
    assert "dummy-key-no-network-call" not in encoded


def test_agentic_observation_projection_strips_receipt_and_transport_internals() -> None:
    request = _agentic_turn_request()
    request["notebook"]["observations"] = [
        {
            "kind": "evidence",
            "status": "success",
            "references": [],
            "content": [
                {
                    "bounded_excerpt": "Dell retained semantic evidence.",
                    "mcp_receipt_chain": [{"route_ids": ["private-route"]}],
                    "source_tool_lane_receipt_id": "private-receipt",
                    "call_id": "private-call",
                    "elapsed_ms": 91.2,
                    "input_tokens": 99,
                    "transport_attempts": 1,
                }
            ],
            "route_completions": [],
            "failure": None,
        }
    ]

    projected = adapter_module._project_request(
        "specialist",
        request,
        specialist_mode="agentic_turn",
    )
    encoded = json.dumps(projected, ensure_ascii=False)

    assert "Dell retained semantic evidence." in encoded
    for forbidden in (
        "private-route",
        "private-receipt",
        "private-call",
        "mcp_receipt_chain",
        "source_tool_lane_receipt_id",
        "elapsed_ms",
        "input_tokens",
        "transport_attempts",
    ):
        assert forbidden not in encoded


def test_agentic_saved_response_replay_skips_transport_and_records_truth() -> None:
    request = _agentic_turn_request()
    models = _models()
    specialist_model = FakeStructuredModel({"must_not_be_used": True})
    models["specialist"] = specialist_model
    events: list[dict[str, Any]] = []
    adapter = DeepSeekStructuredAgentAdapter(
        config=_config(),
        chat_models=models,
        audit_sink=lambda event: events.append(dict(event)),
    )
    replay_body = {
        "schema_version": "fin_ia_dell_specialist_action_replay_record_v1_0",
        "replay_source": "synthetic_qualification",
        "request_digest": canonical_sha256(request),
        "parsed_action": _agentic_action(
            context_digest=request["context_digest"]
        ),
    }
    replay_record = {
        **replay_body,
        "replay_record_digest": canonical_sha256(replay_body),
    }

    result = adapter.replay_specialist_model_turn(
        request,
        replay_record=replay_record,
    )

    assert specialist_model.calls == 0
    assert specialist_model.schemas == []
    assert result["runtime_receipt"]["request_digest"] == canonical_sha256(
        request
    )
    assert result["runtime_receipt"]["output_digest"] == canonical_sha256(
        result["action"]
    )
    assert result["runtime_receipt"]["kind"] == "host"
    assert result["runtime_receipt"]["actor"] == (
        "dell_specialist_saved_response_replay"
    )
    assert result["runtime_receipt"]["total_tokens"] == 0
    assert [event["event"] for event in events] == ["started", "outcome"]
    assert all(event["provider_call_attempted"] is False for event in events)
    assert all(
        event["execution_source"] == "saved_response_replay"
        for event in events
    )
    assert all("semantic_input" not in event for event in events)
    assert all("raw_response" not in event for event in events)


def test_real_chatdeepseek_dict_path_selects_json_not_pydantic_parser() -> None:
    model = adapter_module.ChatDeepSeek(
        model="deepseek-v4-pro",
        api_key=SecretStr("dummy-key-no-network-call"),
        base_url="https://api.deepseek.com",
        max_retries=0,
    )
    provider_schema = adapter_module._provider_function_schema(
        adapter_module.PlannerSemanticPayload,
        strict=False,
    )

    runnable = model.with_structured_output(
        provider_schema,
        method="function_calling",
        include_raw=True,
        strict=False,
    )
    runnable_repr = repr(runnable)

    assert "JsonOutputKeyToolsParser" in runnable_repr
    assert "PydanticToolsParser" not in runnable_repr
    assert "$defs" not in json.dumps(provider_schema)


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
    assert failure_events[1]["input_tokens"] == 101
    assert failure_events[1]["output_tokens"] == 37
    assert failure_events[1]["total_tokens"] == 138
    assert failure_events[1]["usage_reported"] is True


def test_usage_audit_keeps_cache_and_reasoning_counts_without_private_text():
    raw = AIMessage(content="private-answer", additional_kwargs={"reasoning_content": "private-reasoning"},
        usage_metadata={"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100,
                        "input_token_details": {"cache_read": 800}, "output_token_details": {"reasoning": 70}})
    fields = adapter_module._usage_audit_fields(raw)
    assert fields["cache_hit_tokens"] == 800
    assert fields["cache_miss_tokens"] == 200
    assert fields["reasoning_tokens"] == 70
    assert "private" not in json.dumps(fields)
    assert adapter_module._usage_audit_fields(AIMessage(content=""))["cache_hit_tokens"] is None


@pytest.mark.parametrize("value", [-1, True, "800", 1001])
def test_invalid_cache_detail_is_unknown_not_a_negative_bill(value):
    raw = AIMessage(content="", usage_metadata={"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100},
                    response_metadata={"token_usage": {"prompt_cache_hit_tokens": value}})
    assert adapter_module._usage_audit_fields(raw)["cache_miss_tokens"] is None


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
        {"selection_mode": "nearest"},
    ],
)
def test_financial_fact_request_rejects_shapes_the_s2_port_cannot_accept(
    update: dict[str, Any],
) -> None:
    value = _fact_request()
    value.update(update)
    with pytest.raises(ValidationError):
        FinancialFactRequestPayload.model_validate_json(json.dumps(value))


def test_financial_fact_request_requires_explicit_period_selection_mode() -> None:
    value = _fact_request()
    value.pop("selection_mode")

    with pytest.raises(ValidationError, match="selection_mode"):
        FinancialFactRequestPayload.model_validate_json(json.dumps(value))
