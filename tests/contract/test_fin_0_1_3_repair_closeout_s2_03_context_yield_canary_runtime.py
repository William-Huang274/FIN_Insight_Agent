from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from sec_agent.s2_context_yield_canary_runtime import (
    S2ContextYieldCanaryError,
    execute_context_yield_canary,
    issue_context_yield_admission,
    validate_context_yield_admission,
)
from sec_agent.shared_admission_ledger import (
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


ROOT = Path(__file__).resolve().parents[2]
PROGRAM = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_context_yield_and_capacity_zero_call_v1_0.json"
)
S2_DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"
)
SELECTED = "FIN013-S2-NVDA-demand_authenticity_and_sustainability"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _surface() -> tuple[dict, dict]:
    program = _load(PROGRAM)
    compiled = next(row for row in program["role_scoped_contexts"] if row["request_id"] == SELECTED)
    decision = _load(S2_DECISION)
    request = next(
        row
        for row in decision["research_question_method_program"]["representative_requests"]
        if row["request_id"] == SELECTED
    )
    return request, compiled


def _admission() -> dict:
    request, compiled = _surface()
    issued = datetime(2026, 8, 6, 16, 0, tzinfo=timezone.utc)
    return issue_context_yield_admission(
        execution_git_commit="1" * 40,
        runner_sha256="2" * 64,
        program_sha256="3" * 64,
        policy_sha256="4" * 64,
        request_binding={
            "request_id": request["request_id"],
            "request_digest": request["request_digest"],
            "context_digest": compiled["context_digest"],
        },
        issued_at=issued.isoformat(),
        expires_at=(issued + timedelta(minutes=30)).isoformat(),
        run_nonce="fixture-nonce",
        credential_present=True,
        provider={
            "backend": "deepseek",
            "model": "deepseek-v4-pro",
            "model_ref": "deepseek:deepseek-v4-pro",
            "base_url": "https://api.deepseek.com/beta",
            "chat_completions_path": "/chat/completions",
            "api_key_env": "DEEPSEEK_API_KEY",
            "wire_api": "chat_completions_json_object",
        },
        budget={
            "maximum_provider_calls": 1,
            "retry_count": 0,
            "fallback_count": 0,
            "maximum_output_tokens": 900,
            "timeout_seconds": 180,
        },
    )


class FakeProvider:
    def __init__(self, *, fail: bool = False, cross_case: bool = False, raise_error: bool = False) -> None:
        self.calls: list[dict] = []
        self.fail = fail
        self.cross_case = cross_case
        self.raise_error = raise_error

    def __call__(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self.raise_error:
            raise RuntimeError("fixture provider boundary")
        if self.fail:
            return {
                "status": "provider_error",
                "content": "",
                "finish_reason": "",
                "transport_attempt_count": 1,
                "raw_response": {"error": "fixture"},
            }
        context = json.loads(kwargs["messages"][1]["content"])
        output = {
            "epistemic_state": "bounded_inference",
            "answer_direction": "positive",
            "mechanism_alias": context["mechanism_options"][0]["alias"],
            "support_aliases": ["MU_E_FIN_01"] if self.cross_case else [row["alias"] for row in context["evidence_options"][:2]],
            "counterevidence_aliases": [],
            "gap_aliases": [row["alias"] for row in context["gap_options"]],
            "confidence": "medium",
            "what_would_change_aliases": [context["what_would_change_options"][0]["alias"]],
        }
        return {
            "status": "ok",
            "content": json.dumps(output),
            "finish_reason": "stop",
            "input_tokens": 500,
            "output_tokens": 100,
            "total_tokens": 600,
            "transport_attempt_count": 1,
            "raw_response": {"fixture": True, "output": output},
        }


def _execute(tmp_path: Path, provider: FakeProvider, *, runtime_name: str = "runtime") -> dict:
    request, compiled = _surface()
    return execute_context_yield_canary(
        admission=_admission(),
        request=request,
        compiled=compiled,
        execution_git_commit="1" * 40,
        runner_sha256="2" * 64,
        program_sha256="3" * 64,
        policy_sha256="4" * 64,
        runtime_root=tmp_path / runtime_name,
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite"),
        provider_call=provider,
        observed_at="2026-08-06T16:10:00+00:00",
    )


def test_admission_is_exact_once_and_bound_to_compact_context() -> None:
    admission = _admission()
    request, compiled = _surface()
    validate_context_yield_admission(
        admission,
        execution_git_commit="1" * 40,
        runner_sha256="2" * 64,
        program_sha256="3" * 64,
        policy_sha256="4" * 64,
        request=request,
        compiled=compiled,
        observed_at="2026-08-06T16:10:00+00:00",
    )
    assert admission["budget"]["maximum_provider_calls"] == 1
    assert admission["budget"]["retry_count"] == 0
    assert "fixture-secret-value" not in json.dumps(admission)
    assert admission["credential_present"] is True


def test_success_captures_compact_request_before_local_claim_materialization(tmp_path: Path) -> None:
    provider = FakeProvider()
    result = _execute(tmp_path, provider)

    assert result["status"] == "terminal_succeeded_exact_once"
    assert result["completed_calls"] == 1
    assert result["claim"]["case_key"] == "NVDA"
    assert len(provider.calls) == 1
    model_context = json.loads(provider.calls[0]["messages"][1]["content"])
    assert "evidence_options" in model_context
    assert "candidate_id" not in json.dumps(model_context)
    assert provider.calls[0]["max_transport_attempts"] == 1
    assert len(list((tmp_path / "runtime" / "captures").glob("*.json"))) == 1
    assert result["shared_admission_receipt"]["state"] == "terminal"


@pytest.mark.parametrize(
    ("provider", "terminal_prefix"),
    [
        (FakeProvider(fail=True), "context_canary_provider_transport"),
        (FakeProvider(raise_error=True), "context_canary_provider_transport"),
        (FakeProvider(cross_case=True), "context_canary_provider_output_contract_invalid"),
    ],
)
def test_failure_is_terminal_capture_first_and_never_retried(
    tmp_path: Path, provider: FakeProvider, terminal_prefix: str
) -> None:
    result = _execute(tmp_path, provider)
    assert result["status"] == "terminal_failed_no_retry"
    assert result["terminal_code"].startswith(terminal_prefix)
    assert len(provider.calls) == 1
    assert len(list((tmp_path / "runtime" / "captures").glob("*.json"))) == 1


def test_same_admission_cannot_be_consumed_twice(tmp_path: Path) -> None:
    request, compiled = _surface()
    admission = _admission()
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite")
    kwargs = {
        "admission": admission,
        "request": request,
        "compiled": compiled,
        "execution_git_commit": "1" * 40,
        "runner_sha256": "2" * 64,
        "program_sha256": "3" * 64,
        "policy_sha256": "4" * 64,
        "shared_ledger": ledger,
        "provider_call": FakeProvider(),
        "observed_at": "2026-08-06T16:10:00+00:00",
    }
    execute_context_yield_canary(runtime_root=tmp_path / "runtime_a", **kwargs)
    with pytest.raises(SharedAdmissionLedgerError):
        execute_context_yield_canary(runtime_root=tmp_path / "runtime_b", **kwargs)


def test_context_digest_mutation_fails_before_provider_call(tmp_path: Path) -> None:
    request, compiled = _surface()
    broken = json.loads(json.dumps(compiled))
    broken["context_digest"] = "9" * 64
    provider = FakeProvider()
    with pytest.raises(S2ContextYieldCanaryError) as exc:
        execute_context_yield_canary(
            admission=_admission(),
            request=request,
            compiled=broken,
            execution_git_commit="1" * 40,
            runner_sha256="2" * 64,
            program_sha256="3" * 64,
            policy_sha256="4" * 64,
            runtime_root=tmp_path / "runtime",
            shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite"),
            provider_call=provider,
            observed_at="2026-08-06T16:10:00+00:00",
        )
    assert exc.value.code == "context_canary_request_binding_invalid"
    assert provider.calls == []


def test_model_context_mutation_with_stale_digest_fails_before_provider_call(tmp_path: Path) -> None:
    request, compiled = _surface()
    broken = json.loads(json.dumps(compiled))
    broken["model_context"]["decision_question"] = "mutated"
    provider = FakeProvider()
    with pytest.raises(S2ContextYieldCanaryError) as exc:
        execute_context_yield_canary(
            admission=_admission(),
            request=request,
            compiled=broken,
            execution_git_commit="1" * 40,
            runner_sha256="2" * 64,
            program_sha256="3" * 64,
            policy_sha256="4" * 64,
            runtime_root=tmp_path / "runtime",
            shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite"),
            provider_call=provider,
            observed_at="2026-08-06T16:10:00+00:00",
        )
    assert exc.value.code == "context_canary_compact_context_digest_invalid"
    assert provider.calls == []
