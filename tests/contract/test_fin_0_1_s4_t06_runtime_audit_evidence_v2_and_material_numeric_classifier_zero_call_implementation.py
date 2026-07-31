from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_contract_policies import (
    CaseNumericAuthorityPolicy,
    CaseNumericAuthorityViolation,
    S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
    S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BoundedAgentExecutionError,
    BoundedAgentExecutionOutput,
    BoundedAgentInputPack,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.case_service import CaseService
from sec_agent.canonical_runtime.failure_observation_policy import (
    is_registered_failure_observation,
    registered_failure_observation,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_provider_output_capture_persistence import (
    _accepted_case,
    _create_work_unit,
)
from test_fin_0_1_s4_t06_mu_current_case_aware_delivery_identity_boundary_zero_call_implementation import (
    _case_runtime,
)


class _ReportingPeriodOrMaterialFake:
    def __init__(
        self,
        base: Any,
        *,
        material_text: str | None = None,
    ) -> None:
        self._base = base
        self.material_text = material_text
        self.injected = False

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self._base.calls

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        response = dict(self._base(**kwargs))
        request = self.calls[-1]["request"]
        if (
            not self.injected
            and str(request.get("node_id") or "").startswith(
                "domain_specialist:"
            )
            and request.get("segment_id")
            == "facts_explanation_and_terminal"
        ):
            output = json.loads(str(response["content"]))
            if self.material_text is None:
                contract = request["case_numeric_authority_contract"]
                labels = [
                    str(value)
                    for value in contract[
                        "allowed_reporting_period_labels"
                    ]
                    if any(character.isdigit() for character in str(value))
                ]
                prefix = next(
                    (
                        value.replace("_", " ")
                        for value in labels
                        if value.upper().startswith(("FQ", "FY", "Q"))
                    ),
                    labels[0],
                )
            else:
                prefix = self.material_text
            output["fact_layer"][0]["statement"] = (
                f"{prefix} "
                + str(output["fact_layer"][0]["statement"])
            )
            response["content"] = json.dumps(
                output,
                ensure_ascii=False,
                sort_keys=True,
            )
            self.injected = True
        return response


def _v2_runtime(
    ticker: str,
    *,
    material_text: str | None = None,
) -> tuple[
    BoundedAgentInputPack,
    S3ThreeCellBoundedAgentAdmission,
    _ReportingPeriodOrMaterialFake,
]:
    input_pack, admission, base = _case_runtime(ticker)
    v2_admission = admission.model_copy(
        update={
            "admission_id": (
                f"fixture-s4-t06-{ticker.lower()}-audit-numeric-v2"
            ),
            "execution_mode": "zero_call_audit_numeric_v2",
            "case_numeric_authority_policy_ref": (
                S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF
            ),
            "provider_output_capture_policy_ref": (
                S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            ),
        }
    )
    v2_admission.assert_profile_admissible()
    return (
        input_pack,
        v2_admission,
        _ReportingPeriodOrMaterialFake(
            base,
            material_text=material_text,
        ),
    )


def _execute_v2(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
    *,
    material_text: str | None = None,
) -> tuple[BoundedAgentExecutionOutput, _ReportingPeriodOrMaterialFake]:
    input_pack, admission, fake = _v2_runtime(
        ticker,
        material_text=material_text,
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": (
                f"fixture-s4-t06-{ticker.lower()}-audit-numeric-v2"
            ),
            "attempt_id": (
                f"fixture-s4-t06-{ticker.lower()}-audit-numeric-v2"
            ),
        },
    )
    return result, fake


def test_v1_classifier_is_immutable_while_v2_allows_bound_period_labels() -> None:
    input_pack, _, _ = _v2_runtime("MU")
    raw_cell = input_pack.cell_inputs[1]
    v1 = CaseNumericAuthorityPolicy.from_cell_input(
        S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
            raw_cell,
            policy_ref=S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
        )
    )
    v2 = CaseNumericAuthorityPolicy.from_cell_input(
        S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
            raw_cell,
            policy_ref=S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
        )
    )
    assert v1.first_provider_narrative_violation(
        {"fact_layer": [{"statement": "FQ3 2026 定性判断"}]}
    ) is not None
    assert v2.first_provider_narrative_violation(
        {"fact_layer": [{"statement": "FQ3 2026 定性判断"}]}
    ) is None
    matches = v2.provider_narrative_matches(
        {"fact_layer": [{"statement": "FQ3 2026 定性判断"}]}
    )
    assert [match.safe_index() for match in matches] == [
        {
            "validator_rule_code": (
                "material_numeric_provider_narrative_boundary_v2"
            ),
            "field_path": "$.fact_layer[0].statement",
            "semantic_class": "reporting_period_label",
            "terminal": False,
            "raw_match_persisted": False,
        }
    ]


def test_r4_two_path_reporting_period_replay_is_nonterminal_under_v2() -> None:
    input_pack, _, _ = _v2_runtime("MU")
    policy = CaseNumericAuthorityPolicy.from_cell_input(
        S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
            input_pack.cell_inputs[1],
            policy_ref=S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
        )
    )
    replay = {
        "fact_layer": [{"statement": "FQ3 2026 需求保持韧性"}],
        "explanation_layer": ["FQ3 2026 供需机制仍需跟踪"],
    }
    matches = policy.provider_narrative_matches(replay)
    assert policy.first_provider_narrative_violation(replay) is None
    assert {
        (match.field_path, match.semantic_class, match.terminal)
        for match in matches
    } == {
        (
            "$.fact_layer[0].statement",
            "reporting_period_label",
            False,
        ),
        (
            "$.explanation_layer[0]",
            "reporting_period_label",
            False,
        ),
    }


@pytest.mark.parametrize(
    ("text", "semantic_class"),
    (
        ("$4.1B 增长", "financial_amount"),
        ("84.6% 毛利率", "percentage"),
        ("120 days 库存", "measurement"),
        ("FY1900 展望", "unknown_reporting_period_label"),
        ("42 定性判断", "material_numeric_value"),
    ),
)
def test_v2_keeps_material_or_unknown_numeric_surfaces_fail_closed(
    text: str,
    semantic_class: str,
) -> None:
    input_pack, _, _ = _v2_runtime("MU")
    policy = CaseNumericAuthorityPolicy.from_cell_input(
        S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
            input_pack.cell_inputs[1],
            policy_ref=S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
        )
    )
    violation = policy.first_provider_narrative_violation(
        {"explanation_layer": [text]}
    )
    assert violation is not None
    assert violation.subtype == "provider_authored_material_numeric_token"
    assert violation.match_paths == ("$.explanation_layer[0]",)
    assert semantic_class in violation.semantic_classes


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_full_fake_uses_v2_capture_and_bound_period_classification(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
) -> None:
    result, fake = _execute_v2(monkeypatch, ticker)
    assert [len(fake.calls), len(result.provider_output_captures)] == [
        12,
        12,
    ]
    assert len(result.artifacts) == 9
    assert all(
        capture["capture_policy_ref"]
        == S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
        for capture in result.provider_output_captures
    )
    first = result.provider_output_captures[0]
    assert first["model_visible_request"][0]["role"] == "system"
    assert json.loads(
        first["model_visible_request"][1]["content"]
    ) == fake.calls[0]["request"]
    assert first["model_visible_request_digest"] == canonical_digest(
        first["model_visible_request"]
    )
    assert first["nonsecret_inference_arguments_digest"] == canonical_digest(
        first["nonsecret_inference_arguments"]
    )
    assert first["provider_route_digest"] == canonical_digest(
        first["provider_route"]
    )
    assert any(
        row["semantic_class"] == "reporting_period_label"
        and row["terminal"] is False
        for row in first["validator_match_index"]
    )
    assert first["credentials_included"] is False
    assert "DEEPSEEK_API_KEY" not in json.dumps(first)


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_material_failure_binds_safe_path_class_and_capture_sequence(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
) -> None:
    with pytest.raises(BoundedAgentExecutionError) as caught:
        _execute_v2(
            monkeypatch,
            ticker,
            material_text="$4.1B",
        )
    error = caught.value
    assert len(error.provider_output_captures) == 1
    capture = error.provider_output_captures[0]
    assert capture["validator_match_index"] == [
        {
            "validator_rule_code": (
                "material_numeric_provider_narrative_boundary_v2"
            ),
            "field_path": "$.fact_layer[0].statement",
            "semantic_class": "financial_amount",
            "terminal": True,
            "raw_match_persisted": False,
        }
    ]
    telemetry = error.failure_observation["failure_telemetry"][
        "case_numeric_authority"
    ]
    assert telemetry["capture_sequence"] == 1
    assert telemetry["match_paths"] == ["$.fact_layer[0].statement"]
    registered = registered_failure_observation(
        "case_numeric_authority",
        telemetry,
    )
    assert is_registered_failure_observation(registered)


def _v2_capture(*, unsafe: bool = False) -> dict[str, Any]:
    request = [
        {"role": "system", "content": "Return one bounded JSON object."},
        {
            "role": "user",
            "content": (
                "Authorization: Bearer abcdefghijklmnopqrstuvwxyz"
                if unsafe
                else '{"case":"fixture","period":"FQ3 2026"}'
            ),
        },
    ]
    arguments = {
        "api_surface": "chat_completions",
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
        "max_tokens": 128,
        "timeout_seconds": 30,
        "stream": False,
        "enable_thinking": False,
        "reasoning_effort": "none",
        "tools": None,
        "tool_choice": None,
    }
    route = {
        "base_url": "https://api.deepseek.com/beta",
        "request_path": "/chat/completions",
    }
    return {
        "capture_policy_ref": (
            S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
        ),
        "capture_sequence": 1,
        "stage": "domain_specialist:value_and_profit_capture",
        "call_id": "call-audit-v2-1",
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "provider_status": "ok",
        "finish_reason": "stop",
        "assistant_output_text": '{"statement":"$4.1B"}',
        "assistant_output_present": True,
        "model_visible_request": request,
        "model_visible_request_digest": canonical_digest(request),
        "nonsecret_inference_arguments": arguments,
        "nonsecret_inference_arguments_digest": canonical_digest(arguments),
        "provider_route": route,
        "provider_route_digest": canonical_digest(route),
        "validator_match_index": [
            {
                "validator_rule_code": (
                    "material_numeric_provider_narrative_boundary_v2"
                ),
                "field_path": "$.statement",
                "semantic_class": "financial_amount",
                "terminal": True,
                "raw_match_persisted": False,
            }
        ],
        "raw_request_envelope_included": False,
        "raw_provider_response_included": False,
        "private_reasoning_included": False,
        "credentials_included": False,
    }


class _V2CapturedFailureProbe:
    def __init__(self, *, unsafe: bool = False) -> None:
        self.unsafe = unsafe

    def execute(
        self,
        input_pack: BoundedAgentInputPack,
        admission: S3ThreeCellBoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> BoundedAgentExecutionOutput:
        violation = CaseNumericAuthorityViolation(
            subtype="provider_authored_material_numeric_token",
            field_id="statement",
            failing_item_count=1,
            contract_ref=S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
            match_paths=("$.statement",),
            semantic_classes=("financial_amount",),
        )
        raise BoundedAgentExecutionError(
            "domain_specialist:value_and_profit_capture",
            usage_receipts=[],
            estimated_cost_usd=0.0,
            failure_codes=(
                "s4_case_numeric_authority_provider_narrative_invalid",
            ),
            case_numeric_authority=violation.telemetry(
                capture_sequence=1,
                provider_phase="domain_specialist:value_and_profit_capture",
            ),
            provider_output_captures=[
                _v2_capture(unsafe=self.unsafe)
            ],
        )


def _v2_admission() -> S3ThreeCellBoundedAgentAdmission:
    return S3ThreeCellBoundedAgentAdmission(
        admission_id="fin01-s4-t06-audit-evidence-v2-probe",
        execution_enabled=False,
        execution_mode="audit_evidence_v2_contract_probe",
        provider_output_capture_policy_ref=(
            S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
        ),
    )


def test_v2_failure_capture_is_atomic_replayable_indexed_and_not_promoted(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "audit-v2-runtime",
        repo_root=ROOT,
    )
    app = create_app(
        tmp_path / "audit-v2.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_v2_admission(),
        bounded_agent_executor=_V2CapturedFailureProbe(),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="audit-v2")
        response = _create_work_unit(
            client,
            case,
            plan,
            key="audit-v2-bounded",
        )
    assert response.status_code == 202
    failed_event = next(
        row
        for row in case_service._facade.store.list_events()
        if row.get("event_type") == "RESEARCH_RUN_FAILED"
    )
    refs = failed_event["payload"]["provider_output_capture_refs"]
    assert refs[0]["validator_match_index"][0] == {
        "validator_rule_code": (
            "material_numeric_provider_narrative_boundary_v2"
        ),
        "field_path": "$.statement",
        "semantic_class": "financial_amount",
        "terminal": True,
        "raw_match_persisted": False,
    }
    assert refs[0]["object_digest"]
    replayed = (
        case_service._facade.read_research_run_provider_output_captures(
            failed_event["task_run_id"]
        )
    )
    assert replayed[0]["model_visible_request"][1]["content"] == (
        '{"case":"fixture","period":"FQ3 2026"}'
    )
    assert replayed[0]["assistant_output_text"] == '{"statement":"$4.1B"}'
    assert case_service._facade.store.list_latest(
        "canonical_artifact_versions",
        case_id=case["case_id"],
    ) == []


def test_v2_rejects_credential_bearing_request_before_terminal_write(
    tmp_path: Path,
) -> None:
    case_service = CaseService.for_fixture_root(
        tmp_path / "audit-v2-secret-runtime",
        repo_root=ROOT,
    )
    app = create_app(
        tmp_path / "audit-v2-secret.sqlite",
        p02_case_service=case_service,
        bounded_agent_admission=_v2_admission(),
        bounded_agent_executor=_V2CapturedFailureProbe(unsafe=True),
    )
    with TestClient(app) as client:
        case, plan = _accepted_case(client, key="audit-v2-secret")
        with pytest.raises(
            Exception,
            match="provider_interaction_audit_capture_contract_invalid",
        ):
            _create_work_unit(
                client,
                case,
                plan,
                key="audit-v2-secret-bounded",
            )
    assert not any(
        row.get("event_type") == "RESEARCH_RUN_FAILED"
        for row in case_service._facade.store.list_events()
    )
