from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from sec_agent.s2_natural_canary_runtime import (
    S2NaturalCanaryError,
    execute_natural_canary,
    issue_canary_admission,
    validate_canary_admission,
)
from sec_agent.shared_admission_ledger import (
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


ROOT = Path(__file__).resolve().parents[2]
S2_01 = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_01_"
    "research_question_method_contract_translation_v1_0.json"
)
POLICY = ROOT / "configs" / "runtime" / (
    "fin_ia_0_1_3_repair_closeout_s2_"
    "representative_node_and_natural_canary_policy_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _requests() -> tuple[dict[str, dict], list[dict[str, str]]]:
    s2 = _load(S2_01)
    policy = _load(POLICY)
    by_id = {
        row["request_id"]: row
        for row in s2["research_question_method_program"]["representative_requests"]
    }
    ids = [row["request_id"] for row in policy["natural_canary"]["selected_requests"]]
    selected = {request_id: by_id[request_id] for request_id in ids}
    bindings = [
        {
            "request_id": request_id,
            "request_digest": selected[request_id]["request_digest"],
        }
        for request_id in ids
    ]
    return selected, bindings


def _admission() -> dict:
    _, bindings = _requests()
    issued = datetime(2026, 8, 6, 16, 0, tzinfo=timezone.utc)
    return issue_canary_admission(
        execution_git_commit="1" * 40,
        runner_sha256="2" * 64,
        decision_sha256="3" * 64,
        policy_sha256="4" * 64,
        request_bindings=bindings,
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
            "maximum_provider_calls": 3,
            "maximum_calls_per_family": 1,
            "retry_count": 0,
            "fallback_count": 0,
            "maximum_output_tokens_per_call": 900,
            "timeout_seconds_per_call": 180,
        },
    )


class FakeProvider:
    def __init__(self, *, fail_at: int | None = None) -> None:
        self.calls: list[dict] = []
        self.fail_at = fail_at

    def __call__(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        request = json.loads(kwargs["messages"][1]["content"])
        if self.fail_at == len(self.calls):
            return {
                "status": "provider_error",
                "content": "",
                "finish_reason": "",
                "transport_attempt_count": 1,
                "raw_response": {"error": "fixture"},
            }
        evidence = [row["alias"] for row in request["evidence_aliases"]]
        gaps = [row["alias"] for row in request["gap_aliases"]]
        output = {
            "epistemic_state": "mixed_evidence"
            if evidence and gaps
            else "bounded_inference"
            if evidence
            else "cannot_infer",
            "answer_direction": "mixed"
            if evidence and gaps
            else "positive"
            if evidence
            else "cannot_infer",
            "mechanism_alias": request["mechanism_aliases"][0]["alias"],
            "support_aliases": evidence,
            "counterevidence_aliases": evidence
            if request["program_cell_id"].startswith("bottleneck")
            else [],
            "gap_aliases": gaps,
            "confidence": "medium" if evidence else "low",
            "what_would_change_aliases": [
                request["what_would_change_aliases"][0]["alias"]
            ],
        }
        return {
            "status": "ok",
            "content": json.dumps(output),
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 40,
            "total_tokens": 140,
            "transport_attempt_count": 1,
            "raw_response": {"fixture": True, "output": output},
        }


def test_admission_is_bound_and_contains_no_credential_value() -> None:
    admission = _admission()
    requests, _ = _requests()

    validate_canary_admission(
        admission,
        execution_git_commit="1" * 40,
        runner_sha256="2" * 64,
        decision_sha256="3" * 64,
        policy_sha256="4" * 64,
        requests=requests,
        observed_at="2026-08-06T16:10:00+00:00",
    )
    serialized = json.dumps(admission)
    assert "fixture-not-a-real-secret" not in serialized
    assert admission["credential_present"] is True
    assert admission["budget"]["retry_count"] == 0


def test_three_family_success_is_capture_first_and_terminal(
    tmp_path: Path,
) -> None:
    admission = _admission()
    requests, _ = _requests()
    provider = FakeProvider()
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite")
    result = execute_natural_canary(
        admission=admission,
        requests=requests,
        execution_git_commit="1" * 40,
        runner_sha256="2" * 64,
        decision_sha256="3" * 64,
        policy_sha256="4" * 64,
        runtime_root=tmp_path / "runtime",
        shared_ledger=ledger,
        provider_call=provider,
        observed_at="2026-08-06T16:10:00+00:00",
    )

    assert result["status"] == "terminal_succeeded_exact_once"
    assert result["completed_calls"] == 3
    assert len(provider.calls) == 3
    assert result["shared_admission_receipt"]["state"] == "terminal"
    assert len(list((tmp_path / "runtime" / "captures").glob("*.json"))) == 3
    assert (tmp_path / "runtime" / "terminal_result.json").exists()
    assert all(row["rubric"]["pass"] for row in result["family_results"])
    assert all(call["max_transport_attempts"] == 1 for call in provider.calls)


def test_first_provider_failure_stops_without_retry_and_preserves_capture(
    tmp_path: Path,
) -> None:
    admission = _admission()
    requests, _ = _requests()
    provider = FakeProvider(fail_at=1)
    result = execute_natural_canary(
        admission=admission,
        requests=requests,
        execution_git_commit="1" * 40,
        runner_sha256="2" * 64,
        decision_sha256="3" * 64,
        policy_sha256="4" * 64,
        runtime_root=tmp_path / "runtime",
        shared_ledger=SharedAdmissionConsumptionLedger(
            tmp_path / "shared" / "ledger.sqlite"
        ),
        provider_call=provider,
        observed_at="2026-08-06T16:10:00+00:00",
    )

    assert result["status"] == "terminal_failed_no_retry"
    assert result["completed_calls"] == 1
    assert len(result["skipped_request_ids"]) == 2
    assert len(provider.calls) == 1
    assert len(list((tmp_path / "runtime" / "captures").glob("*.json"))) == 1


def test_same_admission_cannot_execute_twice(tmp_path: Path) -> None:
    admission = _admission()
    requests, _ = _requests()
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite")
    kwargs = {
        "admission": admission,
        "requests": requests,
        "execution_git_commit": "1" * 40,
        "runner_sha256": "2" * 64,
        "decision_sha256": "3" * 64,
        "policy_sha256": "4" * 64,
        "shared_ledger": ledger,
        "provider_call": FakeProvider(),
        "observed_at": "2026-08-06T16:10:00+00:00",
    }
    execute_natural_canary(runtime_root=tmp_path / "runtime_a", **kwargs)
    with pytest.raises(SharedAdmissionLedgerError) as exc:
        execute_natural_canary(runtime_root=tmp_path / "runtime_b", **kwargs)
    assert exc.value.code == "shared_admission_already_consumed:terminal"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("execution_git_commit", "9" * 40, "canary_admission_execution_binding_invalid"),
        ("expires_at", "2026-08-06T16:01:00+00:00", "canary_admission_expired"),
    ],
)
def test_admission_mutations_fail_closed(field: str, value: str, code: str) -> None:
    admission = _admission()
    requests, _ = _requests()
    if field == "execution_git_commit":
        observed_commit = value
    else:
        admission[field] = value
        body = {key: item for key, item in admission.items() if key != "admission_digest"}
        from sec_agent.retrieval_evidence_usefulness_program import canonical_digest

        admission["admission_digest"] = canonical_digest(body)
        observed_commit = "1" * 40
    with pytest.raises(S2NaturalCanaryError) as exc:
        validate_canary_admission(
            admission,
            execution_git_commit=observed_commit,
            runner_sha256="2" * 64,
            decision_sha256="3" * 64,
            policy_sha256="4" * 64,
            requests=requests,
            observed_at="2026-08-06T16:10:00+00:00",
        )
    assert exc.value.code == code
