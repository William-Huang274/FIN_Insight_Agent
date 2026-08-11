from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF,
    S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
    S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BoundedAgentExecutionError,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3_TASK_CLAIM_LINK_POLICY_REF,
    S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.prepare_fin_ia_0_1_s3_t09_three_cell_exact_input import (
    prepare,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    EXPECTED_RUNTIME_ROOT_NAME,
    LEGACY_TARGET,
    execute,
)
from scripts.releases.supervise_fin_ia_0_1_s3_t09_exact_live_execution import (
    _launch_detached,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_deepseek_live_execution_runner import (
    ADMISSION,
    _InvalidShapeFakeProvider,
)
from test_fin_0_1_s4_t06_mu_current_case_aware_delivery_identity_boundary_zero_call_implementation import (
    _case_runtime,
)


class _TemporalAuthorityFake:
    def __init__(
        self,
        base: Any,
        *,
        inject_financial_number: bool = False,
        inject_unknown_date_alias: bool = False,
    ) -> None:
        self._base = base
        self.inject_financial_number = inject_financial_number
        self.inject_unknown_date_alias = inject_unknown_date_alias
        self.action_calls = 0
        self.temporal_provider_outputs: list[dict[str, Any]] = []

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self._base.calls

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        request = json.loads(kwargs["messages"][1]["content"])
        if (
            request.get("segment_id")
            != "actionable_what_would_change_tasks"
        ):
            return dict(self._base(**kwargs))
        self.calls.append({"kwargs": dict(kwargs), "request": request})
        contract = request["WWC_judgment_atom_contract"]
        self.action_calls += 1
        claim_alias = contract["allowed_claims"][0]["claim_alias"]
        authority_alias = contract["allowed_authorities"][0][
            "authority_alias"
        ]
        date_alias = contract["allowed_date_aliases"][0]["date_alias"]
        if self.action_calls == 1:
            start_code = "bound_date"
            start_alias = date_alias
            review_code = "next_quarter_end"
            review_alias = "NONE"
        elif self.action_calls == 2:
            start_code = "when_rule_condition_met"
            start_alias = "NONE"
            review_code = "bound_date"
            review_alias = date_alias
        else:
            start_code = "next_authority_event"
            start_alias = "NONE"
            review_code = "unscheduled"
            review_alias = "NONE"
        if self.inject_unknown_date_alias:
            review_code = "bound_date"
            review_alias = "D999"
        output = {
            "program_cell_id": request["analysis_input"]["cell_input"][
                "program_cell_id"
            ],
            "what_would_change_judgment_atoms": [
                {
                    "claim_alias": claim_alias,
                    "primary_authority_alias": authority_alias,
                    "authority_aliases": [authority_alias],
                    "metric_or_observation": (
                        "$4.1B demand observation"
                        if self.inject_financial_number
                        else "qualitative demand observation"
                    ),
                    "rule_type": "evidence_confirmation",
                    "comparator_or_condition": "authority confirms condition",
                    "threshold_or_observation": "qualitative confirmation",
                    "start_trigger_code": start_code,
                    "start_date_alias": start_alias,
                    "review_timing_code": review_code,
                    "review_date_alias": review_alias,
                    "expected_claim_transition": "strengthen",
                    "fallback_stop_condition": "authority withdraws support",
                }
            ],
        }
        self.temporal_provider_outputs.append(output)
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": json.dumps(
                output,
                ensure_ascii=False,
                sort_keys=True,
            ),
            "input_tokens": 10,
            "output_tokens": 10,
            "total_tokens": 20,
            "call_id": f"fixture-temporal-{len(self.calls)}",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "latency_ms": 1,
            "transport_attempt_count": 1,
            "raw_response": {
                "usage": {
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 10,
                }
            },
        }


def _temporal_runtime(ticker: str) -> tuple[Any, Any, Any]:
    input_pack, admission, base = _case_runtime(ticker)
    temporal_admission = admission.model_copy(
        update={
            "admission_id": (
                f"fixture-s4-t06-{ticker.lower()}-temporal-authority-v2"
            ),
            "execution_mode": "zero_call_temporal_authority_v2",
            "wwc_judgment_atom_policy_ref": (
                S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
            ),
            "transport_ref": (
                S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
            ),
            "task_claim_link_policy_ref": S3_TASK_CLAIM_LINK_POLICY_REF,
            "case_numeric_authority_policy_ref": (
                S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF
            ),
            "provider_output_capture_policy_ref": (
                S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            ),
        }
    )
    temporal_admission.assert_profile_admissible()
    return input_pack, temporal_admission, base


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_temporal_authority_full_fake_reaches_twelve_calls_and_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
) -> None:
    input_pack, admission, base = _temporal_runtime(ticker)
    fake = _TemporalAuthorityFake(base)
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
                f"fixture-s4-t06-{ticker.lower()}-temporal-authority-v2"
            ),
            "attempt_id": (
                f"fixture-s4-t06-{ticker.lower()}-temporal-authority-v2"
            ),
        },
    )
    assert len(fake.calls) == 12
    assert fake.action_calls == 3
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    provider_text = json.dumps(
        fake.temporal_provider_outputs,
        ensure_ascii=False,
    )
    assert "deadline_or_review_date" not in provider_text
    assert "2026-09-30" not in provider_text
    artifact_text = json.dumps(
        [row.model_dump(mode="json") for row in result.artifacts],
        ensure_ascii=False,
    )
    assert input_pack.as_of in artifact_text
    assert "unscheduled" in artifact_text
    if input_pack.as_of.startswith("2026-07-26"):
        assert "2026-09-30" in artifact_text


def test_temporal_v2_is_versioned_and_v1_schema_is_immutable() -> None:
    input_pack, admission, base = _temporal_runtime("MU")
    fake = _TemporalAuthorityFake(base)
    assert admission.wwc_judgment_atom_policy_ref == (
        S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
    )
    assert (
        S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
        != S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
    )
    assert fake.action_calls == 0
    assert input_pack.as_of


def test_unknown_temporal_alias_fails_closed_with_typed_atom_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, base = _temporal_runtime("MU")
    fake = _TemporalAuthorityFake(base, inject_unknown_date_alias=True)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    with pytest.raises(BoundedAgentExecutionError) as caught:
        build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=fake,
        ).execute(
            input_pack,
            admission,
            run_identity={
                "research_run_id": "fixture-temporal-alias-failure",
                "attempt_id": "fixture-temporal-alias-failure",
            },
        )
    telemetry = caught.value.failure_observation["failure_telemetry"][
        "segmented_specialist_WWC_judgment_atom"
    ]
    assert telemetry["validator_contract"] == (
        S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
    )
    assert telemetry["failure_subtype"] == (
        "review_date_alias_binding_invalid"
    )
    assert telemetry["raw_atom_persisted"] is False


def test_temporal_v2_does_not_weaken_material_financial_number_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, base = _temporal_runtime("MU")
    fake = _TemporalAuthorityFake(base, inject_financial_number=True)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    with pytest.raises(BoundedAgentExecutionError) as caught:
        build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=fake,
        ).execute(
            input_pack,
            admission,
            run_identity={
                "research_run_id": "fixture-temporal-financial-failure",
                "attempt_id": "fixture-temporal-financial-failure",
            },
        )
    telemetry = caught.value.failure_observation["failure_telemetry"][
        "case_numeric_authority"
    ]
    assert telemetry["acceptance_layer"] == "L1_hard_integrity"
    assert "financial_amount" in telemetry["semantic_classes"]


def test_runner_uses_admission_bound_capture_v2_and_materializes_failure_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_root = tmp_path / EXPECTED_RUNTIME_ROOT_NAME
    prepare(runtime_root)
    payload = json.loads(ADMISSION.read_text(encoding="utf-8"))
    payload["provider_output_capture_policy_ref"] = (
        S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
    )
    admission_path = tmp_path / "capture-v2-admission.json"
    admission_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    admission_digest = canonical_digest(payload)
    target = replace(
        LEGACY_TARGET,
        admission_digest=admission_digest,
        admission_ref=str(admission_path),
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    result = execute(
        runtime_root,
        admission_path,
        chat_completion_fn=_InvalidShapeFakeProvider(),
        target=target,
    )
    assert result["status"] == (
        "terminal_failed_admission_consumed_no_retry"
    )
    capture = result["provider_execution"]["provider_output_capture"]
    assert capture["policy_ref"] == (
        S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
    )
    assert capture["capture_count"] == 1
    assert capture["restricted_readback_count"] == 1
    assert result["runtime_materialization_findings"] == []
    assert (runtime_root / "live_execution_result.json").is_file()


def test_supervised_failure_receipt_hashes_final_stderr_without_provider_call(
    tmp_path: Path,
) -> None:
    supervision_root = tmp_path / "supervision"
    runner = ROOT / (
        "scripts/releases/"
        "run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py"
    )
    command = [
        sys.executable,
        str(runner),
        "execute",
        "--runtime-root",
        str(tmp_path / "missing-runtime"),
        "--admission",
        str(tmp_path / "missing-admission.json"),
    ]
    _launch_detached(
        supervision_root,
        command,
        minimum_lifecycle_budget_seconds=10,
    )
    deadline = time.monotonic() + 15
    exit_path = supervision_root / "exit_receipt.json"
    while not exit_path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert exit_path.is_file()
    receipt = json.loads(exit_path.read_text(encoding="utf-8"))
    stderr_path = Path(receipt["stderr_ref"])
    final_bytes = stderr_path.read_bytes()
    assert receipt["exit_code"] == 1
    assert receipt["typed_unhandled_failure_code"] == "unhandled_RuntimeError"
    assert receipt["stderr_bytes"] == len(final_bytes)
    assert receipt["stderr_sha256"] == hashlib.sha256(
        final_bytes
    ).hexdigest()
    assert b"Traceback" in final_bytes
    assert receipt["runtime_result_ref"] is None
    assert receipt["automatic_retry_count"] == 0
    assert receipt["relaunch_count"] == 0


def test_capture_v1_constant_remains_available_for_historical_admissions() -> None:
    assert S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF == (
        "fin01.s3.provider_output_capture.assistant_final_text_only:v1"
    )
