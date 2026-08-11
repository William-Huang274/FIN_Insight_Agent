from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

IMPLEMENTATION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "minimum_zero_call_implementation_v1_0.json"
)
FRESH_PROOF_DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "fresh_engineering_proof_and_provider_capability_binding_decision_v1_0.json"
)

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S4_NON_AUTHORITATIVE_NARRATIVE_SHELL_REF,
    S4_STRICT_JSON_SCHEMA_PROVIDER_CAPABILITY_REF,
    S4_STRICT_TRUTH_KERNEL_POLICY_REF,
    StrictTruthKernelPolicy,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_OPENAI_BASE_URL,
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from sec_agent.canonical_runtime.failure_observation_policy import (
    OBSERVATION_EXTENSION_REJECTED_CODE,
    is_registered_failure_observation,
    normalize_optional_failure_observation,
)
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)
from test_fin_0_1_s4_t05_case_numeric_authority_and_delivery_identity_zero_call_implementation import (
    _NumericIdentitySafeFake,
    _case_fixture_input_and_admission,
)
from test_fin_0_1_s4_t05_typed_post_provider_failure_envelope_zero_call_implementation import (
    _CanonicalTypedFailureProbe,
)
from test_fin_0_1_s3_t09_provider_output_capture_persistence import (
    _accepted_case,
    _admission,
    _create_work_unit,
)


def _adapted_first_cell(input_pack: Any) -> dict[str, Any]:
    return (
        S3ThreeCellBoundedAgentExecutor
        ._case_numeric_authority_cell_input(
            input_pack.cell_inputs[0]
        )
    )


def _strict_admission(input_pack: Any, admission: Any) -> Any:
    return admission.model_copy(
        update={
            "admission_id": (
                f"fixture-s4-t06-{input_pack.company.lower()}-strict-kernel"
            ),
            "execution_mode": (
                "zero_call_s4_t06_strict_truth_kernel_full_fake"
            ),
            "provider": "openai",
            "model": "fixture-strict-json-schema",
            "model_ref": "openai:fixture-strict-json-schema",
            "api_key_env": "OPENAI_API_KEY",
            "base_url": BOUNDED_OPENAI_BASE_URL,
            "strict_truth_kernel_policy_ref": (
                S4_STRICT_TRUTH_KERNEL_POLICY_REF
            ),
            "provider_capability_ref": (
                S4_STRICT_JSON_SCHEMA_PROVIDER_CAPABILITY_REF
            ),
            "non_authoritative_narrative_shell_ref": (
                S4_NON_AUTHORITATIVE_NARRATIVE_SHELL_REF
            ),
        }
    )


class _StrictResponsesFake:
    def __init__(self, mutator: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.mutator = mutator

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        request = json.loads(kwargs["input"][1]["content"])
        schema = kwargs["text"]["format"]["schema"]
        properties = schema["properties"]
        item_properties = properties["fact_judgments"]["items"][
            "properties"
        ]
        output = {
            "program_cell_id": properties["program_cell_id"]["enum"][0],
            "fact_judgments": [
                {
                    "numeric_alias": (
                        item_properties["numeric_alias"]["enum"][0]
                    ),
                    "direction": "supports",
                    "materiality": "high",
                    "confidence": "high",
                    "interpretation_code": "directional_support",
                    "counterevidence_aliases": [],
                }
            ],
            "terminal_class": "supported",
        }
        if self.mutator is not None:
            self.mutator(output)
        self.calls.append(
            {
                "request": request,
                "schema": deepcopy(schema),
                "output": deepcopy(output),
            }
        )
        return {
            "status": "ok",
            "call_id": f"fixture-strict-{len(self.calls)}",
            "provider": "openai",
            "model": "fixture-strict-json-schema",
            "content": "",
            "finish_reason": "completed",
            "response_status": "completed",
            "response_output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                output,
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        }
                    ],
                }
            ],
            "input_tokens": 10,
            "output_tokens": 30,
            "total_tokens": 40,
            "latency_ms": 1,
            "transport_attempt_count": 1,
            "raw_response": {
                "usage": {
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 10,
                }
            },
        }


class _OpenAIChatFake:
    def __init__(self, inner: _NumericIdentitySafeFake) -> None:
        self.inner = inner

    @property
    def calls(self) -> Any:
        return self.inner.calls

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        result = dict(self.inner(**kwargs))
        result["provider"] = "openai"
        result["model"] = "fixture-strict-json-schema"
        result["call_id"] = f"fixture-chat-{len(self.calls)}"
        return result


def test_strict_truth_kernel_schema_is_alias_enum_only_and_local_rendered() -> None:
    input_pack, _ = _case_fixture_input_and_admission("DELL")
    policy = StrictTruthKernelPolicy.from_cell_input(
        _adapted_first_cell(input_pack)
    )
    schema = policy.json_schema()
    serialized = json.dumps(schema, ensure_ascii=False)
    assert schema["additionalProperties"] is False
    assert all(
        field not in serialized
        for field in (
            "statement",
            "boundary",
            "exact_value",
            "currency",
            "period",
            "entity_ref",
            "lineage",
        )
    )
    provider_output = {
        "program_cell_id": policy.program_cell_id,
        "fact_judgments": [
            {
                "numeric_alias": policy.strict_numeric_aliases[0],
                "direction": "supports",
                "materiality": "high",
                "confidence": "high",
                "interpretation_code": "directional_support",
                "counterevidence_aliases": [],
            }
        ],
        "terminal_class": "supported",
    }
    rendered, violation = policy.render_provider_output(provider_output)
    assert violation is None
    assert rendered is not None
    assert rendered["fact_layer"][0]["support_refs"] == [
        policy.numeric_policy.rows[0].numeric_ref
    ]
    assert (
        policy.numeric_policy.rows[0].rendered_clause()
        in rendered["fact_layer"][0]["statement"]
    )


@pytest.mark.parametrize(
    ("mutation", "subtype"),
    (
        (
            lambda output: output["fact_judgments"][0].update(
                {"numeric_alias": "N999"}
            ),
            "numeric_alias_unknown_or_cross_case",
        ),
        (
            lambda output: output["fact_judgments"][0].update(
                {"direction": "invented"}
            ),
            "enum_value_invalid",
        ),
        (
            lambda output: output.update({"free_text": "forbidden"}),
            "top_level_shape_invalid",
        ),
        (
            lambda output: output["fact_judgments"].append(
                deepcopy(output["fact_judgments"][0])
            ),
            "numeric_alias_duplicate",
        ),
        (
            lambda output: output["fact_judgments"][0].update(
                {
                    "counterevidence_aliases": [
                        "E44E454E88A001",
                        "E44E454E88A001",
                    ]
                }
            ),
            "counterevidence_alias_duplicate",
        ),
    ),
)
def test_strict_truth_kernel_rejects_wrong_alias_enum_extra_text_and_duplicate(
    mutation: Any,
    subtype: str,
) -> None:
    input_pack, _ = _case_fixture_input_and_admission("DELL")
    policy = StrictTruthKernelPolicy.from_cell_input(
        _adapted_first_cell(input_pack)
    )
    output = {
        "program_cell_id": policy.program_cell_id,
        "fact_judgments": [
            {
                "numeric_alias": policy.strict_numeric_aliases[0],
                "direction": "supports",
                "materiality": "medium",
                "confidence": "medium",
                "interpretation_code": "directional_support",
                "counterevidence_aliases": [],
            }
        ],
        "terminal_class": "supported",
    }
    mutation(output)
    rendered, violation = policy.render_provider_output(output)
    assert rendered is None
    assert violation is not None
    assert violation.subtype == subtype


def test_strict_alias_is_case_projection_scoped() -> None:
    dell_input, _ = _case_fixture_input_and_admission("DELL")
    mu_input, _ = _case_fixture_input_and_admission("MU")
    dell = StrictTruthKernelPolicy.from_cell_input(
        _adapted_first_cell(dell_input)
    )
    mu = StrictTruthKernelPolicy.from_cell_input(
        _adapted_first_cell(mu_input)
    )
    assert dell.strict_numeric_aliases[0] != (
        mu.strict_numeric_aliases[0]
    )
    rendered, violation = dell.render_provider_output(
        {
            "program_cell_id": dell.program_cell_id,
            "fact_judgments": [
                {
                    "numeric_alias": mu.strict_numeric_aliases[0],
                    "direction": "supports",
                    "materiality": "high",
                    "confidence": "high",
                    "interpretation_code": "directional_support",
                    "counterevidence_aliases": [],
                }
            ],
            "terminal_class": "supported",
        }
    )
    assert rendered is None
    assert violation is not None
    assert violation.subtype == (
        "numeric_alias_unknown_or_cross_case"
    )


def test_missing_strict_capability_fails_before_any_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission = _case_fixture_input_and_admission("DELL")
    admission = _strict_admission(input_pack, admission)
    calls: list[dict[str, Any]] = []

    def counting_provider(**kwargs: Any) -> Mapping[str, Any]:
        calls.append(dict(kwargs))
        raise AssertionError("provider_must_not_be_called")

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-not-a-real-secret")
    executor = S3ThreeCellBoundedAgentExecutor(
        DeepSeekS3ThreeCellNodeExecutor(
            chat_completion_fn=counting_provider,
            responses_completion_fn=counting_provider,
            strict_truth_kernel_adapter=None,
        )
    )
    with pytest.raises(
        ValueError,
        match=(
            "s4_strict_truth_kernel_capability_unbound_pre_provider"
        ),
    ):
        executor.execute(
            input_pack,
            admission,
            run_identity={"research_run_id": "fixture-capability-missing"},
        )
    assert calls == []


@pytest.mark.parametrize(
    "mutation_kind",
    (
        "wrong_alias",
        "cross_case_alias",
        "numeric_mutation",
        "extra_text",
        "duplicate_counterevidence",
    ),
)
def test_strict_runtime_negative_fixture_fails_on_first_call_before_artifact(
    monkeypatch: pytest.MonkeyPatch,
    mutation_kind: str,
) -> None:
    input_pack, admission = _case_fixture_input_and_admission("DELL")
    admission = _strict_admission(input_pack, admission)
    _, specialists = _shared_local_id_specialists()
    chat_fake = _OpenAIChatFake(
        _NumericIdentitySafeFake(input_pack, specialists)
    )
    mu_input, _ = _case_fixture_input_and_admission("MU")
    mu_policy = StrictTruthKernelPolicy.from_cell_input(
        _adapted_first_cell(mu_input)
    )

    def mutate(output: dict[str, Any]) -> None:
        if mutation_kind == "wrong_alias":
            output["fact_judgments"][0]["numeric_alias"] = "NUNKNOWN"
        elif mutation_kind == "cross_case_alias":
            output["fact_judgments"][0]["numeric_alias"] = (
                mu_policy.strict_numeric_aliases[0]
            )
        elif mutation_kind == "numeric_mutation":
            output["fact_judgments"][0]["numeric_value"] = "999999"
        elif mutation_kind == "duplicate_counterevidence":
            output["fact_judgments"][0][
                "counterevidence_aliases"
            ] = [
                "E44E454E88A001",
                "E44E454E88A001",
            ]
        else:
            output["free_text"] = "forbidden"

    responses_fake = _StrictResponsesFake(mutator=mutate)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-not-a-real-secret")
    with pytest.raises(BoundedAgentExecutionError) as caught:
        build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=chat_fake,
            responses_completion_fn=responses_fake,
        ).execute(
            input_pack,
            admission,
            run_identity={
                "research_run_id": f"fixture-negative-{mutation_kind}"
            },
        )
    assert len(responses_fake.calls) == 1
    assert len(chat_fake.calls) == 0
    assert len(caught.value.provider_output_captures) == 1
    assert caught.value.failure_observation["failure_codes"][0].startswith(
        "s4_strict_truth_kernel_invalid:"
    )


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_cases_full_fake_keep_twelve_callbacks_and_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
) -> None:
    input_pack, admission = _case_fixture_input_and_admission(ticker)
    admission = _strict_admission(input_pack, admission)
    _, specialists = _shared_local_id_specialists()
    specialists = {
        cell_id: deepcopy(specialist)
        for cell_id, specialist in specialists.items()
    }
    inner_chat = _NumericIdentitySafeFake(
        input_pack,
        specialists,
    )
    chat_fake = _OpenAIChatFake(inner_chat)
    responses_fake = _StrictResponsesFake()
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-not-a-real-secret")

    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=chat_fake,
        responses_completion_fn=responses_fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": f"fixture-s4-t06-{ticker.lower()}",
            "attempt_id": f"fixture-s4-t06-{ticker.lower()}",
        },
    )

    assert len(responses_fake.calls) == 3
    assert len(chat_fake.calls) == 9
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert result.execution_observation["observed_counts"][
        "model_calls"
    ] == 12
    assert all(
        call["schema"]["additionalProperties"] is False
        for call in responses_fake.calls
    )
    assert all(
        "uniqueItems"
        not in json.dumps(call["schema"], ensure_ascii=False)
        for call in responses_fake.calls
    )


def test_optional_failure_observation_cannot_veto_terminal_core() -> None:
    known, rejected = normalize_optional_failure_observation(
        {
            "failure_codes": [
                "s4_case_numeric_authority_provider_narrative_invalid"
            ],
            "failure_telemetry": {
                "case_numeric_authority": {
                    "contract_ref": (
                        "fin01.s4.case_numeric_authority_projection_and_"
                        "deterministic_rendering:v1"
                    ),
                    "acceptance_layer": "L1_hard_integrity",
                    "failure_subtype": "provider_authored_numeric_token",
                    "field_id": "fact_layer.statement",
                    "failing_item_count": 1,
                }
            },
        }
    )
    assert rejected is False
    assert is_registered_failure_observation(
        known["failure_telemetry"]["registered_observation"]
    )

    unknown, rejected = normalize_optional_failure_observation(
        {
            "failure_codes": [
                "s3_bounded_profile_result_validation_failed"
            ],
            "failure_telemetry": {
                "unregistered_extension": {
                    "credential": "must-not-persist"
                }
            },
        }
    )
    assert rejected is True
    assert "failure_telemetry" not in unknown
    assert OBSERVATION_EXTENSION_REJECTED_CODE in unknown[
        "failure_codes"
    ]
    assert "credential" not in json.dumps(unknown)


class _FailureObservationExtensionProbe(_CanonicalTypedFailureProbe):
    def __init__(self, extension_kind: str) -> None:
        self.extension_kind = extension_kind

    def execute(
        self,
        input_pack: Any,
        admission: Any,
        *,
        run_identity: Mapping[str, str],
    ) -> Any:
        try:
            return super().execute(
                input_pack,
                admission,
                run_identity=run_identity,
            )
        except BoundedAgentExecutionError as exc:
            if self.extension_kind == "registered":
                exc.failure_observation["failure_telemetry"] = {
                    "case_numeric_authority": {
                        "contract_ref": (
                            "fin01.s4.case_numeric_authority_projection_and_"
                            "deterministic_rendering:v1"
                        ),
                        "acceptance_layer": "L1_hard_integrity",
                        "failure_subtype": (
                            "provider_authored_numeric_token"
                        ),
                        "field_id": "fact_layer.statement",
                        "failing_item_count": 1,
                    }
                }
            else:
                exc.failure_observation["failure_telemetry"] = {
                    "unregistered_secret_like_extension": {
                        "credential": "must-not-persist"
                    }
                }
            raise


@pytest.mark.parametrize("extension_kind", ("registered", "unknown"))
def test_failure_terminal_core_is_atomic_for_registered_and_unknown_extensions(
    tmp_path: Path,
    extension_kind: str,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / f"{extension_kind}-failure-runtime",
        repo_root=ROOT,
    )
    app = create_app(
        tmp_path / f"{extension_kind}-failure.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_admission(),
        bounded_agent_executor=(
            _FailureObservationExtensionProbe(extension_kind)
        ),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(
            client,
            key=f"s4-t06-{extension_kind}",
        )
        response = _create_work_unit(
            client,
            case,
            plan,
            key=f"s4-t06-{extension_kind}-bounded",
        )
    assert response.status_code == 202, response.text

    events = case_service._facade.store.list_events()
    failed_event = next(
        row
        for row in events
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    observation = failed_event["payload"]["failure_observation"]
    state_triplet = [
        case_service._facade.store.list_latest(
            "canonical_work_units",
            case_id=case["case_id"],
        )[0]["state"],
        case_service._facade.store.list_latest(
            "canonical_attempts",
            case_id=case["case_id"],
        )[0]["state"],
        case_service._facade.store.list_latest(
            "canonical_research_run_versions",
            case_id=case["case_id"],
        )[0]["state"],
    ]
    assert state_triplet == ["failed", "failed", "failed"]
    assert len(
        failed_event["payload"]["provider_output_capture_refs"]
    ) == 12
    assert (
        case_service._facade.store.list_latest(
            "canonical_artifact_versions",
            case_id=case["case_id"],
        )
        == []
    )
    assert len(
        case_service._facade.store.list_latest(
            "canonical_attempts",
            case_id=case["case_id"],
        )
    ) == 1
    serialized = json.dumps(failed_event, ensure_ascii=False)
    assert "must-not-persist" not in serialized
    if extension_kind == "registered":
        assert is_registered_failure_observation(
            observation["failure_telemetry"][
                "registered_observation"
            ]
        )
    else:
        assert "failure_telemetry" not in observation
        assert OBSERVATION_EXTENSION_REJECTED_CODE in observation[
            "failure_codes"
        ]


def test_implementation_record_binds_exact_code_and_next_gate() -> None:
    implementation = json.loads(
        IMPLEMENTATION.read_text(encoding="utf-8")
    )
    assert implementation["status"] == (
        "pass_zero_call_implementation_fixture_proven_"
        "engineering_proof_and_provider_capability_binding_decision_pending"
    )
    assert implementation["fixture_proof"][
        "per_case_provider_callbacks"
    ] == 12
    assert implementation["fixture_proof"][
        "per_case_logical_artifacts"
    ] == 9
    assert set(implementation["observed_counts"].values()) == {0}
    assert implementation["scope_limit"][
        "zero_call_implementation_bundles_consumed"
    ] == 1
    assert implementation["next_action"] == (
        "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-FRESH-ENGINEERING-"
        "PROOF-AND-PROVIDER-CAPABILITY-BINDING-DECISION"
    )
    fresh_proof = json.loads(
        FRESH_PROOF_DECISION.read_text(encoding="utf-8")
    )
    assert implementation["exact_code_bindings"] == fresh_proof[
        "fresh_engineering_proof"
    ]["exact_code_bindings"]
    assert hashlib.sha256(IMPLEMENTATION.read_bytes()).hexdigest() == (
        fresh_proof["source_implementation"]["sha256"]
    )
